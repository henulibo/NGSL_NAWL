"""Official NGSL/NAWL learner definitions and the Cambridge core senses judged against them."""
import json


def load_definitions(path, word_ids):
    ids = set(word_ids)
    entries = json.loads(path.read_text())['entries']
    unknown = sorted(set(entries) - ids)
    if unknown:
        raise ValueError(f'Learner definitions for unknown words: {unknown[:8]}')
    definitions = {}
    for word_id, entry in entries.items():
        text = ' '.join(str(entry.get('definition', '')).split())
        # Spreadsheet exports can leak formula errors such as "#NAME?".
        if not text or text.startswith('#'):
            raise ValueError(f'Invalid learner definition: {word_id}: {text!r}')
        definitions[word_id] = text
    return definitions


def load_core_senses(path, cambridge, added_senses, definitions):
    """Core senses are stored as Cambridge sense IDs, which stay stable across page re-parses."""
    core = set()
    for word_id, sense_ids in json.loads(path.read_text())['entries'].items():
        if word_id not in definitions:
            raise ValueError(f'Core senses need an official definition: {word_id}')
        if not sense_ids:
            raise ValueError(f'Empty core sense list: {word_id}')
        page = cambridge.get(word_id, {'senses': []})
        available = {s['id'] for s in page['senses'] + added_senses.get(word_id, [])}
        stale = [sense_id for sense_id in sense_ids if sense_id not in available]
        if stale:
            raise ValueError(f'Stale core sense: {word_id}: {stale}')
        core.update(sense_ids)
    return core
