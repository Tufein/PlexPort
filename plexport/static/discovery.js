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

  const api = { quality, select };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PlexPortDiscovery = api;
})(typeof window === 'undefined' ? globalThis : window);
