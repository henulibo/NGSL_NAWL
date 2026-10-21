"""Official NGSL/NAWL learner definitions."""
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

