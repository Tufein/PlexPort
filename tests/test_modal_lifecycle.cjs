/* Exercise the actual async modal handlers with a small DOM surface and deferred API calls. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const selection = require('../plexport/static/selection.js');
const jobs = require('../plexport/static/jobs.js');

const source = fs.readFileSync(path.join(__dirname, '../plexport/static/app.js'), 'utf8');
const start = source.indexOf('function closeFiles(){');
const end = source.indexOf("document.addEventListener('click',event=>{", start);
assert.ok(start >= 0 && end > start, 'file modal handlers must be present');
const fileHandlers = source.slice(start, end);

function fixture() {
  const nodes = new Map(), requests = [], toasts = [], timers = new Map();
  let timerId = 0;
  class Element {
    constructor(id) {
      this.id = id; this.dataset = {}; this.disabled = false; this.open = false;
      this.listeners = new Map(); this.inputs = []; this._text = ''; this._html = '';
    }
    addEventListener(name, handler) {
      const handlers = this.listeners.get(name) || [];
      handlers.push(handler); this.listeners.set(name, handlers);
    }
    dispatch(name) {
      const event = { defaultPrevented:false, preventDefault(){ this.defaultPrevented = true; } };
      const results = (this.listeners.get(name) || []).map(handler => handler(event));
      return { event, complete:Promise.all(results) };
    }
    showModal() { this.open = true; }
    close() { this.open = false; this.dispatch('close'); }
    set textContent(value) { this._text = String(value); this._html = ''; this.inputs = []; }
    get textContent() { return this._text; }
    set innerHTML(value) {
      this._html = value; this._text = '';
      this.inputs = [...value.matchAll(/<input\b([^>]*)>/g)].map(([, attributes]) => ({
        value:attributes.match(/\bvalue="([^"]*)"/)?.[1],
        disabled:/\bdisabled\b/.test(attributes), checked:/\bchecked\b/.test(attributes),
      }));
    }
    get innerHTML() { return this._html; }
    querySelectorAll(selector) {
      if (this.id === '#files-form') {
        const buttons = ['#files-close', '#files-cancel', '#files-reload', '#files-submit'].map(node);
        return selector === 'button' ? buttons : [...buttons, ...node('#files-list').inputs];
      }
      if (selector === 'input:checked') return this.inputs.filter(input => input.checked);
      return this.inputs;
    }
  }
  function node(id) {
    if (!nodes.has(id)) nodes.set(id, new Element(id));
    return nodes.get(id);
  }
  const context = {
    $:node, status:{jobs:[{id:'A',title:'Series A'}, {id:'B',title:'Series B'}]},
    api:(route, body) => new Promise((resolve, reject) => requests.push({route, body, resolve, reject})),
    PlexPortSelection:selection, PlexPortJobs:jobs,
    bytes:String, esc:value => String(value ?? '').replace(/[&<>"']/g, char => `&#${char.charCodeAt(0)};`),
    toast:(message, error) => toasts.push({message, error}), refresh:async() => {},
    setTimeout:callback => { timers.set(++timerId, callback); return timerId; },
    clearTimeout:id => timers.delete(id),
    icon:() => '', artwork:() => '', activityLabel:() => 'Downloaden', activityNote:() => '', eta:() => '',
  };
  vm.createContext(context);
  vm.runInContext('let filesSnapshot=null, filesTimer, filesLoading=null, filesGeneration=0, filesSubmitting=null;\n'
    + fileHandlers, context);
  const next = route => {
    const request = requests.find(item => item.route === route && !item.taken);
    assert.ok(request, `expected pending ${route} request`);
    request.taken = true;
    return request;
  };
  const submit = () => node('#files-form').dispatch('submit').complete;
  return {context, node, requests, toasts, timers, next, submit};
}

function snapshot(id, changes = {}) {
  return {id, state:'awaiting_selection', metadata_token:`metadata-${id}`, error:'', files:[
    {index:8, name:`${id}.S01E01.mkv`, size:100, kind:'video', selected:true, selectable:true,
      progress:0, season:1, episodes:[1]},
    {index:9, name:'sample.mkv', size:10, kind:'video', selected:false, selectable:false, progress:0},
  ], ...changes};
}
const tick = () => new Promise(resolve => setImmediate(resolve));
async function openReady(app, id='A', changes={}) {
  app.context.openFiles(id);
  app.next('files').resolve(snapshot(id, changes));
  await tick();
}

test('closing A and opening B starts B immediately and ignores the late A snapshot', async () => {
  const app = fixture();
  app.context.openFiles('A'); const a = app.next('files');
  app.context.closeFiles(); app.context.openFiles('B'); const b = app.next('files');
  b.resolve(snapshot('B')); await tick();
  a.resolve(snapshot('A')); await tick();
  assert.equal(app.node('#files-title').textContent, 'Series B');
  assert.match(app.node('#files-list').innerHTML, /B\.S01E01/);
  assert.doesNotMatch(app.node('#files-list').innerHTML, /A\.S01E01/);
  assert.equal(app.node('#files-submit').disabled, false);
});

test('late A failure cannot replace the reopened modal error or disable its fresh load', async () => {
  const app = fixture();
  app.context.openFiles('A'); const a = app.next('files');
  app.context.closeFiles(); app.context.openFiles('B'); const b = app.next('files');
  a.reject(Error('Old task connection failed')); await tick();
  assert.equal(app.node('#files-error').textContent, '');
  b.resolve(snapshot('B')); await tick();
  assert.equal(app.node('#files-submit').disabled, false);
});

test('while saving, close buttons and Escape are locked and another submit is ignored', async () => {
  const app = fixture(); await openReady(app);
  const saving = app.submit(); const request = app.next('select');
  assert.equal(app.node('#files-reload').disabled, true);
  assert.equal(app.node('#files-close').disabled, true);
  assert.ok(app.node('#files-list').inputs.every(input => input.disabled));
  app.context.closeFiles();
  assert.equal(app.node('#files-dialog').open, true);
  assert.equal(app.node('#files-dialog').dispatch('cancel').event.defaultPrevented, true);
  await app.submit();
  assert.equal(app.requests.filter(item => item.route === 'select').length, 1);
  request.resolve({state:'committed'}); await saving;
  assert.equal(app.node('#files-dialog').open, false);
});

test('reopening after a successful save restores close, reload and new selection controls', async () => {
  const app = fixture(); await openReady(app);
  const saving = app.submit(); app.next('select').resolve({state:'committed'}); await saving;
  app.context.openFiles('B');
  for (const id of ['#files-close', '#files-cancel', '#files-reload']) assert.equal(app.node(id).disabled, false);
  assert.equal(app.node('#files-submit').disabled, true);
  app.next('files').resolve(snapshot('B')); await tick();
  assert.equal(app.node('#files-submit').disabled, false);
  assert.equal(app.node('#files-list').inputs[0].disabled, false);
  assert.equal(app.node('#files-list').inputs[1].disabled, true);
});

test('failed saving restores the original disabled status of unsupported files', async () => {
  const app = fixture(); await openReady(app);
  const saving = app.submit(); app.next('select').reject(Error('Downloader unavailable')); await saving;
  assert.equal(app.node('#files-dialog').open, true);
  assert.equal(app.node('#files-list').inputs[0].disabled, false);
  assert.equal(app.node('#files-list').inputs[1].disabled, true);
  assert.match(app.node('#files-error').textContent, /Downloader unavailable/);
});

test('a reload blocks saving until the fresh snapshot arrives', async () => {
  const app = fixture(); await openReady(app);
  const reloading = app.context.loadFiles(); const request = app.next('files');
  assert.equal(app.node('#files-submit').disabled, true);
  await app.submit();
  assert.equal(app.requests.filter(item => item.route === 'select').length, 0);
  request.resolve(snapshot('A')); await reloading;
  const saving = app.submit(); const selectRequest = app.next('select');
  await app.context.loadFiles();
  assert.equal(app.requests.filter(item => item.route === 'files').length, 2);
  assert.equal(app.node('#files-submit').disabled, true);
  selectRequest.resolve({state:'committed'}); await saving;
});

test('metadata changes clear the old choice and retain an explanation after reloading', async () => {
  const app = fixture(); await openReady(app);
  const saving = app.submit();
  const conflict = Error('De bestandslijst is veranderd. Kies opnieuw.'); conflict.report = {code:'metadata_changed'};
  app.next('select').reject(conflict); await tick();
  app.next('files').resolve(snapshot('A', {metadata_token:'new-metadata', files:[
    {index:42,name:'A.S01E02.mkv',size:100,kind:'video',selected:false,selectable:true,progress:0},
  ]})); await saving;
  assert.equal(app.node('#files-list').inputs[0].value, '42');
  assert.equal(app.node('#files-list').inputs[0].checked, false);
  assert.match(app.node('#files-error').textContent, /veranderd|opnieuw/i);
  assert.equal(app.node('#files-close').disabled, false);
});

test('a saved selection with failed resume shows a warning and a persistent task error', async () => {
  const app = fixture(); await openReady(app);
  const saving = app.submit();
  app.next('select').resolve({state:'stopped',selection_error:'Hervatten is niet gelukt.'}); await saving;
  assert.equal(app.toasts.length, 1);
  assert.equal(app.toasts[0].error, true);
  assert.match(app.toasts[0].message, /hervatten is niet gelukt/i);
  assert.doesNotMatch(app.toasts[0].message, /download gaat verder/i);
  const rowStart = source.indexOf('function jobRow(job){');
  vm.runInContext(source.slice(rowStart, source.indexOf('\nfunction renderStatus', rowStart)), app.context);
  const row = app.context.jobRow({id:'A',title:'A',kind:'tv',year:'2020',state:'stopped',source:'Fixture',created:0,
    progress:0,selection_requested:true,selection_state:'committed',selection_error:'Hervatten is niet gelukt.'});
  assert.match(row, /job-error[^>]*>Hervatten is niet gelukt\./);
  assert.match(row, /data-action="resume"/);
});

test('a stopped task does not claim that saving automatically resumed it', async () => {
  const app = fixture(); await openReady(app);
  const saving = app.submit(); app.next('select').resolve({state:'stopped'}); await saving;
  assert.match(app.toasts[0].message, /blijft gestopt/);
  assert.doesNotMatch(app.toasts[0].message, /download gaat verder/i);
});
