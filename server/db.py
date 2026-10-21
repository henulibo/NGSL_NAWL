"""SQLite transactions keep each user's progress and revision consistent."""
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from .security import password_hash, token_hash, verify_password

class ProgressConflict(Exception):
    pass

def public_user(row):
    return {key:row[key] for key in ('id','username','role')} | {'active':bool(row['active'])}

class Database:
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','user')),
              active INTEGER NOT NULL DEFAULT 1, revision INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sessions (
              token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              csrf TEXT NOT NULL, expires_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
            CREATE TABLE IF NOT EXISTS words (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              word_id TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('known','review')),
              PRIMARY KEY(user_id,word_id));
            CREATE TABLE IF NOT EXISTS sync_operations (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              operation_id TEXT NOT NULL, word_id TEXT NOT NULL, status TEXT NOT NULL,
              device_id TEXT NOT NULL, sequence INTEGER NOT NULL,
              PRIMARY KEY(user_id,operation_id));
            CREATE TABLE IF NOT EXISTS sync_cursors (
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              device_id TEXT NOT NULL, word_id TEXT NOT NULL, sequence INTEGER NOT NULL,
              PRIMARY KEY(user_id,device_id,word_id));
            ''')
        self.path.chmod(0o600)

    @contextmanager
    def connection(self, write=False):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_user(self, username, password, role='user'):
        username=username.strip().lower()
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{2,31}',username):
            raise ValueError('用户名须为 3–32 位英文字母、数字、下划线或连字符')
        if role not in ('user','admin'):
            raise ValueError('账号类型无效')
        hashed=password_hash(password)
        with self.connection(True) as db:
            try:
                cursor=db.execute('INSERT INTO users(username,password_hash,role) VALUES(?,?,?)',(username,hashed,role))
            except sqlite3.IntegrityError:
                raise ValueError('用户名已存在') from None
            return cursor.lastrowid

    def user_by_name(self, username):
        with self.connection() as db:
            row=db.execute('SELECT * FROM users WHERE username=?',(username.strip().lower(),)).fetchone()
            return dict(row) if row else None

    def list_users(self):
        with self.connection() as db:
            return [public_user(r) for r in db.execute('SELECT * FROM users ORDER BY id')]

    def authenticate(self, username, password, now, dummy_hash):
        # Verification and session creation share a write transaction: a racing
        # password reset cannot leave a valid session based on the old hash.
        token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
        with self.connection(True) as db:
            row=db.execute('SELECT * FROM users WHERE username=?',(username.strip().lower(),)).fetchone()
            valid=verify_password(password,row['password_hash'] if row else dummy_hash)
            if not valid or not row or not row['active']:
                return None
            db.execute('DELETE FROM sessions WHERE expires_at<=?',(now,))
            db.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(token),row['id'],csrf,now+7*86400))
            return token,csrf,dict(row)

    def session(self, token, now):
        if not token or len(token)>128:
            return None
        with self.connection() as db:
            row=db.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1',(token_hash(token),now)).fetchone()
            return dict(row) if row else None

    def logout(self, token):
        with self.connection(True) as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(token),))

    @staticmethod
    def _snapshot(db, user_id):
        revision=db.execute('SELECT revision FROM users WHERE id=?',(user_id,)).fetchone()['revision']
        words={row['word_id']:row['status'] for row in db.execute('SELECT word_id,status FROM words WHERE user_id=?',(user_id,))}
        return {'revision':revision,'words':words}

    def progress(self,user_id):
        with self.connection() as db:
            return self._snapshot(db,user_id)

    def set_word(self,user_id,word_id,status):
        with self.connection(True) as db:
            if status=='new':
                db.execute('DELETE FROM words WHERE user_id=? AND word_id=?',(user_id,word_id))
            else:
                db.execute('INSERT INTO words VALUES(?,?,?) ON CONFLICT(user_id,word_id) DO UPDATE SET status=excluded.status',(user_id,word_id,status))
            db.execute('UPDATE users SET revision=revision+1 WHERE id=?',(user_id,))
            return self._snapshot(db,user_id)

    def import_progress(self,user_id,words,revision):
        with self.connection(True) as db:
            current=db.execute('SELECT revision FROM users WHERE id=?',(user_id,)).fetchone()['revision']
            if current!=revision:
                raise ProgressConflict('云端进度已变化，请重新读取后确认导入')
            db.execute('DELETE FROM words WHERE user_id=?',(user_id,))
            db.executemany('INSERT INTO words VALUES(?,?,?)',[(user_id,k,v) for k,v in words.items()])
            db.execute('UPDATE users SET revision=revision+1 WHERE id=?',(user_id,))
            return self._snapshot(db,user_id)

    def sync_progress(self,user_id,operations):
        """Apply each durable client operation once, even after a lost response."""
        with self.connection(True) as db:
            applied=0
            for operation in operations:
                previous=db.execute('SELECT word_id,status,device_id,sequence FROM sync_operations WHERE user_id=? AND operation_id=?',
                                    (user_id,operation['id'])).fetchone()
                if previous:
                    if any(previous[key]!=operation[key] for key in ('word_id','status','device_id','sequence')):
                        raise ValueError('同步操作编号重复且内容不一致')
                    continue
                db.execute('INSERT INTO sync_operations VALUES(?,?,?,?,?,?)',
                           (user_id,operation['id'],operation['word_id'],operation['status'],operation['device_id'],operation['sequence']))
                cursor=db.execute('SELECT sequence FROM sync_cursors WHERE user_id=? AND device_id=? AND word_id=?',
                                  (user_id,operation['device_id'],operation['word_id'])).fetchone()
                if cursor and cursor['sequence']>=operation['sequence']:
                    continue
                db.execute('INSERT INTO sync_cursors VALUES(?,?,?,?) ON CONFLICT(user_id,device_id,word_id) DO UPDATE SET sequence=excluded.sequence',
                           (user_id,operation['device_id'],operation['word_id'],operation['sequence']))
                if operation['status']=='new':
                    db.execute('DELETE FROM words WHERE user_id=? AND word_id=?',(user_id,operation['word_id']))
                else:
                    db.execute('INSERT INTO words VALUES(?,?,?) ON CONFLICT(user_id,word_id) DO UPDATE SET status=excluded.status',
                               (user_id,operation['word_id'],operation['status']))
                applied+=1
            db.execute('UPDATE users SET revision=revision+? WHERE id=?',(applied,user_id))
            return self._snapshot(db,user_id)|{'acknowledged':[operation['id'] for operation in operations]}

    def set_active(self,user_id,active,actor_id):
        with self.connection(True) as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
            if not row:
                raise KeyError('账号不存在')
            if not active:
                if user_id==actor_id:
                    raise ValueError('不能停用当前登录的管理员')
                if row['role']=='admin' and row['active']:
                    count=db.execute("SELECT count(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]
                    if count<=1:
                        raise ValueError('不能停用最后一个有效管理员')
                db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))
            db.execute('UPDATE users SET active=? WHERE id=?',(int(active),user_id))

    def reset_password(self,user_id,password,current_password=None):
        hashed=password_hash(password)
        with self.connection(True) as db:
            row=db.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
            if not row:
                raise KeyError('账号不存在')
            if current_password is not None and not verify_password(current_password,row['password_hash']):
                raise ValueError('当前密码不正确')
            db.execute('UPDATE users SET password_hash=? WHERE id=?',(hashed,user_id))
            db.execute('DELETE FROM sessions WHERE user_id=?',(user_id,))

    def backup(self,target):
        target=Path(target)
        if target.resolve()==self.path.resolve():
            raise ValueError('备份目标不能覆盖当前数据库')
        target.parent.mkdir(parents=True,exist_ok=True)
        source=sqlite3.connect(self.path)
        destination=sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close();source.close()
        target.chmod(0o600)
