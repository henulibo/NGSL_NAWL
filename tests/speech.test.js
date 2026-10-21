// Catch American or online-only voices winning over British ones, and silent failures.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const context={};
const source=path.join(__dirname,'../vocab-data/speech.js');
vm.runInNewContext(fs.existsSync(source)?fs.readFileSync(source,'utf8'):'',context);
const voice=(name,lang,localService=true)=>({name,lang,localService});
function fakeSynth(voices){
 const synth={spoken:[],cancelled:0,getVoices:()=>voices,cancel(){synth.cancelled++;},speak(u){synth.spoken.push(u);}};
 return synth;
}
class Utterance{constructor(text){this.text=text;}}

test('British English wins over American, other English and non-English voices',()=>{
 assert.equal(typeof context.pickSpeechVoice,'function','voice selection is not implemented');
 const voices=[voice('Ting-Ting','zh-CN'),voice('Samantha','en-US'),voice('Karen','en-AU'),voice('Daniel','en-GB')];
 assert.equal(context.pickSpeechVoice(voices).name,'Daniel');
 assert.equal(context.pickSpeechVoice(voices.slice(0,3)).name,'Karen');
 assert.equal(context.pickSpeechVoice([voice('Ting-Ting','zh-CN')]),null);
 assert.equal(context.pickSpeechVoice([]),null);
});

test('on-device voices beat network voices of the same accent, so offline study keeps working',()=>{
 const voices=[voice('Google UK English Female','en-GB',false),voice('Daniel','en_GB',true)];
 assert.equal(context.pickSpeechVoice(voices).name,'Daniel');
 assert.equal(context.pickSpeechVoice([voice('Google UK English Female','en-GB',false),voice('Samantha','en-US')]).name,'Google UK English Female');
});

test('joke and robotic system voices never beat a natural voice of the same accent',()=>{
 const voices=[voice('Bubbles','en-US'),voice('Eddy (English (UK))','en-GB'),voice('Daniel','en-GB'),voice('Serena (Premium)','en-GB')];
 assert.equal(context.pickSpeechVoice(voices).name,'Serena (Premium)');
 assert.equal(context.pickSpeechVoice(voices.slice(0,3)).name,'Daniel');
 assert.equal(context.pickSpeechVoice([voice('Bad News','en-US'),voice('Samantha','en-US')]).name,'Samantha');
 assert.equal(context.pickSpeechVoice([voice('Zarvox','en-US')]),null);
});

test('speaking cancels the previous utterance and uses the chosen voice, language and rate',()=>{
 const synth=fakeSynth([voice('Samantha','en-US'),voice('Daniel','en_GB')]);
 const speaker=context.createSpeaker(synth,Utterance);
 assert.equal(speaker.speak('  The  report\nis due.  ',0.8),'ok');
 assert.equal(synth.cancelled,1);
 const u=synth.spoken[0];
 assert.equal(u.text,'The report is due.');
 assert.equal(u.voice.name,'Daniel');
 assert.equal(u.lang,'en-GB');
 assert.equal(u.rate,0.8);
 speaker.speak('word',3);
 assert.equal(synth.spoken[1].rate,1,'unexpected rates fall back to normal speed');
});

test('devices that list no voices still speak by language tag; devices without English report it',()=>{
 const silent=fakeSynth([]);
 assert.equal(context.createSpeaker(silent,Utterance).speak('hello',1),'ok');
 assert.equal(silent.spoken[0].lang,'en-GB');
 assert.equal(silent.spoken[0].voice,undefined);
 const chineseOnly=fakeSynth([voice('Ting-Ting','zh-CN')]);
 assert.equal(context.createSpeaker(chineseOnly,Utterance).speak('hello',1),'no-english');
 assert.equal(chineseOnly.spoken.length,0);
 assert.equal(context.createSpeaker(fakeSynth([]),Utterance).speak('   ',1),'empty');
});

test('missing browser support is reported instead of throwing',()=>{
 const speaker=context.createSpeaker(undefined,undefined);
 assert.equal(speaker.supported,false);
 assert.equal(speaker.speak('hello',1),'unsupported');
});

test('real errors reach the page, while interruptions from a newer click stay quiet',()=>{
 const synth=fakeSynth([voice('Daniel','en-GB')]),errors=[];
 context.createSpeaker(synth,Utterance).speak('hello',1,error=>errors.push(error));
 synth.spoken[0].onerror({error:'interrupted'});
 synth.spoken[0].onerror({error:'canceled'});
 synth.spoken[0].onerror({error:'synthesis-failed'});
 assert.deepEqual(errors,['synthesis-failed']);
});

test('built page wires speak buttons into word rows, dialog title, examples and lookup card',()=>{
 const page=fs.readFileSync(path.join(__dirname,'../NGSL_NAWL_10天学习词表.html'),'utf8');
 assert.ok(!page.includes('__SPEECH_SCRIPT__'),'speech script placeholder was not replaced');
 assert.ok(page.includes('function createSpeaker('));
 assert.match(page,/speakButton\(r\.word,/);
 assert.match(page,/speakButton\(entry\.examples\[x\],/);
 assert.ok(page.includes('id="example-speak"')&&page.includes("$('example-speak').dataset.speak=word"));
 assert.ok(page.includes('id="translation-speak"')&&page.includes("$('translation-speak').dataset.speak=result.word"));
 assert.ok(page.includes('id="rate-btn"'));
 assert.match(page,/@media print\{\.speak-btn,#rate-btn\{display:none!important\}\}/);
});
