# -*- encoding: utf-8 -*-
from hashlib import md5


def _merge(str1: str, str2: str) -> str:
    result = ""
    sub1 = str1[:len(str2)]
    sub2 = str2[:len(sub1)]
    sub3 = str1[len(sub2):]
    sub4 = str2[len(sub2):]
    for z in zip(sub1, sub2):
        result += ''.join(z)
    result += sub3
    result += sub4
    return result


def password_kdf(pwd: str, salt: str) -> str:
    """hash the password to send to the switch
    pwd: password string
    salt: random number string"""
    result = _merge(pwd, salt)
    hash_data = md5(result.encode("utf-8"))
    hash_string = hash_data.digest().hex()
    return hash_string


def simple_slug(text: str):
    return text.strip().lower().replace(' ', '_')
