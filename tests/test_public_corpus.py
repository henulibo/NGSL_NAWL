"""The default build must need only the openly licensed data files."""
import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
assemble = runpy.run_path(str(ROOT / 'vocab-data/public_corpus.py'))['assemble_public']


class PublicCorpusTests(unittest.TestCase):
    def test_missing_entries_and_spelling_variants_are_explicit(self):
        study = {'NGSL': [
            {'word': 'color', 'rank': 1, 'day': 1},
            {'word': 'missing', 'rank': 2, 'day': 1},
        ]}
        entries, corpus = assemble(study, {'NGSL:color': 'a visual quality'}, {
            'colour': {'meaning': 'n. 颜色', 'ipa': 'test'},
        })
        self.assertEqual(entries['NGSL'][0]['meaning'], 'n. 颜色')
        self.assertEqual(entries['NGSL'][0]['ipa'], 'test')
        self.assertEqual(corpus['NGSL:color']['senses'][0]['guide'], '参考词条：colour')
        self.assertEqual(corpus['NGSL:missing']['source'], 'unavailable')
        self.assertEqual(entries['NGSL'][1]['meaning'], '暂无离线中文释义')
        self.assertNotIn('meaning', study['NGSL'][0])

    def test_public_data_has_no_invented_examples_levels_or_core_markers(self):
        data = ROOT / 'vocab-data'
        study = json.loads((data / 'study-data.json').read_text())
        defs = json.loads((data / 'learner-definitions.json').read_text())['entries']
        _, corpus = assemble(study, {k: v['definition'] for k, v in defs.items()},
                             json.loads((data / 'lookup-data.json').read_text()))
        self.assertEqual(len(corpus), 3818)
        for entry in corpus.values():
            self.assertEqual(entry['examples'], [])
            self.assertEqual(entry['translations'], [])
            for sense in entry['senses']:
                self.assertNotIn('level', sense)
                self.assertNotIn('core', sense)

    def test_duplicate_words_and_unknown_definitions_are_rejected(self):
        row = {'word': 'test', 'rank': 1, 'day': 1}
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            assemble({'NGSL': [row, row]}, {}, {})
        with self.assertRaisesRegex(ValueError, 'unknown words'):
            assemble({'NGSL': [row]}, {'NGSL:other': 'x'}, {})
