// Catch lost meanings, wrong source credits, and HTML injected by dictionary text.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const context={};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../vocab-data/entry.js'),'utf8'),context);
const entry={senses:[{pos:'modal',meaning:'能，会'},{pos:'n.',meaning:'罐头'},{meaning:'不'}]};
test('table and CSV keep every sense in order with its part of speech',()=>{
 const html=context.meaningHTML(entry);
 assert.ok(html.indexOf('modal 能，会')<html.indexOf('n. 罐头')&&html.indexOf('n. 罐头')<html.indexOf('不'));
 assert.equal(context.meaningText(entry),'modal 能，会\nn. 罐头\n不');
});
test('public data credits ECDICT and links nowhere when a meaning is unavailable',()=>{
 assert.match(context.sourceHTML({source:'ECDICT'}),/github.com\/skywind3000\/ECDICT/);
 assert.equal(context.sourceHTML({source:'unavailable'}),'');
 assert.equal(context.sourceHTML(undefined),'');
});
test('dictionary meanings are escaped before insertion into the page',()=>{
 const html=context.meaningHTML({senses:[{pos:'n.',meaning:'<img src=x onerror=alert(1)>'}]});
 assert.ok(html.includes('&lt;img'));
 assert.doesNotMatch(html,/<img/);
});
test('official English definition is escaped and credited to the right list',()=>{
 const html=context.learnerDefinitionHTML({definition:'a <b>test</b> & more'},'NAWL');
 assert.match(html,/NAWL 官方英文释义/);
 assert.match(html,/new-academic-word-list/);
 assert.match(html,/CC BY-SA 4\.0/);
 assert.match(html,/a &lt;b&gt;test&lt;\/b&gt; &amp; more/);
 assert.match(context.learnerDefinitionHTML({definition:'x'},'NGSL'),/new-general-service-list/);
 assert.equal(context.learnerDefinitionHTML({definition:null},'SUP'),'');
});
test('built page carries no CEFR, core-sense or Cambridge rendering',()=>{
 const page=fs.readFileSync(path.join(__dirname,'../vocab-data/page-template.html'),'utf8')+fs.readFileSync(path.join(__dirname,'../vocab-data/entry.js'),'utf8');
 assert.doesNotMatch(page,/cefr-|cefrBadge|core-tag|coreFirst|dictionary\.cambridge|剑桥译文/i);
});
