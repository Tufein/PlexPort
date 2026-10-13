/* Shared classifications for the download overview and its dependency-free tests. */
(function (root) {
  'use strict';
  function isActive(job) {
    return !['done', 'error', 'stopped'].includes(job.state);
  }
  function hasImports(job) {
    return Array.isArray(job.files_imported) && job.files_imported.length > 0;
  }
  function matchesFilter(job, filter) {
    switch (filter) {
      case 'active': return isActive(job);
      case 'error': return job.state === 'error';
      case 'stopped': return job.state === 'stopped';
      case 'imported': return hasImports(job);
      default: return true;
    }
  }
  function counts(jobs) {
    return Object.fromEntries(['all', 'active', 'error', 'imported', 'stopped']
      .map(filter => [filter, jobs.filter(job => matchesFilter(job, filter)).length]));
  }
  const api = { isActive, hasImports, matchesFilter, counts };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PlexPortJobs = api;
})(typeof window === 'undefined' ? globalThis : window);
