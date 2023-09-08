from collections import defaultdict
from typing import Dict, List, Set
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
    _general_info_pattern = re.compile("(?<=var sysGeneInfor = ')([A-Za-z0-9.?:-]+)(?=';)")
    _secure_rand_pattern = re.compile("(?<=var secureRand = ')([A-Z0-9]+)(?=';)")
    _vlanmem_pattern = re.compile("(?<=var vlanMem = ')([TU0-9,?]+)(?=';)")
    _pvid_pattern = re.compile("(?<=var pvid = ')[0-9?]+(?=';)")

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
        self._secure_rand = matched.group(0)

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
        res = self._s.get(SW_URI_INFO)
        matched = self._general_info_pattern.search(res.text)
        if matched == None:
            return dict()
        data_list = matched.group(0).split('?')
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

    def _enable_8021q_vlan(self):
        form_data = {
            "submitId": "vlanDot1VidCfg",
            "secureRand": self._secure_rand,
            "aDot1VLAN": "Enable",
            "changeType": "1",
            "addVid": "",
            "delVid": "0",
            "confirmOK": "0",
            "submitEnd": "",
        }
        res = self._s.post(SW_URI_8021Q_CONF, data=form_data)
        assert SW_URI_8021Q_CONF.strip('/') in res.text, "Failed to enable advanced 802.1Q VLAN! Maybe you need a re-login?"

    def fetch_vlan_membership(self) -> VlanConfig:
        res = self._s.get(SW_URI_8021Q_CONF)
        matched = self._vlanmem_pattern.search(res.text)
        assert matched != None, f"No VLAN information found! Server response: {res.text}"
        vlan_membership: VlanConfig = defaultdict(lambda: {i: VlanPortMembership.IGNORED for i in range(1, self._port_count + 1)})
        vlan_groups = matched.group(0).split(',')
        for vlan in vlan_groups:
            vlan_info = vlan.split('?')
            vid = VlanId(vlan_info[0])
            # touch each vid, so it's created even if it's empty
            vlan_membership[vid]
            for pid, v in enumerate(vlan_info[1:], 1):
                if v == 'T':
                    vlan_membership[vid][pid] = VlanPortMembership.TAGGED
                elif v == 'U':
                    vlan_membership[vid][pid] = VlanPortMembership.UNTAGGED
                # else: # v==''
                #     vlan_membership[vid][pid] = VlanPortMembership.IGNORED
        return dict(vlan_membership)

    def fetch_pvids(self) -> PvidConfig:
        res = self._s.get(SW_URI_8021Q_CONF)
        matched = self._pvid_pattern.search(res.text)
        assert matched != None, f"No PVID information found! Server response: {res.text}"
        pvids = matched.group(0).split('?')
        pvid_config: PvidConfig = {
            i: VlanId(v)
            for i, v in enumerate(pvids, 1)
        }
        return pvid_config

    def _add_vlan(self, vid: VlanId):
        form_data = {
            "submitId": "vlanDot1VidCfg",
            "secureRand": self._secure_rand,
            "addVid": vid,
            "submitEnd": "",
        }
        res = self._s.post(SW_URI_8021Q_CONF, data=form_data)
        assert SW_URI_8021Q_CONF.split('/')[-1] in res.text, \
            f"Cannot add VLAN! Server response: {res.text}"

    def _delete_vlans(self, vids: List[VlanId]):
        form_data = {
            "submitId": "vlanDot1VidCfg",
            "secureRand": self._secure_rand,
            "delVid": vids,
            "submitEnd": "",
        }
        res = self._s.post(SW_URI_8021Q_CONF, data=form_data)
        assert SW_URI_8021Q_CONF.split('/')[-1] in res.text, \
            f"Cannot delete VLAN(s)! Server response: {res.text}"

    def _set_vlan_membership(self, vid: VlanId, membership: Dict[PortId, VlanPortMembership]):
        mask_member = 0
        mask_tagged = 0

        for pid, mb in membership.items():
            if mb == VlanPortMembership.UNTAGGED:
                mask_member |= 1 << pid
            elif mb == VlanPortMembership.TAGGED:
                mask_member |= 1 << pid
                mask_tagged |= 1 << pid

        form_data = {
            'submitId': 'vlanDot1TagCfg',
            'secureRand': self._secure_rand,
            'vid': vid,
            'member': mask_member,
            'tag': mask_tagged,
            'submitEnd': '',
        }
        # Posting to SW_URI_8021Q_CONF seems ok as well.
        # Maybe the only thing matters is the form data.
        res = self._s.post(SW_URI_8021Q_MEMBERSHIP, data=form_data)
        # when succeeded, it will jump to original page
        # the parameter is the VLAN to show
        assert SW_URI_8021Q_MEMBERSHIP.split('/')[-1] + f"?{vid}" in res.text, \
            f"Cannot update VLAN membership! Server response: {res.text}"

    def _set_pvids(self, pvids: PvidConfig):
        form = [
            'submitId=vlanDot1PvidCfg',
            f'secureRand={self._secure_rand}',
        ]
        # order matters, and keys dulplicated, so we need to construct the data ourselves
        for pid, vid in pvids.items():
            form.append(f'port={pid}&pvid={vid}')
        form.append('submitEnd=')
        form_data = '&'.join(form)
        res = self._s.post(SW_URI_8021Q_PVID, data=form_data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        assert SW_URI_8021Q_PVID.split('/')[-1] in res.text, \
            f"Cannot update VLAN membership! Server response: {res.text}"
