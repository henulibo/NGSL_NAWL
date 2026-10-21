// Shared rendering for the workbook, print view, example dialog, and CSV export.
// Every sense comes straight from the Cambridge English-Chinese dictionary, so a
// CEFR level is shown exactly as Cambridge marks it; unmarked senses stay unrated.
const CEFR_GROUP={A1:1,A2:1,B1:2,B2:2,C1:3,C2:3};
const CEFR_PRIORITY=['','① 基础优先','② 重点扩展','③ 进阶学习'];
const TABLE_SENSES=6;
const CAMBRIDGE='https://dictionary.cambridge.org/dictionary/english-chinese-simplified/';
function cefrInfo(sense){
 const level=sense.level,group=CEFR_GROUP[level];
 if(!group)return {label:'未评级',short:'未评级',group:0,note:'剑桥词典未给此义项标注 CEFR 等级；不表示 C2，也不表示不重要。'};
 return {label:level+' · '+CEFR_PRIORITY[group],short:level+' · '+['','①','②','③'][group],group,note:level+' · '+CEFR_PRIORITY[group]+'（剑桥词典义项等级）'};
}
function escapeCefr(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function cefrBadge(sense,full){
 const info=cefrInfo(sense);
 return '<span class="cefr-badge cefr-'+info.group+'" title="'+escapeCefr(info.note)+'" aria-label="'+escapeCefr(info.label)+'">'+escapeCefr(full?info.label:info.short)+'</span>';
}
function cefrDefinition(sense){return (sense.pos?sense.pos+' ':'')+sense.meaning;}
// Core senses match the official NGSL/NAWL learner definition, so they lead
// every list; Cambridge's own order (most common first) is kept within each group.
function coreFirst(senses){return senses.filter(sense=>sense.core).concat(senses.filter(sense=>!sense.core));}
const CORE_NOTE='核心义：与 NGSL / NAWL 官方英文释义对应的义项';
function coreTag(sense){return sense.core?'<b class="core-tag" title="'+CORE_NOTE+'">核心</b>':'';}
// The table stays scannable: core senses first, then at most a handful more;
// specialist senses and the long tail are left to the example dialog.
function tableSenses(entry){
 const general=coreFirst(entry.senses.filter(sense=>sense.core||!/\bspecialized\b/i.test(sense.labels||'')));
 const core=general.filter(sense=>sense.core).length;
 return general.slice(0,Math.max(TABLE_SENSES,core));
}
function cefrMeaningHTML(entry){
 const shown=tableSenses(entry),hidden=entry.senses.length-shown.length;
 return shown.map(sense=>'<span class="meaning-sense'+(sense.core?' core':'')+'">'+(cefrInfo(sense).group?cefrBadge(sense):'<span class="cefr-gap" aria-hidden="true"></span>')+'<span>'+coreTag(sense)+escapeCefr(cefrDefinition(sense))+'</span></span>').join('')
  +(hidden?'<span class="meaning-more">另有 '+hidden+' 个义项，见弹框</span>':'');
}
function learnerDefinitionHTML(entry,list){
 if(!entry||!entry.definition)return '';
 const source=list==='NAWL'?['NAWL','https://www.newgeneralservicelist.com/new-academic-word-list']:['NGSL','https://www.newgeneralservicelist.com/new-general-service-list'];
 return '<p class="learner-definition"><span class="learner-label">'+source[0]+' 官方英文释义</span><span lang="en">'+escapeCefr(entry.definition)+'</span><a href="'+source[1]+'" target="_blank" rel="noopener">'+source[0]+' · CC BY-SA 4.0 ↗</a></p>';
}
function cefrWordBadge(entry){
 const level=entry&&entry.level,group=CEFR_GROUP[level];
 if(!group)return '';
 return '<span class="cefr-badge cefr-word cefr-'+group+'" title="'+escapeCefr('词级 '+level+' · '+CEFR_PRIORITY[group]+'：该词各义项中最基础的剑桥等级')+'" aria-label="'+escapeCefr('词级 '+level+' '+CEFR_PRIORITY[group])+'">词 '+level+'</span>';
}
function cefrMeaningText(entry){
 return coreFirst(entry.senses).map(sense=>(sense.core?'[核心] ':'')+'['+cefrInfo(sense).label+'] '+cefrDefinition(sense)).join('\n');
}
// Most entries omit the URL because it is the headword's own Cambridge page.
function cambridgeURL(entry,word){return entry&&entry.url||CAMBRIDGE+encodeURIComponent(String(word||'').toLowerCase());}
function cambridgeSourceHTML(entry,word){
 if(entry&&entry.source==='ECDICT')return '<a href="https://github.com/skywind3000/ECDICT" target="_blank" rel="noopener">ECDICT · MIT ↗</a>';
 if(entry&&entry.source==='unavailable')return '';
 const url=cambridgeURL(entry,word);
 if(!url.startsWith(CAMBRIDGE))return '';
 return '<a class="cambridge-source" href="'+escapeCefr(url)+'" target="_blank" rel="noopener">剑桥英汉词典原词条 ↗</a>';
}
