"""Build the public standalone workbook; no network or private data required."""
import html
import json
import runpy
from pathlib import Path

root = Path(__file__).resolve().parent
template = (root / 'page-template.html').read_text(encoding='utf-8')
entries = json.loads((root / 'study-data.json').read_text(encoding='utf-8'))
learner = runpy.run_path(str(root / 'learner.py'))
word_ids = [name + ':' + row['word'] for name, rows in entries.items() for row in rows]
definitions = learner['load_definitions'](root / 'learner-definitions.json', word_ids)
public = runpy.run_path(str(root / 'public_corpus.py'))
entries, corpus = public['assemble_public'](
    entries, definitions, json.loads((root / 'lookup-data.json').read_text(encoding='utf-8')))
data = json.dumps(entries, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
examples = json.dumps(corpus, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
(root / 'examples-data.json').write_text(examples + '\n', encoding='utf-8')
lookup = (root / 'lookup-data.json').read_text(encoding='utf-8').replace('<', '\\u003c')
lookup_script = (root / 'lookup.js').read_text(encoding='utf-8')
cefr_script = (root / 'cefr.js').read_text(encoding='utf-8')
speech_script = (root / 'speech.js').read_text(encoding='utf-8')
expected = {list_name + ':' + row['word'] for list_name, rows in entries.items() for row in rows}
if set(corpus) != expected:
    raise ValueError('Every vocabulary word must have a complete example entry before building.')
license_text = html.escape((root / 'ecdict-license.txt').read_text(encoding='utf-8'))
project_license = html.escape((root.parent / 'LICENSE').read_text(encoding='utf-8'))
output = template.replace('__VOCAB_DATA__', data).replace('__EXAMPLES_DATA__', examples).replace('__LOOKUP_DATA__', lookup).replace('__LOOKUP_SCRIPT__', lookup_script).replace('__CEFR_SCRIPT__', cefr_script).replace('__SPEECH_SCRIPT__', speech_script).replace('__ECDICT_LICENSE__', license_text).replace('__PROJECT_LICENSE__', project_license)
target = root.parent / 'NGSL_NAWL_10天学习词表.html'
target.write_text(output, encoding='utf-8')
print(f'Built {target.name}: {target.stat().st_size:,} bytes')
