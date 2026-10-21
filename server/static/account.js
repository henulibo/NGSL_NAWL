(function(){
 'use strict';
 let csrf='',me=null,resetId=null;
 const $=id=>document.getElementById(id);
 async function api(path,method='GET',body){
  let response;
  try{response=await fetch(path,{method,credentials:'same-origin',headers:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{})},...(body!==undefined?{body:JSON.stringify(body)}:{})});}
  catch(error){throw new Error('网络连接失败，请重试');}
  const data=await response.json().catch(()=>({detail:'服务器返回异常'}));
  if(!response.ok){if(response.status===401&&path!=='/api/auth/login')location.replace('/login');throw new Error(data.detail||'操作失败');}
  return data;
 }
 async function localAccount(){
  if(typeof openOfflineStore!=='function')return null;
  let local;try{local=await openOfflineStore();}catch(error){return null;}
  const record=await local.read(me.id);
  if(record&&Object.keys(record.pending).length)throw new Error('还有待同步的学习进度，请返回词表联网同步后再操作');
  return local;
 }
 function bindForm(id,messageId,operation){
  $(id).addEventListener('submit',async event=>{
   event.preventDefault();const button=$(id).querySelector('button[type="submit"]');button.disabled=true;$(messageId).textContent='正在处理…';
   try{await operation();}catch(error){$(messageId).textContent=error.message;}finally{button.disabled=false;}
  });
 }
 if($('login-form')){
  if(new URLSearchParams(location.search).has('pending'))$('message').textContent='本机仍有待同步进度，重新登录原账号后会自动续传。';
  bindForm('login-form','message',async()=>{
   let local;
   if(typeof openOfflineStore==='function'){
    try{local=await openOfflineStore();await local.deactivate();}
    catch(error){if(typeof indexedDB!=='undefined')throw new Error('无法更新本机账号状态，请关闭旧页面后刷新重试');}
   }
   const result=await api('/api/auth/login','POST',{username:$('username').value.trim(),password:$('password').value});
   if(local)await local.activate(result.user);
   location.replace('/');
  });return;
 }
 async function loadUsers(){
  const data=await api('/api/admin/users');$('users').replaceChildren();
  for(const user of data.users){
   const row=document.createElement('div');row.className='account-row';
   const info=document.createElement('div'),name=document.createElement('div'),role=document.createElement('div');
   name.className='account-username';name.textContent=user.username;
   role.className='account-role';role.textContent=(user.role==='admin'?'管理员':'学习账号')+' · '+(user.active?'已启用':'已停用');info.append(name,role);
   const actions=document.createElement('div');actions.className='account-actions';
   const toggle=document.createElement('button');toggle.textContent=user.active?'停用':'启用';toggle.disabled=user.id===me.id;
   toggle.addEventListener('click',async()=>{if(user.active&&!confirm('停用 '+user.username+' 的账号？现有登录会失效。'))return;toggle.disabled=true;try{await api('/api/admin/users/'+user.id,'PATCH',{active:!user.active});await loadUsers();$('users-message').textContent='账号状态已更新。';}catch(error){$('users-message').textContent=error.message;toggle.disabled=false;}});
   const reset=document.createElement('button');reset.textContent='重置密码';reset.disabled=user.id===me.id;
   reset.addEventListener('click',()=>{resetId=user.id;$('reset-heading').textContent='重置 '+user.username+' 的密码';$('reset-form').reset();$('reset-message').textContent='';$('reset-dialog').showModal();});
   actions.append(toggle,reset);row.append(info,actions);$('users').append(row);
  }
 }
 bindForm('password-form','password-message',async()=>{
  const local=await localAccount();
  await api('/api/password','POST',{current_password:$('current-password').value,new_password:$('new-password').value});
  const cleanup=local?await local.clearUser(me.id):null;$('password-form').reset();location.replace('/login'+(cleanup?.pending?'?pending=1':''));
 });
 bindForm('create-form','create-message',async()=>{
  const username=$('new-username').value.trim();await api('/api/admin/users','POST',{username,password:$('initial-password').value});
  $('create-form').reset();$('create-message').textContent='账号 '+username+' 已创建。';await loadUsers();
 });
 bindForm('reset-form','reset-message',async()=>{await api('/api/admin/users/'+resetId+'/password','POST',{password:$('reset-password').value});$('reset-form').reset();$('reset-dialog').close();$('users-message').textContent='密码已重置，原有登录已失效。';});
 $('reset-cancel').addEventListener('click',()=>$('reset-dialog').close());
 $('logout').addEventListener('click',async()=>{try{const local=await localAccount();await api('/api/auth/logout','POST',{});const cleanup=local?await local.clearUser(me.id):null;location.replace('/login'+(cleanup?.pending?'?pending=1':''));}catch(error){$('account-info').textContent=error.message;}});
 api('/api/me').then(async data=>{me=data.user;csrf=data.csrf;$('account-heading').textContent=me.username+' · 我的账号';$('account-info').textContent=me.role==='admin'?'管理员 · 可创建和管理学习账号':'学习账号 · 进度按账号独立保存';if(me.role==='admin'){$('create-card').hidden=false;$('users-card').hidden=false;await loadUsers();}}).catch(error=>{$('account-info').textContent=error.message;});
})();
