(function () {
  'use strict';
  const key = 'plexport-theme';
  const options = ['system', 'light', 'dark'];
  const system = window.matchMedia('(prefers-color-scheme: dark)');
  let preference = 'system';
  try {
    const saved = localStorage.getItem(key);
    if (options.includes(saved)) preference = saved;
  } catch (_) { /* Theme still works when browser storage is unavailable. */ }
  function apply() {
    const dark = preference === 'dark' || (preference === 'system' && system.matches);
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    const color = document.querySelector('meta[name="theme-color"]');
    if (color) color.content = dark ? '#10141d' : '#f4f6fa';
    const control = document.getElementById('theme-choice');
    if (control) control.value = preference;
  }
  window.PlexPortTheme = {
    get preference() { return preference; },
    set(value) {
      if (!options.includes(value)) return;
      preference = value;
      try { localStorage.setItem(key, value); } catch (_) {}
      apply();
    }
  };
  system.addEventListener('change', apply);
  window.addEventListener('storage', function (event) {
    if (event.key === key) {
      preference = options.includes(event.newValue) ? event.newValue : 'system';
      apply();
    }
  });
  apply();
})();
