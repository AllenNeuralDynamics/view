from view.widgets.acquisition_widgets.channel_plan_widget import ChannelPlanWidget
from qtpy.QtWidgets import QApplication
import sys
from unittest.mock import MagicMock
from pathlib import Path
import os
from voxel.devices.lasers.simulated import SimulatedLaser
from voxel.devices.stage.simulated import Stage
from view.widgets.device_widgets.laser_widget import LaserWidget
from view.widgets.device_widgets.stage_widget import StageWidget
from threading import Lock

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

    properties = {
        'lasers': ['power_setpoint_mw'],
        'focusing_stages': ['position_mm'],
        'start_delay_time': {
            'delegate': 'spin',
            'type': 'float',
            'minimum': 0,
            'initial_value': 15,
        },
        'repeats': {
            'delegate': 'spin',
            'type': 'int',
            'minimum': 0,
        },
        'example': {
            'delegate': 'combo',
            'type': 'str',
            'items': ['this', 'is', 'an', 'example'],
            'initial_value': 'example'
        }
    }

    lasers = {
        '488nm': SimulatedLaser(id='hello', wavelength=488),
        '639nm': SimulatedLaser(id='there', wavelength=639)
    }

    focusing_stages = {
        'n': Stage(hardware_axis='n', instrument_axis='n')
    }

    laser_widgets = {
        '488nm': LaserWidget(lasers['488nm']),
        '639nm': LaserWidget(lasers['639nm'])
    }

    stage_widgets = {
        'n': StageWidget(focusing_stages['n']),
    }

    mocked_instrument = MagicMock()
    mocked_instrument.configure_mock(
        lasers=lasers,
        focusing_stages=focusing_stages)
    mocked_instrument_view = MagicMock()
    mocked_instrument_view.configure_mock(instrument=mocked_instrument,
                                          laser_widgets=laser_widgets,
                                          stage_widgets=stage_widgets
                                          )

    plan = ChannelPlanWidget(mocked_instrument_view,
                             channels,
                             properties)
    plan.show()

    plan.channelAdded.connect(lambda ch: plan.add_channel_rows(ch, [[0, 0]]))

    sys.exit(app.exec_())
