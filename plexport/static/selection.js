/* File identities come from the downloader; never infer file indices from a name. */
(function (root) {
  'use strict';
  function selectionPayload(snapshot, values) {
    if (!snapshot || !snapshot.metadata_token || !Array.isArray(snapshot.files)) throw Error('Controleer de bestandslijst opnieuw.');
    const indices = values.map(value => {
      if (typeof value !== 'number' && !(typeof value === 'string' && /^\d+$/.test(value))) throw Error('Ongeldige bestandskeuze.');
      const index = Number(value);
      if (!Number.isSafeInteger(index) || index < 0) throw Error('Ongeldige bestandskeuze.');
      return index;
    });
    const selected = [...new Set(indices)].map(index => {
      const file = snapshot.files.find(file => file.index === index);
      if (!file || !file.selectable) throw Error('De bestandslijst is veranderd. Controleer je keuze opnieuw.');
      return file;
    });
    if (!selected.some(file => file.kind === 'video')) throw Error('Kies minstens één ondersteunde video.');
    return { id: snapshot.id, metadata_token: snapshot.metadata_token, files: selected.map(file => file.index) };
  }
  function fileDescription(file) {
    if (file.reason === 'sample') return 'Voorbeeldbestand · wordt niet geïmporteerd';
    if (file.reason === 'extra') return 'Extra · controleer de aflevering en kies dit bestand alleen bewust';
    if (file.kind === 'subtitle') return 'Ondertitel · apart kiezen bij de bijbehorende video';
    if (file.kind !== 'video') return 'Dit bestand wordt niet geïmporteerd';
    if (file.episodes?.length && Number.isInteger(file.season)) {
      return 'Seizoen ' + file.season + ' · ' + (file.episodes.length > 1 ? 'afleveringen ' : 'aflevering ') + file.episodes.join(', ')
        + (file.episodes.length > 1 ? ' · één videobestand' : '');
    }
    return 'Video · afleveringsnummer niet herkend; controleer de bestandsnaam';
  }
  const api = { selectionPayload, fileDescription };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.PlexPortSelection = api;
})(typeof window === 'undefined' ? globalThis : window);
