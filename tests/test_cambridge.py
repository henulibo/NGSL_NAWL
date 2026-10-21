"""Cambridge pages must yield only the headword's own senses, with clean example text."""
import runpy
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
cambridge = runpy.run_path(str(ROOT / 'vocab-data' / 'cambridge.py'))
URL = 'https://dictionary.cambridge.org/dictionary/english-chinese-simplified/'


def block(sense_id, en, zh, level='', examples=(), phrase=''):
    egs = ''.join(f'<div class="examp dexamp"><span class="eg deg">{eg}</span>'
                  f'<span class="trans dtrans">{tr}</span></div>' for eg, tr in examples)
    body = (f'<div class="def-block ddef_block" data-wl-senseid="{sense_id}"><div class="ddef_h">'
            f'<span class="def-info ddef-info">' + (f'<span class="epp-xref dxref">{level}</span>' if level else '') +
            f'</span><div class="def ddef_d db">{en}:</div></div>'
            f'<div class="def-body ddef_b"><span class="trans dtrans">{zh}</span>{egs}</div></div>')
    if phrase:
        return (f'<div class="phrase-block dphrase-block"><span class="phrase-title dphrase-title">{phrase}</span>'
                f'<div class="phrase-body">{body}</div></div>')
    return body


def entry(headword, pos, *blocks, guide=''):
    guideword = f'<span class="guideword dsense_gw">({guide})</span>' if guide else ''
    return (f'<div class="pr entry-body__el"><div class="pos-header dpos-h"><span class="hw dhw">{headword}</span>'
            f'<span class="pos dpos">{pos}</span><span class="uk dpron-i"><span class="ipa dipa">ipa-{headword}</span></span></div>'
            f'<div class="pr dsense">{guideword}' + ''.join(blocks) + '</div></div>')


def page(word, *entries):
    return URL + word + '\n<html><body>' + ''.join(entries) + '</body></html>'


class CambridgeParseTests(unittest.TestCase):
    def test_senses_keep_level_guide_and_translated_examples(self):
        result = cambridge['parse_page']('tree', page('tree', entry('tree', 'noun', block(
            'ID_1', 'a tall plant', '树', 'A1', [('a <strong class="cl">pine</strong>tree', '一棵松树')]), guide='plant')))
        self.assertEqual(result['ipa'], {'uk': 'ipa-tree'})
        [sense] = result['senses']
        self.assertEqual((sense['id'], sense['pos'], sense['guide'], sense['en'], sense['zh'], sense['level']),
                         ('ID_1', 'n.', 'Plant', 'a tall plant', '树', 'A1'))
        self.assertEqual(sense['examples'], [['a pine tree', '一棵松树']])

    def test_other_headwords_acronyms_abbreviations_and_untranslated_senses_are_dropped(self):
        result = cambridge['parse_page']('it', page('it',
            entry('it', 'pronoun', block('ID_1', 'the thing', '它')),
            entry('IT', 'noun', block('ID_2', 'information technology', '信息技术')),
            entry('its', 'determiner', block('ID_3', 'belonging to it', '它的')),
            entry('it', 'noun', block('ID_4', 'abbreviation for something', '缩写'), block('ID_5', 'no translation', ''))))
        self.assertEqual([s['id'] for s in result['senses']], ['ID_1'])

    def test_month_names_do_not_take_the_lowercase_word(self):
        result = cambridge['parse_page']('May', page('may',
            entry('may', 'modal verb', block('ID_1', 'possibility', '可能')),
            entry('May', 'noun', block('ID_2', 'the fifth month', '五月'))))
        self.assertEqual([s['id'] for s in result['senses']], ['ID_2'])

    def test_phrases_are_only_used_when_the_word_has_no_ordinary_sense(self):
        phrase = block('ID_9', 'to remove something', '去除', phrase='get rid of something')
        only_phrase = cambridge['parse_page']('rid', page('rid', entry('rid', 'adjective', phrase)))
        self.assertEqual([(s['id'], s['guide']) for s in only_phrase['senses']], [('ID_9', 'get rid of something')])
        mixed = cambridge['parse_page']('lot', page('lot', entry('lot', 'noun', block('ID_1', 'a group', '一批'), phrase)))
        self.assertEqual([s['id'] for s in mixed['senses']], ['ID_1'])

    def test_known_run_together_example_words_are_separated(self):
        result = cambridge['parse_page']('supplement', page('supplement', entry('supplement', 'noun', block(
            'ID_1', 'an addition', '补充', examples=[('teaching eveningnight classes', '教夜校')]))))
        self.assertEqual(result['senses'][0]['examples'][0][0], 'teaching evening/night classes')

    def test_us_spellings_keep_their_own_page_but_not_british_phonetics(self):
        result = cambridge['parse_page']('harbor', page('harbour', entry('harbour', 'noun', block('ID_1', 'a port', '港口'))))
        self.assertEqual([s['id'] for s in result['senses']], ['ID_1'])
        self.assertEqual(result['ipa'], {})
        self.assertEqual(cambridge['slug']('harbor'), 'harbour')


if __name__ == '__main__':
    unittest.main()
