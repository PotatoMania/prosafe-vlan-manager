import hmac

from hashlib import md5
from .consts import SW_HMAC_MD5_KEY


def _hex_hmac_md5(key: str, msg: str):
    return hmac.new(key.encode(), msg.encode(), md5).hexdigest()


def password_kdf(password: str):
    ext_length = len(password) + 1
    repeat_count = 2048 // ext_length
    pwd = (password + '\0') * repeat_count
    pwd += '\0' * (2048 - len(pwd))
    pwd = _hex_hmac_md5(SW_HMAC_MD5_KEY, pwd)
    return pwd
