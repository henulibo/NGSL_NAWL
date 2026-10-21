"""HTTP account and progress API for the vocabulary workbook."""
import hmac
import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from .db import Database, ProgressConflict, public_user
from .security import LoginLimiter, password_hash, verify_password

ROOT=Path(__file__).resolve().parents[1]
COOKIE='ielts_session'
MAX_BODY=256*1024
DUMMY_HASH=password_hash('non-user-dummy-password-2468')

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class Credentials(Input):
    username: str=Field(min_length=3,max_length=32,pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    password: str=Field(min_length=1,max_length=128)

class NewUser(Credentials):
    password: str=Field(min_length=12,max_length=128)

class WordChange(Input):
    word_id: str=Field(max_length=150)
    status: Literal['known','review','new']

class ImportProgress(Input):
    words: dict[str,Literal['known','review']]
    revision: int=Field(ge=0)

class SyncOperation(WordChange):
    id: str=Field(min_length=16,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    device_id: str=Field(min_length=16,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    sequence: int=Field(ge=1,le=9007199254740991)

class SyncProgress(Input):
    operations: list[SyncOperation]=Field(min_length=1,max_length=200)

class Activation(Input):
    active: bool

class NewPassword(Input):
    password: str=Field(min_length=12,max_length=128)

class PasswordChange(Input):
    current_password: str=Field(min_length=1,max_length=128)
    new_password: str=Field(min_length=12,max_length=128)

class RequestBoundary:
    """Cap streaming bodies before parsing and reject cross-origin writes."""
    def __init__(self,app,origin):
        self.app=app;self.origin=origin
    async def __call__(self,scope,receive,send):
        if scope['type']!='http':
            return await self.app(scope,receive,send)
        headers={k.decode('latin-1').lower():v.decode('latin-1') for k,v in scope.get('headers',[])}
        unsafe=scope['method'] not in ('GET','HEAD','OPTIONS')
        if unsafe and headers.get('origin') not in (None,self.origin):
            return await JSONResponse({'detail':'请求来源不匹配'},status_code=403)(scope,receive,send)
        try:
            declared=int(headers.get('content-length','0'))
        except ValueError:
            return await JSONResponse({'detail':'请求长度无效'},status_code=400)(scope,receive,send)
        if declared<0 or declared>MAX_BODY:
            return await JSONResponse({'detail':'请求内容过大'},status_code=413)(scope,receive,send)
        messages=[];size=0
        if unsafe:
            while True:
                event=await receive()
                if event['type']=='http.disconnect':
                    return
                size+=len(event.get('body',b''))
                if size>MAX_BODY:
                    return await JSONResponse({'detail':'请求内容过大'},status_code=413)(scope,receive,send)
                messages.append(event)
                if not event.get('more_body',False):
                    break
            if size and headers.get('content-type','').split(';')[0].lower()!='application/json':
                return await JSONResponse({'detail':'请提交 JSON 请求'},status_code=415)(scope,receive,send)
        async def replay():
            if messages:
                return messages.pop(0)
            return await receive()
        async def response_send(event):
            if event['type']=='http.response.start':
                event.setdefault('headers',[]).extend([
                    (b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),
                    (b'x-frame-options',b'DENY'),(b'referrer-policy',b'same-origin')])
            await send(event)
        await self.app(scope,replay,response_send)


def create_app(db_path=None, *, origin=None, secure_cookie=True, static_dir=None, clock=time.time):
    origin=(origin or os.environ.get('APP_ORIGIN','https://study.example.com')).rstrip('/')
    db=Database(db_path or os.environ.get('DATABASE_PATH','/data/study.db'))
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    app.state.db=db;app.state.clock=clock
    limiter=LoginLimiter()
    rows=json.loads((ROOT/'vocab-data/study-data.json').read_text())
    allowed={name+':'+r['word'] for name,words in rows.items() for r in words}
    static=Path(static_dir or ROOT/'server/static')
    web=ROOT/'server/web/index.html'
    workbook=web.read_text() if web.exists() else None
    version_file=ROOT/'server/web/version.txt'
    version=version_file.read_text().strip() if version_file.exists() else 'unbuilt'
    app.add_middleware(RequestBoundary,origin=origin)

    @app.exception_handler(RequestValidationError)
    async def bad_input(request,exc):
        # Validation diagnostics must not echo submitted passwords.
        return JSONResponse({'detail':'输入格式不正确，请检查用户名、密码或进度内容'},status_code=422)

    @app.exception_handler(ValueError)
    async def invalid_operation(request,exc):
        return JSONResponse({'detail':str(exc)},status_code=400)

    @app.exception_handler(KeyError)
    async def missing_user(request,exc):
        return JSONResponse({'detail':'账号不存在'},status_code=404)

    def current(request:Request):
        user=db.session(request.cookies.get(COOKIE),clock())
        if not user:
            raise HTTPException(401,'请先登录')
        nonce=request.headers.get('x-csrf-token')
        if nonce is not None and not hmac.compare_digest(nonce.encode(),user['csrf'].encode()):
            raise HTTPException(403,'会话已变化，请刷新后重试')
        return user

    def write_user(request:Request,user=Depends(current)):
        nonce=request.headers.get('x-csrf-token','')
        if not hmac.compare_digest(nonce.encode(),user['csrf'].encode()):
            raise HTTPException(403,'会话验证失败，请刷新后重试')
        return user

    def admin_read(user=Depends(current)):
        if user['role']!='admin':
            raise HTTPException(403,'仅管理员可管理账号')
        return user

    def admin_write(user=Depends(write_user)):
        if user['role']!='admin':
            raise HTTPException(403,'仅管理员可管理账号')
        return user

    def check_words(words):
        if any(key not in allowed for key in words):
            raise HTTPException(422,'进度包含未收录的词条')

    def page(text):
        nonce=secrets.token_urlsafe(18)
        text=re.sub(r'((?:src|href)=["\'])(/assets/[^"\'?]+)(["\'])',lambda match:match[1]+match[2]+'?v='+version+match[3],text)
        html=text.replace('<script',f'<script nonce="{nonce}"')
        return HTMLResponse(html,headers={'X-Workbook-Version':version,'Content-Security-Policy':
            f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; worker-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"})

    @app.get('/healthz')
    def health():
        with db.connection() as conn:
            conn.execute('SELECT 1')
        return {'status':'ok'}

    def check_version(request):
        requested=request.query_params.get('v')
        if requested is not None and requested!=version:
            raise HTTPException(409,'资源版本已更新，请联网刷新页面')

    @app.get('/login')
    def login_page(request:Request):
        check_version(request)
        return page((static/'login.html').read_text())

    @app.get('/')
    @app.get('/offline-shell')
    def study_page(request:Request):
        check_version(request)
        if not db.session(request.cookies.get(COOKIE),clock()):
            return RedirectResponse('/login',status_code=303)
        if workbook is None:
            raise HTTPException(503,'学习页面尚未构建')
        return page(workbook)

    @app.get('/account')
    def account_page(request:Request):
        if not db.session(request.cookies.get(COOKIE),clock()):
            return RedirectResponse('/login',status_code=303)
        return page((static/'account.html').read_text())

    @app.get('/service-worker.js')
    def service_worker():
        worker=ROOT/'server/web/service-worker.js'
        if not worker.exists():
            raise HTTPException(503,'离线资源尚未构建')
        return Response(worker.read_text(),media_type='application/javascript',headers={'Service-Worker-Allowed':'/'})

    @app.get('/assets/{filename}')
    def asset(filename:str,request:Request):
        check_version(request)
        if filename not in {'cloud.js','sync-client.js','account.js','styles.css','offline-store.js','offline-client.js','offline-resources.js'}:
            raise HTTPException(404)
        return FileResponse(static/filename,headers={'X-Workbook-Version':version})

    @app.post('/api/auth/login')
    def login(values:Credentials,request:Request):
        address=request.client.host if request.client else 'unknown'
        now=clock()
        attempt=limiter.begin(address,now)
        if attempt is None:
            raise HTTPException(429,'登录尝试过多，请一分钟后重试',headers={'Retry-After':'60'})
        result=db.authenticate(values.username,values.password,now,DUMMY_HASH)
        if not result:
            raise HTTPException(401,'用户名或密码不正确')
        limiter.succeeded(address,attempt)
        token,csrf,user=result
        response=JSONResponse({'user':public_user(user),'csrf':csrf})
        response.set_cookie(COOKIE,token,max_age=7*86400,httponly=True,secure=secure_cookie,samesite='lax',path='/')
        return response

    @app.get('/api/me')
    def me(user=Depends(current)):
        return {'user':public_user(user),'csrf':user['csrf']}

    @app.post('/api/auth/logout')
    def logout(request:Request,user=Depends(write_user)):
        db.logout(request.cookies[COOKIE])
        response=JSONResponse({'ok':True})
        response.delete_cookie(COOKIE,path='/',secure=secure_cookie,httponly=True,samesite='lax')
        return response

    @app.post('/api/password')
    def change_password(values:PasswordChange,user=Depends(write_user)):
        db.reset_password(user['id'],values.new_password,values.current_password)
        response=JSONResponse({'ok':True})
        response.delete_cookie(COOKIE,path='/',secure=secure_cookie,httponly=True,samesite='lax')
        return response

    @app.get('/api/progress')
    def get_progress(user=Depends(current)):
        return db.progress(user['id'])

    @app.patch('/api/progress')
    def update_progress(values:WordChange,user=Depends(write_user)):
        check_words({values.word_id:values.status})
        return db.set_word(user['id'],values.word_id,values.status)

    @app.post('/api/progress/import')
    def import_progress(values:ImportProgress,user=Depends(write_user)):
        check_words(values.words)
        try:
            return db.import_progress(user['id'],values.words,values.revision)
        except ProgressConflict as exc:
            raise HTTPException(409,str(exc)) from None

    @app.post('/api/progress/sync')
    def sync_progress(values:SyncProgress,user=Depends(write_user)):
        operations=[operation.model_dump() for operation in values.operations]
        check_words({operation['word_id']:operation['status'] for operation in operations})
        return db.sync_progress(user['id'],operations)

    @app.get('/api/admin/users')
    def users(user=Depends(admin_read)):
        return {'users':db.list_users()}

    @app.post('/api/admin/users',status_code=201)
    def create_user(values:NewUser,user=Depends(admin_write)):
        user_id=db.create_user(values.username,values.password)
        return {'id':user_id,'username':values.username.lower(),'role':'user','active':True}

    @app.patch('/api/admin/users/{user_id}')
    def set_active(user_id:int,values:Activation,user=Depends(admin_write)):
        db.set_active(user_id,values.active,user['id'])
        return {'ok':True}

    @app.post('/api/admin/users/{user_id}/password')
    def reset_password(user_id:int,values:NewPassword,user=Depends(admin_write)):
        db.reset_password(user_id,values.password)
        return {'ok':True}

    return app


def application():
    return create_app(secure_cookie=os.environ.get('COOKIE_SECURE','true').lower()!='false')
