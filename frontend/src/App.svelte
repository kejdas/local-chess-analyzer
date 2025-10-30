<script>
  import { onMount } from 'svelte';
  import Router from 'svelte-spa-router';
  import Header from './lib/components/Header.svelte';
  import Home from './lib/components/Home.svelte';
  import Settings from './lib/components/Settings.svelte';
  import Sync from './lib/components/Sync.svelte';
  import Games from './lib/components/Games.svelte';
  import SetupWizard from './lib/components/SetupWizard.svelte';
  import { getSettings } from './lib/api/client.js';

  const routes = {
    '/': Home,
    '/settings': Settings,
    '/sync': Sync,
    '/games': Games,
  };

  let showWizard = false;
  let checkingSetup = true;

  onMount(async () => {
    try {
      const settings = await getSettings();

      // Show wizard if chess_com_username is not set (null or empty)
      if (!settings.chess_com_username || settings.chess_com_username === 'null') {
        showWizard = true;
      }
    } catch (error) {
      console.error('Failed to check settings:', error);
    } finally {
      checkingSetup = false;
    }
  });

  function handleWizardComplete() {
    showWizard = false;
  }

  function handleWizardSkip() {
    showWizard = false;
  }
</script>

<div class="app">
  {#if checkingSetup}
    <div class="checking-setup">
      <p>Loading...</p>
    </div>
  {:else}
    {#if showWizard}
      <SetupWizard
        onComplete={handleWizardComplete}
        onSkip={handleWizardSkip}
      />
    {/if}

    <Header />
    <main>
      <Router {routes} />
    </main>
  {/if}
</div>

<style>
  .app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  main {
    flex: 1;
    background: #f5f5f5;
  }

  .checking-setup {
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f5f5f5;
  }

  .checking-setup p {
    font-size: 1.25rem;
    color: #666;
  }
</style>
