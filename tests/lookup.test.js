// Catch lost capitalization/punctuation handling and accidental phrase lookups.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const context = {};
const source = path.join(__dirname, '../vocab-data/lookup.js');
vm.runInNewContext(fs.existsSync(source) ? fs.readFileSync(source, 'utf8') : '', context);
const dictionary = JSON.parse('{"went":{"meaning":"go的过去式","lemma":"go","baseMeaning":"去"},"children\u0027s":{"meaning":"孩子的"},"eight-hour":{"meaning":"八小时"}}');
test('selected word survives capitals, surrounding punctuation and curly apostrophes', () => {
  assert.equal(typeof context.lookupWord, 'function', 'word lookup is not implemented');
  assert.equal(context.lookupWord(' “Went,” ', dictionary).entry.baseMeaning, '去');
  assert.equal(context.lookupWord('children’s', dictionary).entry.meaning, '孩子的');
  assert.equal(context.lookupWord('eight-hour', dictionary).entry.meaning, '八小时');
});
test('phrases and unrelated selections are rejected while unknown words report a miss', () => {
  assert.equal(typeof context.lookupWord, 'function', 'word lookup is not implemented');
  for (const text of ['', 'two words', '中文', '123', '<script>']) assert.equal(context.lookupWord(text, dictionary), null);
  const missing = context.lookupWord('Unrecorded', dictionary);
  assert.equal(missing.word, 'unrecorded');
  assert.equal(missing.entry, null);
});
