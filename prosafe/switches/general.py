from enum import IntEnum, StrEnum
from typing import Dict
from contextlib import contextmanager


VlanId = int
PortId = int


SWITCH_PORT_COUNT = {
    'gs108ev3': 8,
    'gs116ev2': 16,
}

class SwitchModel(StrEnum):
    GS108EV3 = 'gs108ev3'
    GS116EV2 = 'gs116ev2'

    @property
    def port_count(self):
        return SWITCH_PORT_COUNT[self.value]


class VlanPortMembership(IntEnum):
    # These values are from web interface
    UNTAGGED = 1
    TAGGED = 2
    IGNORED = 3


SingleVlanConfig = Dict[PortId, VlanPortMembership]
VlanConfig = Dict[VlanId, SingleVlanConfig]
PvidConfig = Dict[PortId, VlanId]


def vlan_ports_to_config_string(vlan_ports_settings: SingleVlanConfig):
    """vlan_ports_settings must contain all ports"""
    pids = sorted(vlan_ports_settings.keys())
    string = ''.join(map(str, [vlan_ports_settings[pid] for pid in pids]))
    return string


class BaseSwitch:
    def login(self):
        raise NotImplementedError()

    def logout(self):
        raise NotImplementedError()

    @contextmanager
    def logged_in(self, *args, **kwargs):
        self.login()
        try:
            yield
        finally:
            self.logout()

    def backup(self) -> bytes:
        """Switch configs are small, modern computer can handle them at no effort"""
        raise NotImplementedError()

    def restore(self, config: bytes):
        raise NotImplementedError()

    def fetch_information(self) -> Dict[str, str]:
        """fetch basic information like switch's name, firmware version, etc."""
        raise NotImplementedError()

    def fetch_vlan_membership(self) -> VlanConfig:
        """fetch and return current switch's VLAN configuration"""
        raise NotImplementedError()
    
    def fetch_pvids(self) -> PvidConfig:
        """fetch pvids"""
        raise NotImplementedError()

    def apply_vlan_config(self, membership: VlanConfig, pvids: PvidConfig):
        """apply the given VLAN configuration
        
        the configuration must be a full configuration"""
        raise NotADirectoryError()

    def fetch_statistics(self) -> Dict:
        """fetch latest ports statistic"""
        raise NotImplementedError()
