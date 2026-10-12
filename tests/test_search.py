import unittest

from plexport.search import MAX_TITLE_LENGTH, filter_results, prepare_query


class WildcardSearchTests(unittest.TestCase):
    def matches(self, query, title, **extra):
        result = {'title': title, **extra}
        return bool(filter_results([result], prepare_query(query)))

    def test_literal_query_keeps_provider_text_and_results_unchanged(self):
        query = '  Spider-Man (2020) [1080p]  '
        prepared = prepare_query(query)
        self.assertEqual(prepared, {'query': query.strip(), 'term': query.strip(), 'wildcard': False})
        results = [{'title': 'Completely different', 'link': 'magnet:example'}]
        self.assertIs(filter_results(results, prepared), results)

    def test_provider_receives_longest_useful_literal_fragment(self):
        cases = {'Harry*Potter': 'Potter', 'Star*': 'Star', '*Lord of the Rings*': 'Lord of the Rings',
                 '*Star?Wars*': 'Star', 'Spider-Man*': 'Spider Man', '*Amélie+[Café]*': 'Amélie Café',
                 '*Ｓｔａｒ*': 'Star', 'S01*': 'S01', '*A...[Very long punctuation]*End*': 'A Very long punctuation'}
        for query, term in cases.items():
            with self.subTest(query=query):
                self.assertEqual(prepare_query(query), {'query': query, 'term': term, 'wildcard': True})
                self.assertNotIn('*', term)
                self.assertNotIn('?', term)

    def test_wildcards_require_a_useful_fragment(self):
        for query in ('*', '**', '??', '*?*?', '*...*', '*a*b*', 'S?E*', '[?]*'):
            with self.subTest(query=query), self.assertRaises(ValueError):
                prepare_query(query)
        self.assertEqual(prepare_query('*a b*')['term'], 'a b')
        self.assertEqual(prepare_query('AB*')['term'], 'AB')

    def test_query_validation(self):
        for query in ('', ' ', 'a', None, 123, [], 'x' * 201):
            with self.subTest(query=query), self.assertRaises(ValueError):
                prepare_query(query)
        self.assertEqual(len(prepare_query('a' * 200)['term']), 200)
        self.assertEqual(prepare_query('  ab*  ')['query'], 'ab*')

    def test_star_matches_zero_or_many_characters_and_substrings(self):
        for title in ('HarryPotter', 'Harry Potter', 'Harry_and_the_Potter_2024', 'The Harry-Potter collection'):
            with self.subTest(title=title):
                self.assertTrue(self.matches('Harry*Potter', title))
        self.assertFalse(self.matches('Harry*Potter', 'Potter Harry'))
        self.assertFalse(self.matches('Harry*Potter', 'Harry meets Peter'))
        self.assertTrue(self.matches('Star*', 'Lego Star Wars'))
        self.assertTrue(self.matches('*Alien*', 'Aliens'))

    def test_question_mark_matches_exactly_one_normalized_character(self):
        for title in ('Star Wars', 'Star.Wars', 'Star_Wars', 'Star-Wars', 'StarXWars'):
            with self.subTest(title=title):
                self.assertTrue(self.matches('*Star?Wars*', title))
        self.assertFalse(self.matches('Star?Wars', 'StarWars'))
        self.assertFalse(self.matches('Star?Wars', 'StarXXWars'))
        self.assertTrue(self.matches('M?ssion*', 'Mission Impossible'))

    def test_unicode_normalization_casefold_and_release_separators(self):
        self.assertTrue(self.matches('*CAFÉ*', 'Le Cafe\u0301.2024.1080p'))
        self.assertTrue(self.matches('*ＳＴＡＲ*', 'star_wars'))
        self.assertTrue(self.matches('*straße*', 'Die STRASSE 2020'))
        self.assertTrue(self.matches('*Wall.E*', 'WALL-E.2008'))
        self.assertTrue(self.matches('*Spider_Man*', 'Spider-Man'))

    def test_other_metacharacters_remain_literal_without_regex_or_character_classes(self):
        for literal in ('[AB]', '(AB)', 'AB+', 'AB^', 'AB$', 'AB|CD', r'AB\CD', 'AB{2}'):
            with self.subTest(literal=literal):
                self.assertTrue(self.matches('*' + literal + '*', 'Film ' + literal + ' 2020'))
                self.assertFalse(self.matches('*' + literal + '*', 'AB CD 2020'))
        self.assertFalse(self.matches('*[AB]*', 'A film'))
        self.assertFalse(self.matches('*(AB)+*', 'ABABAB'))
        self.assertTrue(self.matches('*AB＊*', 'AB*'))
        self.assertFalse(self.matches('*AB＊*', 'ABCD'))

    def test_matches_library_or_release_title_without_inventing_year_metadata(self):
        self.assertTrue(self.matches('Example*2020', 'Example.2020.1080p', library_title='Example', year='2020'))
        self.assertTrue(self.matches('*Full Title*', 'Variant.1080p', library_title='A Full Title', year='2020'))
        self.assertFalse(self.matches('Example*2020', 'Example.1080p', library_title='Example', year='2020'))
        self.assertFalse(self.matches('*Title*', None, library_title=123))

    def test_filter_preserves_order_identity_and_download_selection_metadata(self):
        items = [{'title': 'Star.Wars', 'link': 'magnet:one', 'seeders': 10, 'size': 100, 'index': 2,
                  'year': '1977', 'source': 'A', 'season': '01', 'episode': '02'},
                 {'title': 'Other film', 'link': 'magnet:two', 'seeders': 20},
                 {'title': 'Star Trek', 'link': 'magnet:three', 'seeders': 5}]
        before = [dict(item) for item in items]
        filtered = filter_results(items, prepare_query('*Star*'))
        self.assertEqual(filtered, [items[0], items[2]])
        self.assertIs(filtered[0], items[0])
        self.assertIs(filtered[1], items[2])
        self.assertEqual(items, before)

    def test_repeated_wildcards_and_long_failed_patterns_do_not_use_regex(self):
        self.assertTrue(self.matches('*' * 90 + 'Film' + '*' * 90, 'A Film 2020'))
        self.assertFalse(self.matches('AB*' + 'a*' * 60 + 'Z', 'AB' + 'a' * 2000))

    def test_pathological_titles_are_skipped_but_another_valid_title_still_matches(self):
        huge = 'Film' + 'x' * MAX_TITLE_LENGTH
        expanded = 'Film' + '\ufb03' * 1000  # NFKC expands each ligature to three characters.
        self.assertFalse(self.matches('*Film*', huge, library_title=huge))
        self.assertFalse(self.matches('*Film*', expanded, library_title=expanded))
        self.assertTrue(self.matches('*Film*', huge, library_title='Film'))
        self.assertTrue(self.matches('*Film*', 'Film', library_title=huge))
        result = [{'title': huge}]
        self.assertIs(filter_results(result, prepare_query('Film')), result)


if __name__ == '__main__':
    unittest.main()
