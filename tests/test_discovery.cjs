const test = require('node:test');
const assert = require('node:assert/strict');
const { quality, select, preferences, readPreferences, readFilters, writeFilters, group, matches } = require('../plexport/static/discovery.js');
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

test('form filter mapping shares saved choices while keeping the source temporary', () => {
  const values = { quality: '1080', size: '4', seeders: '5', source: 'B', sort: 'smallest' };
  const saved = readPreferences(values);
  assert.deepEqual(saved, { quality: '1080', max_gb: 4, min_seeders: 5, sort: 'smallest' });
  assert.deepEqual(readFilters(values), { quality: '1080', maxGB: 4, minSeeders: 5, source: 'B', sort: 'smallest' });
  assert.deepEqual(writeFilters(saved), { ...values, source: 'all' });
  assert.deepEqual(select(versions, readFilters(values)).map(row => row.index), [1]);
  assert.deepEqual(values, { quality: '1080', size: '4', seeders: '5', source: 'B', sort: 'smallest' });
  assert.deepEqual(writeFilters(), { quality: 'all', size: '0', seeders: '0', source: 'all', sort: 'seeders' });
  assert.deepEqual(readPreferences(null), preferences());
  assert.deepEqual(readFilters(null), readFilters());
  assert.deepEqual(readPreferences({ quality: 'bad', size: true, seeders: 'wrong', sort: '<script>' }), preferences());
});

test('title groups retain every release and its original selection index after sorting and filtering', () => {
  const results = [
    { title: 'Nosferatu.2024.2160p', library_title: 'Nosferatu', year: '2024', source: 'A', link: 'magnet:one', size: 12 * GB, seeders: 8 },
    { title: 'Nosferatu.2024.1080p', library_title: ' NOSFERATU ', year: 2024, source: 'B', link: 'magnet:two', size: 3 * GB, seeders: 20 },
    { title: 'Other.2024.1080p', library_title: 'Other', year: '2024', source: 'A', link: 'magnet:three', size: GB, seeders: 10 },
    { title: 'Nosferatu.2024.720p', library_title: 'Nosferatu', year: '2024', source: 'A', link: 'magnet:four', size: GB, seeders: 0 }
  ];
  const original = structuredClone(results);
  const selected = select(results, { minSeeders: 1 });
  const groups = group(selected, 'movie');
  assert.deepEqual(groups.map(entry => entry.title), ['NOSFERATU', 'Other']);
  assert.deepEqual(groups.map(entry => entry.versions.map(row => row.index)), [[1, 0], [2]]);
  assert.equal(groups[0].versions[0], selected[0]);
  for (const entry of groups) for (const row of entry.versions) {
    const { index, quality: rowQuality, ...release } = row;
    assert.deepEqual(release, results[index]);
    assert.equal(rowQuality, quality(results[index].title));
  }
  assert.deepEqual(results, original);
  assert.deepEqual(group(select(results, { maxGB: 4, source: 'B' }), 'movie')[0].versions.map(row => row.index), [1]);
});

test('remakes and movies or series with the same name remain separate', () => {
  const base = { title: 'Example.S01E01.1080p', library_title: 'Example', year: '2024', season: 1, episode: 1 };
  const rows = select([
    { ...base, kind: 'movie' },
    { ...base, kind: 'movie', year: '1922' },
    { ...base, kind: 'tv' },
    { ...base, kind: 'tv', year: '1922' }
  ]);
  assert.equal(group(rows, 'movie').length, 4);
});

test('series groups match only the same known season and episode', () => {
  const base = { library_title: 'A Show', year: '2020', kind: 'tv', season: '01', episode: '01' };
  const rows = select([
    { ...base, title: 'A.Show.S01E01.1080p' },
    { ...base, title: 'A.Show.S01E01-720p', season: 1, episode: 1 },
    { ...base, title: 'A.Show.S01E02.1080p', episode: '02' },
    { ...base, title: 'A.Show.S02E01.1080p', season: '02' }
  ]);
  assert.deepEqual(group(rows, 'tv').map(entry => entry.versions.map(row => row.index)), [[0, 1], [2], [3]]);
});

test('unknown or invalid title identities stay independent without dropping duplicate releases', () => {
  const movie = { title: 'A.Movie.1080p', library_title: 'A Movie', year: '2024' };
  const uncertain = [
    { ...movie, library_title: undefined },
    { ...movie, library_title: ' ' },
    { ...movie, library_title: 42 },
    { ...movie, year: '' },
    { ...movie, year: true },
    { ...movie, year: '2024?' },
    { ...movie, year: '0000' },
    { ...movie, kind: 'unknown' }
  ];
  const rows = select(uncertain.flatMap(row => [{ ...row }, { ...row }]));
  assert.equal(group(rows, 'movie').length, rows.length);
  assert.equal(group(select([movie, { ...movie }])).length, 2);
  assert.equal(group(select([movie, { ...movie }]), 'movie')[0].versions.length, 2);
  assert.deepEqual(group([], 'movie'), []);
});

test('ambiguous series releases and conflicting episode metadata do not merge', () => {
  const base = { title: 'Show.S01E01.1080p', library_title: 'Show', year: '2024', season: 1, episode: 1 };
  const uncertain = [
    { ...base, season: '' },
    { ...base, episode: undefined },
    { ...base, episode: -1 },
    { ...base, episode: true },
    { ...base, season: 1000 },
    { ...base, episode: 2 },
    { ...base, title: 'Show.S01E01E02.1080p' },
    { ...base, title: 'Show_S01E01E02_1080p' },
    { ...base, title: 'Show.S01E01-E02.1080p' },
    { ...base, title: 'Show.S01E01-02.1080p' },
    { ...base, title: 'Show.S01E01.S01E02.1080p' },
    { ...base, title: 'Show.S01E01+E02.1080p' },
    { ...base, title: 'Show.S01E01 to 02.1080p' },
    { ...base, title: 'Show.S01E0100.1080p', episode: 10 }
  ];
  const rows = select(uncertain.flatMap(row => [{ ...row }, { ...row }]));
  assert.equal(group(rows, 'tv').length, rows.length);
});

test('ambiguous episode headings omit the provider first-episode guess without altering the chosen release', () => {
  const release = { title: 'Show.S01E01-E02.1080p', library_title: 'Show', year: '2024',
    season: '01', episode: '01', link: 'magnet:one', source: 'A' };
  const selected = select([release, { ...release, link: 'magnet:two' }]);
  const groups = group(selected, 'tv');
  assert.equal(groups.length, 2);
  for (const [index, entry] of groups.entries()) {
    assert.equal(entry.season, '');
    assert.equal(entry.episode, '');
    assert.equal(entry.versions[0], selected[index]);
    assert.equal(entry.versions[0].season, '01');
    assert.equal(entry.versions[0].episode, '01');
    assert.equal(entry.versions[0].index, index);
  }
  assert.equal(release.season, '01');
  assert.equal(release.episode, '01');
});
