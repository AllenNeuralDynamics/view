from view.widgets.acquisition_widgets.volume_widget import VolumeWidget
from qtpy.QtWidgets import QApplication
import sys
from unittest.mock import MagicMock
from pathlib import Path
import os
from voxel.devices.lasers.simulated import SimulatedLaser
from view.widgets.device_widgets.laser_widget import LaserWidget
from threading import Lock

RESOURCES_DIR = (
        Path(os.path.dirname(os.path.realpath(__file__))) / "resources"
)
INSTRUMENT_YAML = RESOURCES_DIR / 'simulated_instrument.yaml'


class MockInstrument:
    def __init__(self, **kwds):
        for key, value in kwds.items():
            setattr(self, key, value)


if __name__ == "__main__":

    app = QApplication(sys.argv)
    channels = {
        '488': {
            'filters': ['BP488'],
            'lasers': ['488nm'],
            'cameras': ['vnp - 604mx', 'vp-151mx']},
        '639': {
            'filters': ['LP638'],
            'lasers': ['639nm'],
            'cameras': ['vnp - 604mx', 'vp-151mx']}
    }

    settings = {
        'lasers': ['power_setpoint_mw'],
    }

    lasers = {
        '488nm': SimulatedLaser(port='hello'),
        '639nm': SimulatedLaser(port='there')
    }

    laser_widgets = {
        '488nm': LaserWidget(lasers['488nm']),
        '639nm': LaserWidget(lasers['639nm'])
    }

    laser_widget_locks = {
        '488nm': Lock(),
        '639nm': Lock()
    }

    mocked_instrument = MagicMock()
    mocked_instrument.configure_mock(lasers=lasers)
    mocked_instrument_view = MagicMock()
    mocked_instrument_view.configure_mock(instrument=mocked_instrument, laser_widgets=laser_widgets, laser_widget_locks=laser_widget_locks)
    volume_widget = VolumeWidget(mocked_instrument_view, channels, settings)

    sys.exit(app.exec_())
