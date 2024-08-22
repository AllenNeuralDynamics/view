""" testing AcquisitionView """

import unittest
from view.acquisition_view import AcquisitionView
from qtpy.QtWidgets import QApplication, QWidget
from qtpy.QtCore import Qt
import sys
import numpy as np
from unittest.mock import MagicMock
from pathlib import Path
import os
from voxel.devices.lasers.simulated import SimulatedLaser
from voxel.devices.stage.simulated import Stage
from view.widgets.device_widgets.laser_widget import LaserWidget
from threading import Lock
from qtpy.QtTest import QTest, QSignalSpy

app = QApplication(sys.argv)


class AcquisitionViewTests(unittest.TestCase):
    """Tests for AcquisitionView"""

    # TODO: A lot more to test for

    def test_update_tiles(self):
        """test update_tiles functions"""

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
        }

        lasers = {
            '488nm': SimulatedLaser(id='hello', wavelength=488),
            '639nm': SimulatedLaser(id='there', wavelength=639)
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

        gui_config = {
            'acquisition_view': {
                'coordinate_plane': ['x', 'y', 'z'],
                'unit': 'mm',
                'fov_dimensions': [1, 1, 0],
                'acquisition_widgets': {
                    'channel_plan': {
                        'init': {
                            'properties': properties
                        }
                    }
                }
            }
        }

        instrument_config = {
            'instrument': {
                'channels': channels
            }
        }

        acquisition_config = {
            'acquisition': {
                'operations': {},
                'tiles': []
            }
        }

        mocked_instrument = MagicMock()
        mocked_instrument.configure_mock(config=instrument_config,
                                         lasers=lasers,
                                         tiling_stages=tiling_stages,
                                         scanning_stages=scanning_stages)
        mocked_instrument_view = MagicMock()
        mocked_instrument_view.configure_mock(instrument=mocked_instrument,
                                              laser_widgets=laser_widgets,
                                              laser_widget_locks=laser_widget_locks,
                                              config=gui_config)

        mocked_acquisition = MagicMock()
        mocked_acquisition.configure_mock(instrument=mocked_instrument,
                                          config=acquisition_config)

        view = AcquisitionView(mocked_acquisition, mocked_instrument_view)

        valueChanged_spy = QSignalSpy(view.volume_plan.valueChanged)
        channelsAdded_spy = QSignalSpy(view.channel_plan.channelAdded)
        channelChanged_spy = QSignalSpy(view.channel_plan.channelChanged)

        view.volume_plan.rows.setValue(2)
        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())

        view.channel_plan.add_channel('488')
        # check channel added is emitted once
        self.assertEqual(len(channelsAdded_spy), 1)  # triggered once
        self.assertTrue(channelsAdded_spy.isValid())

        expected_tiles = [{
            'channel': '488',
            'position_mm': {
                'x': 0.0,
                'y': 0.5,
                'z': 0.0
            },
            'tile_number': 0,
            '488nm': {
                'power_setpoint_mw': 0.0
            },
            'steps': 0,
            'step_size': 0.0,
            'prefix': ''},
            {
                'channel': '488',
                'position_mm': {
                    'x': 0.0,
                    'y': -0.5,
                    'z': 0.0
                }, 'tile_number': 1,
                '488nm': {
                    'power_setpoint_mw': 0.0
                },
                'steps': 0,
                'step_size': 0.0,
                'prefix': ''}]
        actual_tiles = mocked_acquisition.config['acquisition']['tiles']
        self.assertEqual(expected_tiles, actual_tiles)

        table = getattr(view.channel_plan, '488_table')
        table.item(0, 2).setData(Qt.EditRole, 'tile_prefix')

        # check channel changed is emitted once
        self.assertEqual(len(channelChanged_spy), 1)  # triggered once
        self.assertTrue(channelChanged_spy.isValid())

        expected_tiles = [{
            'channel': '488',
            'position_mm': {
                'x': 0.0,
                'y': 0.5,
                'z': 0.0
            },
            'tile_number': 0,
            '488nm': {
                'power_setpoint_mw': 0.0
            },
            'steps': 0,
            'step_size': 0.0,
            'prefix': 'tile_prefix'},
            {
                'channel': '488',
                'position_mm': {
                    'x': 0.0,
                    'y': -0.5,
                    'z': 0.0
                }, 'tile_number': 1,
                '488nm': {
                    'power_setpoint_mw': 0.0
                },
                'steps': 0,
                'step_size': 0.0,
                'prefix': 'tile_prefix'}]
        actual_tiles = mocked_acquisition.config['acquisition']['tiles']
        self.assertEqual(expected_tiles, actual_tiles)

if __name__ == "__main__":
    unittest.main()
    sys.exit(app.exec_())
