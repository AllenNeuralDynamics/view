import logging
from sympy import symbols, solve
from serial import Serial
from enum import Enum
import sys

# Define StrEnums if they don't yet exist.
if sys.version_info < (3, 11):
    class StrEnum(str, Enum):
        pass
else:
    from enum import StrEnum


class BoolVal(StrEnum):
    OFF = "0"
    ON = "1"


MODULATION_MODES = {
    'off': {'external_control_mode': 'OFF', 'digital_modulation': 'OFF'},
    'analog': {'external_control_mode': 'ON', 'digital_modulation': 'OFF'},
    'digital': {'external_control_mode': 'OFF', 'digital_modulation': 'ON'}
}
TEST_PROPERTY = {
    "value0": {
        "internal": None,
        "external": 0,
    },
    "value1": {
        "on": True,
        "off": False,
    }
}


class SimulatedCombiner:

    def __init__(self, port):
        """Class for the L6CC oxxius combiner. This combiner can have LBX lasers or LCX"""

        self.ser = Serial
        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._PercentageSplitStatus = 0

    @property
    def percentage_split(self):
        """Set percentage split of lasers"""

        return self._PercentageSplitStatus

    @percentage_split.setter
    def percentage_split(self, value):
        """Get percentage split of lasers"""
        if value > 100 or value < 0:
            self.log.error(f'Impossible to set percentage spilt to {value}')
            return
        self._PercentageSplitStatus = value


class SimulatedLaser:

    def __init__(self, port: Serial or str, prefix: str = '', coefficients: dict = {}):
        """Communicate with specific LBX laser in L6CC Combiner box.

                :param port: comm port for lasers.
                :param prefix: prefix specic to laser.
                """

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.prefix = prefix
        self.ser = Serial
        self._simulated_power_setpoint_m = 10.0
        self._max_power_mw = 100.0
        self._modulation_mode = 'digital'
        self._temperature = 20.0
        self._cdrh = BoolVal.ON
        self._test_property = {"value0":"external", "value1":"on"}

    @property
    def power_setpoint_mw(self):
        """Power of laser in mw"""
        return self._simulated_power_setpoint_m

    @power_setpoint_mw.setter
    def power_setpoint_mw(self, value: float):
        self._simulated_power_setpoint_m = value

    @property
    def max_power_mw(self):
        """Maximum power of laser in mw"""
        return self._max_power_mw

    @property
    def modulation_mode(self):
        """Modulation mode of laser"""
        return self._modulation_mode

    @modulation_mode.setter
    def modulation_mode(self, value: str):
        if value not in MODULATION_MODES.keys():
            raise ValueError("mode must be one of %r." % MODULATION_MODES.keys())
        for attribute, state in MODULATION_MODES[value].items():
            setattr(self, attribute, state)

    @property
    def temperature(self):
        """Temperature of laser in Celsius"""
        return self._temperature

    def status(self):
        return []

    @property
    def cdrh(self):
        """Status of five-second safety delay"""
        return self._cdrh

    @cdrh.setter
    def cdrh(self, value: BoolVal or str):
        self._cdrh = value

    @property
    def test_property(self):
        """Test property used for UI construction"""
        return self._test_property

    @test_property.setter
    def test_property(self, value: dict):

        value0 = value['value0']
        value1 = value['value1']

        if value0 not in TEST_PROPERTY['value0'].keys():
            raise ValueError("mode must be one of %r." % TEST_PROPERTY['value0'].keys())
        if value1 not in TEST_PROPERTY['value1'].keys():
            raise ValueError("mode must be one of %r." % TEST_PROPERTY['value1'].keys())
        self._test_property = value

    def enable(self):
        pass

    def disable(self):
        pass
