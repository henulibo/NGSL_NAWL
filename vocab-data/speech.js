// Read words and examples aloud with the browser's own voices, British English first.
const SPEECH_RATES=[1,0.8];
// macOS ships joke voices and robotic Eloquence voices alongside its natural ones.
const NOVELTY_VOICES=/^(Albert|Bad News|Bahh|Bells|Boing|Bubbles|Cellos|Good News|Jester|Organ|Superstar|Trinoids|Whisper|Wobble|Zarvox|Junior|Fred|Kathy|Ralph)\b/i;
const ELOQUENCE_VOICES=/^(Eddy|Flo|Grandma|Grandpa|Reed|Rocko|Sandy|Shelley)\b/i;
function speechVoiceRank(voice){
 const lang=String(voice.lang).replace('_','-').toLowerCase(),name=String(voice.name||'');
 if(!/^en(-|$)/.test(lang)||NOVELTY_VOICES.test(name))return -1;
 // Accent first, then on-device voices (they work offline), then natural-sounding ones.
 return (lang==='en-gb'?0:lang==='en-us'?2:1)*8+(voice.localService===false?4:0)+(ELOQUENCE_VOICES.test(name)?2:0)+(/enhanced|premium|natural/i.test(name)?0:1);
}
function pickSpeechVoice(voices){
 let best=null,bestRank=Infinity;
 for(const voice of voices||[]){const rank=speechVoiceRank(voice);if(rank>=0&&rank<bestRank){best=voice;bestRank=rank;}}
 return best;
}
function createSpeaker(synth,Utterance){
 const supported=!!(synth&&typeof synth.speak==='function'&&typeof Utterance==='function');
 return {
  supported,
  // 'ok', 'unsupported', 'empty', or 'no-english' when the device lists voices but none speak English.
  speak(text,rate,onError){
   if(!supported)return 'unsupported';
   const clean=String(text).replace(/\s+/g,' ').trim();if(!clean)return 'empty';
   const voices=synth.getVoices(),voice=pickSpeechVoice(voices);
   if(!voice&&voices.length)return 'no-english';
   synth.cancel();
   const utterance=new Utterance(clean);
   // Some Android browsers list no voices yet still speak by language tag.
   utterance.lang=voice?voice.lang.replace('_','-'):'en-GB';
   if(voice)utterance.voice=voice;
   utterance.rate=SPEECH_RATES.includes(rate)?rate:1;
   if(onError)utterance.onerror=event=>{if(!['interrupted','canceled'].includes(event.error))onError(event.error);};
   synth.speak(utterance);
   return 'ok';
  }
 };
}
