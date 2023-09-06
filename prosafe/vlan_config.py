# -*- encoding: utf-8 -*-

import tomllib
from typing import List, Dict
from typing_extensions import Annotated

from pydantic import BaseModel
from pydantic.functional_validators import AfterValidator, model_validator

from .switches.general import VlanPortMembership, VlanId, PortId
from .switches.general import SwitchModel


def validate_vlan_note_list(notes: List[str]):
    data = dict()
    for note in notes:
        vid = int(note[:-1])
        status = note[-1:]
        if status == 'U':
            status = VlanPortMembership.UNTAGGED
        elif status == 'T':
            status = VlanPortMembership.TAGGED
        elif status == 'N':
            status = VlanPortMembership.IGNORED
        else:
            assert False, f"Unsupported status {status}, should be one of U, T, N"
        vid = int(vid)
        # TODO: move this validation to upper level, so more readable
        assert vid not in data, f"Duplicate VLAN ID: {vid}"
        data[vid] = status

    return data


_VlanNoteDict = Annotated[List[str], AfterValidator(validate_vlan_note_list)]


class _PortVlanConfig(BaseModel):
    pvid: VlanId
    vlans: _VlanNoteDict


class SwitchVlanConfig(BaseModel):
    address: str
    password: str
    port_count: int
    model: SwitchModel
    ports: Dict[PortId, _PortVlanConfig]

    @model_validator(mode='after')
    def check_pvid_and_pid(self):
        for p, c in self.ports.items():
            assert c.pvid in c.vlans, f"Port {p} assigned pvid {c.pvid} but it's NOT in VLAN{c.pvid}!"
            assert 1 <= p <= self.port_count, f"Port {p} exceeds acceptable port ID range[1,{self.port_count}(port_count)], please check your config!"
    
    def get_config_by_vlan(self, vid: VlanId):
        data = dict()
        for pid, port_config in self.ports.items():
            data[pid] = port_config.vlans.get(vid, VlanPortMembership.IGNORED)
        # only contain ports mentioned in the config
        return data


def load_config(filename: str) -> Dict[str, SwitchVlanConfig]:
    with open(filename, 'rb') as f:
        config_data = tomllib.load(f)

    switches: Dict = config_data.get('switches', None)
    assert switches != None, "Invalid config! Please specify your switches under [switches]!"

    configs: Dict[SwitchVlanConfig] = dict()
    for sw_name, sw_config in switches.items():
        cfg = SwitchVlanConfig(**sw_config)
        configs[sw_name] = cfg

    return configs
