# -*- encoding: utf-8 -*-

from collections import defaultdict
import tomllib
from typing import List, Dict
from typing_extensions import Annotated

from pydantic import BaseModel, validate_call
from pydantic.functional_validators import BeforeValidator, model_validator

from .switches.general import PvidConfig, VlanConfig, VlanPortMembership, VlanId, PortId
from .switches import SwitchModel


@validate_call
def _validate_vlan_note_list(notes: List[str]):
    data = dict()
    for note in notes:
        status = note[-1:]
        if status == 'U':
            status = VlanPortMembership.UNTAGGED
        elif status == 'T':
            status = VlanPortMembership.TAGGED
        elif status == 'N':
            status = VlanPortMembership.IGNORED
        else:
            assert False, f"Unsupported status {status}, should be one of U, T, N"
        vid = VlanId(note[:-1])
        # TODO: move this validation to upper level, so more readable
        assert vid not in data, f"Duplicate VLAN ID: {vid}"
        data[vid] = status

    return data


_VlanNoteDict = Annotated[Dict[VlanId, VlanPortMembership], BeforeValidator(_validate_vlan_note_list)]


class _PortVlanConfig(BaseModel):
    pvid: VlanId
    vlans: _VlanNoteDict


class SwitchVlanConfig(BaseModel):
    address: str
    password: str
    model: SwitchModel
    ports: Dict[PortId, _PortVlanConfig]

    @model_validator(mode='after')
    def check_pvid_and_pid(self):
        for p, c in self.ports.items():
            assert c.pvid in c.vlans, f"Port {p} assigned pvid {c.pvid} but it's NOT in VLAN{c.pvid}!"
            assert 1 <= p <= (pcount := self.model.port_count), \
                f"Port {p} exceeds acceptable port ID range[1,{pcount}(port_count)], please check your config!"
    
    def get_config_by_vlan(self, vid: VlanId):
        data = dict()
        for pid, port_config in self.ports.items():
            data[pid] = port_config.vlans.get(vid, VlanPortMembership.IGNORED)
        # only contain ports mentioned in the config
        return data
    
    def get_vlan_membership(self) -> VlanConfig:
        data = defaultdict(lambda: {i: VlanPortMembership.IGNORED for i in range(1, self.model.port_count + 1)})
        for pid, port_config in self.ports.items():
            for vid, membership in port_config.vlans.items():
                data[vid][pid] = membership
        return dict(data)
    
    def get_pvids(self) -> PvidConfig:
        data: PvidConfig = dict()
        for pid, port_config in self.ports.items():
            data[pid] = port_config.pvid
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
