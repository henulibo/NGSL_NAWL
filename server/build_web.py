"""Adapt only the persistence hooks; the original offline workbook stays intact."""
import re
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
page=(ROOT/'NGSL_NAWL_10天学习词表.html').read_text()

def replace_once(old,new):
    global page
    if page.count(old)!=1:
        raise ValueError('Offline template hook changed: '+old[:75])
    page=page.replace(old,new)

replace_once('</head>','<link rel="stylesheet" href="/assets/styles.css">'+''.join('<script src="/assets/'+name+'.js"></script>' for name in ['sync-client','offline-store','offline-client','offline-resources','cloud'])+'</head>')
replace_once('<span class="quiet" id="save-status">进度保存在此浏览器</span>','<span class="quiet" id="save-status">正在读取账号进度…</span><a class="pill account-link" id="account-link" href="/account">我的账号</a><button class="pill" id="logout-btn">退出</button>')
initial=next(line for line in page.splitlines() if line.startswith('try{const saved=localStorage.getItem(KEY);'))
replace_once(initial,'// Online progress is loaded only from the authenticated account.')
saver=next(line for line in page.splitlines() if line.startswith('function save(){'))
replace_once(saver,'function save(){cloud.saveView();}')
replace_once("$('words').addEventListener('click',e=>{","$('words').addEventListener('click',async e=>{")
old=next(line for line in page.splitlines() if line.startswith(' if(b){const id=state.list+'))
replace_once(old,""" if(b){
  const id=state.list+':'+b.dataset.word,next=progress[id]===b.dataset.status?'new':b.dataset.status;
  b.disabled=true;
  try{await cloud.setWord(id,next);const replacement=Array.from($('words').querySelectorAll('[data-status]')).find(x=>x.dataset.word===b.dataset.word&&x.dataset.status===b.dataset.status);if(replacement)replacement.focus({preventScroll:true});}
  catch(error){toast(error.message);renderWords();}
  return;
 }""")
replace_once("progress=next;save();render();toast('进度已导入。');", "await cloud.importWords(next);toast('进度已导入并同步。');")
replace_once("$('backup-btn').addEventListener('click',()=>{download(", "$('backup-btn').addEventListener('click',()=>{if(!cloud.ready){toast('正在读取账号进度，请稍候');return;}download(")
old_final="render();if(!storageAvailable){$('save-status').textContent='无法自动保存，请备份进度';$('save-status').classList.add('storage-warning');toast('此浏览器无法自动保存进度，请使用「备份进度」。');}"
replace_once(old_final,"""render();
cloud.boot({
 readView:()=>({list:state.list,day:state.day}),
 applyView:view=>{if(['NGSL','NAWL','SUP'].includes(view.list)&&Number.isInteger(view.day)&&view.day>=0&&view.day<=5){state.list=view.list;state.day=view.day;render();}},
 applySnapshot:snapshot=>{progress=validProgress(snapshot.words);render();},
 toast
}).catch(error=>{$('save-status').textContent='读取进度失败，请刷新重试';$('save-status').classList.add('storage-warning');toast(error.message);});""")
replace_once('进度存在当前浏览器；换浏览器、移动文件或清理浏览器数据可能影响进度，请用「备份进度」保存 JSON，并在新环境导入。','首次联网登录并显示「离线资源已就绪」后可断网学习；操作先保存到本机，恢复联网或下次打开页面时自动同步。同一单词以服务器最后收到的操作为准。登录、账号管理和进度导入需要联网。清除网站数据可能丢失未同步进度，可用「备份进度」另存。')
folder=ROOT/'server/web';folder.mkdir(exist_ok=True)
version=hashlib.sha256(page.encode()+b''.join(path.read_bytes() for path in sorted((ROOT/'server/static').glob('*')) if path.is_file())).hexdigest()[:16]
page=page.replace('</head>','<meta name="workbook-version" content="'+version+'"></head>')
(folder/'index.html').write_text(page)
(folder/'version.txt').write_text(version)
assets=[path+'?v='+version for path in ['/offline-shell','/login']]+['/assets/'+name+'?v='+version for name in ['styles.css','sync-client.js','offline-store.js','offline-client.js','offline-resources.js','cloud.js','account.js']]
worker=(ROOT/'server/static/service-worker.js').read_text().replace('__CACHE_VERSION__',version).replace('__ASSETS__',json.dumps(assets))
(folder/'service-worker.js').write_text(worker)
print('Built authenticated online workbook:',len(page.encode()),'bytes')
