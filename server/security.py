"""Password hashing and bounded login throttling; no plaintext credentials stored."""
import base64
import hashlib
import hmac
import secrets
import threading
from collections import OrderedDict, deque

_HASH_SLOTS = threading.BoundedSemaphore(4)

def password_hash(password: str) -> str:
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('密码须为 12–128 个字符')
    salt = secrets.token_bytes(16)
    with _HASH_SLOTS:
        digest = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=1, maxmem=64*1024*1024)
    return 'scrypt$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(digest).decode()

def verify_password(password: str, encoded: str) -> bool:
    if not isinstance(password, str) or len(password) > 128:
        return False
    try:
        algorithm, salt, expected = encoded.split('$')
        if algorithm != 'scrypt':
            return False
        with _HASH_SLOTS:
            digest = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=32768, r=8, p=1, maxmem=64*1024*1024)
        return hmac.compare_digest(digest, base64.b64decode(expected))
    except (ValueError, TypeError):
        return False

def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()

class LoginLimiter:
    """Bounded per-IP failed-login window for the single application worker."""
    def __init__(self):
        self.attempts = OrderedDict()
        self.lock = threading.Lock()

    def begin(self, address: str, now: float):
        # Reserve a slot before verification so parallel failures cannot all
        # pass a check performed against the same pre-failure counter.
        with self.lock:
            queue=self.attempts.setdefault(address,deque())
            while queue and queue[0][0]<=now-60:
                queue.popleft()
            self.attempts.move_to_end(address)
            while len(self.attempts)>4096:
                self.attempts.popitem(last=False)
            if len(queue)>=5:
                return None
            token=secrets.token_hex(8)
            queue.append((now,token))
            return token

    def succeeded(self, address: str, token: str):
        with self.lock:
            queue=self.attempts.get(address)
            if queue is not None:
                self.attempts[address]=deque(item for item in queue if item[1]!=token)
