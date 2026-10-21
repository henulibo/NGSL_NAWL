"""Exercise real HTTP account and progress boundaries with isolated databases."""
import sqlite3
import pytest
from fastapi.testclient import TestClient
from server.app import create_app

PASSWORD = 'test-password-2468'
ORIGIN = 'https://testserver'

@pytest.fixture
def env(tmp_path):
    clock = [1000.0]
    app = create_app(tmp_path / 'study.db', origin=ORIGIN, secure_cookie=True, clock=lambda: clock[0])
    admin = app.state.db.create_user('admin', PASSWORD, 'admin')
    alice = app.state.db.create_user('alice', PASSWORD)
    bob = app.state.db.create_user('bob', PASSWORD)
    return app, tmp_path, clock, admin, alice, bob

def login(app, username='alice', password=PASSWORD):
    client = TestClient(app, base_url=ORIGIN, follow_redirects=False)
    response = client.post('/api/auth/login', json={'username':username,'password':password}, headers={'Origin':ORIGIN})
    assert response.status_code == 200, response.text
    client.headers.update({'Origin':ORIGIN,'X-CSRF-Token':client.get('/api/me').json()['csrf']})
    return client

def mark(client, word='NGSL:child', status='known'):
    return client.patch('/api/progress', json={'word_id':word,'status':status})

def test_users_are_isolated_and_only_admin_can_manage(env):
    app,*_ = env
    a,b = login(app),login(app,'bob')
    assert mark(a).status_code == 200
    assert b.get('/api/progress').json()['words'] == {}
    assert b.get('/api/admin/users').status_code == 403
    assert b.post('/api/admin/users',json={'username':'charlie','password':PASSWORD}).status_code == 403
    assert a.patch('/api/progress',json={'word_id':'NGSL:child','status':'review','user_id':3}).status_code == 422
    admin=login(app,'admin')
    assert admin.post('/api/admin/users',json={'username':'charlie','password':PASSWORD}).status_code == 201
    assert login(app,'charlie').get('/api/progress').json()['words'] == {}

def test_two_devices_merge_different_words_and_same_word_last_write_wins(env):
    app,*_=env
    a,b=login(app),login(app)
    assert mark(a).status_code==200
    result=mark(b,'NGSL:the','review').json()
    assert result['words']=={'NGSL:child':'known','NGSL:the':'review'}
    assert result['revision']==2
    assert mark(a,status='review').json()['revision']==3
    assert b.get('/api/progress').json()['words']['NGSL:child']=='review'
    assert mark(b,status='new').status_code==200
    assert 'NGSL:child' not in a.get('/api/progress').json()['words']

def test_stale_import_conflicts_and_does_not_erase_newer_progress(env):
    app,*_=env
    a,b=login(app),login(app)
    previous=a.get('/api/progress').json()['revision']
    mark(b)
    response=a.post('/api/progress/import',json={'words':{'NGSL:the':'review'},'revision':previous})
    assert response.status_code==409
    assert a.get('/api/progress').json()['words']=={'NGSL:child':'known'}
    revision=a.get('/api/progress').json()['revision']
    response=a.post('/api/progress/import',json={'words':{'NGSL:the':'review'},'revision':revision})
    assert response.status_code==200
    assert response.json()['words']=={'NGSL:the':'review'}

def test_disable_and_reset_revoke_all_sessions(env):
    app,_,_,admin_id,alice_id,bob_id=env
    admin=login(app,'admin');a,b=login(app),login(app)
    assert admin.post(f'/api/admin/users/{alice_id}/password',json={'password':'replacement-password-123'}).status_code==200
    assert a.get('/api/me').status_code==401 and b.get('/api/me').status_code==401
    fresh=login(app,password='replacement-password-123')
    assert admin.patch(f'/api/admin/users/{alice_id}',json={'active':False}).status_code==200
    assert fresh.get('/api/me').status_code==401
    assert admin.patch(f'/api/admin/users/{admin_id}',json={'active':False}).status_code==400

def test_password_change_and_logout_invalidate_session(env):
    app,*_=env
    a,b=login(app),login(app)
    assert a.post('/api/password',json={'current_password':'wrong-password','new_password':'changed-password-123'}).status_code==400
    assert a.post('/api/password',json={'current_password':PASSWORD,'new_password':'changed-password-123'}).status_code==200
    assert b.get('/api/me').status_code==401
    c=login(app,password='changed-password-123')
    assert c.post('/api/auth/logout').status_code==200
    assert c.get('/api/me').status_code==401

def test_origin_csrf_and_cookie_flags(env):
    app,*_=env
    a=login(app)
    cookie=a.cookies.get('ielts_session')
    client=TestClient(app,base_url=ORIGIN)
    client.cookies.set('ielts_session',cookie)
    assert mark(client).status_code==403
    client.headers.update({'X-CSRF-Token':a.headers['X-CSRF-Token'],'Origin':'https://evil.example'})
    assert mark(client).status_code==403
    response=TestClient(app,base_url=ORIGIN).post('/api/auth/login',json={'username':'alice','password':PASSWORD},headers={'Origin':'https://evil.example'})
    assert response.status_code==403
    response=a.post('/api/auth/login',json={'username':'alice','password':PASSWORD})
    header=response.headers['set-cookie'].lower()
    assert 'httponly' in header and 'secure' in header and 'samesite=lax' in header
    assert a.get('/api/me').headers['cache-control']=='no-store'

def test_expiry_and_login_rate_limit(env):
    app,_,clock,*_=env
    a=login(app);clock[0]+=8*86400
    assert a.get('/api/me').status_code==401
    bad=TestClient(app,base_url=ORIGIN)
    codes=[bad.post('/api/auth/login',json={'username':'alice','password':'wrong-password'}).status_code for _ in range(8)]
    assert codes[-1]==429 and 401 in codes

def test_input_limits_and_validation_never_echo_password(env):
    app,*_=env
    a=login(app)
    assert mark(a,'unknown:word').status_code==422
    assert mark(a,status='unexpected').status_code==422
    response=a.post('/api/admin/users',json={'username':'x','password':'short-secret'})
    assert 'short-secret' not in response.text
    assert a.post('/api/auth/login',content='x'*300000,headers={'Content-Type':'application/json'}).status_code==413
    assert a.post('/api/progress/import',json={'words':{'NGSL:the':'garbage'},'revision':0}).status_code==422

def test_persistence_and_online_backup(env):
    app,folder,*_=env
    a=login(app);mark(a)
    backup=folder/'backup.db'
    app.state.db.backup(backup)
    reopened=create_app(folder/'study.db',origin=ORIGIN,secure_cookie=True)
    assert login(reopened).get('/api/progress').json()['words']=={'NGSL:child':'known'}
    restored=create_app(backup,origin=ORIGIN,secure_cookie=True)
    assert login(restored).get('/api/progress').json()['words']=={'NGSL:child':'known'}
    with sqlite3.connect(backup) as db:
        stored=db.execute('SELECT password_hash FROM users WHERE username=?',('alice',)).fetchone()[0]
        assert PASSWORD not in stored
        token=db.execute('SELECT token_hash FROM sessions LIMIT 1').fetchone()[0]
        assert token!=a.cookies.get('ielts_session')

def test_page_guard_and_private_files_are_not_served(env):
    app,*_=env
    anonymous=TestClient(app,base_url=ORIGIN,follow_redirects=False)
    assert anonymous.get('/').status_code==303
    assert anonymous.get('/api/me').status_code==401
    assert anonymous.get('/healthz').status_code==200
    assert anonymous.get('/.env').status_code==404
    assert anonymous.get('/.git/config').status_code==404
    assert anonymous.get('/server/db.py').status_code==404


def test_non_ascii_csrf_is_rejected_without_server_error(env):
    app,*_=env
    a=login(app)
    response=a.patch('/api/progress',json={'word_id':'NGSL:child','status':'known'},headers=[(b'x-csrf-token',b'\xff')])
    assert response.status_code==403


def test_parallel_login_failures_are_limited(env,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import time
    import threading
    app,*_=env
    def slow_failure(*args):
        time.sleep(0.5)
        return None
    monkeypatch.setattr(app.state.db,'authenticate',slow_failure)
    barrier=threading.Barrier(8)
    def attempt(_):
        client=TestClient(app,base_url=ORIGIN)
        barrier.wait()
        return client.post('/api/auth/login',json={'username':'alice','password':'wrong-password'}).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes=list(pool.map(attempt,range(8)))
    assert codes.count(401)<=5
    assert 429 in codes


def test_progress_read_rejects_a_previous_tabs_session(env):
    app, *_ = env
    client = login(app, 'alice')
    old_csrf = client.headers['X-CSRF-Token']
    # Logging into a second account replaces the shared browser cookie.
    response = client.post('/api/auth/login', json={'username': 'bob', 'password': PASSWORD})
    assert response.status_code == 200
    response = client.get('/api/progress', headers={'X-CSRF-Token': old_csrf})
    assert response.status_code == 403


def test_offline_batch_retries_do_not_replay_after_another_device_changes_word(env):
    app, *_ = env
    a, device = login(app), login(app)
    body={'operations':[{'id':'offline-operation-0001','word_id':'NGSL:child','status':'known','device_id':'offline-device-0001','sequence':1},
                        {'id':'offline-operation-0002','word_id':'NGSL:the','status':'review','device_id':'offline-device-0001','sequence':2}]}
    first=a.post('/api/progress/sync',json=body)
    assert first.status_code==200
    assert first.json()['words']=={'NGSL:child':'known','NGSL:the':'review'}
    assert first.json()['acknowledged']==['offline-operation-0001','offline-operation-0002']
    mark(device,'NGSL:child','review')
    revision=device.get('/api/progress').json()['revision']
    retried=a.post('/api/progress/sync',json=body)
    assert retried.status_code==200
    assert retried.json()['revision']==revision
    assert retried.json()['words']['NGSL:child']=='review'


def test_offline_operations_are_user_scoped_and_reused_id_is_atomic(env):
    app, *_ = env
    a,b=login(app),login(app,'bob')
    operation={'id':'offline-operation-0003','word_id':'NGSL:child','status':'known','device_id':'offline-device-0001','sequence':1}
    assert a.post('/api/progress/sync',json={'operations':[operation]}).status_code==200
    operation['status']='review'
    assert b.post('/api/progress/sync',json={'operations':[operation]}).status_code==200
    before=a.get('/api/progress').json()
    invalid=[{'id':'offline-operation-0004','word_id':'NGSL:the','status':'known','device_id':'offline-device-0001','sequence':2},operation]
    assert a.post('/api/progress/sync',json={'operations':invalid}).status_code==400
    assert a.get('/api/progress').json()==before
    assert b.get('/api/progress').json()['words']=={'NGSL:child':'review'}


def test_offline_batch_validation_permissions_and_new_status(env):
    app, *_ = env
    a=login(app)
    op={'id':'offline-operation-0005','word_id':'NGSL:child','status':'known','device_id':'offline-device-0001','sequence':1}
    for body in [{'operations':[]},{'operations':[op]*201},{'operations':[op],'user_id':1},
                 {'operations':[op|{'word_id':'NO:word'}]},{'operations':[op|{'id':'short'}]}]:
        assert a.post('/api/progress/sync',json=body).status_code==422
    assert a.post('/api/progress/sync',json={'operations':[op]},headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert a.post('/api/progress/sync',json={'operations':[op]}).status_code==200
    assert a.post('/api/progress/sync',json={'operations':[op|{'id':'offline-operation-0006','status':'new','sequence':2}]}).json()['words']=={}


def test_late_request_from_same_browser_cannot_undo_a_newer_operation(env):
    app,*_=env
    a=login(app)
    newer={'id':'offline-operation-0008','word_id':'NGSL:child','status':'review','device_id':'offline-device-0001','sequence':2}
    assert a.post('/api/progress/sync',json={'operations':[newer]}).status_code==200
    previous=a.get('/api/progress').json()
    older=newer|{'id':'offline-operation-0007','status':'known','sequence':1}
    result=a.post('/api/progress/sync',json={'operations':[older]})
    assert result.status_code==200
    assert result.json()['words']=={'NGSL:child':'review'}
    assert result.json()['revision']==previous['revision']
    assert result.json()['acknowledged']==['offline-operation-0007']


def test_service_worker_scope_and_authenticated_offline_shell(env):
    app,*_=env
    anonymous=TestClient(app,base_url=ORIGIN,follow_redirects=False)
    assert anonymous.get('/offline-shell').status_code==303
    worker=anonymous.get('/service-worker.js')
    assert worker.status_code==200
    assert worker.headers['service-worker-allowed']=='/'
    assert 'javascript' in worker.headers['content-type']
    assert '__CACHE_VERSION__' not in worker.text
    a=login(app);shell=a.get('/offline-shell')
    assert shell.status_code==200 and shell.headers['x-workbook-version']
    assert 'worker-src' in shell.headers['content-security-policy']
    for name in ['offline-store.js','offline-client.js','offline-resources.js']:
        assert anonymous.get('/assets/'+name).status_code==200


def test_stale_asset_version_is_rejected_and_cache_resources_are_version_stamped(env):
    app,*_=env
    a=login(app);version=a.get('/offline-shell').headers['x-workbook-version']
    for route in ['/login','/assets/cloud.js']:
        assert a.get(route).headers['x-workbook-version']==version
    assert a.get('/assets/cloud.js?v=older-release').status_code==409
    assert a.get('/login?v=older-release').status_code==409
    assert a.get('/offline-shell?v=older-release').status_code==409
