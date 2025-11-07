<script>
  import { onMount, onDestroy } from 'svelte';
  import { Chessground } from 'chessground';
  import 'chessground/assets/chessground.base.css';
  import 'chessground/assets/chessground.brown.css';
  import 'chessground/assets/chessground.cburnett.css';
  import { Chess } from 'chess.js';
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

  // Reactive: Get current evaluation - update when currentMoveIndex or analysis changes
  $: {
    if (analysis && currentMoveIndex >= 0 && currentMoveIndex < analysis.moves.length) {
      currentEvaluation = analysis.moves[currentMoveIndex].analysis;
    } else {
      currentEvaluation = null;
    }
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

      loading = false;

      // Initialize board after loading
      initBoard();
    } catch (err) {
      error = err.message;
      loading = false;
    }
  }

  // Initialize chessground board
  function initBoard() {
    if (!boardElement || !chess) {
      console.error('[GameView] Board element or chess instance not ready', { boardElement, chess });
      return;
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
    } catch (err) {
      console.error('[GameView] Failed to initialize chessground:', err);
    }
  }

  // Update board to current position
  function updateBoard() {
    if (!chessground || !chess) return;

    chessground.set({
      fen: chess.fen(),
      lastMove: currentMoveIndex >= 0 && moves[currentMoveIndex]
        ? [moves[currentMoveIndex].from, moves[currentMoveIndex].to]
        : undefined,
      check: chess.inCheck()
    });

    // Clear best move highlight when position changes
    showBestMove = false;
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

  // Show best move for current position
  function toggleBestMove() {
    if (!analysis || currentMoveIndex >= analysis.moves.length) {
      alert('No analysis available for this position');
      return;
    }

    showBestMove = !showBestMove;

    if (showBestMove) {
      const moveAnalysis = analysis.moves[currentMoveIndex];
      const bestMove = moveAnalysis.analysis.best_move;

      if (bestMove && bestMove.length >= 4) {
        const from = bestMove.substring(0, 2);
        const to = bestMove.substring(2, 4);

        chessground.setShapes([
          { orig: from, dest: to, brush: 'paleGreen' }
        ]);
      }
    } else {
      chessground.setShapes([]);
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

  onMount(async () => {
    await loadGame();
    // Ensure board initializes after DOM is fully ready
    setTimeout(() => {
      if (boardElement && chess && !chessground) {
        console.log('[GameView] Retrying board initialization');
        initBoard();
      }
    }, 100);
  });

  onDestroy(() => {
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

          <!-- Chess board -->
          <div class="board-wrapper">
            <div class="board" bind:this={boardElement}></div>
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
                    {@const moveEval = analysis.moves[pairIndex * 2].analysis}
                    <span class="move-eval" title="Engine evaluation">
                      {formatScore(moveEval)}
                    </span>
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
                      {@const moveEval = analysis.moves[pairIndex * 2 + 1].analysis}
                      <span class="move-eval" title="Engine evaluation">
                        {formatScore(moveEval)}
                      </span>
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
</style>
