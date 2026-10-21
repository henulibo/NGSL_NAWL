"""Prepare an offline dictionary scoped to every word in the retained examples.

Usage: python3 vocab-data/prepare_lookup.py [ecdict.csv examples.json output.json]
Daily HTML builds use the retained output and do not need the full CSV.
"""
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOKEN = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)*")


def prepare(source, examples, target):
    corpus = json.loads(examples.read_text(encoding='utf-8'))
    tokens = {word.lower().replace('’', "'") for entry in corpus.values()
              for sentence in entry['examples'] for word in TOKEN.findall(sentence)}
    query_words = tokens | {part for word in tokens for part in word.split('-')}
    query_words |= {word[:-2] for word in query_words if word.endswith("'s")}
    with source.open(encoding='utf-8', newline='') as file:
        rows = {row['word'].lower(): row for row in csv.DictReader(file)}
    forms = {}
    for word, row in rows.items():
        if not row['translation']:
            continue
        for item in row.get('exchange', '').split('/'):
            if ':' not in item:
                continue
            tag, value = item.split(':', 1)
            if tag in ('p', 'd', 'i', '3', 's', 'r', 't'):
                for form in value.split(','):
                    if form.lower() in query_words and form.lower() != word:
                        forms.setdefault(form.lower(), word)

    def translated(word):
        return bool(rows.get(word, {}).get('translation'))

    def base_of(word):
        row = rows.get(word, {})
        for item in row.get('exchange', '').split('/'):
            if item.startswith('0:'):
                base = item[2:].lower()
                if base != word and translated(base):
                    return base
        return None

    def resolve(word):
        row = rows.get(word)
        if row and row['translation']:
            result = {'meaning': row['translation'].replace('\\r', '').replace('\\n', '\n'), 'ipa': row['phonetic']}
            base = base_of(word)
            if base:
                result.update(lemma=base, baseMeaning=rows[base]['translation'].replace('\\r', '').replace('\\n', '\n'))
            return result
        base = forms.get(word)
        if word.endswith("'s"):
            owner = word[:-2]
            if translated(owner):
                base = base_of(owner) or owner
        # Fallback for regular forms missing from ECDICT's exchange column.
        if not base:
            candidates = []
            if word.endswith('ies'):
                candidates.append(word[:-3] + 'y')
            if word.endswith('ed'):
                candidates.extend([word[:-2], word[:-1], word[:-3] if len(word) > 3 and word[-3] == word[-4] else ''])
            if word.endswith('ing'):
                candidates.extend([word[:-3], word[:-3] + 'e', word[:-4] if len(word) > 4 and word[-4] == word[-5] else ''])
            if word.endswith('es'):
                candidates.append(word[:-2])
            if word.endswith('s'):
                candidates.append(word[:-1])
            base = next((candidate for candidate in candidates if translated(candidate)), None)
        if base and translated(base):
            meaning = rows[base]['translation'].replace('\\r', '').replace('\\n', '\n')
            return {'meaning': meaning, 'ipa': '', 'lemma': base, 'baseMeaning': meaning}
        if '-' in word:
            parts = []
            for part in word.split('-'):
                entry = resolve(part)
                if not entry:
                    return None
                parts.append({'word': part, 'meaning': entry['meaning']})
            return {'meaning': '', 'ipa': '', 'components': parts}
        return None

    dictionary = {word: entry for word in sorted(query_words) if (entry := resolve(word)) is not None}
    bases = {entry['lemma'] for entry in dictionary.values() if entry.get('lemma')}
    for base in sorted(bases - dictionary.keys()):
        dictionary[base] = resolve(base)
    dictionary = dict(sorted(dictionary.items()))
    target.write_text(json.dumps(dictionary, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    missing = sorted(tokens - dictionary.keys())
    print(f'Offline dictionary: {len(tokens) - len(missing)}/{len(tokens)} example word forms; {len(dictionary)} searchable entries; missing: {missing}')


if __name__ == '__main__':
    paths = [Path(value) for value in sys.argv[1:]]
    if paths and len(paths) != 3:
        raise SystemExit('Expected three paths: ECDICT CSV, examples JSON, output JSON')
    prepare(*(paths or [Path('/tmp/ielts-ecdict.csv'), ROOT / 'examples-data.json', ROOT / 'lookup-data.json']))
