"""Catch missing inflection meanings and gaps in the example dictionary."""
import csv
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LookupDataTests(unittest.TestCase):
    def test_dictionary_keeps_surface_meanings_and_resolves_inflections(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'dictionary.csv'
            with source.open('w', newline='') as file:
                writer = csv.DictWriter(file, fieldnames=['word', 'phonetic', 'translation', 'exchange'])
                writer.writeheader()
                writer.writerows([
                    dict(word='go', phonetic='ɡəʊ', translation='v. 去', exchange='p:went/d:gone'),
                    dict(word='went', phonetic='went', translation='go的过去式', exchange='0:go/1:p'),
                    dict(word='child', phonetic='tʃaɪld', translation='n. 孩子', exchange='s:children'),
                    dict(word='children', phonetic='', translation='pl. 孩子们', exchange='0:child/1:s'),
                    dict(word='researcher', phonetic='', translation='n. 研究员', exchange='s:researchers'),
                    dict(word='eight', phonetic='', translation='num. 八', exchange=''),
                    dict(word='hour', phonetic='', translation='n. 小时', exchange='s:hours'),
                    dict(word='epistemology', phonetic='', translation='n. 认识论', exchange=''),
                ])
            examples = root / 'examples.json'
            examples.write_text(json.dumps({'sample': {'examples': ["Went researchers children’s eight-hour epistemology mysteryword."]}}))
            target = root / 'lookup.json'
            result = subprocess.run(['python3', str(ROOT / 'vocab-data/prepare_lookup.py'), str(source), str(examples), str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(target.read_text())
            self.assertEqual(data['went']['meaning'], 'go的过去式')
            self.assertEqual(data['went']['lemma'], 'go')
            self.assertEqual(data['went']['baseMeaning'], 'v. 去')
            self.assertEqual(data['researchers']['lemma'], 'researcher')
            self.assertEqual(data["children's"]['baseMeaning'], 'n. 孩子')
            # Native double-click can select just the base/part of a compound.
            self.assertEqual(data.get('child', {}).get('meaning'), 'n. 孩子')
            self.assertEqual(data.get('hour', {}).get('meaning'), 'n. 小时')
            self.assertEqual([part['word'] for part in data['eight-hour']['components']], ['eight', 'hour'])
            self.assertEqual(data['epistemology']['meaning'], 'n. 认识论')
            self.assertNotIn('mysteryword', data)


if __name__ == '__main__':
    unittest.main()
