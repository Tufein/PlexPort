'use strict';
const form = document.getElementById('login-form');
const password = document.getElementById('login-password');
const toggle = document.getElementById('password-toggle');
const submit = document.getElementById('login-submit');
const error = document.getElementById('login-error');
const theme = document.getElementById('theme-choice');
theme.value = window.PlexPortTheme.preference;
theme.addEventListener('change', () => window.PlexPortTheme.set(theme.value));
toggle.addEventListener('click', () => {
  const show = password.type === 'password';
  password.type = show ? 'text' : 'password';
  toggle.textContent = show ? 'Verbergen' : 'Tonen';
  toggle.setAttribute('aria-pressed', String(show));
});
form.addEventListener('submit', async event => {
  event.preventDefault();
  error.hidden = true;
  submit.disabled = true;
  submit.querySelector('span').textContent = 'Even aanmelden…';
  try {
    const response = await fetch('/auth/login', {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-PlexPort': '1'},
      body: JSON.stringify({username: form.elements.username.value.trim(), password: password.value})
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Aanmelden lukt nu niet. Probeer opnieuw.');
    password.value = '';
    window.location.replace('/' + window.location.hash);
  } catch (exception) {
    error.textContent = exception.message === 'Failed to fetch' ? 'Je server is niet bereikbaar. Controleer je verbinding en probeer opnieuw.' : exception.message;
    error.hidden = false;
  } finally {
    submit.disabled = false;
    submit.querySelector('span').textContent = 'Aanmelden';
  }
});
