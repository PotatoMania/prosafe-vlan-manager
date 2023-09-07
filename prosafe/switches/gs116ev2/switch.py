from typing import Dict
import re
from functools import partial

from requests import Session
from bs4 import BeautifulSoup

from .utils import password_kdf
from .consts import *
from ..general import BaseSwitch, VlanPortMembership, VlanId, PortId, PvidConfig, VlanConfig


BeautifulSoup = partial(BeautifulSoup, features="html.parser")


class SwitchSession(Session):
    def __init__(self, address: str) -> None:
        self.__address = address
        super().__init__()

    def get(self, url: str, *args, **kwargs):
        url = self.__address + url
        return super().get(url, *args, **kwargs)

    def post(self, url: str, *args, **kwargs):
        url = self.__address + url
        return super().post(url, *args, **kwargs)


class Switch(BaseSwitch):
    _port_count: int = 16
    _address: str
    _password: str
    _s: SwitchSession
    _secure_rand: str
    _general_info_pattern = re.compile("var sysGeneInfor = '([A-Za-z0-9.?-]+)';")
    _secure_rand_pattern = re.compile("var secureRand = '([A-Z0-9]+)';")

    def __init__(self, address: str, password: str) -> None:
        if address.startswith('http'):
            self._address = address
        else:
            self._address = 'http://' + address
        
        self._password = password
        self._s = SwitchSession(self._address)
    
    def login(self):
        self._s.get(SW_URI_LOGIN)
        login_form = {
            'submitId': 'pwdLogin',
            'password': password_kdf(self._password),
            'submitEnd': '',
        }
        res = self._s.post(SW_URI_LOGIN, data=login_form)
        redirect = BeautifulSoup(res.text).find('script').text.strip()
        assert SW_URI_INDEX + '?0' in redirect, \
            "Login failed, check your password!"
        
        # cache secure rand
        res = self._s.get(SW_URI_INDEX)
        matched = self._secure_rand_pattern.search(res.text)
        assert matched != None, "Secure rand can't be found in the response text! Aborting!"
        self._secure_rand = matched[1]
    
    def logout(self):
        logout_form = {
            'submitId': 'logoutBtn',
            'secureRand': self._secure_rand,
            'submitEnd': '',
        }
        res = self._s.post(SW_URI_INDEX, data=logout_form)
        res.raise_for_status()
        self._secure_rand = None
    
    def fetch_information(self) -> Dict[str, str]:
        res = self._s.get(SW_URI_INDEX)
        matched = self._general_info_pattern.search(res.text)
        if matched == None:
            return dict()
        data_list = matched[1].split('?')
        data = {
            'Product Name':     data_list[0],
            'Switch Name':      data_list[1],
            'MAC Address':      data_list[2],
            'Firmware Version': data_list[3],
            'DHCP Mode':        data_list[4],
            'IP Address':       data_list[5],
            'Subnet Mask':      data_list[6],
            'Gateway Address':  data_list[7],
            'Serial Number':    data_list[8],
        }
        return data
