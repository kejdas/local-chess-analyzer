<script>
  import { onMount } from 'svelte';
  import { getGames, startSync, getSyncStatus, getSettings } from '../api/client.js';

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
  let playerName = ''; // For result filtering - which player to check results for
  let dateFrom = '';
  let dateTo = '';
  let sortBy = 'date'; // date, result, status
  let sortOrder = 'desc'; // asc, desc
  let syncing = false;
  let syncError = null;
  let syncSuccess = null;
  let username = ''; // From settings, used as default for playerName

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
  $: if (hasInitialLoad && (dateFrom || dateTo || statusFilter !== 'all')) {
    currentPage = 0;
    loadGames();
  }

  // Also reload when clearing filters back to defaults
  $: if (hasInitialLoad && !dateFrom && !dateTo && statusFilter === 'all') {
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

  function getStatusBadgeClass(status) {
    switch (status) {
      case 'completed': return 'status-completed';
      case 'analyzing': return 'status-analyzing';
      case 'queued': return 'status-queued';
      default: return 'status-unknown';
    }
  }

  onMount(() => {
    loadGames();
  });
</script>

<div class="games-page">
  <div class="header">
    <h1>Game Library</h1>
    <button
      class="sync-btn"
      on:click={handleSync}
      disabled={syncing}
    >
      {syncing ? 'Syncing...' : 'Fetch New Games'}
    </button>
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
            <th class="sortable" on:click={() => handleColumnSort('date')}>
              Date
              {#if sortBy === 'date'}
                <span class="sort-indicator">{sortOrder === 'asc' ? '↑' : '↓'}</span>
              {/if}
            </th>
            <th>White</th>
            <th>Black</th>
            <th>Result</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {#each displayedGames as game (game.id)}
            <tr>
              <td class="date-cell">{formatDate(game.game_date)}</td>
              <td class="player-cell">{game.white_player || 'Unknown'}</td>
              <td class="player-cell">{game.black_player || 'Unknown'}</td>
              <td class="result-cell">{game.result || 'N/A'}</td>
              <td class="status-cell">
                <span class="status-badge {getStatusBadgeClass(game.analysis_status)}">
                  {game.analysis_status}
                </span>
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
          disabled={currentPage === 0}
          class="page-btn"
        >
          Previous
        </button>

        <span class="page-info">
          Page {currentPage + 1} of {totalPages}
        </span>

        <button
          on:click={nextPage}
          disabled={currentPage >= totalPages - 1}
          class="page-btn"
        >
          Next
        </button>
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

  .result-cell {
    font-weight: 600;
    color: #34495e;
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
