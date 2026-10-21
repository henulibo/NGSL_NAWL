"""Core-sense markers must stay tied to an official definition and a live Cambridge sense."""
import json
import runpy
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
learner = runpy.run_path(str(ROOT / 'vocab-data' / 'learner.py'))
IDS = ['NGSL:account']
CAMBRIDGE = {'NGSL:account': {'senses': [{'id': 'ID_1'}, {'id': 'ID_2'}]}}


def write(folder, name, entries):
    path = Path(folder) / name
    path.write_text(json.dumps({'version': 2, 'entries': entries}, ensure_ascii=False))
    return path


class LearnerDataTests(unittest.TestCase):
    def test_definition_whitespace_is_normalised(self):
        with tempfile.TemporaryDirectory() as folder:
            path = write(folder, 'defs.json', {'NGSL:account': {'definition': ' a  bank\naccount '}})
            self.assertEqual(learner['load_definitions'](path, IDS), {'NGSL:account': 'a bank account'})

    def test_spreadsheet_errors_and_unknown_words_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            bad = write(folder, 'bad.json', {'NGSL:account': {'definition': '#NAME?'}})
            with self.assertRaisesRegex(ValueError, 'Invalid learner definition'):
                learner['load_definitions'](bad, IDS)
            unknown = write(folder, 'unknown.json', {'NGSL:ghost': {'definition': 'x'}})
            with self.assertRaisesRegex(ValueError, 'unknown words'):
                learner['load_definitions'](unknown, IDS)

    def test_core_senses_point_at_live_cambridge_or_added_senses(self):
        defs = {'NGSL:account': 'arrangement with a bank'}
        added = {'NGSL:account': [{'id': 'own:account-1'}]}
        with tempfile.TemporaryDirectory() as folder:
            good = write(folder, 'core.json', {'NGSL:account': ['ID_2', 'own:account-1']})
            self.assertEqual(learner['load_core_senses'](good, CAMBRIDGE, added, defs), {'ID_2', 'own:account-1'})
            stale = write(folder, 'stale.json', {'NGSL:account': ['ID_9']})
            with self.assertRaisesRegex(ValueError, 'Stale core sense'):
                learner['load_core_senses'](stale, CAMBRIDGE, added, defs)
            empty = write(folder, 'empty.json', {'NGSL:account': []})
            with self.assertRaisesRegex(ValueError, 'Empty core sense'):
                learner['load_core_senses'](empty, CAMBRIDGE, added, defs)
            with self.assertRaisesRegex(ValueError, 'official definition'):
                learner['load_core_senses'](good, CAMBRIDGE, added, {})

    def test_public_data_covers_almost_every_word_without_private_dictionaries(self):
        data = ROOT / 'vocab-data'
        study = json.loads((data / 'study-data.json').read_text())
        ids = [name + ':' + row['word'] for name, rows in study.items() for row in rows]
        defs = learner['load_definitions'](data / 'learner-definitions.json', ids)
        self.assertGreater(len(defs), 3700)
        self.assertEqual(len(ids), 3818)
        for rows in study.values():
            for row in rows:
                self.assertEqual(set(row), {'word', 'rank', 'day'})


if __name__ == '__main__':
    unittest.main()
