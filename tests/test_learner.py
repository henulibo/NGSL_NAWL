"""Official learner definitions must be clean and match the word lists."""
import json
import runpy
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
learner = runpy.run_path(str(ROOT / 'vocab-data' / 'learner.py'))
IDS = ['NGSL:account']


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
