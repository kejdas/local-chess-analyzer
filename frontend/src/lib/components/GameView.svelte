<script>
  import { onMount, onDestroy } from 'svelte';
  import { Chessground } from 'chessground';
  import 'chessground/assets/chessground.base.css';
  import 'chessground/assets/chessground.brown.css';
  import 'chessground/assets/chessground.cburnett.css';
  import { Chess } from 'chess.js';
  // Classification icons
  import bestIcon from '../../assets/classifications/best.png';
  import excellentIcon from '../../assets/classifications/excellent.png';
  import goodIcon from '../../assets/classifications/good.png';
  import inaccuracyIcon from '../../assets/classifications/inaccuracy.png';
  import mistakeIcon from '../../assets/classifications/mistake.png';
  import blunderIcon from '../../assets/classifications/blunder.png';
  import brilliantIcon from '../../assets/classifications/brilliant.png';
  import greatIcon from '../../assets/classifications/great.png';
  import missIcon from '../../assets/classifications/miss.png';
  import { getGame, getGameAnalysis, analyzeGame } from '../api/client.js';

  export let params = {};

  let gameId = params.id;
  let game = null;
  let analysis = null;
  let chess = null;
  let chessground = null;
  let boardElement;

  let currentMoveIndex = -1; // -1 means starting position
  let moves = [];
  let loading = true;
  let analyzing = false;
  let error = null;
  let showBestMove = false;
  let currentEvaluation = null;
  // Clocks parsed from PGN (remaining time after each move)
  let whiteClocksByMove = []; // index -> clock string for white after that move (only set on white moves)
  let blackClocksByMove = []; // index -> clock string for black after that move (only set on black moves)
  // Board size tracker for overlay positioning
  let boardSize = 0;
  let classificationIconUrl = null;
  let classificationIconPos = null; // { top, left }

  function classificationIconForMoveIndex(index) {
    if (!analysis || index < 0 || index >= analysis.moves.length) return null;
    const mv = analysis.moves[index];
    // Prefer special classification icon if available
    const special = (mv.special_classification || '').toLowerCase();
    const primary = (mv.classification || '').toLowerCase();
    if (special === 'brilliant') return brilliantIcon;
    if (special === 'great move' || special === 'great') return greatIcon;
    if (special === 'miss') return missIcon;
    switch (primary) {
      case 'best': return bestIcon;
      case 'excellent': return excellentIcon;
      case 'good': return goodIcon;
      case 'inaccuracy': return inaccuracyIcon;
      case 'mistake': return mistakeIcon;
      case 'blunder': return blunderIcon;
      default: return null;
    }
  }

  function squareTopLeftFromDest(dest) {
    if (!boardElement || !dest || dest.length < 2) return null;
    const fileChar = dest[0];
    const rankChar = dest[1];
    const file = fileChar.charCodeAt(0) - 'a'.charCodeAt(0); // 0..7
    const rank = parseInt(rankChar, 10); // 1..8
    if (isNaN(file) || isNaN(rank)) return null;
    const size = boardElement.clientWidth || 0;
    const square = size / 8;
    // White at bottom: rank 1 is bottom row -> y from top is (8 - rank)
    const top = square * (8 - rank);
    const left = square * file;
    return { top, left, square };
  }

  function updateClassificationOverlay() {
    if (!boardElement) {
      classificationIconUrl = null;
      classificationIconPos = null;
      return;
    }
    const icon = classificationIconForMoveIndex(currentMoveIndex);
    if (!icon) {
      classificationIconUrl = null;
      classificationIconPos = null;
      return;
    }
    // Destination square of the last applied move:
    const mv = analysis && analysis.moves && analysis.moves[currentMoveIndex];
    const uci = mv && mv.uci;
    const dest = uci && uci.length >= 4 ? uci.substring(2, 4) : null;
    const coord = squareTopLeftFromDest(dest);
    if (!coord) {
      classificationIconUrl = null;
      classificationIconPos = null;
      return;
    }
    const iconSize = 18;
    const margin = 2;
    classificationIconUrl = icon;
    classificationIconPos = {
      top: coord.top + margin,
      left: coord.left + coord.square - iconSize - margin
    };
  }

  // Reactive: Get current evaluation - update when currentMoveIndex or analysis changes
  $: {
    if (analysis && currentMoveIndex >= 0 && currentMoveIndex < analysis.moves.length) {
      currentEvaluation = analysis.moves[currentMoveIndex].analysis;
    } else {
      currentEvaluation = null;
    }

    // Update best move arrow when position or analysis changes
    if (chessground && analysis) {
      updateBestMoveArrow();
    }
    // Update classification overlay
    updateClassificationOverlay();
  }

  // Load game data
  async function loadGame() {
    try {
      loading = true;
      error = null;

      game = await getGame(gameId);

      // Initialize chess.js with the PGN
      chess = new Chess();
      chess.loadPgn(game.pgn);

      // Extract moves
      moves = chess.history({ verbose: true });

      // Reset chess to starting position
      chess.reset();

      // Load analysis if available
      if (game.has_analysis) {
        try {
          const analysisResponse = await getGameAnalysis(gameId);
          analysis = analysisResponse.analysis;
        } catch (err) {
          console.warn('Could not load analysis:', err);
        }
      }

      // Parse clocks from PGN (if present) using the extracted move list
      parseClocksFromPgn(game.pgn, moves);

      loading = false;

      // Initialize board after loading
      // Use setTimeout to ensure DOM is ready after loading state changes
      setTimeout(() => {
        initBoard();
      }, 50);
    } catch (err) {
      error = err.message;
      loading = false;
    }
  }

  // Parse move clocks from PGN comments like {%clk 1:23:45} or [%clk 1:23:45.8]
  function parseClocksFromPgn(pgnText, movesList = []) {
    whiteClocksByMove = [];
    blackClocksByMove = [];

    try {
      // Match {%clk H:MM[:SS[.ff]]} or [%clk ...], allow fractional seconds
      const clkRegex = /[\[{]\s*%?clk\s+(\d{1,2}:[0-5]\d(?::[0-5]\d(?:\.\d+)?)?)[\]}]/gi;
      const found = [];
      let m;
      while ((m = clkRegex.exec(pgnText)) !== null) {
        found.push(m[1]);
      }
      if (found.length === 0) {
        return;
      }
      // Assign sequentially to moves in order; each clock corresponds to the player who just moved
      const verboseMoves = movesList;
      for (let i = 0; i < verboseMoves.length && i < found.length; i++) {
        const mv = verboseMoves[i];
        const clk = found[i];
        if (mv.color === 'w') {
          whiteClocksByMove[i] = clk;
        } else {
          blackClocksByMove[i] = clk;
        }
      }
    } catch (e) {
      console.warn('[GameView] Failed to parse clocks from PGN', e);
    }
  }

  function getClockForSideAtIndex(side, index) {
    if (index < 0) return null;
    // Walk back from index to find last clock for that side
    for (let i = index; i >= 0; i--) {
      if (side === 'w' && whiteClocksByMove[i]) return whiteClocksByMove[i];
      if (side === 'b' && blackClocksByMove[i]) return blackClocksByMove[i];
    }
    return null;
  }

  $: currentWhiteClock = getClockForSideAtIndex('w', currentMoveIndex);
  $: currentBlackClock = getClockForSideAtIndex('b', currentMoveIndex);

  // Initialize chessground board
  function initBoard() {
    if (!boardElement || !chess) {
      console.error('[GameView] Board element or chess instance not ready', { boardElement, chess });
      return;
    }

    // Destroy existing chessground instance if it exists
    if (chessground) {
      try {
        chessground.destroy();
      } catch (err) {
        console.warn('[GameView] Error destroying existing chessground:', err);
      }
      chessground = null;
    }

    try {
      console.log('[GameView] Initializing chessground board', { fen: chess.fen() });
      chessground = Chessground(boardElement, {
        fen: chess.fen(),
        viewOnly: true,
        coordinates: true,
        animation: {
          enabled: true,
          duration: 200
        }
      });
      console.log('[GameView] Chessground initialized successfully');

      // Update board position and best move arrow after initialization
      updateBoard();
    } catch (err) {
      console.error('[GameView] Failed to initialize chessground:', err);
    }
  }

  // Update board to current position
  function updateBoard() {
    if (!chessground || !chess) return;

    // Determine side in check for accurate king highlight
    let checkProp = undefined;
    try {
      if (chess.inCheck()) {
        checkProp = chess.turn() === 'w' ? 'white' : 'black';
      }
    } catch (e) {
      // chess.js can throw if called in invalid state; ignore
      checkProp = undefined;
    }

    chessground.set({
      fen: chess.fen(),
      lastMove: currentMoveIndex >= 0 && moves[currentMoveIndex]
        ? [moves[currentMoveIndex].from, moves[currentMoveIndex].to]
        : undefined,
      check: checkProp
    });

    // Auto-show best move if analysis is available
    updateBestMoveArrow();
  }

  // Update best move arrow based on current position
  function updateBestMoveArrow() {
    if (!chessground || !analysis) {
      chessground?.setShapes([]);
      return;
    }

    // The analysis.moves array contains analysis for each move that was made
    // Each entry analyzes the position BEFORE that move was made
    // analysis.moves[0] = analysis of starting position (best move is move 1)
    // analysis.moves[1] = analysis of position after move 1 (best move is move 2)
    // etc.

    // So to show the best move for the current position:
    // - If at starting position (currentMoveIndex = -1), show analysis.moves[0].best_move
    // - If after move N (currentMoveIndex = N), show analysis.moves[N+1].best_move (if exists)

    let moveAnalysis = null;
    if (currentMoveIndex === -1 && analysis.moves.length > 0) {
      // Starting position - show best move for first move
      moveAnalysis = analysis.moves[0];
    } else if (currentMoveIndex >= 0 && currentMoveIndex < analysis.moves.length - 1) {
      // After move N - show best move for next move (move N+1)
      moveAnalysis = analysis.moves[currentMoveIndex + 1];
    }
    // If at last move, no next move to show

    if (moveAnalysis && moveAnalysis.analysis && moveAnalysis.analysis.best_move) {
      const bestMove = moveAnalysis.analysis.best_move;
      if (bestMove && bestMove.length >= 4) {
        const from = bestMove.substring(0, 2);
        const to = bestMove.substring(2, 4);
        chessground.setShapes([
          { orig: from, dest: to, brush: 'paleGreen' }
        ]);
        showBestMove = true;
      } else {
        chessground.setShapes([]);
        showBestMove = false;
      }
    } else {
      chessground.setShapes([]);
      showBestMove = false;
    }
  }

  // Navigation functions
  function goToStart() {
    chess.reset();
    currentMoveIndex = -1;
    updateBoard();
  }

  function goToPrevious() {
    if (currentMoveIndex >= 0) {
      chess.reset();
      currentMoveIndex--;

      // Replay moves up to current position
      for (let i = 0; i <= currentMoveIndex; i++) {
        chess.move(moves[i].san);
      }

      updateBoard();
    }
  }

  function goToNext() {
    if (currentMoveIndex < moves.length - 1) {
      currentMoveIndex++;
      chess.move(moves[currentMoveIndex].san);
      updateBoard();
    }
  }

  function goToEnd() {
    chess.reset();
    currentMoveIndex = moves.length - 1;

    // Replay all moves
    for (let i = 0; i < moves.length; i++) {
      chess.move(moves[i].san);
    }

    updateBoard();
  }

  function goToMove(index) {
    chess.reset();
    currentMoveIndex = index;

    // Replay moves up to selected position
    for (let i = 0; i <= index; i++) {
      chess.move(moves[i].san);
    }

    updateBoard();
  }

  // Analyze game
  async function handleAnalyze() {
    if (!confirm('This will analyze the game with Stockfish. This may take a few minutes depending on game length and settings. Continue?')) {
      return;
    }

    try {
      analyzing = true;
      const result = await analyzeGame(gameId);

      if (result.success) {
        // Reload game data to get updated analysis status
        await loadGame();
        alert('Game analyzed successfully!');
      }
    } catch (err) {
      alert(`Analysis failed: ${err.message}`);
    } finally {
      analyzing = false;
    }
  }

  // Toggle best move visibility (now just toggles, since auto-show is enabled)
  function toggleBestMove() {
    if (!analysis) {
      alert('No analysis available for this position');
      return;
    }

    showBestMove = !showBestMove;

    if (showBestMove) {
      updateBestMoveArrow();
    } else {
      chessground?.setShapes([]);
    }
  }

  // Get evaluation for current move
  function getCurrentEvaluation() {
    if (!analysis || currentMoveIndex < 0 || currentMoveIndex >= analysis.moves.length) {
      return null;
    }

    const moveAnalysis = analysis.moves[currentMoveIndex];
    return moveAnalysis.analysis;
  }

  // Format evaluation score
  function formatScore(evaluation) {
    if (!evaluation) return '0.00';

    if (evaluation.score_type === 'mate') {
      return `M${evaluation.score_value}`;
    }

    // Convert centipawns to pawns
    const score = evaluation.score_value / 100;
    return score >= 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
  }

  // Calculate evaluation bar percentage (0-100)
  function getEvalBarPercentage(evaluation) {
    if (!evaluation) return 50; // Equal position

    if (evaluation.score_type === 'mate') {
      // Mate scores: positive = white winning, negative = black winning
      return evaluation.score_value > 0 ? 100 : 0;
    }

    // Centipawns: cap at ±1000 (±10 pawns)
    const cappedScore = Math.max(-1000, Math.min(1000, evaluation.score_value));

    // Convert to percentage: -1000cp = 0%, 0cp = 50%, +1000cp = 100%
    return 50 + (cappedScore / 20);
  }

  // Handle keyboard navigation
  function handleKeyDown(event) {
    // Only handle arrow keys if not typing in an input/textarea
    if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
      return;
    }

    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      goToPrevious();
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      goToNext();
    }
  }

  onMount(async () => {
    await loadGame();
    // Ensure board initializes after DOM is fully ready
    setTimeout(() => {
      if (boardElement && chess && !chessground) {
        console.log('[GameView] Retrying board initialization');
        initBoard();
      }
    }, 100);

    // Add keyboard event listener
    window.addEventListener('keydown', handleKeyDown);
    // Track board size for overlay positioning
    const handleResize = () => {
      boardSize = boardElement ? boardElement.clientWidth : 0;
      updateClassificationOverlay();
    };
    window.addEventListener('resize', handleResize);
    handleResize();
  });

  onDestroy(() => {
    // Remove keyboard event listener
    window.removeEventListener('keydown', handleKeyDown);
    window.removeEventListener('resize', () => {});

    if (chessground) {
      chessground.destroy();
    }
  });
</script>

<div class="game-view">
  {#if loading}
    <div class="loading">
      <p>Loading game...</p>
    </div>
  {:else if error}
    <div class="error">
      <h2>Error</h2>
      <p>{error}</p>
      <a href="#/games">← Back to Games</a>
    </div>
  {:else}
    <div class="game-container">
      <!-- Header -->
      <div class="game-header">
        <div class="back-link">
          <a href="#/games">← Back to Games</a>
        </div>
        <div class="game-info">
          <h2>{game.white_player} vs {game.black_player}</h2>
          <div class="meta">
            <span class="result">{game.result}</span>
            <span class="date">{game.game_date}</span>
            <span class="status badge-{game.analysis_status}">{game.analysis_status}</span>
          </div>
        </div>
      </div>

      <!-- Main content -->
      <div class="game-content">
        <!-- Left side: Board and evaluation -->
        <div class="board-section">
          <!-- Evaluation bar -->
          {#if analysis}
            {@const displayEval = currentMoveIndex >= 0 ? currentEvaluation : null}
            <div class="eval-bar-container">
              <div class="eval-bar">
                <div class="eval-bar-black" style="width: {displayEval ? 100 - getEvalBarPercentage(displayEval) : 50}%"></div>
                <div class="eval-bar-white" style="width: {displayEval ? getEvalBarPercentage(displayEval) : 50}%"></div>
              </div>
              <div class="eval-score">
                {displayEval ? formatScore(displayEval) : '0.00'}
              </div>
            </div>
          {/if}

          <!-- Player (Black) above board -->
          <div class="player-row top">
            <div class="player-name">
              <span class="name">{game.black_player || 'Black'}</span>
              {#if game.black_rating}<span class="rating">({game.black_rating})</span>{/if}
            </div>
          </div>

          <!-- Chess board -->
          <div class="board-wrapper">
            <div class="board" bind:this={boardElement}></div>
            {#if currentBlackClock}
              <div class="clock-overlay clock-top-right">{currentBlackClock}</div>
            {/if}
            {#if currentWhiteClock}
              <div class="clock-overlay clock-bottom-right">{currentWhiteClock}</div>
            {/if}
            {#if classificationIconUrl && classificationIconPos}
              <img
                src={classificationIconUrl}
                alt="move classification"
                class="class-icon-overlay"
                style="top: {classificationIconPos.top}px; left: {classificationIconPos.left}px;"
                width="18"
                height="18"
              />
            {/if}
          </div>

          <!-- Player (White) below board -->
          <div class="player-row bottom">
            <div class="player-name">
              <span class="name">{game.white_player || 'White'}</span>
              {#if game.white_rating}<span class="rating">({game.white_rating})</span>{/if}
            </div>
          </div>

          <!-- Navigation controls -->
          <div class="controls">
            <button on:click={goToStart} disabled={currentMoveIndex === -1}>
              ⏮ Start
            </button>
            <button on:click={goToPrevious} disabled={currentMoveIndex === -1}>
              ◀ Previous
            </button>
            <button on:click={goToNext} disabled={currentMoveIndex === moves.length - 1}>
              Next ▶
            </button>
            <button on:click={goToEnd} disabled={currentMoveIndex === moves.length - 1}>
              End ⏭
            </button>
          </div>

          <!-- Action buttons -->
          <div class="actions">
            {#if !game.has_analysis}
              <button
                class="btn-analyze"
                on:click={handleAnalyze}
                disabled={analyzing}
              >
                {analyzing ? 'Analyzing...' : 'Analyze Game'}
              </button>
            {/if}

            {#if game.has_analysis && currentMoveIndex >= 0}
              <button
                class="btn-best-move"
                on:click={toggleBestMove}
              >
                {showBestMove ? 'Hide Best Move' : 'Show Best Move'}
              </button>
            {/if}
          </div>
        </div>

        <!-- Right side: Move list -->
        <div class="moves-section">
          <h3>Moves</h3>
          <div class="moves-list">
            {#each {length: Math.ceil(moves.length / 2)} as _, pairIndex}
              {@const whiteMove = moves[pairIndex * 2]}
              {@const blackMove = moves[pairIndex * 2 + 1]}

              <div class="move-row">
                <span class="move-number">{pairIndex + 1}.</span>

                <button
                  class="move-button"
                  class:active={pairIndex * 2 === currentMoveIndex}
                  on:click={() => goToMove(pairIndex * 2)}
                >
                  {whiteMove.san}
                  {#if analysis && analysis.moves[pairIndex * 2]}
                    {@const mv = analysis.moves[pairIndex * 2]}
                    <span class="move-eval" title="Engine evaluation">
                      {formatScore(mv.analysis)}
                    </span>
                    {#if mv.classification || mv.special_classification}
                      {@const icon = classificationIconForMoveIndex(pairIndex * 2)}
                      {#if icon}
                        <img class="class-inline-icon" src={icon} alt="class" width="16" height="16" />
                      {/if}
                    {/if}
                  {/if}
                </button>

                {#if blackMove}
                  <button
                    class="move-button"
                    class:active={pairIndex * 2 + 1 === currentMoveIndex}
                    on:click={() => goToMove(pairIndex * 2 + 1)}
                  >
                    {blackMove.san}
                    {#if analysis && analysis.moves[pairIndex * 2 + 1]}
                      {@const mv = analysis.moves[pairIndex * 2 + 1]}
                      <span class="move-eval" title="Engine evaluation">
                        {formatScore(mv.analysis)}
                      </span>
                      {#if mv.classification || mv.special_classification}
                        {@const icon = classificationIconForMoveIndex(pairIndex * 2 + 1)}
                        {#if icon}
                          <img class="class-inline-icon" src={icon} alt="class" width="16" height="16" />
                        {/if}
                      {/if}
                    {/if}
                  </button>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .game-view {
    padding: 2rem;
    max-width: 1400px;
    margin: 0 auto;
  }

  .loading, .error {
    text-align: center;
    padding: 3rem;
  }

  .error {
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .game-container {
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    overflow: hidden;
  }

  .game-header {
    padding: 1.5rem;
    border-bottom: 1px solid #e0e0e0;
  }

  .back-link {
    margin-bottom: 0.5rem;
  }

  .back-link a {
    color: #3498db;
    text-decoration: none;
    font-size: 0.9rem;
  }

  .back-link a:hover {
    text-decoration: underline;
  }

  .game-info h2 {
    margin: 0 0 0.5rem 0;
    color: #2c3e50;
  }

  .meta {
    display: flex;
    gap: 1rem;
    align-items: center;
  }

  .result {
    font-weight: bold;
    font-size: 1.1rem;
  }

  .date {
    color: #666;
  }

  .badge-queued {
    background: #3498db;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.85rem;
  }

  .badge-analyzing {
    background: #f39c12;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.85rem;
  }

  .badge-completed {
    background: #27ae60;
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 12px;
    font-size: 0.85rem;
  }

  .game-content {
    display: grid;
    grid-template-columns: minmax(400px, 600px) 1fr;
    gap: 2rem;
    padding: 2rem;
  }

  @media (max-width: 1000px) {
    .game-content {
      grid-template-columns: 1fr;
    }
  }

  .board-section {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .player-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    max-width: 600px;
    margin: 0 auto;
    padding: 0.25rem 0.5rem;
  }

  .player-row.top {
    margin-bottom: 0.25rem;
  }
  .player-row.bottom {
    margin-top: 0.25rem;
  }

  .player-name {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-weight: 600;
    color: #2c3e50;
  }

  .player-label.black {
    color: #2c3e50;
  }
  .player-label.white {
    color: #2c3e50;
  }

  .player-name .rating {
    color: #7f8c8d;
    font-weight: 500;
  }

  .clock {
    font-family: monospace;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 0.2rem 0.5rem;
    min-width: 70px;
    text-align: center;
  }

  .board-wrapper {
    position: relative;
    width: 100%;
    max-width: 600px;
    height: 600px;
    margin: 0 auto;
  }

  .board {
    width: 600px;
    height: 600px;
  }

  @media (max-width: 700px) {
    .board-wrapper {
      max-width: 400px;
      height: 400px;
    }

    .board {
      width: 400px;
      height: 400px;
    }
  }

  .clock-overlay {
    position: absolute;
    font-family: monospace;
    background: rgba(255, 255, 255, 0.9);
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    padding: 0.25rem 0.5rem;
    min-width: 70px;
    text-align: center;
    color: #2c3e50;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    z-index: 4;
  }
  .clock-top-right {
    top: -32px; /* place above the board */
    right: 0;
  }
  .clock-bottom-right {
    bottom: -32px; /* place below the board */
    right: 0;
  }

  .class-icon-overlay {
    position: absolute;
    z-index: 5;
    pointer-events: none;
    filter: drop-shadow(0 1px 1px rgba(0,0,0,0.4));
  }

  .eval-bar-container {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .eval-bar {
    flex: 1;
    height: 40px;
    border: 2px solid #2c3e50;
    border-radius: 4px;
    overflow: hidden;
    position: relative;
    display: flex;
    flex-direction: row;
  }

  .eval-bar-black {
    height: 100%;
    background: #2c3e50;
    transition: width 0.3s ease;
  }

  .eval-bar-white {
    height: 100%;
    background: #f0f0f0;
    transition: width 0.3s ease;
  }

  .eval-score {
    font-weight: bold;
    font-size: 1.3rem;
    min-width: 80px;
    text-align: center;
    font-family: monospace;
    padding: 0.5rem 1rem;
    background: #f8f9fa;
    border-radius: 4px;
    border: 2px solid #e0e0e0;
  }

  @media (max-width: 700px) {
    .eval-bar {
      height: 30px;
    }

    .eval-score {
      font-size: 1rem;
      min-width: 65px;
      padding: 0.4rem 0.6rem;
    }
  }

  .controls {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
  }

  .controls button {
    flex: 1;
    padding: 0.75rem;
    background: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.9rem;
    font-weight: 500;
    transition: background 0.2s;
  }

  .controls button:hover:not(:disabled) {
    background: #2980b9;
  }

  .controls button:disabled {
    background: #bdc3c7;
    cursor: not-allowed;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
  }

  .actions button {
    flex: 1;
    padding: 1rem;
    border: none;
    border-radius: 4px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }

  .btn-analyze {
    background: #3498db;
    color: white;
  }

  .btn-analyze:hover:not(:disabled) {
    background: #2980b9;
  }

  .btn-best-move {
    background: #27ae60;
    color: white;
  }

  .btn-best-move:hover {
    background: #229954;
  }

  .moves-section {
    overflow-y: auto;
    max-height: 600px;
  }

  .moves-section h3 {
    margin: 0 0 1rem 0;
    color: #2c3e50;
  }

  .moves-list {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .move-row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .move-number {
    font-weight: bold;
    color: #666;
    min-width: 40px;
  }

  .move-button {
    flex: 1;
    padding: 0.5rem 0.75rem;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    cursor: pointer;
    text-align: left;
    transition: all 0.2s;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .move-button:hover {
    background: #e9ecef;
    border-color: #3498db;
  }

  .move-button.active {
    background: #3498db;
    color: white;
    border-color: #3498db;
  }

  .move-eval {
    font-size: 0.85rem;
    font-family: monospace;
    opacity: 0.7;
  }

  .move-button.active .move-eval {
    opacity: 1;
  }

  .badge {
    display: inline-block;
    margin-left: 0.5rem;
    padding: 0.1rem 0.4rem;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .badge-class {
    background: #e8f4f8;
    color: #2c3e50;
    border: 1px solid #cde9f3;
  }
  .class-inline-icon {
    margin-left: 0.4rem;
    vertical-align: middle;
  }
</style>
