const test = require('node:test');
const assert = require('node:assert/strict');
const { quality, select } = require('../plexport/static/discovery.js');
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
