<script>
  import { onMount } from 'svelte';
  import { getGames, startSync, getSyncStatus, getSettings, analyzeGame, getGameAnalysis, bulkAnalyzeGames } from '../api/client.js';

  // State
  let games = [];
  let total = 0;
  let loading = true;
  let error = null;
  let currentPage = 0;
  let pageSize = 20;
  let searchTerm = '';
  let statusFilter = 'all';
  let resultFilter = 'all'; // all, win, loss, draw
  let timeClassFilter = 'all'; // all, bullet, blitz, rapid, daily, other
  let playerName = ''; // For result filtering - which player to check results for
  let dateFrom = '';
  let dateTo = '';
  let sortBy = 'date'; // date, result, status
  let sortOrder = 'desc'; // asc, desc
  let syncing = false;
  let syncError = null;
  let syncSuccess = null;
  let username = ''; // From settings, used as default for playerName
  let analyzingGames = new Set(); // Track games currently being analyzed
  let selectedAnalysis = null; // Currently viewed analysis
  let showAnalysisModal = false; // Show/hide analysis modal
  let analysisError = null;
  let analyzingPage = false; // Bulk-analyzing current page
  let pageAnalysisProgress = 0;
  let pageAnalysisTotal = 0;
  let pageAnalysisError = null;

  // Derived flags for UX
  $: isAnalysisInProgress = analyzingPage || (analyzingGames && analyzingGames.size > 0);
  $: displayedAnalyzingGames = displayedGames.filter(g => analyzingGames.has(g.id));

  // Computed
  $: totalPages = Math.ceil(total / pageSize);
  $: skip = currentPage * pageSize;

  // Apply client-side filtering (search and result filter)
  $: displayedGames = games.filter(game => {
    // Result filter (win/loss/draw for the selected player) - must be client-side
    if (resultFilter !== 'all' && playerName.trim()) {
      const isWhite = game.white_player && game.white_player.toLowerCase() === playerName.toLowerCase().trim();
      const isBlack = game.black_player && game.black_player.toLowerCase() === playerName.toLowerCase().trim();

      if (resultFilter === 'win') {
        if (isWhite && game.result !== '1-0') return false;
        if (isBlack && game.result !== '0-1') return false;
        if (!isWhite && !isBlack) return false;
      } else if (resultFilter === 'loss') {
        if (isWhite && game.result !== '0-1') return false;
        if (isBlack && game.result !== '1-0') return false;
        if (!isWhite && !isBlack) return false;
      } else if (resultFilter === 'draw') {
        if (game.result !== '1/2-1/2') return false;
        // Must be a player in the game
        if (!isWhite && !isBlack) return false;
      }
    }

    // Search filter (case-insensitive text search)
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const searchableText = [
        game.white_player,
        game.black_player,
        game.result,
        game.game_date
      ].join(' ').toLowerCase();

      if (!searchableText.includes(term)) return false;
    }

    return true;
  });

  // Track if initial load has happened
  let hasInitialLoad = false;

  // Reload games when filters change (but not on initial mount)
  $: if (hasInitialLoad && !isAnalysisInProgress && (dateFrom || dateTo || statusFilter !== 'all' || timeClassFilter !== 'all')) {
    currentPage = 0;
    loadGames();
  }

  // Also reload when clearing filters back to defaults
  $: if (hasInitialLoad && !isAnalysisInProgress && !dateFrom && !dateTo && statusFilter === 'all' && timeClassFilter === 'all') {
    loadGames();
  }

  async function loadGames() {
    loading = true;
    error = null;
    try {
      // Build filters object for API
      const filters = {};
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;
      if (statusFilter && statusFilter !== 'all') filters.status = statusFilter;
      if (timeClassFilter && timeClassFilter !== 'all') filters.time_class = timeClassFilter;

      // Build sort object for API
      const sort = {
        sort_by: sortBy,
        sort_order: sortOrder
      };

      // Fetch games with filters, sorting, and settings
      const [gamesResponse, settings] = await Promise.all([
        getGames(skip, pageSize, filters, sort),
        getSettings()
      ]);

      games = gamesResponse.games;
      total = gamesResponse.total;
      username = settings.chess_com_username || '';

      // Pre-populate playerName with username from settings if not already set
      if (!playerName && username) {
        playerName = username;
      }

      console.log('[Games] Loaded:', gamesResponse.games.length, 'Total:', gamesResponse.total, 'Sort:', sortBy, sortOrder);

      // Mark that initial load has completed
      hasInitialLoad = true;
    } catch (err) {
      error = err.message;
      console.error('Failed to load games:', err);
    } finally {
      loading = false;
    }
  }

  function handleColumnSort(column) {
    if (isAnalysisInProgress) return;
    if (sortBy === column) {
      // Toggle sort order if clicking same column
      sortOrder = sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      // New column - default to descending
      sortBy = column;
      sortOrder = 'desc';
    }
    // Reset to first page when sorting changes
    currentPage = 0;
    loadGames();
  }

  function clearFilters() {
    searchTerm = '';
    statusFilter = 'all';
    resultFilter = 'all';
    playerName = username; // Reset to default username from settings
    dateFrom = '';
    dateTo = '';
    timeClassFilter = 'all';
  }

  async function handleSync() {
    syncing = true;
    syncError = null;
    syncSuccess = null;

    try {
      await startSync();

      // Poll for sync completion
      let attempts = 0;
      const maxAttempts = 60; // 60 seconds max

      while (attempts < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        const status = await getSyncStatus();

        if (!status.is_running) {
          if (status.last_result && status.last_result.success) {
            syncSuccess = `Successfully synced! Fetched ${status.last_result.total_fetched} games (${status.last_result.created} new, ${status.last_result.skipped} duplicates)`;
            await loadGames(); // Reload games
          } else if (status.last_result && status.last_result.error) {
            syncError = status.last_result.error;
          }
          break;
        }
        attempts++;
      }

      if (attempts >= maxAttempts) {
        syncError = 'Sync is taking longer than expected. Check sync status on the Sync page.';
      }
    } catch (err) {
      syncError = err.message;
      console.error('Failed to sync games:', err);
    } finally {
      syncing = false;
    }
  }

  function goToPage(page) {
    if (isAnalysisInProgress) return;
    currentPage = page;
    loadGames();
  }

  function nextPage() {
    if (currentPage < totalPages - 1) {
      goToPage(currentPage + 1);
    }
  }

  function prevPage() {
    if (currentPage > 0) {
      goToPage(currentPage - 1);
    }
  }

  function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleDateString();
  }

  function formatType(type) {
    if (!type) return 'Other';
    return type.charAt(0).toUpperCase() + type.slice(1);
  }

  function getStatusBadgeClass(status) {
    switch (status) {
      case 'completed': return 'status-completed';
      case 'analyzing': return 'status-analyzing';
      case 'queued': return 'status-queued';
      default: return 'status-unknown';
    }
  }

  function getEffectiveStatus(game) {
    if (analyzingGames.has(game.id) && !game.has_analysis) {
      return 'analyzing';
    }
    return game.analysis_status;
  }

  async function handleAnalyzeGame(gameId) {
    analyzingGames.add(gameId);
    analyzingGames = analyzingGames; // Trigger reactivity
    analysisError = null;

    try {
      const result = await analyzeGame(gameId);
      console.log('[Games] Analysis completed:', result);

      // Update local state without forcing a refresh
      const idx = games.findIndex(g => g.id === gameId);
      if (idx !== -1) {
        const updated = { ...games[idx] };
        updated.analysis_status = 'completed';
        updated.has_analysis = true;
        games[idx] = updated;
        games = [...games];
      }

      // Show success message
      const movesMsg = typeof result?.total_moves === 'number'
        ? `${result.total_moves} moves analyzed.`
        : (result?.status === 'already_completed' ? 'Already analyzed.' : 'Analysis completed.');
      syncSuccess = `Game analyzed successfully! ${movesMsg}`;
      setTimeout(() => syncSuccess = null, 5000);
    } catch (err) {
      console.error('[Games] Analysis failed:', err);
      analysisError = `Failed to analyze game: ${err.message}`;
      setTimeout(() => analysisError = null, 5000);
    } finally {
      analyzingGames.delete(gameId);
      analyzingGames = analyzingGames; // Trigger reactivity
    }
  }

  async function handleAnalyzePage() {
    const ids = displayedGames.map(g => g.id);
    if (!ids.length) return;
    pageAnalysisError = null;
    analyzingPage = true;
    pageAnalysisTotal = ids.length;
    pageAnalysisProgress = 0;

    // Mark all displayed games as analyzing for UI feedback
    for (const id of ids) {
      analyzingGames.add(id);
    }
    analyzingGames = new Set(analyzingGames);

    try {
      // Always run client-side concurrent analysis to get immediate per-game updates
      const concurrency = 4;
      function markAnalyzing(gameId, on) {
        if (on) {
          analyzingGames.add(gameId);
        } else {
          analyzingGames.delete(gameId);
        }
        analyzingGames = new Set(analyzingGames);
      }
      async function runWithConcurrency(tasks, limit) {
        let running = 0;
        let index = 0;
        return new Promise((resolve) => {
          function next() {
            if (index >= tasks.length && running === 0) return resolve();
            while (running < limit && index < tasks.length) {
              const i = index++;
              running++;
              tasks[i]()
                .catch(() => {})
                .finally(() => {
                  running--;
                  pageAnalysisProgress += 1;
                  next();
                });
            }
          }
          next();
        });
      }
      let failedCount = 0;
      const tasks = ids.map((gameId) => async () => {
        try {
          markAnalyzing(gameId, true);
          await analyzeGame(gameId);
          // Update local game status to completed and enable View Analysis
          const idx = games.findIndex(g => g.id === gameId);
          if (idx !== -1) {
            const updated = { ...games[idx] };
            updated.analysis_status = 'completed';
            updated.has_analysis = true;
            games[idx] = updated;
            games = [...games];
          }
        } catch (err) {
          console.error('Analyze failed for game', gameId, err);
          failedCount += 1;
          const idx = games.findIndex(g => g.id === gameId);
          if (idx !== -1) {
            const updated = { ...games[idx] };
            updated.analysis_status = 'queued';
            games[idx] = updated;
            games = [...games];
          }
        } finally {
          // Remove from analyzing summary immediately upon finishing
          markAnalyzing(gameId, false);
        }
      });
      await runWithConcurrency(tasks, concurrency);
      if (failedCount === 0) {
        syncSuccess = `Analyzed ${ids.length} game${ids.length === 1 ? '' : 's'} successfully.`;
        setTimeout(() => (syncSuccess = null), 5000);
      } else {
        pageAnalysisError = `Completed ${ids.length - failedCount}/${ids.length}. ${failedCount} failed.`;
      }
    } finally {
      // Clear analyzing flags for the displayed ids
      for (const id of ids) {
        analyzingGames.delete(id);
      }
      analyzingGames = new Set(analyzingGames);
      analyzingPage = false;
      // Single refresh at the very end to reconcile anything we might have missed
      await loadGames();
    }
  }

  async function handleViewAnalysis(gameId) {
    try {
      const result = await getGameAnalysis(gameId);
      selectedAnalysis = result.analysis;
      showAnalysisModal = true;
      analysisError = null;
    } catch (err) {
      console.error('[Games] Failed to load analysis:', err);
      analysisError = `Failed to load analysis: ${err.message}`;
      setTimeout(() => analysisError = null, 5000);
    }
  }

  function closeAnalysisModal() {
    showAnalysisModal = false;
    selectedAnalysis = null;
  }

  onMount(() => {
    loadGames();
  });
</script>

<div class="games-page">
  <div class="header">
    <h1>Game Library</h1>
    <div class="header-actions">
      <button
        class="sync-btn"
        on:click={handleSync}
        disabled={syncing || isAnalysisInProgress}
      >
        {syncing ? 'Syncing...' : 'Fetch New Games'}
      </button>
      <button
        class="sync-btn analyze-page-btn"
        on:click={handleAnalyzePage}
        disabled={analyzingPage || displayedGames.length === 0}
      >
        {analyzingPage
          ? 'Analyzing...'
          : 'Analyze This Page'}
      </button>
      {#if isAnalysisInProgress}
        <div class="analysis-progress">
          <div class="progress-label">
            {analyzingPage ? `Analyzing ${pageAnalysisTotal || displayedAnalyzingGames.length} games on this page...` : `Analyzing ${displayedAnalyzingGames.length} game${displayedAnalyzingGames.length === 1 ? '' : 's'}...`}
          </div>
          <div class="progress-bar">
            <div class="progress-fill" style="width: {pageAnalysisTotal ? Math.min(100, Math.round((pageAnalysisProgress / pageAnalysisTotal) * 100)) : 100}%"></div>
          </div>
          {#if displayedAnalyzingGames.length > 0}
            <div class="progress-list">
              {#each displayedAnalyzingGames.slice(0, 4) as g}
                <span class="progress-pill">{g.white_player || 'White'} vs {g.black_player || 'Black'}</span>
              {/each}
              {#if displayedAnalyzingGames.length > 4}
                <span class="progress-more">+{displayedAnalyzingGames.length - 4} more</span>
              {/if}
            </div>
          {/if}
        </div>
      {/if}
    </div>
  </div>

  <!-- Sync feedback messages -->
  {#if syncSuccess}
    <div class="alert alert-success">
      {syncSuccess}
      <button class="alert-close" on:click={() => syncSuccess = null}>×</button>
    </div>
  {/if}

  {#if syncError}
    <div class="alert alert-error">
      Error: {syncError}
      <button class="alert-close" on:click={() => syncError = null}>×</button>
    </div>
  {/if}

  {#if analysisError}
    <div class="alert alert-error">
      {analysisError}
      <button class="alert-close" on:click={() => analysisError = null}>×</button>
    </div>
  {/if}

  {#if pageAnalysisError}
    <div class="alert alert-error">
      {pageAnalysisError}
      <button class="alert-close" on:click={() => pageAnalysisError = null}>×</button>
    </div>
  {/if}

  <!-- Filters and search -->
  <div class="controls">
    <div class="search-box">
      <input
        type="text"
        placeholder="Search games (player names, result, date)..."
        bind:value={searchTerm}
      />
    </div>

    <div class="filter-row">
      <div class="filter-box">
        <label for="status-filter">Status:</label>
        <select id="status-filter" bind:value={statusFilter}>
          <option value="all">All</option>
          <option value="queued">Queued</option>
          <option value="analyzing">Analyzing</option>
          <option value="completed">Completed</option>
        </select>
      </div>

      <div class="filter-box">
        <label for="result-filter">Result:</label>
        <select id="result-filter" bind:value={resultFilter}>
          <option value="all">All</option>
          <option value="win">Wins</option>
          <option value="loss">Losses</option>
          <option value="draw">Draws</option>
        </select>
      </div>

      <div class="filter-box">
        <label for="time-class-filter">Type:</label>
        <select id="time-class-filter" bind:value={timeClassFilter}>
          <option value="all">All</option>
          <option value="bullet">Bullet</option>
          <option value="blitz">Blitz</option>
          <option value="rapid">Rapid</option>
          <option value="daily">Daily</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div class="filter-box">
        <label for="player-name">Player:</label>
        <input
          type="text"
          id="player-name"
          placeholder="Enter player name..."
          bind:value={playerName}
        />
      </div>

      <div class="filter-box">
        <label for="date-from">From:</label>
        <input
          type="date"
          id="date-from"
          bind:value={dateFrom}
        />
      </div>

      <div class="filter-box">
        <label for="date-to">To:</label>
        <input
          type="date"
          id="date-to"
          bind:value={dateTo}
        />
      </div>

      <button class="clear-filters-btn" on:click={clearFilters}>
        Clear Filters
      </button>
    </div>
  </div>

  <!-- Games table -->
  {#if loading}
    <div class="loading">Loading games...</div>
  {:else if error}
    <div class="error">
      <p>Failed to load games: {error}</p>
      <button on:click={loadGames}>Retry</button>
    </div>
  {:else if displayedGames.length === 0}
    <div class="empty">
      {#if total === 0}
        <h2>No games yet</h2>
        <p>Click "Fetch New Games" to import your games from Chess.com</p>
      {:else}
        <h2>No matching games</h2>
        <p>Try adjusting your search or filters</p>
      {/if}
    </div>
  {:else}
    <div class="results-summary">
      Showing {displayedGames.length} game{displayedGames.length !== 1 ? 's' : ''} on this page (Total: {total} matching your filters)
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th class="sortable {isAnalysisInProgress ? 'disabled' : ''}" on:click={() => !isAnalysisInProgress && handleColumnSort('date')}>
              Date
              {#if sortBy === 'date'}
                <span class="sort-indicator">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </th>
            <th class="sortable {isAnalysisInProgress ? 'disabled' : ''}" on:click={() => !isAnalysisInProgress && handleColumnSort('white')}>
              White
              {#if sortBy === 'white'}
                <span class="sort-indicator">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </th>
            <th class="sortable {isAnalysisInProgress ? 'disabled' : ''}" on:click={() => !isAnalysisInProgress && handleColumnSort('black')}>
              Black
              {#if sortBy === 'black'}
                <span class="sort-indicator">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </th>
            <th class="sortable {isAnalysisInProgress ? 'disabled' : ''}" on:click={() => !isAnalysisInProgress && handleColumnSort('result')}>
              Result
              {#if sortBy === 'result'}
                <span class="sort-indicator">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </th>
            <th class="sortable {isAnalysisInProgress ? 'disabled' : ''}" on:click={() => !isAnalysisInProgress && handleColumnSort('time_class')}>
              Type
              {#if sortBy === 'time_class'}
                <span class="sort-indicator">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </th>
            <th class="sortable status-header {isAnalysisInProgress ? 'disabled' : ''}" on:click={() => !isAnalysisInProgress && handleColumnSort('status')}>
              Status
              {#if sortBy === 'status'}
                <span class="sort-indicator">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each displayedGames as game (game.id)}
            <tr>
              <td class="date-cell">{formatDate(game.game_date)}</td>
              <td class="player-cell">
                <span class:player-bold={playerName && game.white_player && game.white_player.toLowerCase() === playerName.toLowerCase().trim()}>
                  {game.white_player || 'Unknown'}
                </span>
                {#if game.white_rating}
                  <span class="rating">({game.white_rating})</span>
                {/if}
              </td>
              <td class="player-cell">
                <span class:player-bold={playerName && game.black_player && game.black_player.toLowerCase() === playerName.toLowerCase().trim()}>
                  {game.black_player || 'Unknown'}
                </span>
                {#if game.black_rating}
                  <span class="rating">({game.black_rating})</span>
                {/if}
              </td>
              <td class="result-cell">{game.result || 'N/A'}</td>
              <td class="type-cell">{formatType(game.time_class)}</td>
              <td class="status-cell">
                <span class="status-badge {getStatusBadgeClass(getEffectiveStatus(game))}">
                  {getEffectiveStatus(game)}
                </span>
              </td>
              <td class="actions-cell">
                <a href="#/games/{game.id}" class="action-btn view-game-btn">
                  View Game
                </a>
                {#if game.has_analysis}
                  <button
                    class="action-btn view-btn"
                    on:click={() => handleViewAnalysis(game.id)}
                  >
                    View Analysis
                  </button>
                {:else if analyzingGames.has(game.id)}
                  <button class="action-btn analyzing-btn" disabled>
                    Analyzing...
                  </button>
                {:else}
                  <button
                    class="action-btn analyze-btn"
                    on:click={() => handleAnalyzeGame(game.id)}
                  >
                    Analyze Game
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div class="pagination">
      <div class="pagination-info">
        Showing {skip + 1}-{Math.min(skip + pageSize, total)} of {total} games
      </div>

      <div class="pagination-controls">
        <button
          on:click={prevPage}
          disabled={currentPage === 0 || isAnalysisInProgress}
          class="page-btn"
        >
          ‹ Prev
        </button>

        <span class="page-info">
          {currentPage + 1} / {totalPages}
        </span>

        <button
          on:click={nextPage}
          disabled={currentPage >= totalPages - 1 || isAnalysisInProgress}
          class="page-btn"
        >
          Next ›
        </button>
      </div>
    </div>
  {/if}

  <!-- Analysis Modal -->
  {#if showAnalysisModal && selectedAnalysis}
    <div
      class="modal-overlay"
      role="button"
      tabindex="0"
      aria-label="Close analysis modal"
      on:click={closeAnalysisModal}
      on:keydown={(e) => {
        if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          closeAnalysisModal();
        }
      }}
    >
      <div class="modal-content" role="dialog" aria-modal="true" tabindex="-1" on:mousedown|stopPropagation>
        <div class="modal-header">
          <h2>Game Analysis</h2>
          <button class="close-btn" on:click={closeAnalysisModal}>×</button>
        </div>

        <div class="modal-body">
          <!-- Game Info -->
          <div class="analysis-section">
            <h3>Game Information</h3>
            <div class="game-info">
              <p><strong>White:</strong> {selectedAnalysis.game_info.white}</p>
              <p><strong>Black:</strong> {selectedAnalysis.game_info.black}</p>
              <p><strong>Result:</strong> {selectedAnalysis.game_info.result}</p>
              <p><strong>Date:</strong> {selectedAnalysis.game_info.date}</p>
              <p><strong>Total Moves:</strong> {selectedAnalysis.total_moves}</p>
            </div>
          </div>

          <!-- Analysis Settings -->
          <div class="analysis-section">
            <h3>Analysis Settings</h3>
            <div class="analysis-settings">
              <p><strong>Depth:</strong> {selectedAnalysis.analysis_settings.depth}</p>
              <p><strong>Time per move:</strong> {selectedAnalysis.analysis_settings.time_ms}ms</p>
              <p><strong>Threads:</strong> {selectedAnalysis.analysis_settings.threads}</p>
              <p><strong>Hash:</strong> {selectedAnalysis.analysis_settings.hash_mb}MB</p>
            </div>
          </div>

          <!-- Moves Analysis -->
          <div class="analysis-section">
            <h3>Move-by-Move Analysis</h3>
            <div class="moves-list">
              {#each selectedAnalysis.moves as move, index}
                <div class="move-card">
                  <div class="move-header">
                    <strong>Move {move.move_number}:</strong>
                    <span class="move-notation">{move.move}</span>
                    <span class="score {move.analysis.score_type === 'mate' ? 'mate-score' : ''}">
                      {move.analysis.score}
                    </span>
                    {#if move.classification || move.special_classification}
                      <!-- Inline classification icon -->
                      {#if move.special_classification && move.special_classification.toLowerCase() === 'brilliant'}
                        <img class="class-inline-icon" src="../../assets/classifications/brilliant.png" alt="brilliant" width="16" height="16" />
                      {:else if move.special_classification && (move.special_classification.toLowerCase() === 'great move' || move.special_classification.toLowerCase() === 'great')}
                        <img class="class-inline-icon" src="../../assets/classifications/great.png" alt="great move" width="16" height="16" />
                      {:else if move.special_classification && move.special_classification.toLowerCase() === 'miss'}
                        <img class="class-inline-icon" src="../../assets/classifications/miss.png" alt="miss" width="16" height="16" />
                      {:else}
                        {#if move.classification && move.classification.toLowerCase() === 'best'}
                          <img class="class-inline-icon" src="../../assets/classifications/best.png" alt="best" width="16" height="16" />
                        {:else if move.classification && move.classification.toLowerCase() === 'excellent'}
                          <img class="class-inline-icon" src="../../assets/classifications/excellent.png" alt="excellent" width="16" height="16" />
                        {:else if move.classification && move.classification.toLowerCase() === 'good'}
                          <img class="class-inline-icon" src="../../assets/classifications/good.png" alt="good" width="16" height="16" />
                        {:else if move.classification && move.classification.toLowerCase() === 'inaccuracy'}
                          <img class="class-inline-icon" src="../../assets/classifications/inaccuracy.png" alt="inaccuracy" width="16" height="16" />
                        {:else if move.classification && move.classification.toLowerCase() === 'mistake'}
                          <img class="class-inline-icon" src="../../assets/classifications/mistake.png" alt="mistake" width="16" height="16" />
                        {:else if move.classification && move.classification.toLowerCase() === 'blunder'}
                          <img class="class-inline-icon" src="../../assets/classifications/blunder.png" alt="blunder" width="16" height="16" />
                        {/if}
                      {/if}
                    {/if}
                  </div>
                  <div class="move-details">
                    <p><strong>Best move:</strong> {move.analysis.best_move || 'N/A'}</p>
                    {#if move.analysis.pv && move.analysis.pv.length > 0}
                      <p><strong>Principal variation:</strong> {move.analysis.pv.slice(0, 3).join(' ')}</p>
                    {/if}
                    {#if move.expected_points}
                      <p><strong>EP:</strong> {move.expected_points.mover_before} → {move.expected_points.mover_after} (Δ {move.expected_points.gain ? `+${move.expected_points.gain}` : `-${move.expected_points.loss}`})</p>
                    {/if}
                  </div>
                </div>
              {/each}
            </div>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .games-page {
    padding: 2rem;
    max-width: 1400px;
    margin: 0 auto;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 2rem;
  }

  .header-actions {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
  }

  h1 {
    margin: 0;
    color: #2c3e50;
  }

  .sync-btn {
    padding: 0.75rem 1.5rem;
    background: #27ae60;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
    font-weight: 500;
    transition: background 0.2s;
  }

  .sync-btn:hover:not(:disabled) {
    background: #229954;
  }

  .sync-btn:disabled {
    background: #95a5a6;
    cursor: not-allowed;
  }

  .analyze-page-btn {
    background: #3498db;
  }

  .analyze-page-btn:hover:not(:disabled) {
    background: #2980b9;
  }

  .analysis-progress {
    width: 320px;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .progress-label {
    font-size: 0.85rem;
    color: #34495e;
    text-align: right;
  }

  .progress-bar {
    height: 8px;
    background: #ecf0f1;
    border-radius: 6px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #27ae60, #2ecc71);
    width: 0%;
    transition: width 0.3s ease;
  }

  .progress-list {
    display: flex;
    gap: 0.25rem;
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .progress-pill {
    background: #e8f4f8;
    border: 1px solid #cde9f3;
    color: #2c3e50;
    border-radius: 12px;
    padding: 0.15rem 0.5rem;
    font-size: 0.75rem;
  }

  .progress-more {
    color: #7f8c8d;
    font-size: 0.75rem;
  }

  .alert {
    padding: 1rem 1.5rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .alert-success {
    background: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
  }

  .alert-error {
    background: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
  }

  .alert-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0;
    line-height: 1;
    opacity: 0.5;
  }

  .alert-close:hover {
    opacity: 1;
  }

  .controls {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .search-box {
    width: 100%;
  }

  .search-box input {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
  }

  .filter-row {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    align-items: center;
  }

  .filter-box {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .filter-box label {
    font-weight: 500;
    color: #555;
    white-space: nowrap;
  }

  .filter-box select,
  .filter-box input[type="date"],
  .filter-box input[type="text"] {
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
  }

  .filter-box select,
  .filter-box input[type="date"] {
    cursor: pointer;
  }

  .filter-box input[type="date"],
  .filter-box input[type="text"] {
    min-width: 150px;
  }

  .clear-filters-btn {
    padding: 0.75rem 1rem;
    background: #95a5a6;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: background 0.2s;
    white-space: nowrap;
  }

  .clear-filters-btn:hover {
    background: #7f8c8d;
  }

  .results-summary {
    margin-bottom: 1rem;
    padding: 0.75rem 1rem;
    background: #e8f4f8;
    border-radius: 4px;
    font-weight: 500;
    color: #2c3e50;
  }

  .loading {
    text-align: center;
    padding: 3rem;
    color: #666;
    font-size: 1.1rem;
  }

  .error {
    background: #fee;
    border: 1px solid #fcc;
    padding: 1.5rem;
    border-radius: 8px;
    text-align: center;
  }

  .error button {
    margin-top: 1rem;
    padding: 0.5rem 1.5rem;
    background: #e74c3c;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }

  .empty {
    text-align: center;
    padding: 4rem 2rem;
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }

  .empty h2 {
    margin-bottom: 1rem;
    color: #2c3e50;
  }

  .empty p {
    color: #666;
    font-size: 1.1rem;
  }

  .table-container {
    background: white;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    overflow: hidden;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  thead {
    background: #34495e;
    color: white;
  }

  th {
    padding: 1rem;
    text-align: left;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.875rem;
    letter-spacing: 0.5px;
  }

  th.sortable {
    cursor: pointer;
    user-select: none;
    transition: background 0.2s;
  }

  th.sortable:hover {
    background: #2c3e50;
  }

  th.sortable.disabled {
    opacity: 0.5;
    pointer-events: none;
    cursor: default;
  }

  .sort-indicator {
    margin-left: 0.5rem;
    font-size: 1rem;
  }

  tbody tr {
    border-bottom: 1px solid #ecf0f1;
    transition: background 0.2s;
  }

  tbody tr:hover {
    background: #f8f9fa;
  }

  td {
    padding: 1rem;
  }

  .date-cell {
    color: #7f8c8d;
    font-size: 0.9rem;
  }

  .player-cell {
    font-weight: 500;
    color: #2c3e50;
  }

  .player-bold {
    font-weight: 700;
  }

  .rating {
    color: #7f8c8d;
    font-size: 0.875rem;
    font-weight: 400;
    margin-left: 0.5rem;
  }

  .result-cell {
    font-weight: 600;
    color: #34495e;
  }

  .status-header {
    text-align: center;
  }

  .status-cell {
    text-align: center;
  }

  .status-badge {
    display: inline-block;
    padding: 0.35rem 0.75rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .status-completed {
    background: #d4edda;
    color: #155724;
  }

  .status-analyzing {
    background: #fff3cd;
    color: #856404;
  }

  .status-queued {
    background: #d1ecf1;
    color: #0c5460;
  }

  .status-unknown {
    background: #f8d7da;
    color: #721c24;
  }

  .pagination {
    margin-top: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .pagination-info {
    color: #666;
    font-size: 0.9rem;
  }

  .pagination-controls {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .page-btn {
    padding: 0.5rem 1rem;
    background: #3498db;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: background 0.2s;
  }

  .page-btn:hover:not(:disabled) {
    background: #2980b9;
  }

  .page-btn:disabled {
    background: #bdc3c7;
    cursor: not-allowed;
  }

  .page-info {
    font-weight: 500;
    color: #2c3e50;
  }

  /* Actions column */
  .actions-cell {
    display: flex;
    gap: 0.5rem;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    padding: 0.5rem;
  }

  .action-btn {
    padding: 0.5rem 0.75rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 500;
    transition: all 0.2s;
    white-space: nowrap;
  }

  .analyze-btn {
    background: #3498db;
    color: white;
  }

  .analyze-btn:hover {
    background: #2980b9;
  }

  .view-btn {
    background: #27ae60;
    color: white;
  }

  .view-btn:hover {
    background: #229954;
  }

  .analyzing-btn {
    background: #f39c12;
    color: white;
    cursor: not-allowed;
    opacity: 0.7;
  }

  .view-game-btn {
    background: #9b59b6;
    color: white;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .view-game-btn:hover {
    background: #8e44ad;
    text-decoration: none;
  }

  /* Analysis Modal */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 2rem;
  }

  .modal-content {
    background: white;
    border-radius: 8px;
    max-width: 1000px;
    max-height: 90vh;
    width: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1.5rem;
    border-bottom: 1px solid #e0e0e0;
  }

  .modal-header h2 {
    margin: 0;
    color: #2c3e50;
  }

  .close-btn {
    background: none;
    border: none;
    font-size: 2rem;
    cursor: pointer;
    color: #7f8c8d;
    line-height: 1;
    padding: 0;
    width: 2rem;
    height: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .close-btn:hover {
    color: #e74c3c;
  }

  .modal-body {
    padding: 1.5rem;
    overflow-y: auto;
  }

  .analysis-section {
    margin-bottom: 2rem;
  }

  .analysis-section h3 {
    color: #2c3e50;
    margin-bottom: 1rem;
    font-size: 1.25rem;
  }

  .game-info,
  .analysis-settings {
    background: #f8f9fa;
    padding: 1rem;
    border-radius: 4px;
  }

  .game-info p,
  .analysis-settings p {
    margin: 0.5rem 0;
    color: #34495e;
  }

  .moves-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    max-height: 400px;
    overflow-y: auto;
    padding: 0.5rem;
  }

  .move-card {
    background: #f8f9fa;
    padding: 1rem;
    border-radius: 4px;
    border-left: 4px solid #3498db;
  }

  .move-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.5rem;
  }

  .move-notation {
    font-family: monospace;
    background: #ecf0f1;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-size: 1rem;
    font-weight: 600;
  }

  .score {
    margin-left: auto;
    font-weight: 600;
    padding: 0.25rem 0.75rem;
    border-radius: 3px;
    background: #3498db;
    color: white;
  }

  .mate-score {
    background: #e74c3c;
  }

  .move-details {
    font-size: 0.875rem;
    color: #7f8c8d;
  }

  .move-details p {
    margin: 0.25rem 0;
  }

  /* Classification badge (shares style with GameView) */
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

  /* Responsive design */
  @media (max-width: 768px) {
    .header {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }

    .controls {
      flex-direction: column;
    }

    .search-box,
    .filter-box {
      width: 100%;
    }

    .filter-box {
      flex-direction: column;
      align-items: flex-start;
    }

    .table-container {
      overflow-x: auto;
    }

    table {
      min-width: 600px;
    }

    .pagination {
      flex-direction: column;
      align-items: center;
    }
  }
</style>
