from enum import StrEnum
from .general import BaseSwitch
from .gs108ev3 import Switch as DRI_GS108EV3


SWITCH_PORT_COUNT = {
    'gs108ev3': 8,
    'gs116ev2': 16,
}

SWITCH_DRIVER = {
    'gs108ev3': DRI_GS108EV3,
    'gs116ev2': BaseSwitch,
}

class SwitchModel(StrEnum):
    GS108EV3 = 'gs108ev3'
    GS116EV2 = 'gs116ev2'

    @property
    def port_count(self):
        return SWITCH_PORT_COUNT.get(self.value, 0)
    
    @property
    def driver(self):
        return SWITCH_DRIVER.get(self.value, BaseSwitch)
