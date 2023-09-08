# -*- encoding: utf-8 -*-
from collections import defaultdict
from io import BytesIO
from copy import deepcopy
from typing import Dict, List, Set
from functools import partial

from bs4 import BeautifulSoup
import requests

from ..general import BaseSwitch, PortId, PvidConfig, SingleVlanConfig, VlanConfig, VlanId, VlanPortMembership
from .consts import *
from .utils import password_kdf, simple_slug


BeautifulSoup = partial(BeautifulSoup, features="html.parser")


def vlan_ports_to_config_string(vlan_ports_settings: SingleVlanConfig):
    """vlan_ports_settings must contain all ports"""
    pids = sorted(vlan_ports_settings.keys())
    string = ''.join(map(str, [vlan_ports_settings[pid] for pid in pids]))
    return string


class SwitchSession(requests.Session):
    def __init__(self, address: str) -> None:
        self.__address = address
        super().__init__()

    def get(self, url: str, *args, **kwargs):
        url = self.__address + url
        if url.endswith('..'):
            url = url[:-1] + 'htm'
        return super().get(url, *args, **kwargs)

    def post(self, url: str, *args, **kwargs):
        url = self.__address + url
        if url.endswith('..'):
            url = url[:-1] + 'cgi'
        return super().post(url, *args, **kwargs)


class Switch(BaseSwitch):
    _port_count: int = 8  # gs108ev3 has 8 ports each

    def __init__(self, address: str, password: str):
        if address.startswith('http'):
            self._address = address
        else:
            self._address = 'http://' + address

        self._password = password

        self._s = SwitchSession(self._address)  # a wrapper, makes url cleaner
        self._session_hash = None

    def login(self):
        res = self._s.get(SW_LOGIN)
        soup = BeautifulSoup(res.text)
        random_number = soup.find(id=SW_FORM_RAND_ID).get('value', None)
        assert isinstance(random_number, str), "Cannot get salt/rand from form data, so cannot login!"

        hashed_password = password_kdf(self._password, random_number)
        login_form = {'password': hashed_password}
        res = self._s.post(SW_LOGIN, data=login_form)
        soup = BeautifulSoup(res.text)
        err_msg = soup.find(id=SW_FORM_ERRMSG_ID)
        assert err_msg == None, f"Login error: {err_msg.get('value')}"
        assert 'top.location.href = "index.htm";' in res.text, "Unable to login!"

        res = self._s.get(SW_INFO)  # cache the session hash
        soup = BeautifulSoup(res.text)
        session_hash = soup.find('input', id='hash').get('value', None)
        self._session_hash = session_hash
        assert isinstance(self._session_hash, str), "Cannot get a valid session hash!"

    def logout(self):
        self._session_hash = None
        # logout don't have to succeed
        self._s.get(SW_LOGOUT)

    def backup(self) -> bytes:
        r = self._s.get(SW_BACKUP)
        r.raise_for_status()
        data = bytes()
        for i in r.iter_content():
            data += i
        return data

    def restore(self, config: bytes):
        file_size = len(config)
        res = self._s.get(SW_RESTORE)
        soup = BeautifulSoup(res.text)
        file_size_limit = int(soup.find(id='configSize').get('value'))
        assert file_size <= file_size_limit, "Config binary too large({file_size} > {file_size_limit}), check your data!"

        form_data = {'hash': self._session_hash}
        config_file = BytesIO(config)
        files = {'backup.cfg': config_file}
        res = self._s.post(SW_RESTORE, data=form_data, files=files)
        res.raise_for_status()
        soup = BeautifulSoup(res.text)
        if err_msg := soup.find(id=SW_FORM_ERRMSG_ID):
            err_msg = err_msg.get('value', '')
            assert len(err_msg) == 0, f"Restore config error: {err_msg}"
        elif SW_RESTORE_NOTICE in res.text:
            print("Config uploaded, device is restarting. You must relogin. Logging out now.")
            self.logout()

    def fetch_information(self) -> Dict[str, str]:
        # changable, find by tag and etc.
        _changable_keys = [
            "Switch Name",  # input, id=switch_name, value
            "DHCP Mode",  # id=dhcp_mode, value = 0 disable, 1 enable
        ]

        # read-only, need prior knowledge of html structure. td, text=key, next td, text
        _nonchangable_keys = [
            "Serial Number",
            "MAC Address",
            "Bootloader Version",
            "Firmware Version",
        ]

        # may changable, but not required at all
        # for simplicity, skipped
        # ip_address: str  # IP Address
        # subnet_mask: str  # Subnet Mask
        # gateway_address: str  # Gateway Address

        data = dict()

        text = self._s.get(SW_INFO).text
        soup = BeautifulSoup(text)

        for key in _changable_keys:
            slug = simple_slug(key)
            value = soup.find('input', id=slug).get('value', 'not found')
            data[key] = value

        for key in _nonchangable_keys:
            comp = soup.find('td', string=key)
            value = comp.find_next('td').text
            data[key] = value

        return data

    def _get_current_vlans(self):
        vlans = set()
        res = self._s.get(SW_8021Q_MEMBERSHIP)
        soup = BeautifulSoup(res.text)
        # get all listed vlans, which each has an option
        selection = soup.find('select', id='vlanIdOption')
        for op in selection.find_all('option'):
            value = VlanId(op.get('value', None))
            if value != None:
                vlans.add(value)
        return vlans

    def fetch_vlan_membership(self) -> VlanConfig:
        vlans = self._get_current_vlans()
        vlan_config: VlanConfig = dict()
        for vid in map(VlanId, vlans):
            vlan_config[vid] = self._load_vlan_by_id(vid)
        return vlan_config

    def _load_vlan_by_id(self, vid: VlanId) -> SingleVlanConfig:
        data = {
            'VLAN_ID': vid,
            'hash': self._session_hash,
        }
        res = self._s.post(SW_8021Q_MEMBERSHIP, data=data)
        soup = BeautifulSoup(res.text)
        current_id = soup.find('input', attrs={'name': "VLAN_ID_HD"}).get('value')
        assert current_id == str(vid), f"Unexpected error, cannot fetch vlan{vid} data, get vlan{current_id}."
        # port settings are in a string formed like "12122223"
        port_settings: str = soup.find('input', id='hiddenMem').get("value", None)
        settings_dict = {
            idx: VlanPortMembership(int(state))
            for idx, state in enumerate(port_settings, start=1)
        }
        return settings_dict

    def fetch_pvids(self) -> PvidConfig:
        res = self._s.get(SW_8021Q_PVIDS)
        soup = BeautifulSoup(res.text)
        pvids: PvidConfig = dict()
        for port in soup.find_all('tr', attrs={'class': 'portID'}):
            pvid = VlanId(port.find('td', attrs={'class': 'def', 'sel': 'input'}).text)
            pid = PortId(port.find('input', attrs={'type': 'hidden'}).get('value'))
            pvids[pid] = pvid
        return pvids

    def apply_vlan_config(self, membership: VlanConfig, pvids: PvidConfig):
        self._apply_vlan_settings(membership, pvids)

    def _apply_vlan_settings(self, membership: VlanConfig, pvids: PvidConfig):
        port_count_plus_1 = self._port_count + 1

        old_vlans = self.fetch_vlan_membership()
        new_vlans = membership
        old_pvids = self.fetch_pvids()
        new_pvids = pvids

        active_ports = set()
        for m in membership.values():
            for p, s in m.items():
                if s != VlanPortMembership.IGNORED:
                    active_ports.add(p)
        # These are the ports ommitted/always IGNORED in the VlanConfig
        ports_preserved = set(range(1,port_count_plus_1)) - active_ports

        # check VLAN changes
        vids_old: Set[VlanId] = set(old_vlans.keys())
        vids_new: Set[VlanId] = set(new_vlans.keys())
        vids_to_add = vids_new - vids_old
        vids_to_remove = vids_old - vids_new

        # track port membership changes
        # step1: add more T or U
        # step2: remove existing T or U
        step1_membership: VlanConfig = dict()
        step2_membership: VlanConfig = dict()
        for vid in vids_to_add:
            # newly created, just add in step1
            step1_membership[vid] = deepcopy(new_vlans[vid])
        for vid in vids_to_remove:
            # removed, just clear all in step2
            step2_membership[vid] = {i: VlanPortMembership.IGNORED for i in range(1, port_count_plus_1)}
        for vid in vids_new & vids_old:
            # modifiy
            # enable all T, U in both old and new
            old_membership = old_vlans[vid]
            merged_membership: SingleVlanConfig = {i: VlanPortMembership.IGNORED for i in range(1, port_count_plus_1)}
            for pid, new_port_membership in new_vlans[vid].items():
                old_port_membership = old_membership[pid]
                # NOTE: here min relies on IntEnum and its order
                merged_membership[pid] = min(new_port_membership, old_port_membership)
            step1_membership[vid] = merged_membership
            # then continue to expected setup
            step2_membership[vid] = deepcopy(new_vlans[vid])

        # preserved ports, only because they need a pvid but not assigned by user
        # - remove their pvids from vids_to_remove,
        # - copy its original membership on vlan[pvid] to new config
        vids_to_preserve: Set[VlanId] = set()
        for port_id in ports_preserved:
            pvid = old_pvids[port_id]
            vids_to_preserve.add(pvid)
            # the pvid must exist as a vid in VlanConfig, because all vids are processed,
            # and old pvid must be one of the vids.
            step2_membership[pvid][port_id] = old_vlans[pvid][port_id]

        vids_to_remove -= vids_to_preserve

        # transpose the new_pvids, so it can be processed in batch
        new_vpids: Dict[VlanId, List[PortId]] = defaultdict(lambda: list())
        for pid, vid in new_pvids.items():
            new_vpids[vid].append(pid)
        new_vpids = dict(new_vpids)  # make it a plain dict

        # what we have now:
        # - vids_to_add
        # - step1_membership
        # - new_vpids
        # - step2_membership
        # - vids_to_remove
        # debug:
        # print("======")
        # print(vids_to_add)
        # print(step1_membership)
        # print(new_vpids)
        # print(step2_membership)
        # print(vids_to_remove)
        # print("======")
        # return  # now testing
        for vid in vids_to_add:
            self._add_vlan(vid)
        for vid, membership in step1_membership.items():
            membership_string = vlan_ports_to_config_string(membership)
            self._set_vlan_membership(vid, membership_string)
        for vid, pids in new_vpids.items():
            self._set_ports_pvid(pids, vid)
        for vid, membership in step2_membership.items():
            membership_string = vlan_ports_to_config_string(membership)
            self._set_vlan_membership(vid, membership_string)
        self._delete_vlans(list(vids_to_remove))

    def _get_vlan_count(self):
        res = self._s.get(SW_8021Q_CFG)
        soup = BeautifulSoup(res.text)
        vlan_num = soup.find('input', attrs={'name': 'vlanNum'}).get('value')
        return int(vlan_num)

    def _add_vlan(self, vid: VlanId):
        vlanNum = self._get_vlan_count()
        data = {
            'status': 'Enable',  # doesn't matter, but required
            'hiddVlan': '',  # doesn't matter, but required
            'ADD_VLANID': vid,
            'vlanNum': vlanNum,
            'hash': self._session_hash,
            'ACTION': "Add",
        }
        res = self._s.post(SW_8021Q_CFG, data=data)
        soup = BeautifulSoup(res.text)
        err_msg = soup.find(id=SW_FORM_ERRMSG_ID).get('value', '')
        assert len(err_msg) == 0, f"Add VLAN error: {err_msg}"

    def _delete_vlans(self, vids: List[VlanId]):
        vlanNum = self._get_vlan_count()
        current_vlans = sorted(self._get_current_vlans())
        form = {
            'status': "Enable",
            'hiddVlan': '',
            'ADD_VLANID': '',
            'vlanNum': vlanNum,
            'hash': self._session_hash,
            'ACTION': "Delete",
        }
        for v in vids:
            try:
                vid_index = current_vlans.index(v)  # this index must match or Web UI will break
            except:
                print(f"VLAN{v} not found in current database, will not delete VLAN{v}.")
                continue
            # again, index must match vid, or UI will break
            key = f'vlanck{vid_index}'
            form[key] = v

        res = self._s.post(SW_8021Q_CFG, data=form)
        soup = BeautifulSoup(res.text)
        err_msg = soup.find(id=SW_FORM_ERRMSG_ID).get('value', '')
        assert len(err_msg) == 0, f"Delete VLAN error: {err_msg}"

    def _set_vlan_membership(self, vid: VlanId, membership: str):
        """ports_membership is a string like '12321333'.
        1: UNTAGGED
        2: TAGGED
        3: IGNORE
        This is consistent with VlanPortMembership(IntEnum)."""
        assert (lm := len(membership)) == self._port_count, \
            f"Ports membership string's length must be the number of ports available! Expect {self._port_count}, but got {lm}"
        form = {
            'VLAN_ID': vid,
            'VLAN_ID_HD': vid,
            'hash': self._session_hash,
            'hiddenMem': membership, }
        res = self._s.post(SW_8021Q_MEMBERSHIP, data=form)
        err_msg = BeautifulSoup(res.text).find(id=SW_FORM_ERRMSG_ID).get('value', '')
        assert len(err_msg) == 0, f"Set ports membership failed! Msg: {err_msg}"

    def _set_ports_pvid(self, ports: List[PortId], vid: VlanId):
        form = {
            'pvid': vid,
            'hash': self._session_hash, }
        for pid in ports:
            assert 1 <= pid <= self._port_count, f"Port index out of range, expect 1 <= pid <= {self._port_count}"
            form[f'port{pid}'] = 'checked'
        res = self._s.post(SW_8021Q_PVIDS, data=form)
        err_msg = BeautifulSoup(res.text).find(id=SW_FORM_ERRMSG_ID).get('value', '')
        assert len(err_msg) == 0, f"Set port vlan id failed! Msg: {err_msg}"

    def fetch_statistics(self) -> Dict:
        return super().fetch_statistics()

def init_switch(address: str, password: str) -> Switch:
    pass