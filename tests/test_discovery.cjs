const test = require('node:test');
const assert = require('node:assert/strict');
const { quality, select, preferences, matches } = require('../plexport/static/discovery.js');
const GB = 1024 ** 3;
const versions = [
  { title: 'Example.2160p.mkv', size: 12 * GB, seeders: 5, source: 'A' },
  { title: 'Example_1080p.mkv', size: 3 * GB, seeders: 20, source: 'B' },
  { title: 'Example.720p.mkv', size: GB, seeders: 0, source: 'A' },
  { title: 'Example.mkv', size: 0, seeders: 8, source: 'A' }
];

test('recognises common release names without treating years as image quality', () => {
  assert.equal(quality('Example_1080p_x265'), '1080');
  assert.equal(quality('Example 4K'), '2160');
  assert.equal(quality('Example 2026'), 'unknown');
});
test('combines quality, size and availability while preserving the chosen result index', () => {
  const rows = select(versions, { quality: '1080', maxGB: 4, minSeeders: 5 });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].index, 1);
  assert.equal(rows[0].title, versions[1].title);
});
test('hides unknown sizes only when a size limit is requested', () => {
  assert.equal(select(versions).length, 4);
  assert.deepEqual(select(versions, { maxGB: 2 }).map(row => row.index), [2]);
  assert.equal(select(versions, { minSeeders: 1 }).length, 3);
});
test('smallest-first puts unknown sizes last and source filters do not modify results', () => {
  assert.deepEqual(select(versions, { sort: 'smallest' }).map(row => row.index), [2, 1, 0, 3]);
  assert.deepEqual(select(versions, { source: 'B' }).map(row => row.index), [1]);
  assert.equal(versions[0].index, undefined);
});

test('saved choices restore the intended filters without losing the chosen release index', () => {
  const saved = preferences({ quality: '1080', max_gb: 4, min_seeders: 5, sort: 'smallest' });
  const rows = select(versions, { quality: saved.quality, maxGB: saved.max_gb, minSeeders: saved.min_seeders, sort: saved.sort });
  assert.deepEqual(rows.map(row => row.index), [1]);
  assert.deepEqual(preferences(), { quality: 'all', max_gb: 0, min_seeders: 0, sort: 'seeders' });
  assert.deepEqual(preferences(null), preferences());
  assert.deepEqual(preferences({ quality: 'bad', max_gb: true, min_seeders: -1, sort: '<script>' }), preferences());
});

test('wildcard download searches recognize release separators and respect one-character matches', () => {
  assert.equal(matches('Harry.Potter.and.the.Stone', 'harry*potter'), true);
  assert.equal(matches('Star Wars', 'star?wars'), true);
  assert.equal(matches('Star Great Wars', 'star?wars'), false);
  assert.equal(matches('Stargate', 'Star*'), true);
  assert.equal(matches('Film[HD].1080p', 'Film[HD]*'), true);
  assert.equal(matches('FilmHD.1080p', 'Film[HD]*'), false);
  assert.equal(matches('A Movie', ''), true);
  assert.equal(matches('Ａ Movie', 'a*movie'), true);
  assert.equal(matches('Nosferatu', 'FER'), true);
});

test('temporary all-results filters leave saved choices intact', () => {
  const saved = { quality: '1080', max_gb: 4, min_seeders: 5, sort: 'smallest' };
  assert.equal(select(versions).length, 4);
  assert.deepEqual(saved, { quality: '1080', max_gb: 4, min_seeders: 5, sort: 'smallest' });
  assert.deepEqual(preferences(saved), saved);
});
