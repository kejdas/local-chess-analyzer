export function applyTheme(theme) {
  try {
    const isDark = theme === 'dark';
    const isLight = theme === 'light';
    document.body.classList.toggle('theme-dark', isDark);
    document.body.classList.toggle('theme-light', isLight);
  } catch (e) {
    // no-op in non-browser contexts
  }
}


