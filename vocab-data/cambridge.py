"""Parse saved Cambridge English-Chinese (Simplified) pages into per-sense study data.

Usage: python cambridge.py <folder of word.html.gz pages>  ->  cambridge-senses.json
Each saved page starts with the final URL on its own line, followed by the HTML.
"""
import gzip
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

from lxml import html

ROOT = Path(__file__).resolve().parent
LEVELS = {'A1', 'A2', 'B1', 'B2', 'C1', 'C2'}
POS = {'noun': 'n.', 'verb': 'v.', 'adjective': 'adj.', 'adverb': 'adv.', 'preposition': 'prep.',
       'conjunction': 'conj.', 'pronoun': 'pron.', 'determiner': 'det.', 'exclamation': 'int.',
       'number': 'num.', 'ordinal number': 'num.', 'auxiliary verb': 'aux.', 'modal verb': 'modal',
       'predeterminer': 'det.', 'prefix': 'prefix', 'suffix': 'suffix', 'abbreviation': 'abbr.',
       'phrasal verb': 'phr. v.', 'combining form': 'comb.', 'symbol': 'symbol'}


# NGSL/NAWL use some US spellings or inflected forms that the English-Chinese
# dictionary files under another headword: word -> (page slug, accepted headwords).
ALIASES = {
    'toward': ('toward', {'towards'}), 'behavior': ('behavior', {'behaviour'}),
    'neighbor': ('neighbor', {'neighbour'}), 'neighborhood': ('neighborhood', {'neighbourhood'}),
    'okay': ('okay', {'ok'}), 'ought': ('ought', {'ought to'}), 'criteria': ('criteria', {'criterion'}),
    'fulfill': ('fulfill', {'fulfil'}), 'whilst': ('whilst', {'while'}), 'catalog': ('catalog', {'catalogue'}),
    'harbor': ('harbour', {'harbour'}), 'dialog': ('dialogue', {'dialogue'}),
    'behavioral': ('behavioural', {'behavioural'}), 'tumor': ('tumour', {'tumour'}),
    'amino': ('amino-acid', {'amino acid'}), 'orient': ('orientate', {'orientate'}),
    'amongst': ('amongst', {'among'}), 'afterward': ('afterward', {'afterwards'}),
    'aluminum': ('aluminum', {'aluminium'}), 'kilometer': ('kilometer', {'kilometre'}),
    'millimeter': ('millimeter', {'millimetre'}), 'statistics': ('statistic', {'statistic', 'statistics'}),
    'ethics': ('ethic', {'ethic', 'ethics'}), 'descendent': ('descendant', {'descendant'}),
    'non': ('non', {'non-'}), 'pre': ('pre', {'pre-'}), 'multi': ('multi', {'multi-'}),
}
# The English-Chinese dictionary has no entry for these; senses-extra.json supplies them.
RESPELLING = re.compile(r'(?:(?:US|UK|American|Australian)[\w ]*? spelling of|non-standard form of) ([a-z][a-z -]*?)(?: UK| mainly UK)?$')
NOT_IN_CAMBRIDGE = {'letter', 'binary', 'quintillion'}
# Words run together in the dictionary's own example text.
EXAMPLE_FIXES = {
    'thegrey': 'the grey', 'Turish': 'Turkish', "Idon't": "I don't", 'movingaway': 'moving away',
    'shopand': 'shop and', 'teacherteacher': 'teacher', 'Yangzte': 'Yangtze', 'friendlyto': 'friendly to',
    'whiteline': 'white line', 'eveningnight': 'evening/night',
}
EXAMPLE_TYPO = re.compile('|'.join(map(re.escape, EXAMPLE_FIXES)))
# Phrase senses kept alongside the ordinary ones because they carry the word's
# main meaning ("a lot of", "can afford"): word -> [(page slug, sense id, pos)].
# Phrases shown as a panel on the word's page are translated on their own page.
PHRASE_SENSES = {
    'able': [('be-able-to-do', 'ID_00000070_01', 'adj.')],
    'afford': [('can-afford', 'ID_00000517_01', 'v.')],
    'depend': [('depend-on-upon', 'ID_00008492_03', 'phr. v.'), ('depend-on-upon', 'ID_00008492_04', 'phr. v.')],
    'ease': [('at-ease', 'ID_00010015_09', 'n.')],
    'figure': [('figure-out', 'ID_00011839_14', 'phr. v.')],
    'foundation': [('foundations', 'ID_00012648_04', 'n.')],
    'ground': [('ground', 'ID_00014246_01', 'n.')],
    'lot': [('lot-of', 'ID_00019047_01', 'n.'), ('lot', 'ID_00019047_02', 'adv.')],
    'onset': [('onset-of', 'ID_00022397_01', 'n.')],
    'sake': [('sake', 'ID_00027927_01', 'n.'), ('sake', 'ID_00027927_02', 'n.')],
    'scale': [('scale', 'ID_00028189_19', 'n.')],
}


def slug(word):
    return ALIASES.get(word.lower(), (word.lower(), None))[0]


def cls(name):
    return 'contains(concat(" ",normalize-space(@class)," ")," ' + name + ' ")'


def text(node):
    return ' '.join(''.join(node.itertext()).split())


def first(nodes):
    return text(nodes[0]) if nodes else ''


def space_collocations(tree):
    # Bold collocations ("a <strong>petrol</strong>pump") rely on page styling for the gap.
    for node in tree.xpath('//*[' + cls('cl') + ']'):
        if node.tail and node.tail[0].isalnum():
            node.tail = ' ' + node.tail


def parse_page(word, raw):
    url, body = raw.split('\n', 1)
    tree = html.fromstring(body)
    space_collocations(tree)
    if word.lower() in NOT_IN_CAMBRIDGE:
        return {'url': url, 'ipa': {}, 'senses': []}
    accepted = ALIASES.get(word.lower(), (None, {word.lower()}))[1]
    # Prefer ordinary senses; some words only appear inside phrases ("get rid of",
    # "relatively speaking") or phrasal verbs ("refer to"), so fall back to those.
    for mode in ('plain', 'phrases', 'page'):
        result = collect(tree, word, accepted, mode)
        if result['senses']:
            break
    result['url'] = url
    if word.lower() in ALIASES:
        result['ipa'] = {}  # the page headword is another spelling; keep the list's own phonetics
    return result


def collect(tree, word, accepted, mode):
    ipa, senses = {}, []
    entries = tree.xpath('//*[' + cls('entry-body__el') + ']') if mode != 'page' else [tree]
    for entry in entries:
        header = entry.xpath('.//*[' + cls('pos-header') + ']')
        if mode != 'page':
            if not header:
                continue
            headword = first(header[0].xpath('.//*[' + cls('hw') + ']'))
            if headword.lower() not in accepted:
                continue
            # Month and day names ("May", "March") must not pick up the lowercase verb or modal.
            if word.istitle() and len(word) > 1 and headword != word:
                continue
            # Acronym homographs (IT, OR, ADD, SAD...) are different words from the lowercase headword.
            if len(headword) > 1 and headword.isupper() and headword.lower() != 'ok':
                continue
        elif not header:
            header = [entry]
        pos_names = [text(p) for p in header[0].xpath('.//*[' + cls('pos') + ']')]
        pos = ' / '.join(dict.fromkeys(POS.get(p, p) for p in pos_names if p))
        for region in ('uk', 'us'):
            found = header[0].xpath('.//*[' + cls(region) + ']//*[' + cls('ipa') + ']')
            if found and region not in ipa:
                ipa[region] = text(found[0])
        for block in entry.xpath('.//*[' + cls('def-block') + ']'):
            phrase = block.xpath('ancestor::*[' + cls('phrase-block') + ' or ' + cls('idiom-block') + ' or ' + cls('pv-block') + ' or ' + cls('phrase-di-block') + ']')
            if phrase and mode == 'plain':
                continue
            body = block.xpath('./*[' + cls('def-body') + ']')
            zh = first(body[0].xpath('./*[' + cls('trans') + ']')) if body else ''
            en = first(block.xpath('.//*[' + cls('ddef_d') + ']')).rstrip(': ')
            if not zh or not en or re.match(r'(written )?abbreviation for\b', en):
                continue
            levels = {t.strip() for t in block.xpath('.//*[' + cls('epp-xref') + ']/text()')} & LEVELS
            info = block.xpath('.//*[' + cls('def-info') + ']')
            labels = ''
            if info:
                parts = [text(n) for n in info[0].xpath('./*[not(' + cls('epp-xref') + ') and not(contains(@class, "pron"))]')]
                labels = ' '.join(p for p in parts if p)
                labels = re.sub(r",?\s*(?:uk|us)\s+Your browser doesn't support HTML5 audio\s*/[^/]+/", '', labels)
            guide = first(block.xpath('ancestor::*[' + cls('dsense') + '][1]//*[' + cls('guideword') + ']'))
            if phrase:
                guide = first(phrase[-1].xpath('.//*[' + cls('phrase-title') + ' or ' + cls('pv-title') + ' or ' + cls('di-title') + ']')) or guide
            examples = []
            for example in (body[0].xpath('./*[' + cls('examp') + ']') if body else []):
                eg = EXAMPLE_TYPO.sub(lambda m: EXAMPLE_FIXES[m.group()], first(example.xpath('./*[' + cls('eg') + ']')))
                trans = first(example.xpath('./*[' + cls('trans') + ']'))
                if eg:
                    examples.append([eg, trans])
            sense_pos = pos
            if phrase and 'pv-block' in phrase[-1].get('class', ''):
                sense_pos = 'phr. v.'
            elif phrase and 'phrase-di-block' in phrase[-1].get('class', ''):
                sense_pos = 'n.'  # only "goods", filed as a plural-noun phrase entry
            senses.append({
                'id': block.get('data-wl-senseid', ''),
                'pos': sense_pos,
                'guide': guide.strip() if phrase else (guide.strip('() ').title() if guide else ''),
                'labels': labels,
                'en': en,
                'zh': zh,
                'level': next(iter(levels)) if len(levels) == 1 else None,
                'examples': examples,
            })
    return {'ipa': ipa, 'senses': senses}


def main():
    pages = Path(sys.argv[1])
    study = json.loads((ROOT / 'study-data.json').read_text())
    data = {}
    for list_name, rows in study.items():
        for row in rows:
            path = pages / (quote(slug(row['word']), safe='') + '.html.gz')
            if not path.exists():
                raise SystemExit(f'Missing page: {path}')
            entry = parse_page(row['word'], gzip.decompress(path.read_bytes()).decode())
            # "US spelling of colour": the real senses live under the British headword.
            senses = []
            for sense in entry['senses']:
                target = RESPELLING.match(sense['en'])
                if not target:
                    senses.append(sense)
                    continue
                other = target.group(1)
                page = pages / (quote(other.replace(' ', '-'), safe='') + '.html.gz')
                if not page.exists():
                    raise SystemExit(f'Missing page for {other}: {page}')
                senses += parse_page(other, gzip.decompress(page.read_bytes()).decode())['senses']
            for page_slug, sense_id, pos in PHRASE_SENSES.get(row['word'].lower(), []):
                page = pages / (page_slug + '.html.gz')
                if not page.exists():
                    raise SystemExit(f'Missing phrase page: {page}')
                tree = html.fromstring(gzip.decompress(page.read_bytes()).decode().split('\n', 1)[1])
                space_collocations(tree)
                found = [s for s in collect(tree, page_slug, set(), 'page')['senses'] if s['id'] == sense_id]
                if not found:
                    raise SystemExit(f'{sense_id} not on {page}')
                senses.append({**found[0], 'pos': pos})
            entry['senses'] = list({sense['id']: sense for sense in senses}.values())
            data[list_name + ':' + row['word']] = entry
    (ROOT / 'cambridge-senses.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    empty = [k for k, v in data.items() if not v['senses']]
    print(f'{len(data)} words, {sum(len(v["senses"]) for v in data.values())} senses; '
          f'{sum(1 for v in data.values() for s in v["senses"] if not s["examples"])} senses without examples; '
          f'empty: {empty}')


if __name__ == '__main__':
    main()
