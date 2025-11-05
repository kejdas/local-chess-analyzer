<script>
  import { onMount } from 'svelte';
  import { getGamesStats, getSyncStatus } from '../api/client.js';

  let stats = null;
  let syncStatus = null;
  let loading = true;
  let error = null;

  async function loadData() {
    loading = true;
    error = null;
    try {
      [stats, syncStatus] = await Promise.all([
        getGamesStats(),
        getSyncStatus()
      ]);
    } catch (err) {
      error = err.message;
      console.error('Failed to load dashboard data:', err);
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadData();
  });
</script>

<div class="home">
  <h1>Dashboard</h1>

  {#if loading}
    <div class="loading">Loading dashboard data...</div>
  {:else if error}
    <div class="error">
      <p>Failed to load data: {error}</p>
      <button on:click={loadData}>Retry</button>
    </div>
  {:else}
    <div class="dashboard-grid">
      <!-- Games Statistics Card -->
      <div class="card">
        <h2>Game Statistics</h2>
        {#if stats}
          <div class="stats">
            <div class="stat-item">
              <span class="stat-label">Total Games</span>
              <span class="stat-value">{stats.total}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Queued for Analysis</span>
              <span class="stat-value">{stats.queued}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Analyzing</span>
              <span class="stat-value">{stats.analyzing}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Completed</span>
              <span class="stat-value">{stats.completed}</span>
            </div>
          </div>
          <a href="#/games" class="card-link">View All Games →</a>
        {/if}
      </div>

      <!-- Sync Status Card -->
      <div class="card">
        <h2>Sync Status</h2>
        {#if syncStatus}
          <div class="sync-info">
            {#if syncStatus.is_running}
              <div class="status running">
                <span class="status-indicator"></span>
                Sync in progress...
              </div>
            {:else if syncStatus.last_result}
              <div class="status idle">
                <span class="status-indicator"></span>
                Last sync: {new Date(syncStatus.last_run).toLocaleString()}
              </div>
              {#if syncStatus.last_result.success}
                <div class="sync-result success">
                  <p><strong>Username:</strong> {syncStatus.last_result.username}</p>
                  <p><strong>Fetched:</strong> {syncStatus.last_result.total_fetched} games</p>
                  <p><strong>Created:</strong> {syncStatus.last_result.created}</p>
                  <p><strong>Skipped:</strong> {syncStatus.last_result.skipped}</p>
                </div>
              {:else}
                <div class="sync-result error">
                  <p>Error: {syncStatus.last_result.error}</p>
                </div>
              {/if}
            {:else}
              <div class="status idle">
                <span class="status-indicator"></span>
                No sync performed yet
              </div>
            {/if}
          </div>
          <a href="#/sync" class="card-link">Go to Sync →</a>
        {/if}
      </div>

      <!-- Quick Actions Card -->
      <div class="card">
        <h2>Quick Actions</h2>
        <div class="actions">
          <a href="#/sync" class="action-btn">Sync Games</a>
          <a href="#/settings" class="action-btn">Configure Settings</a>
          <a href="#/games" class="action-btn">Browse Games</a>
        </div>
      </div>

      <!-- Info Card -->
      <div class="card">
        <h2>About</h2>
        <p>Welcome to Chess Analyzer! This application helps you:</p>
        <ul>
          <li>Import games from Chess.com</li>
          <li>Analyze games with Stockfish engine</li>
          <li>Track your performance over time</li>
          <li>Identify patterns and improve</li>
        </ul>
        <p class="info-text">
          Start by configuring your Chess.com username in <a href="#/settings">Settings</a>,
          then <a href="#/sync">sync your games</a>.
        </p>
      </div>
    </div>
  {/if}
</div>

<style>
  .home {
    padding: 2rem;
    max-width: 1200px;
    margin: 0 auto;
  }

  h1 {
    margin-bottom: 2rem;
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

  .dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 1.5rem;
  }

  .card {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }

  .card h2 {
    margin-top: 0;
    margin-bottom: 1rem;
    color: #2c3e50;
    font-size: 1.25rem;
  }

  .stats {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .stat-item {
    display: flex;
    justify-content: space-between;
    padding: 0.75rem;
    background: #f8f9fa;
    border-radius: 4px;
  }

  .stat-label {
    color: #666;
  }

  .stat-value {
    font-weight: 600;
    color: #2c3e50;
    font-size: 1.25rem;
  }

  .sync-info {
    margin-bottom: 1rem;
  }

  .status {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem;
    background: #f8f9fa;
    border-radius: 4px;
    margin-bottom: 1rem;
  }

  .status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #95a5a6;
  }

  .status.running .status-indicator {
    background: #3498db;
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .sync-result {
    padding: 1rem;
    border-radius: 4px;
    font-size: 0.9rem;
  }

  .sync-result.success {
    background: #d4edda;
    border: 1px solid #c3e6cb;
  }

  .sync-result.error {
    background: #f8d7da;
    border: 1px solid #f5c6cb;
  }

  .sync-result p {
    margin: 0.25rem 0;
  }

  :global(.card-link) {
    display: inline-block;
    margin-top: 1rem;
    color: #3498db;
    text-decoration: none;
    font-weight: 500;
  }

  :global(.card-link:hover) {
    text-decoration: underline;
  }

  .actions {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  :global(.action-btn) {
    display: block;
    padding: 0.75rem 1rem;
    background: #3498db;
    color: white;
    text-decoration: none;
    border-radius: 4px;
    text-align: center;
    transition: background 0.2s;
  }

  :global(.action-btn:hover) {
    background: #2980b9;
  }

  .card ul {
    margin: 1rem 0;
    padding-left: 1.5rem;
  }

  .card li {
    margin: 0.5rem 0;
    color: #555;
  }

  .info-text {
    margin-top: 1rem;
    padding: 1rem;
    background: #e8f4f8;
    border-radius: 4px;
    font-size: 0.9rem;
  }
</style>
