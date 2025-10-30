<script>
  import { onMount } from 'svelte';
  import { getSystemResources, updateSettings } from '../api/client.js';

  export let onComplete = () => {};
  export let onSkip = () => {};

  let step = 1;
  let username = '';
  let systemResources = null;
  let loading = false;
  let error = null;
  let saving = false;

  // Settings
  let threads = 1;
  let hashMb = 128;
  let depth = 15;
  let timeMs = 1000;

  // Load system resources
  onMount(async () => {
    await loadResources();
  });

  async function loadResources() {
    loading = true;
    error = null;
    try {
      systemResources = await getSystemResources();

      // Set recommended values
      threads = systemResources.cpu.recommended_threads;
      hashMb = systemResources.memory.recommended_hash_mb;
    } catch (err) {
      error = 'Failed to detect system resources. Using default values.';
      console.error(err);
    } finally {
      loading = false;
    }
  }

  function nextStep() {
    if (step < 4) {
      step++;
    }
  }

  function prevStep() {
    if (step > 1) {
      step--;
    }
  }

  async function completeSetup() {
    saving = true;
    error = null;

    try {
      await updateSettings({
        chess_com_username: username || null,
        stockfish_threads: threads.toString(),
        stockfish_hash_mb: hashMb.toString(),
        analysis_depth: depth.toString(),
        analysis_time_ms: timeMs.toString()
      });

      onComplete();
    } catch (err) {
      error = 'Failed to save settings: ' + err.message;
      console.error(err);
    } finally {
      saving = false;
    }
  }

  function handleSkip() {
    if (confirm('Skip setup? You can configure settings later.')) {
      onSkip();
    }
  }
</script>

<div class="wizard-overlay">
  <div class="wizard-container">
    <!-- Header -->
    <div class="wizard-header">
      <h2>Chess Analyzer Setup</h2>
      <div class="progress-bar">
        <div class="progress-fill" style="width: {(step / 4) * 100}%"></div>
      </div>
      <p class="step-indicator">Step {step} of 4</p>
    </div>

    <!-- Content -->
    <div class="wizard-content">
      {#if loading && step === 1}
        <div class="loading">
          <p>Detecting system resources...</p>
        </div>
      {:else if step === 1}
        <!-- Welcome Step -->
        <div class="step-content">
          <div class="welcome-icon">🎯</div>
          <h3>Welcome to Chess Analyzer!</h3>
          <p class="intro-text">
            Let's get you set up in just a few steps. We'll help you configure
            optimal settings for your system and connect to Chess.com.
          </p>

          <div class="features-list">
            <div class="feature">
              <span class="icon">♟️</span>
              <span>Import games from Chess.com</span>
            </div>
            <div class="feature">
              <span class="icon">🔍</span>
              <span>Analyze with Stockfish engine</span>
            </div>
            <div class="feature">
              <span class="icon">📊</span>
              <span>Track your performance</span>
            </div>
          </div>
        </div>
      {:else if step === 2}
        <!-- Username Step -->
        <div class="step-content">
          <div class="step-icon">👤</div>
          <h3>Chess.com Username</h3>
          <p class="step-description">
            Enter your Chess.com username to import and analyze your games.
            This is optional and can be added later.
          </p>

          <div class="form-group">
            <label for="username">Username (optional)</label>
            <input
              type="text"
              id="username"
              bind:value={username}
              placeholder="e.g., magnus, hikaru"
              class="username-input"
            />
            <p class="help-text">
              Your public games will be imported for analysis.
              You can leave this blank and add it later in Settings.
            </p>
          </div>
        </div>
      {:else if step === 3}
        <!-- System Resources Step -->
        <div class="step-content">
          <div class="step-icon">⚙️</div>
          <h3>Stockfish Configuration</h3>
          <p class="step-description">
            We've detected your system resources and suggest these settings
            for optimal performance.
          </p>

          {#if systemResources}
            <div class="resources-info">
              <div class="resource-item">
                <strong>CPU:</strong>
                {systemResources.cpu.logical_cores} cores available
              </div>
              <div class="resource-item">
                <strong>RAM:</strong>
                {Math.floor(systemResources.memory.available_mb / 1024)} GB available
              </div>
              <div class="resource-item">
                <strong>Stockfish:</strong>
                {systemResources.stockfish.valid ? '✅ Ready' : '❌ Not found'}
              </div>
            </div>
          {/if}

          <div class="settings-grid">
            <div class="setting-group">
              <label for="threads">
                Threads
                <span class="recommended">Recommended: {systemResources?.cpu.recommended_threads || 1}</span>
              </label>
              <input
                type="number"
                id="threads"
                bind:value={threads}
                min="1"
                max={systemResources?.cpu.logical_cores || 16}
              />
              <p class="setting-help">
                Number of CPU cores to use for analysis. Recommended to leave some cores free for your system.
              </p>
            </div>

            <div class="setting-group">
              <label for="hashMb">
                Hash Size (MB)
                <span class="recommended">Recommended: {systemResources?.memory.recommended_hash_mb || 128}</span>
              </label>
              <input
                type="number"
                id="hashMb"
                bind:value={hashMb}
                min="128"
                max={systemResources?.memory.available_mb || 2048}
                step="64"
              />
              <p class="setting-help">
                Memory allocated for Stockfish. More memory = faster analysis, but leave room for your system.
              </p>
            </div>

            <div class="setting-group">
              <label for="depth">Analysis Depth</label>
              <input
                type="number"
                id="depth"
                bind:value={depth}
                min="5"
                max="30"
              />
              <p class="setting-help">
                Search depth for analysis. Higher = more accurate but slower. 15 is a good balance.
              </p>
            </div>

            <div class="setting-group">
              <label for="timeMs">Analysis Time (ms)</label>
              <input
                type="number"
                id="timeMs"
                bind:value={timeMs}
                min="100"
                max="10000"
                step="100"
              />
              <p class="setting-help">
                Time spent analyzing each position. 1000ms (1 second) provides good accuracy quickly.
              </p>
            </div>
          </div>
        </div>
      {:else if step === 4}
        <!-- Confirmation Step -->
        <div class="step-content">
          <div class="step-icon">✓</div>
          <h3>Review & Confirm</h3>
          <p class="step-description">
            Please review your settings before completing setup.
          </p>

          <div class="summary">
            <div class="summary-item">
              <strong>Chess.com Username:</strong>
              <span>{username || 'Not set (can add later)'}</span>
            </div>
            <div class="summary-item">
              <strong>Stockfish Threads:</strong>
              <span>{threads}</span>
            </div>
            <div class="summary-item">
              <strong>Hash Size:</strong>
              <span>{hashMb} MB</span>
            </div>
            <div class="summary-item">
              <strong>Analysis Depth:</strong>
              <span>{depth}</span>
            </div>
            <div class="summary-item">
              <strong>Analysis Time:</strong>
              <span>{timeMs} ms</span>
            </div>
          </div>

          {#if error}
            <div class="error-message">
              {error}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <!-- Footer -->
    <div class="wizard-footer">
      <button class="btn-skip" on:click={handleSkip} disabled={saving}>
        Skip Setup
      </button>

      <div class="button-group">
        {#if step > 1}
          <button class="btn-secondary" on:click={prevStep} disabled={saving}>
            Back
          </button>
        {/if}

        {#if step < 4}
          <button class="btn-primary" on:click={nextStep}>
            Next
          </button>
        {:else}
          <button class="btn-primary" on:click={completeSetup} disabled={saving}>
            {saving ? 'Saving...' : 'Complete Setup'}
          </button>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .wizard-overlay {
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
    padding: 1rem;
  }

  .wizard-container {
    background: white;
    border-radius: 12px;
    width: 100%;
    max-width: 600px;
    max-height: 90vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
  }

  .wizard-header {
    padding: 2rem 2rem 1rem;
    border-bottom: 1px solid #e0e0e0;
  }

  .wizard-header h2 {
    margin: 0 0 1rem;
    color: #2c3e50;
    font-size: 1.75rem;
  }

  .progress-bar {
    height: 4px;
    background: #e0e0e0;
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }

  .progress-fill {
    height: 100%;
    background: #3498db;
    transition: width 0.3s ease;
  }

  .step-indicator {
    margin: 0;
    font-size: 0.875rem;
    color: #666;
  }

  .wizard-content {
    flex: 1;
    overflow-y: auto;
    padding: 2rem;
  }

  .step-content {
    animation: fadeIn 0.3s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .loading {
    text-align: center;
    padding: 3rem;
    color: #666;
  }

  .welcome-icon, .step-icon {
    font-size: 3rem;
    text-align: center;
    margin-bottom: 1rem;
  }

  .step-content h3 {
    margin: 0 0 0.5rem;
    color: #2c3e50;
    text-align: center;
  }

  .intro-text, .step-description {
    text-align: center;
    color: #666;
    margin-bottom: 2rem;
    line-height: 1.6;
  }

  .features-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    margin-top: 2rem;
  }

  .feature {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1rem;
    background: #f8f9fa;
    border-radius: 8px;
  }

  .feature .icon {
    font-size: 1.5rem;
  }

  .form-group {
    margin: 2rem 0;
  }

  .form-group label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #2c3e50;
  }

  .username-input {
    width: 100%;
    padding: 0.75rem;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 1rem;
    transition: border-color 0.2s;
  }

  .username-input:focus {
    outline: none;
    border-color: #3498db;
  }

  .help-text {
    margin-top: 0.5rem;
    font-size: 0.875rem;
    color: #666;
  }

  .resources-info {
    background: #e8f4f8;
    padding: 1rem;
    border-radius: 8px;
    margin-bottom: 1.5rem;
  }

  .resource-item {
    padding: 0.5rem 0;
    color: #2c3e50;
  }

  .settings-grid {
    display: grid;
    gap: 1.5rem;
  }

  .setting-group label {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
    font-weight: 500;
    color: #2c3e50;
  }

  .recommended {
    font-size: 0.875rem;
    color: #3498db;
    font-weight: normal;
  }

  .setting-group input[type="number"] {
    width: 100%;
    padding: 0.75rem;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 1rem;
  }

  .setting-group input[type="number"]:focus {
    outline: none;
    border-color: #3498db;
  }

  .setting-help {
    margin-top: 0.25rem;
    font-size: 0.8125rem;
    color: #666;
    line-height: 1.4;
  }

  .summary {
    background: #f8f9fa;
    padding: 1.5rem;
    border-radius: 8px;
    margin-top: 1rem;
  }

  .summary-item {
    display: flex;
    justify-content: space-between;
    padding: 0.75rem 0;
    border-bottom: 1px solid #e0e0e0;
  }

  .summary-item:last-child {
    border-bottom: none;
  }

  .error-message {
    margin-top: 1rem;
    padding: 1rem;
    background: #fee;
    border: 1px solid #fcc;
    border-radius: 8px;
    color: #c33;
  }

  .wizard-footer {
    padding: 1.5rem 2rem;
    border-top: 1px solid #e0e0e0;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .button-group {
    display: flex;
    gap: 0.75rem;
  }

  .btn-skip {
    padding: 0.75rem 1rem;
    background: transparent;
    border: none;
    color: #666;
    cursor: pointer;
    font-size: 0.9375rem;
  }

  .btn-skip:hover:not(:disabled) {
    color: #333;
    text-decoration: underline;
  }

  .btn-secondary {
    padding: 0.75rem 1.5rem;
    background: #95a5a6;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 1rem;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #7f8c8d;
  }

  .btn-primary {
    padding: 0.75rem 1.5rem;
    background: #3498db;
    color: white;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 1rem;
    font-weight: 500;
  }

  .btn-primary:hover:not(:disabled) {
    background: #2980b9;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
