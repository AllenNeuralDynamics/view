from view.widgets.acquisition_widgets.volume_widget import VolumeWidget
from qtpy.QtWidgets import QApplication
import sys
from unittest.mock import MagicMock
from pathlib import Path
import os
from ruamel.yaml import YAML
from voxel.devices.lasers.simulated import SimulatedLaser
from voxel.devices.stage.simulated import Stage
from view.widgets.device_widgets.laser_widget import LaserWidget
from threading import Lock
from qtpy.QtCore import Qt

RESOURCES_DIR = (
        Path(os.path.dirname(os.path.realpath(__file__))) / "resources"
)
ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'

if __name__ == "__main__":

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_ShareOpenGLContexts)
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
        '488nm': SimulatedLaser(id='hello'),
        '639nm': SimulatedLaser(id='there')
    }

    tiling_stages = {
        'x': Stage(hardware_axis='x', instrument_axis='x'),
        'y': Stage(hardware_axis='y', instrument_axis='y')
    }

    scanning_stages = {
        'z': Stage(hardware_axis='z', instrument_axis='z')
    }

    laser_widgets = {
        '488nm': LaserWidget(lasers['488nm']),
        '639nm': LaserWidget(lasers['639nm'])
    }

    laser_widget_locks = {
        '488nm': Lock(),
        '639nm': Lock()
    }


    tile_list = YAML().load(ACQUISITION_YAML)['acquisition']['tiles']

    mocked_instrument = MagicMock()
    mocked_instrument.configure_mock(lasers=lasers, tiling_stages=tiling_stages, scanning_stages=scanning_stages)
    mocked_instrument_view = MagicMock()
    mocked_instrument_view.configure_mock(instrument=mocked_instrument,
                                          laser_widgets=laser_widgets,
                                          laser_widget_locks=laser_widget_locks)
    volume_widget = VolumeWidget(mocked_instrument_view, channels, settings, fov_dimensions=[ 10.672384, 8.00128 ])
    volume_widget.autopopulate_tiles(tile_list)
    sys.exit(app.exec_())
