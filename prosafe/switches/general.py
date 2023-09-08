from enum import IntEnum
from typing import Dict
from contextlib import contextmanager


VlanId = int
PortId = int


class VlanPortMembership(IntEnum):
    # These values are from GS108Ev3's web interface
    # order matters!
    UNTAGGED = 1
    TAGGED = 2
    IGNORED = 3


SingleVlanConfig = Dict[PortId, VlanPortMembership]
VlanConfig = Dict[VlanId, SingleVlanConfig]
PvidConfig = Dict[PortId, VlanId]


class BaseSwitch:
    def __init__(self, address: str, password: str) -> None:
        pass

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
