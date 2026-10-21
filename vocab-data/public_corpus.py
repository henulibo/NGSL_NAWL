"""Assemble the public workbook from NGSL/NAWL definitions and ECDICT only."""

# American spellings in the word lists can have British ECDICT headwords.
SPELLING_ALIASES = {
    'center': 'centre', 'color': 'colour', 'behavior': 'behaviour',
    'favorite': 'favourite', 'favor': 'favour', 'defense': 'defence',
    'analyze': 'analyse', 'neighborhood': 'neighbourhood', 'dialog': 'dialogue',
    'fulfill': 'fulfil', 'whilst': 'while', 'humor': 'humour', 'harbor': 'harbour',
    'behavioral': 'behavioural', 'tumor': 'tumour', 'fiber': 'fibre',
    'artifact': 'artefact', 'afterward': 'afterwards', 'aluminum': 'aluminium',
    'liter': 'litre', 'millimeter': 'millimetre', 'descendent': 'descendant',
}


def assemble_public(study, definitions, lookup):
    """Return display rows and popup data without inventing levels or examples."""
    entries, corpus = {}, {}
    seen = set()
    for list_name, rows in study.items():
        entries[list_name] = []
        for row in rows:
            word = row['word']
            word_id = list_name + ':' + word
            if word_id in seen:
                raise ValueError(f'Duplicate vocabulary word: {word_id}')
            seen.add(word_id)
            headword = word.lower()
            if headword not in lookup:
                headword = SPELLING_ALIASES.get(headword, headword)
            dictionary = lookup.get(headword, {})
            meaning = dictionary.get('meaning', '').replace('\\r', '').strip()
            source = 'ECDICT' if meaning else 'unavailable'
            meaning = meaning or '暂无离线中文释义'
            definition = definitions.get(word_id, '')
            sense = {'meaning': meaning, 'en': definition, 'examples': [], 'source': source}
            if dictionary and headword != word.lower():
                sense['guide'] = '参考词条：' + headword
            corpus[word_id] = {
                'senses': [sense], 'examples': [], 'translations': [],
                'definition': definition, 'source': source,
            }
            entries[list_name].append({
                **row, 'meaning': meaning, 'ipa': dictionary.get('ipa', ''),
            })
    unknown = set(definitions) - seen
    if unknown:
        raise ValueError('Definitions for unknown words: ' + ', '.join(sorted(unknown)[:8]))
    return entries, corpus
