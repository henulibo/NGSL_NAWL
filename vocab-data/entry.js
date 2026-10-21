// Shared rendering for the workbook, print view, entry dialog, and CSV export.
// Public entries carry ECDICT meanings and the official NGSL/NAWL definition only.
function escapeEntry(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function senseText(sense){return (sense.pos?sense.pos+' ':'')+sense.meaning;}
function meaningHTML(entry){
 return entry.senses.map(sense=>'<span class="meaning-sense"><span>'+escapeEntry(senseText(sense))+'</span></span>').join('');
}
function learnerDefinitionHTML(entry,list){
 if(!entry||!entry.definition)return '';
 const source=list==='NAWL'?['NAWL','https://www.newgeneralservicelist.com/new-academic-word-list']:['NGSL','https://www.newgeneralservicelist.com/new-general-service-list'];
 return '<p class="learner-definition"><span class="learner-label">'+source[0]+' 官方英文释义</span><span lang="en">'+escapeEntry(entry.definition)+'</span><a href="'+source[1]+'" target="_blank" rel="noopener">'+source[0]+' · CC BY-SA 4.0 ↗</a></p>';
}
function meaningText(entry){return entry.senses.map(senseText).join('\n');}
function sourceHTML(entry){
 if(entry&&entry.source==='ECDICT')return '<a href="https://github.com/skywind3000/ECDICT" target="_blank" rel="noopener">ECDICT · MIT ↗</a>';
 return '';
}
