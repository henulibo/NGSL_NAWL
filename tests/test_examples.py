"""Every Cambridge sense must reach the popup with a Chinese meaning and a translated example."""
import runpy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
merge = runpy.run_path(str(ROOT / 'vocab-data' / 'merge_examples.py'))
URL = 'https://dictionary.cambridge.org/dictionary/english-chinese-simplified/'


def sense(sense_id, examples, **extra):
    return {'id': sense_id, 'pos': 'n.', 'en': 'a test sense', 'zh': '测试', 'examples': examples, **extra}


def assemble(senses, added_senses=None, added_examples=None, core=(), url=URL + 'test'):
    cambridge = {'NGSL:test': {'url': url, 'senses': senses}}
    return merge['assemble'](['NGSL:test'], cambridge, added_senses or {}, added_examples or {},
                             {'NGSL:test': 'an official definition'}, set(core))


class ExampleCorpusTests(unittest.TestCase):
    def test_full_sentences_are_preferred_and_shared_examples_stored_once(self):
        corpus, own = assemble([
            sense('ID_1', [['a tall tree', '一棵高树'], ['The tree is tall.', '这棵树很高。'], ['It grew.', '它长大了。']],
                  level='B1'),
            sense('ID_2', [['The tree is tall.', '这棵树很高。']], level='A2'),
        ])
        entry = corpus['NGSL:test']
        self.assertEqual(entry['examples'], ['The tree is tall.', 'It grew.'])
        self.assertEqual([s['examples'] for s in entry['senses']], [[0, 1], [0]])
        self.assertEqual(entry['translations'], ['这棵树很高。', '它长大了。'])
        self.assertEqual(entry['level'], 'A2')
        self.assertEqual(own, 0)
        self.assertNotIn('url', entry)

    def test_sense_without_translated_example_uses_and_flags_an_added_one(self):
        corpus, own = assemble([sense('ID_1', [['Untranslated.', '']])],
                               added_examples={'ID_1': ['Written here.', '本页补写。']}, core={'ID_1'})
        entry = corpus['NGSL:test']
        self.assertEqual(entry['examples'], ['Written here.'])
        self.assertEqual(entry['own'], [0])
        self.assertTrue(entry['senses'][0]['core'])
        self.assertEqual(own, 1)

    def test_missing_examples_and_unknown_added_examples_block_output(self):
        with self.assertRaisesRegex(ValueError, 'Sense without example'):
            assemble([sense('ID_1', [])])
        with self.assertRaisesRegex(ValueError, 'Missing Chinese translation'):
            assemble([sense('ID_1', [])], added_examples={'ID_1': ['Written here.', 'not chinese']})
        with self.assertRaisesRegex(ValueError, 'unknown senses'):
            assemble([sense('ID_1', [['Fine.', '好。']])], added_examples={'ID_9': ['x', '中文']})
        with self.assertRaisesRegex(ValueError, 'Incomplete sense'):
            assemble([sense('ID_1', [['Fine.', '好。']], zh='')])

    def test_added_senses_follow_cambridge_and_redirected_pages_keep_their_url(self):
        added = {'NGSL:test': [sense('own:test-1', [['Our own.', '本页的。']])]}
        corpus, _ = assemble([sense('ID_1', [['Fine.', '好。']])], added_senses=added, url=URL + 'other')
        entry = corpus['NGSL:test']
        self.assertEqual(entry['own'], [1])
        self.assertEqual(entry['url'], URL + 'other')
        self.assertEqual(len(entry['senses']), 2)


if __name__ == '__main__':
    unittest.main()
