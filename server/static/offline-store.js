(function(root){
 'use strict';
 const databaseName='ielts-study-offline-v1';
 const makeId=()=>root.crypto.randomUUID();
 const publicUser=user=>({id:user.id,username:user.username,role:user.role,active:user.active!==false});
 const blank=user=>({user:publicUser(user),snapshot:{revision:-1,words:{}},pending:{}});
 function validSnapshot(snapshot){
  if(!snapshot||!Number.isSafeInteger(snapshot.revision)||snapshot.revision<0||!snapshot.words||Array.isArray(snapshot.words)||typeof snapshot.words!=='object')throw new Error('云端进度格式不正确');
  if(Object.values(snapshot.words).some(value=>!['known','review'].includes(value)))throw new Error('云端进度状态不正确');
 }
 function openOfflineStore({indexedDB=root.indexedDB,name=databaseName,newId=makeId}={}){
  return new Promise((resolve,reject)=>{
   if(!indexedDB){reject(new Error('此浏览器无法离线保存'));return;}
   const opening=indexedDB.open(name,1);
   opening.onupgradeneeded=()=>{opening.result.createObjectStore('users');opening.result.createObjectStore('meta');};
   opening.onerror=()=>reject(opening.error);
   opening.onblocked=()=>reject(new Error('本机存储被其他页面占用，请关闭旧页面重试'));
   opening.onsuccess=()=>{
    const db=opening.result;db.onversionchange=()=>db.close();
    function transaction(names,mode,action){
     return new Promise((done,fail)=>{
      let tx,result,failure;
      try{tx=db.transaction(names,mode,{durability:'strict'});}catch(error){try{tx=db.transaction(names,mode);}catch(e){fail(e);return;}}
      const rejectOperation=error=>{failure=error;try{tx.abort();}catch(e){fail(error);}};
      const get=(store,key,callback)=>{
       const request=tx.objectStore(store).get(key);
       request.onsuccess=()=>{try{callback(request.result);}catch(error){rejectOperation(error);}};
      };
      tx.oncomplete=()=>done(result);tx.onabort=()=>fail(failure||tx.error||new Error('本机保存未完成，请重试'));
      try{action({tx,get,setResult:value=>{result=value;}});}catch(error){rejectOperation(error);}
     });
    }
    function requireActive(active,userId){
     if(!active||active.id!==userId){const error=new Error('登录账号已变化，请刷新页面');error.code='ACCOUNT_CHANGED';throw error;}
    }
    const store={
     activate(user,options={}){
      if(!user||!Number.isSafeInteger(user.id)||user.id<1||typeof user.username!=='string')return Promise.reject(new Error('账号信息无效'));
      return transaction(['users','meta'],'readwrite',({tx,get,setResult})=>{
       get('meta','login-transition',transition=>{
        if(transition&&'expectedActiveId' in options){const error=new Error('请完成账号登录后再继续学习');error.code='LOGIN_TRANSITION';error.status=401;throw error;}
        get('meta','active',active=>{
         if('expectedActiveId' in options&&(active?.id||null)!==options.expectedActiveId){const error=new Error('登录账号已变化，请刷新页面');error.code='ACCOUNT_CHANGED';throw error;}
         get('users',user.id,record=>{record=record||blank(user);record.user=publicUser(user);tx.objectStore('users').put(record,user.id);tx.objectStore('meta').put(publicUser(user),'active');tx.objectStore('meta').delete('login-transition');setResult(record);});
        });
       });
       get('meta','device',device=>{if(!device)tx.objectStore('meta').put({id:newId(),sequence:0},'device');});
      });
     },
     active(){return transaction(['meta'],'readonly',({get,setResult})=>get('meta','active',user=>setResult(user||null)));},
     deactivate(){return transaction(['meta'],'readwrite',({tx})=>{tx.objectStore('meta').delete('active');tx.objectStore('meta').put(true,'login-transition');});},
     read(userId){return transaction(['users'],'readonly',({get,setResult})=>get('users',userId,record=>setResult(record||null)));},
     enqueue(userId,{word_id,status}){
      if(typeof word_id!=='string'||!word_id||word_id.length>150||!['known','review','new'].includes(status))return Promise.reject(new Error('单词状态无效'));
      return transaction(['users','meta'],'readwrite',({tx,get,setResult})=>{
       get('meta','active',active=>{requireActive(active,userId);
        get('meta','device',device=>{
         if(!device||!Number.isSafeInteger(device.sequence)||device.sequence>=Number.MAX_SAFE_INTEGER)throw new Error('本机操作序号无效，请备份进度后重试');
         get('users',userId,record=>{
          if(!record)throw new Error('本机账号进度未准备好');
          const operation={id:newId(),word_id,status,device_id:device.id,sequence:device.sequence+1};
          record.pending[word_id]=operation;device.sequence=operation.sequence;
          tx.objectStore('users').put(record,userId);tx.objectStore('meta').put(device,'device');setResult(operation);
         });
        });
       });
      });
     },
     accept(userId,snapshot,ackIds=[]){
      try{validSnapshot(snapshot);}catch(error){return Promise.reject(error);}
      return transaction(['users'],'readwrite',({tx,get,setResult})=>get('users',userId,record=>{
       if(!record)throw new Error('本机账号进度不存在');
       if(snapshot.revision>record.snapshot.revision)record.snapshot={revision:snapshot.revision,words:{...snapshot.words}};
       const confirmed=new Set(ackIds);
       for(const [word,operation] of Object.entries(record.pending))if(confirmed.has(operation.id))delete record.pending[word];
       tx.objectStore('users').put(record,userId);setResult(record);
      }));
     },
     clearUser(userId){
      return transaction(['users','meta'],'readwrite',({tx,get,setResult})=>{
       get('users',userId,record=>{
        const pending=record?Object.keys(record.pending).length:0;
        if(!pending)tx.objectStore('users').delete(userId);
        setResult({pending});
       });
       get('meta','active',active=>{if(active&&active.id===userId)tx.objectStore('meta').delete('active');});
      });
     },
     lease(name,owner,expiresAt,now=Date.now()){
      return transaction(['meta'],'readwrite',({tx,get,setResult})=>get('meta','lease:'+name,lease=>{
       if(lease&&lease.owner!==owner&&lease.expiresAt>now){setResult(false);return;}
       tx.objectStore('meta').put({owner,expiresAt},'lease:'+name);setResult(true);
      }));
     },
     release(name,owner){
      return transaction(['meta'],'readwrite',({tx,get})=>get('meta','lease:'+name,lease=>{
       if(lease&&lease.owner===owner)tx.objectStore('meta').delete('lease:'+name);
      }));
     }
    };
    resolve(store);
   };
  });
 }
 root.openOfflineStore=openOfflineStore;
 if(typeof module!=='undefined'&&module.exports)module.exports={openOfflineStore};
})(typeof globalThis!=='undefined'?globalThis:this);
