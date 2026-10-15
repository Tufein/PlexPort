/* Shared by the browser and the small, dependency-free filter tests. */
(function (root) {
  function quality(title) {
    const text = String(title || '').replace(/_/g, ' ');
    if (/(?:\b2160p\b|\b4k\b)/i.test(text)) return '2160';
    if (/\b1080[pi]\b/i.test(text)) return '1080';
    if (/\b720p\b/i.test(text)) return '720';
    if (/\b(?:480p|576p|sd)\b/i.test(text)) return 'sd';
    return 'unknown';
  }

  function select(results, filters = {}) {
    const limit = Number(filters.maxGB) > 0 ? Number(filters.maxGB) * 1024 ** 3 : 0;
    const minimum = Math.max(0, Number(filters.minSeeders) || 0);
    const rows = results.map((result, index) => ({ ...result, index, quality: quality(result.title) }))
      .filter(result => (!filters.quality || filters.quality === 'all' || result.quality === filters.quality)
        && (!filters.source || filters.source === 'all' || result.source === filters.source)
        && Number(result.seeders || 0) >= minimum
        && (!limit || (Number(result.size) > 0 && Number(result.size) <= limit)));
    rows.sort((a, b) => {
      if (filters.sort === 'smallest') return (Number(a.size) || Infinity) - (Number(b.size) || Infinity) || a.index - b.index;
      if (filters.sort === 'title') return String(a.title).localeCompare(String(b.title), 'nl') || a.index - b.index;
      return Number(b.seeders || 0) - Number(a.seeders || 0) || a.index - b.index;
    });
    return rows;
  }

  function recommend(versions) {
    const qualityRank = { '2160':4, '1080':3, '720':2, sd:1, unknown:0 };
    const seeders = row => Number.isFinite(Number(row.seeders)) ? Math.max(0, Number(row.seeders)) : 0;
    const size = row => Number.isFinite(Number(row.size)) && Number(row.size) > 0 ? Number(row.size) : Infinity;
    const rank = row => qualityRank[row.quality] ?? qualityRank[quality(row.title)];
    const compare = (a, b) => seeders(b) - seeders(a) || rank(b) - rank(a)
      || size(a) - size(b) || a.index - b.index;
    // Only consider the already filtered versions. Return the original row so
    // the existing confirmation dialog opens its exact provider result/link.
    return versions.reduce((best, row) => {
      if (!row || !Number.isSafeInteger(row.index) || row.index < 0) return best;
      return !best || compare(row, best) < 0 ? row : best;
    }, null);
  }

  function preferences(value = {}) {
    value = value && typeof value === 'object' ? value : {};
    return {
      quality: ['all', '1080', '720', '2160', 'sd', 'unknown'].includes(value.quality) ? value.quality : 'all',
      max_gb: [0, 2, 4, 10, 25].includes(value.max_gb) ? value.max_gb : 0,
      min_seeders: [0, 1, 5, 20].includes(value.min_seeders) ? value.min_seeders : 0,
      sort: ['seeders', 'smallest', 'title'].includes(value.sort) ? value.sort : 'seeders'
    };
  }

  function readPreferences(values = {}) {
    values = values && typeof values === 'object' ? values : {};
    const number = value => typeof value === 'string' || typeof value === 'number' ? Number(value) : NaN;
    return preferences({ quality: values.quality, max_gb: number(values.size), min_seeders: number(values.seeders), sort: values.sort });
  }

  function readFilters(values = {}) {
    const saved = readPreferences(values);
    return { quality: saved.quality, maxGB: saved.max_gb, minSeeders: saved.min_seeders,
      source: typeof values?.source === 'string' && values.source ? values.source : 'all', sort: saved.sort };
  }

  function writeFilters(value) {
    const saved = preferences(value);
    return { quality: saved.quality, size: String(saved.max_gb), seeders: String(saved.min_seeders), source: 'all', sort: saved.sort };
  }

  function group(rows, searchKind) {
    const groups = [], identities = new Map();
    const number = value => typeof value === 'number' && Number.isInteger(value) && value >= 0 && value <= 999 ? value
      : typeof value === 'string' && /^\d{1,3}$/.test(value) ? Number(value) : null;
    for (const row of rows) {
      const title = typeof row.library_title === 'string' ? row.library_title.trim() : '';
      const kind = row.kind === undefined ? searchKind : row.kind;
      const year = typeof row.year === 'string' || typeof row.year === 'number' ? String(row.year).trim() : '';
      const season = number(row.season), episode = number(row.episode);
      let reliable = title && /^(18|19|20|21)\d{2}$/.test(year) && ['movie', 'tv'].includes(kind);
      if (kind === 'tv') {
        reliable = reliable && season !== null && episode !== null;
        const codes = [...String(row.title || '').matchAll(/(?:^|[^a-z0-9])S(\d{1,3})[ ._-]*E(\d{1,3})/gi)];
        // An explicit first episode must not turn a multi-episode release into a single-episode group.
        if (codes.length > 1 || codes.some(code => Number(code[1]) !== season || Number(code[2]) !== episode
          || /^(?:\d|[ ._-]*E\d|\s*[-+&]\s*E?\d{1,3}(?![a-z0-9])|\s+(?:to|and)\s+E?\d{1,3}(?![a-z0-9]))/i.test(String(row.title).slice(code.index + code[0].length)))) reliable = false;
      }
      const identity = reliable ? JSON.stringify([kind, title.normalize('NFKC').toLocaleLowerCase('nl').replace(/\s+/g, ' '), year,
        ...(kind === 'tv' ? [season, episode] : [])]) : null;
      let entry = identity === null ? null : identities.get(identity);
      if (!entry) {
        entry = { title: title || row.title || '', year, kind,
          season: reliable && kind === 'tv' ? season : '', episode: reliable && kind === 'tv' ? episode : '', versions: [] };
        groups.push(entry);
        if (identity !== null) identities.set(identity, entry);
      }
      // Keep the selected row and its original input index: grouping never chooses or deduplicates a release.
      entry.versions.push(row);
    }
    return groups;
  }

  function matches(title, query) {
    const normalize = value => String(value || '').normalize('NFKC').toLocaleLowerCase('nl').replace(/[._-]/g, ' ').replace(/\s+/g, ' ').trim();
    const text = normalize(title), pattern = normalize(query);
    if (!/[?*]/.test(pattern)) return text.includes(pattern);
    const tokens = Array.from('*' + pattern + '*');
    let previous = tokens.map(() => false);
    previous.unshift(true);
    for (let i = 1; i <= tokens.length; i++) previous[i] = tokens[i - 1] === '*' && previous[i - 1];
    for (const character of Array.from(text)) {
      const current = new Array(tokens.length + 1).fill(false);
      for (let i = 1; i <= tokens.length; i++) {
        current[i] = tokens[i - 1] === '*' ? current[i - 1] || previous[i] : previous[i - 1] && (tokens[i - 1] === '?' || tokens[i - 1] === character);
      }
      previous = current;
    }
    return previous[tokens.length];
  }

  const api = { quality, select, recommend, preferences, readPreferences, readFilters, writeFilters, group, matches };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PlexPortDiscovery = api;
})(typeof window === 'undefined' ? globalThis : window);
