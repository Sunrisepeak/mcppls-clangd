#!/usr/bin/env python3
"""Controls for the actual-edit applier; no engine or compiler required."""
import unittest
from completion_insertion import apply, offset, snippet


class CompletionInsertionTest(unittest.TestCase):
    def test_utf16_and_simultaneous_additional_edits(self):
        text = '// \U0001f642\nstd::ve value;\n'
        self.assertEqual(offset(text, {'line': 0, 'character': 5}), 4)
        item = {'insertTextFormat': 2, 'textEdit': {
            'range': {'start': {'line': 1, 'character': 5},
                      'end': {'line': 1, 'character': 7}},
            'newText': 'vector<${1:typename T}>$0'},
            'additionalTextEdits': [{'range': {'start': {'line': 0, 'character': 0},
                                               'end': {'line': 0, 'character': 0}},
                                    'newText': '#include <vector>\n'}]}
        self.assertEqual(apply(text, {'line': 1, 'character': 7}, item, {'1': 'int'}),
                         '#include <vector>\n// \U0001f642\nstd::vector<int> value;\n')

    def test_insert_replace_uses_replace_range(self):
        item = {'textEdit': {'insert': {'start': {'line': 0, 'character': 0},
                                       'end': {'line': 0, 'character': 2}},
                             'replace': {'start': {'line': 0, 'character': 0},
                                         'end': {'line': 0, 'character': 4}},
                             'newText': 'cli'}}
        self.assertEqual(apply('clxx;', {'line': 0, 'character': 2}, item, {}), 'cli;')

    def test_unknown_snippet_and_overlaps_fail_closed(self):
        with self.assertRaises(ValueError):
            snippet('${TM_FILENAME}', {})
        with self.assertRaises(ValueError):
            snippet('${1/(.*)/$1/}', {})
        same = {'start': {'line': 0, 'character': 0}, 'end': {'line': 0, 'character': 1}}
        with self.assertRaises(ValueError):
            apply('x', {'line': 0, 'character': 1}, {
                'textEdit': {'range': same, 'newText': 'y'},
                'additionalTextEdits': [{'range': same, 'newText': 'z'}]}, {})


if __name__ == '__main__':
    unittest.main()
