const test = require('node:test');
const assert = require('node:assert/strict');
const { isActive, hasImports, matchesFilter, counts } = require('../plexport/static/jobs.js');

test('imported tasks stay visible after a failed scan or stopping the downloader', () => {
  for (const state of ['scan_pending', 'error', 'stopped', 'done']) {
    const job = { state, files_imported: ['/media/Example.mkv'] };
    assert.equal(hasImports(job), true);
    assert.equal(matchesFilter(job, 'imported'), true);
  }
  assert.equal(matchesFilter({ state: 'done', files_imported: [] }, 'imported'), false);
  assert.equal(hasImports({ state: 'done' }), false);
});

test('the overview and tabs use the same active classification', () => {
  for (const state of ['queued', 'downloading', 'importing', 'scan_pending']) {
    assert.equal(isActive({ state }), true);
    assert.equal(matchesFilter({ state }, 'active'), true);
  }
  for (const state of ['done', 'error', 'stopped']) assert.equal(isActive({ state }), false);
  assert.equal(matchesFilter({ state: 'stopped' }, 'stopped'), true);
  assert.equal(matchesFilter({ state: 'error' }, 'error'), true);
});

test('all tasks remain reachable and tab counts allow imports that need attention', () => {
  const jobs = [
    { state: 'downloading' },
    { state: 'error', files_imported: ['/media/Needs-scan.mkv'] },
    { state: 'stopped', files_imported: ['/media/Stopped.mkv'] },
    { state: 'done', files_imported: ['/media/Done.mkv'] }
  ];
  assert.deepEqual(counts(jobs), { all: 4, active: 1, error: 1, imported: 3, stopped: 1 });
  assert.equal(jobs.every(job => matchesFilter(job, 'all')), true);
});
