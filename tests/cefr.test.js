// Catch wrong priority groups, lost meanings, and HTML injected by dictionary text.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const context={};
const source=path.join(__dirname,'../vocab-data/cefr.js');
vm.runInNewContext(fs.existsSync(source)?fs.readFileSync(source,'utf8'):'',context);
const entry={senses:[
 {pos:'modal',guide:'Able',meaning:'能，会',level:'A1'},
 {pos:'n.',guide:'Container',meaning:'罐头',level:'A2'},
 {pos:'n.',labels:'specialized',meaning:'作废字符'}
]};
test('each sense shows the Cambridge level, with unmarked senses kept separate from advanced',()=>{
 assert.equal(typeof context.cefrBadge,'function','CEFR labels are not implemented');
 assert.match(context.cefrBadge(entry.senses[0]),/A1/);
 assert.match(context.cefrBadge(entry.senses[1]),/A2/);
 assert.match(context.cefrBadge({level:'B1'},true),/② 重点扩展/);
 assert.match(context.cefrBadge({level:'C2'},true),/③ 进阶学习/);
 assert.match(context.cefrBadge(entry.senses[2]),/未评级/);
 assert.equal(context.cefrInfo(entry.senses[2]).group,0);
 assert.doesNotMatch(context.cefrBadge({level:'B1'}),/≈/);
 assert.match(context.cefrInfo({level:'C1'}).note,/剑桥词典义项等级/);
});
test('table keeps specialised senses for the dialog, while CSV keeps everything',()=>{
 const html=context.cefrMeaningHTML(entry);
 for(const text of ['A1','A2','能，会','罐头'])assert.ok(html.includes(text),text);
 for(const text of ['作废字符','未评级'])assert.ok(!html.includes(text),text);
 assert.match(html,/另有 1 个义项，见弹框/);
 const unrated=context.cefrMeaningHTML({senses:[{pos:'adv.',meaning:'不'}]});
 assert.ok(unrated.includes('不')&&unrated.includes('cefr-gap')&&!unrated.includes('未评级'));
 assert.equal(context.cefrMeaningText(entry),'[A1 · ① 基础优先] modal 能，会\n[A2 · ① 基础优先] n. 罐头\n[未评级] n. 作废字符');
});
test('the table shows at most six senses unless more of them are core',()=>{
 const many={senses:Array.from({length:9},(_,i)=>({pos:'n.',meaning:'义'+i,core:i>=1&&i<=7}))};
 const shown=context.tableSenses(many).map(sense=>sense.meaning);
 assert.deepEqual(shown,['义1','义2','义3','义4','义5','义6','义7']);
 assert.equal(context.tableSenses({senses:Array.from({length:9},(_,i)=>({pos:'n.',meaning:'义'+i}))}).length,6);
});
test('word badge shows the most basic Cambridge level and nothing when the source has none',()=>{
 assert.match(context.cefrWordBadge({level:'A2'}),/词 A2/);
 assert.match(context.cefrWordBadge({level:'C1'}),/cefr-3/);
 assert.equal(context.cefrWordBadge({level:null}),'');
 assert.equal(context.cefrWordBadge({level:'<b>'}),'');
});
test('source link falls back to the headword page and only links to Cambridge',()=>{
 assert.match(context.cambridgeSourceHTML({},'Mother-in-law'),/english-chinese-simplified\/mother-in-law"/);
 assert.match(context.cambridgeSourceHTML({url:'https://dictionary.cambridge.org/dictionary/english-chinese-simplified/harbour'},'harbor'),/\/harbour"/);
 assert.equal(context.cambridgeSourceHTML({url:'javascript:alert(1)'},'cat'),'');
});
test('public data credits ECDICT and never implies a Cambridge source',()=>{
 assert.match(context.cambridgeSourceHTML({source:'ECDICT'},'color'),/github.com\/skywind3000\/ECDICT/);
 assert.doesNotMatch(context.cambridgeSourceHTML({source:'ECDICT'},'color'),/cambridge/);
 assert.equal(context.cambridgeSourceHTML({source:'unavailable'},'unknown'),'');
});
test('dictionary meanings are escaped before insertion into the page',()=>{
 const html=context.cefrMeaningHTML({senses:[{pos:'n.',meaning:'<img src=x onerror=alert(1)>'}]});
 assert.ok(html.includes('&lt;img'));
 assert.doesNotMatch(html,/<img/);
});
test('core senses lead the table and CSV, even when the core sense is specialised',()=>{
 const word={senses:[
  {pos:'n.',meaning:'报告'},
  {pos:'n.',labels:'specialized',meaning:'帐户',core:true},
  {pos:'n.',meaning:'帐目',level:'B1',core:true},
  {pos:'n.',labels:'specialized',meaning:'利润'}
 ]};
 const html=context.cefrMeaningHTML(word);
 assert.ok(html.indexOf('帐户')<html.indexOf('帐目')&&html.indexOf('帐目')<html.indexOf('报告'),'core senses keep their order and come first');
 assert.equal((html.match(/core-tag/g)||[]).length,2);
 assert.doesNotMatch(html,/利润/);
 assert.match(html,/另有 1 个义项/);
 assert.deepEqual(context.cefrMeaningText(word).split('\n').map(line=>line.startsWith('[核心]')),[true,true,false,false]);
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
