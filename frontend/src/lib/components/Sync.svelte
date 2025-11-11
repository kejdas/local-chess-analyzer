<script>
  import { onMount } from 'svelte';
  import { startSync, getSyncStatus, getSettings } from '../api/client.js';

  let defaultUsername = '';
  let username = '';
  let limitMonths = null; // null means all

  let syncing = false;
  let status = null;
  let error = null;
  let success = null;
  let polling = null;

  async function loadInitial() {
    try {
      const [settings, s] = await Promise.all([getSettings(), getSyncStatus()]);
      defaultUsername = settings.chess_com_username || '';
      if (!username) username = '';
      status = s;
    } catch (e) {
      console.error('[Sync] Failed to load initial data', e);
      error = e.message || 'Failed to load sync status';
      setTimeout(() => (error = null), 5000);
    }
  }

  onMount(loadInitial);

  function startPolling() {
    stopPolling();
    polling = setInterval(async () => {
      try {
        const s = await getSyncStatus();
        status = s;
        if (!s.is_running) {
          stopPolling();
          if (s.last_result) {
            if (s.last_result.success) {
              success = `Fetched ${s.last_result.total_fetched} games. Created ${s.last_result.created}, skipped ${s.last_result.skipped}.`;
              setTimeout(() => (success = null), 6000);
            } else if (s.last_result.error) {
              error = s.last_result.error;
              setTimeout(() => (error = null), 6000);
            }
          }
          syncing = false;
        }
      } catch (e) {
        console.warn('[Sync] Polling failed', e);
      }
    }, 1000);
  }

  function stopPolling() {
    if (polling) {
      clearInterval(polling);
      polling = null;
    }
  }

  async function handleStartSync() {
    syncing = true;
    error = null;
    success = null;
    try {
      const bodyUsername = username && username.trim() ? username.trim() : null;
      const lm = limitMonths ? Number(limitMonths) : null;
      await startSync(bodyUsername, lm);
      // Begin polling until it completes
      startPolling();
    } catch (e) {
      syncing = false;
      if (e?.status === 409) {
        error = 'A sync is already in progress.';
      } else if (e?.message) {
        error = e.message;
      } else {
        error = 'Failed to start sync.';
      }
      setTimeout(() => (error = null), 6000);
    }
  }

  async function refreshStatus() {
    try {
      status = await getSyncStatus();
    } catch (e) {
      error = e.message || 'Failed to refresh status';
      setTimeout(() => (error = null), 4000);
    }
  }
</script>

<div class="sync-page">
  <div class="header">
    <h1>Sync Games</h1>
    <p>Fetch games from Chess.com into your local database.</p>
  </div>

  {#if success}
    <div class="alert success">
      {success}
      <button class="close" on:click={() => (success = null)}>×</button>
    </div>
  {/if}
  {#if error}
    <div class="alert error">
      {error}
      <button class="close" on:click={() => (error = null)}>×</button>
    </div>
  {/if}

  <div class="panel">
    <h2>Options</h2>
    <div class="row">
      <label for="username">Username override</label>
      <div class="input-wrap">
        <input
          id="username"
          type="text"
          placeholder={defaultUsername ? `Leave blank to use "${defaultUsername}"` : 'Enter Chess.com username or configure in Settings'}
          bind:value={username}
        />
        <small class="hint">If left empty, the Settings username will be used.</small>
      </div>
    </div>

    <div class="row">
      <label for="months">Limit months</label>
      <select id="months" bind:value={limitMonths}>
        <option value={null}>All time</option>
        <option value="1">Last 1 month</option>
        <option value="3">Last 3 months</option>
        <option value="6">Last 6 months</option>
        <option value="12">Last 12 months</option>
      </select>
    </div>

    <div class="actions">
      <button class="primary" on:click={handleStartSync} disabled={syncing || status?.is_running}>
        {syncing || status?.is_running ? 'Syncing…' : 'Start Sync'}
      </button>
      <button on:click={refreshStatus}>Refresh Status</button>
    </div>
  </div>

  <div class="panel">
    <h2>Status</h2>
    {#if status}
      <div class="status">
        {#if status.is_running}
          <div class="badge running">Running</div>
          <p>Sync is in progress…</p>
        {:else}
          <div class="badge idle">Idle</div>
          {#if status.last_run}
            <p>Last run: {new Date(status.last_run).toLocaleString()}</p>
          {:else}
            <p>No sync performed yet.</p>
          {/if}
        {/if}
      </div>

      {#if status.last_result}
        {#if status.last_result.success}
          <div class="result ok">
            <p><strong>Username:</strong> {status.last_result.username}</p>
            <p><strong>Fetched:</strong> {status.last_result.total_fetched}</p>
            <p><strong>Created:</strong> {status.last_result.created}</p>
            <p><strong>Skipped:</strong> {status.last_result.skipped}</p>
          </div>
        {:else}
          <div class="result fail">
            <p><strong>Error:</strong> {status.last_result.error}</p>
          </div>
        {/if}
      {/if}
    {:else}
      <p>Loading status…</p>
    {/if}
  </div>
</div>

<style>
  .sync-page {
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1rem;
  }
  .header h1 {
    margin: 0 0 0.25rem 0;
    color: #2c3e50;
  }
  .header p {
    margin: 0;
    color: #666;
  }
  .panel {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    padding: 1.25rem;
    margin-top: 1rem;
  }
  .panel h2 {
    margin: 0 0 1rem 0;
    color: #2c3e50;
  }
  .row {
    display: grid;
    grid-template-columns: 180px 1fr;
    gap: 1rem;
    align-items: start;
    margin-bottom: 1rem;
  }
  .row label {
    font-weight: 600;
    color: #34495e;
    padding-top: 0.35rem;
  }
  .input-wrap input, select {
    width: 100%;
    padding: 0.6rem 0.75rem;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 1rem;
  }
  .hint {
    display: block;
    color: #7f8c8d;
    margin-top: 0.35rem;
    font-size: 0.85rem;
  }
  .actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }
  .actions button {
    padding: 0.6rem 1rem;
    border: none;
    border-radius: 6px;
    background: #ecf0f1;
    color: #2c3e50;
    cursor: pointer;
  }
  .actions button.primary {
    background: #3498db;
    color: #fff;
  }
  .actions button:disabled {
    opacity: 0.7;
    cursor: not-allowed;
  }
  .status {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }
  .badge {
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 700;
  }
  .badge.running {
    background: #eaf7ec;
    color: #27ae60;
  }
  .badge.idle {
    background: #eef3f7;
    color: #2c3e50;
  }
  .result {
    border-radius: 6px;
    padding: 0.75rem;
    margin-top: 0.5rem;
  }
  .result.ok {
    background: #eaf7ec;
    border: 1px solid #caeed0;
  }
  .result.fail {
    background: #fdecea;
    border: 1px solid #f5c6cb;
  }
  .alert {
    margin-top: 1rem;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .alert.success {
    background: #eaf7ec;
    border: 1px solid #caeed0;
    color: #207245;
  }
  .alert.error {
    background: #fdecea;
    border: 1px solid #f5c6cb;
    color: #8a1c1c;
  }
  .alert .close {
    background: none;
    border: none;
    font-size: 1.2rem;
    cursor: pointer;
    padding: 0;
    opacity: 0.6;
  }
</style>
