<script>
  import { onMount } from 'svelte';
  import { getSettings, updateSettings } from '../api/client.js';

  let settings = {
    chess_com_username: '',
    stockfish_path: '',
    stockfish_threads: '',
    stockfish_hash_mb: '',
    analysis_depth: '',
    analysis_time_ms: '',
    auto_sync_enabled: '',
    theme: ''
  };

  let loading = true;
  let saving = false;
  let error = null;
  let successMessage = null;

  async function loadSettings() {
    loading = true;
    error = null;
    try {
      settings = await getSettings();
    } catch (err) {
      error = 'Failed to load settings: ' + err.message;
      console.error('Failed to load settings:', err);
    } finally {
      loading = false;
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    saving = true;
    error = null;
    successMessage = null;

    try {
      const result = await updateSettings(settings);
      successMessage = `Settings saved successfully! Updated: ${result.updated_settings.join(', ')}`;
      setTimeout(() => {
        successMessage = null;
      }, 3000);
    } catch (err) {
      error = 'Failed to save settings: ' + err.message;
      console.error('Failed to save settings:', err);
    } finally {
      saving = false;
    }
  }

  onMount(() => {
    loadSettings();
  });
</script>

<div class="settings">
  <h1>Settings</h1>

  {#if loading}
    <div class="loading">Loading settings...</div>
  {:else}
    <form on:submit={handleSubmit}>
      {#if error}
        <div class="alert alert-error">
          {error}
        </div>
      {/if}

      {#if successMessage}
        <div class="alert alert-success">
          {successMessage}
        </div>
      {/if}

      <div class="settings-section">
        <h2>Chess.com Integration</h2>

        <div class="form-group">
          <label for="chess_com_username">
            Chess.com Username
            <span class="help-text">Your Chess.com username for syncing games</span>
          </label>
          <input
            type="text"
            id="chess_com_username"
            bind:value={settings.chess_com_username}
            placeholder="Enter your Chess.com username"
          />
        </div>

        <div class="form-group">
          <label for="auto_sync_enabled">
            Auto Sync Enabled
            <span class="help-text">Automatically sync games periodically</span>
          </label>
          <select id="auto_sync_enabled" bind:value={settings.auto_sync_enabled}>
            <option value="false">Disabled</option>
            <option value="true">Enabled</option>
          </select>
        </div>
      </div>

      <div class="settings-section">
        <h2>Stockfish Engine</h2>

        <div class="form-group">
          <label for="stockfish_path">
            Stockfish Binary Path
            <span class="help-text">Path to the Stockfish executable (read-only)</span>
          </label>
          <input
            type="text"
            id="stockfish_path"
            value={settings.stockfish_path}
            readonly
            disabled
          />
        </div>

        <div class="form-group">
          <label for="stockfish_threads">
            Threads
            <span class="help-text">Number of CPU threads to use (1-16)</span>
          </label>
          <input
            type="number"
            id="stockfish_threads"
            bind:value={settings.stockfish_threads}
            min="1"
            max="16"
          />
        </div>

        <div class="form-group">
          <label for="stockfish_hash_mb">
            Hash Size (MB)
            <span class="help-text">Memory allocated for hash table (16-2048)</span>
          </label>
          <input
            type="number"
            id="stockfish_hash_mb"
            bind:value={settings.stockfish_hash_mb}
            min="16"
            max="2048"
          />
        </div>
      </div>

      <div class="settings-section">
        <h2>Analysis Parameters</h2>

        <div class="form-group">
          <label for="analysis_depth">
            Analysis Depth
            <span class="help-text">Search depth for analysis (5-30)</span>
          </label>
          <input
            type="number"
            id="analysis_depth"
            bind:value={settings.analysis_depth}
            min="5"
            max="30"
          />
        </div>

        <div class="form-group">
          <label for="analysis_time_ms">
            Analysis Time (ms)
            <span class="help-text">Time per move in milliseconds (100-10000)</span>
          </label>
          <input
            type="number"
            id="analysis_time_ms"
            bind:value={settings.analysis_time_ms}
            min="100"
            max="10000"
            step="100"
          />
        </div>
      </div>

      <div class="settings-section">
        <h2>Appearance</h2>

        <div class="form-group">
          <label for="theme">
            Theme
            <span class="help-text">Application theme</span>
          </label>
          <select id="theme" bind:value={settings.theme}>
            <option value="default">Default</option>
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </div>
      </div>

      <div class="form-actions">
        <button type="submit" class="btn btn-primary" disabled={saving}>
          {saving ? 'Saving...' : 'Save Settings'}
        </button>
        <button type="button" class="btn btn-secondary" on:click={loadSettings} disabled={saving}>
          Reset
        </button>
      </div>
    </form>
  {/if}
</div>

<style>
  .settings {
    padding: 2rem;
    max-width: 800px;
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

  .alert {
    padding: 1rem;
    border-radius: 4px;
    margin-bottom: 1.5rem;
  }

  .alert-error {
    background: #fee;
    border: 1px solid #fcc;
    color: #c33;
  }

  .alert-success {
    background: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
  }

  .settings-section {
    background: white;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  }

  .settings-section h2 {
    margin-top: 0;
    margin-bottom: 1.5rem;
    color: #2c3e50;
    font-size: 1.25rem;
    border-bottom: 2px solid #ecf0f1;
    padding-bottom: 0.5rem;
  }

  .form-group {
    margin-bottom: 1.5rem;
  }

  label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #2c3e50;
  }

  .help-text {
    display: block;
    font-size: 0.875rem;
    font-weight: normal;
    color: #666;
    margin-top: 0.25rem;
  }

  input[type="text"],
  input[type="number"],
  select {
    width: 100%;
    padding: 0.75rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 1rem;
    transition: border-color 0.2s;
  }

  input:focus,
  select:focus {
    outline: none;
    border-color: #3498db;
  }

  input:disabled {
    background: #f5f5f5;
    cursor: not-allowed;
  }

  .form-actions {
    display: flex;
    gap: 1rem;
    margin-top: 2rem;
  }

  .btn {
    padding: 0.75rem 1.5rem;
    border: none;
    border-radius: 4px;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
  }

  .btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-primary {
    background: #3498db;
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: #2980b9;
  }

  .btn-secondary {
    background: #95a5a6;
    color: white;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #7f8c8d;
  }
</style>
