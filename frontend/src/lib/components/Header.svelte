<script>
  import { location } from 'svelte-spa-router';
  import active from 'svelte-spa-router/active';
</script>

<header>
  <div class="container">
    <h1 class="logo">Chess Analyzer</h1>
    <nav>
      <a href="#/" use:active>Home</a>
      <a href="#/settings" use:active>Settings</a>
      <a href="#/sync" use:active>Sync</a>
      <a href="#/games" use:active>Games</a>
    </nav>
  </div>
</header>

<style>
  header {
    background: #2c3e50;
    color: white;
    padding: 1rem 0;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .logo {
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }

  nav {
    display: flex;
    gap: 2rem;
  }

  nav a {
    color: white;
    text-decoration: none;
    padding: 0.5rem 1rem;
    border-radius: 4px;
    transition: background 0.2s;
  }

  nav a:hover {
    background: rgba(255,255,255,0.1);
  }

  nav :global(a.active) {
    background: rgba(255,255,255,0.2);
    font-weight: 600;
  }
</style>
