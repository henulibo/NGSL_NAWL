"""Validate the Cambridge senses, core markers and examples, then assemble the popup corpus."""
import json
import re
import runpy
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent
CAMBRIDGE = 'https://dictionary.cambridge.org/dictionary/english-chinese-simplified/'
LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
MAX_EXAMPLES = 2
HAN = re.compile(r'[㐀-鿿]')


def load(name, default=None):
    path = ROOT / name
    return json.loads(path.read_text()) if path.exists() else default


def sentence_first(examples):
    # Cambridge mixes collocations ("about six feet tall") with full sentences;
    # full sentences teach usage better, so they are preferred when available.
    return sorted(examples, key=lambda pair: not re.search(r'[.!?]["\'”’)]*$', pair[0]))


def assemble(ids, cambridge, added_senses, added_examples, definitions, core_ids):
    """Return the popup corpus and how many examples were written for this page."""
    corpus = {}
    own_count = 0
    for word_id in ids:
        word = word_id.split(':', 1)[1]
        page = cambridge.get(word_id)
        if page is None:
            raise ValueError(f'Missing Cambridge entry: {word_id}')
        senses_in = page['senses'] + added_senses.get(word_id, [])
        if not senses_in:
            raise ValueError(f'No senses for {word_id}')
        examples, translations, own, senses = [], [], [], []
        index = {}

        def add(sentence, translated, authored):
            if not HAN.search(translated or ''):
                raise ValueError(f'Missing Chinese translation: {word_id}: {sentence}')
            if sentence not in index:
                index[sentence] = len(examples)
                examples.append(sentence)
                translations.append(translated.strip())
                if authored:
                    own.append(index[sentence])
            return index[sentence]

        for sense in senses_in:
            if not sense.get('id') or not HAN.search(sense.get('zh', '')) or not sense.get('en'):
                raise ValueError(f'Incomplete sense: {word_id}: {sense}')
            pairs = [pair for pair in sense.get('examples', []) if HAN.search(pair[1] or '')]
            chosen = [add(en, zh, sense['id'].startswith('own:')) for en, zh in sentence_first(pairs)[:MAX_EXAMPLES]]
            if not chosen:
                extra = added_examples.get(sense['id'])
                if not extra:
                    raise ValueError(f'Sense without example: {word_id}: {sense["id"]} {sense["en"]}')
                chosen = [add(extra[0], extra[1], True)]
            item = {'pos': sense['pos'], 'guide': sense.get('guide', ''), 'labels': sense.get('labels', ''),
                    'en': sense['en'], 'meaning': sense['zh'], 'level': sense.get('level'), 'examples': chosen}
            if sense['id'] in core_ids:
                item['core'] = True
            senses.append({k: v for k, v in item.items() if v not in ('', None)})
        own_count += len(own)
        levels = [s['level'] for s in senses if s.get('level')]
        entry = {'senses': senses, 'examples': examples, 'translations': translations,
                 'definition': definitions.get(word_id),
                 'level': min(levels, key=LEVELS.index) if levels else None}
        if own:
            entry['own'] = own
        if page['url'] != CAMBRIDGE + quote(word.lower(), safe="-_.!~*'()"):
            entry['url'] = page['url']
        corpus[word_id] = {k: v for k, v in entry.items() if v is not None}

    unused = set(added_examples) - {s['id'] for page in cambridge.values() for s in page['senses']} \
        - {s['id'] for extra in added_senses.values() for s in extra}
    if unused:
        raise ValueError(f'Examples for unknown senses: {sorted(unused)[:8]}')
    return corpus, own_count


def main():
    required = ['cambridge-senses.json', 'core-senses.json']
    if any(not (ROOT / name).is_file() for name in required):
        raise SystemExit('Legacy dictionary inputs are not bundled. '
                         'Use vocab-data/build.py for the public build; see docs/data.md.')
    study = load('study-data.json')
    cambridge = load('cambridge-senses.json')
    added_senses = load('senses-extra.json', {})
    added_examples = load('examples-extra.json', {})
    learner = runpy.run_path(str(ROOT / 'learner.py'))
    ids = [name + ':' + row['word'] for name, rows in study.items() for row in rows]
    definitions = learner['load_definitions'](ROOT / 'learner-definitions.json', ids)
    core_ids = learner['load_core_senses'](ROOT / 'core-senses.json', cambridge, added_senses, definitions)
    corpus, own_count = assemble(ids, cambridge, added_senses, added_examples, definitions, core_ids)
    (ROOT / 'examples-data.json').write_text(json.dumps(corpus, ensure_ascii=False, separators=(',', ':')))
    print(f'Validated {len(corpus):,} words, {sum(len(w["senses"]) for w in corpus.values()):,} Cambridge senses, '
          f'{sum(len(w["examples"]) for w in corpus.values()):,} examples ({own_count:,} written for this page).')


if __name__ == '__main__':
    main()
