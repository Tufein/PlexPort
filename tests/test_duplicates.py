import copy
import unittest

from plexport.duplicates import title_conflicts


def movie(**changes):
    return {'id': 'existing', 'title': 'The Thing', 'kind': 'movie', 'year': '1982',
            'season': None, 'episode': None, 'state': 'downloading', 'files_imported': [], **changes}


def episode(**changes):
    return movie(**{'title': 'Example Show', 'kind': 'tv', 'year': '2020', 'season': 1, 'episode': 2, **changes})


class TitleConflictTests(unittest.TestCase):
    def match(self, existing=None, candidate=None):
        matches = title_conflicts([existing or movie()], candidate or movie(id='candidate'))
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_movie_uses_confirmed_library_title_and_known_year(self):
        match = self.match()
        self.assertEqual((match['certainty'], match['reason']), ('definite', 'same_title'))
        self.assertEqual((match['id'], match['title'], match['year']), ('existing', 'The Thing', '1982'))

    def test_unicode_nfkc_casefold_and_whitespace_normalization(self):
        cases = [('  THE\tTHING\n', 'The Thing'), ('Ｔｈｅ　Ｔｈｉｎｇ', 'the thing'),
                 ('CAFÉ', 'Cafe\u0301'), ('STRASSE', 'Straße')]
        for old, new in cases:
            with self.subTest(old=old, new=new):
                self.assertEqual(self.match(movie(title=old), movie(title=new))['certainty'], 'definite')

    def test_different_known_years_are_distinct_films_even_with_loose_titles(self):
        for title in ('The Thing', 'The-Thing'):
            with self.subTest(title=title):
                self.assertEqual(title_conflicts([movie(title=title)], movie(year='2011')), [])

    def test_missing_year_in_either_direction_is_only_a_caution(self):
        for old_year, new_year in [('', '1982'), ('1982', ''), (None, None), ('', '')]:
            with self.subTest(old=old_year, new=new_year):
                match = self.match(movie(year=old_year), movie(year=new_year))
                self.assertEqual((match['certainty'], match['reason']), ('possible', 'missing_year'))

    def test_numeric_and_padded_metadata_normalizes_without_guessing_years(self):
        match = self.match(movie(year=1982), movie(year=' 1982 '))
        self.assertEqual((match['certainty'], match['year']), ('definite', '1982'))
        for value in ('82', '1982 remake', [], True, 1982.0, '２９８２'):
            with self.subTest(value=value):
                self.assertEqual(self.match(movie(year=value))['certainty'], 'possible')

    def test_punctuation_variants_are_possible_and_never_certain(self):
        for old, new in [('Spider-Man', 'Spider Man'), ('WALL.E', 'Wall E'), ('Hello, World', 'Hello World')]:
            with self.subTest(old=old, new=new):
                match = self.match(movie(title=old), movie(title=new))
                self.assertEqual((match['certainty'], match['reason']), ('possible', 'ambiguous_title'))

    def test_release_like_confirmed_titles_never_claim_certain_identity(self):
        for title in ('Example 1080p', 'Example WEB-DL', 'Example S01E02', 'Example BluRay'):
            with self.subTest(title=title):
                match = self.match(movie(title=title), movie(title=title))
                self.assertEqual((match['certainty'], match['reason']), ('possible', 'ambiguous_title'))

    def test_does_not_strip_years_release_tags_accents_or_match_prefixes(self):
        for title in ('The Thing 1982', 'The Thing (1982)', 'The Thing 1080p', 'The Things', 'Thing',
                      'The Thing Part Two', 'The.Th ing', 'The Thíng'):
            with self.subTest(title=title):
                self.assertEqual(title_conflicts([movie()], movie(title=title)), [])
        self.assertEqual(title_conflicts([movie(title='A+B')], movie(title='A B')), [])

    def test_film_and_series_are_never_conflated(self):
        self.assertEqual(title_conflicts([movie()], movie(kind='tv', season=1, episode=2)), [])
        self.assertEqual(title_conflicts([movie(kind='tv')], movie()), [])

    def test_tv_requires_same_known_year_season_and_episode_for_definite(self):
        match = self.match(episode(), episode(id='candidate', season='01', episode='002'))
        self.assertEqual((match['certainty'], match['season'], match['episode']), ('definite', 1, 2))
        self.assertEqual(self.match(episode(season=0, episode=0), episode(season='0', episode='0'))['certainty'],
                         'definite')

    def test_other_tv_episodes_seasons_and_series_years_do_not_match(self):
        for candidate in (episode(episode=3), episode(season=2), episode(year='2021'),
                          episode(season=None, episode=3), episode(season=2, episode=None)):
            with self.subTest(candidate=candidate):
                self.assertEqual(title_conflicts([episode()], candidate), [])

    def test_tv_missing_year_never_claims_certain_episode_identity(self):
        match = self.match(episode(year=''), episode())
        self.assertEqual((match['certainty'], match['reason']), ('possible', 'missing_year'))

    def test_tv_season_pack_has_separate_explanation_in_both_directions(self):
        pack = episode(episode=None)
        for existing, candidate in ((pack, episode()), (episode(), pack), (pack, pack)):
            with self.subTest(existing=existing, candidate=candidate):
                match = self.match(existing, candidate)
                self.assertEqual((match['certainty'], match['reason']), ('possible', 'season_pack'))
        self.assertEqual(title_conflicts([pack], episode(season=2, episode=None)), [])

    def test_missing_tv_identity_is_only_possible_not_a_season_pack_claim(self):
        for existing, candidate in ((episode(season=None), episode()), (episode(), episode(season=None)),
                                    (episode(season=None, episode=None), episode()),
                                    (episode(), episode(season=None, episode=None))):
            with self.subTest(existing=existing, candidate=candidate):
                match = self.match(existing, candidate)
                self.assertEqual((match['certainty'], match['reason']), ('possible', 'missing_episode'))

    def test_imported_status_comes_from_recorded_imports_even_after_stop_or_error(self):
        for state in ('queued', 'downloading', 'importing', 'scan_pending', 'done', 'stopped', 'error'):
            for files in ([], ['/private/media/The Thing.mkv']):
                with self.subTest(state=state, files=files):
                    match = self.match(movie(state=state, files_imported=files))
                    self.assertEqual(match['state'], state)
                    self.assertEqual(match['imported'], bool(files))
        for files in (None, 'not-a-recorded-list', {}, True):
            with self.subTest(files=files):
                self.assertFalse(self.match(movie(state='done', files_imported=files))['imported'])

    def test_only_current_history_is_consulted_and_input_order_preserved(self):
        jobs = [movie(id='stopped', state='stopped'), movie(id='other', title='Another title'),
                movie(id='imported', state='done', files_imported=['private'])]
        self.assertEqual([item['id'] for item in title_conflicts(iter(jobs), movie())], ['stopped', 'imported'])
        self.assertEqual(title_conflicts([], movie()), [])

    def test_match_allowlist_never_exposes_paths_connections_or_torrent_identity(self):
        existing = movie(config={'password': 'secret'}, link='private-url', torrent_fingerprint='private-hash',
                         metainfo='private-binary', remote_dir='/private/downloads',
                         files_imported=['/private/library/file.mkv'], error='private-endpoint')
        match = self.match(existing)
        self.assertEqual(set(match), {'id', 'title', 'kind', 'year', 'season', 'episode', 'state',
                                      'imported', 'certainty', 'reason'})
        self.assertNotIn('private', repr(match))

    def test_history_candidate_and_nested_values_are_not_mutated(self):
        jobs = [episode(title='  EXAMPLE SHOW  ', files_imported=['/library/file.mkv'], config={'secret': ['x']})]
        candidate = episode(title='Example Show', season='01', episode='02')
        before = copy.deepcopy((jobs, candidate))
        title_conflicts(jobs, candidate)
        self.assertEqual((jobs, candidate), before)

    def test_invalid_candidate_and_unusable_history_are_ignored(self):
        for candidate in (None, [], 'title', {}, movie(kind='other'), movie(title=None), movie(title='...'),
                          movie(title='x' * 513)):
            with self.subTest(candidate=candidate):
                self.assertEqual(title_conflicts([movie()], candidate), [])
        for invalid in (None, [], 'title', {}, movie(id=''), movie(id=None), movie(kind='other'),
                        movie(title=None), movie(title='...'), movie(title='x' * 513)):
            with self.subTest(invalid=invalid):
                self.assertEqual(title_conflicts([invalid, movie()], movie()), title_conflicts([movie()], movie()))

    def test_nfkc_expansion_is_bounded_and_special_characters_are_not_patterns(self):
        huge = '\ufb03' * 180  # Normalizes to 540 characters.
        self.assertEqual(title_conflicts([movie(title=huge)], movie(title=huge)), [])
        self.assertEqual(title_conflicts([movie(title='The .* Thing')], movie(title='The Fantastic Thing')), [])


if __name__ == '__main__':
    unittest.main()
