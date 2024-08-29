""" testing CameraWidget """

from types import SimpleNamespace
import unittest
from view.widgets.device_widgets.camera_widget import CameraWidget
from qtpy.QtTest import QTest, QSignalSpy
from qtpy.QtWidgets import QApplication, QWidget
from qtpy.QtCore import Qt
import sys
import numpy as np
from unittest.mock import MagicMock, PropertyMock

app = QApplication(sys.argv)


class CameraWidgetTests(unittest.TestCase):
    """Tests for CameraWidget"""

    def test_format(self):
        """Test format of camera widget is correct"""

        mock_camera = MagicMock()
        mock_camera.configure_mock(
            _binning=1,
            _pixel_type='mono8',
            _exposure_time_ms=20.0,
            _sensor_width_px=100,
            _sensor_height_px=100,
            _width_px=100,
            _width_offset_px=0,
            _height_px=100,
            _height_offset_px=0,
            roi_widget=QWidget(),
            _latest_frame=np.zeros((100, 100)))

        type(mock_camera).binning = property(fget=lambda inst: getattr(inst, '_binning'),
                                             fset=lambda inst, val: setattr(inst, '_binning', val))
        type(mock_camera).frame_time_ms = property(fget=lambda inst: inst.height_px * inst.line_interval_us / 1000 +
                                                                     inst.exposure_time_ms)
        type(mock_camera).line_interval_us = property(fget=lambda inst: 20.0)
        type(mock_camera).binning = property(fget=lambda inst: getattr(inst, '_binning'),
                                             fset=lambda inst, val: setattr(inst, '_binning', val))
        type(mock_camera).pixel_type = property(fget=lambda inst: getattr(inst, '_pixel_type'),
                                                fset=lambda inst, val: setattr(inst, '_pixel_type', val))
        type(mock_camera).exposure_time_ms = property(fget=lambda inst: getattr(inst, '_exposure_time_ms'),
                                                      fset=lambda inst, v: setattr(inst, '_exposure_time_ms', v))
        type(mock_camera).sensor_width_px = property(fget=lambda inst: getattr(inst, '_sensor_width_px'),
                                                     fset=lambda inst, v: setattr(inst, '_sensor_width_px', v))
        type(mock_camera).sensor_height_px = property(fget=lambda inst: getattr(inst, '_sensor_height_px'),
                                                      fset=lambda inst, v: setattr(inst, '_sensor_height_px',
                                                                                   v))
        type(mock_camera).width_px = property(fget=lambda inst: getattr(inst, '_width_px'),
                                              fset=lambda inst, v: setattr(inst, '_width_px', v))
        type(mock_camera).width_offset_px = property(fget=lambda inst: getattr(inst, '_width_offset_px'),
                                                     fset=lambda inst, v: setattr(inst, '_width_offset_px', v))
        type(mock_camera).height_px = property(fget=lambda inst: getattr(inst, '_height_px'),
                                               fset=lambda inst, v: setattr(inst, '_height_px', v))
        type(mock_camera).height_offset_px = property(fget=lambda inst: getattr(inst, '_height_offset_px'),
                                                      fset=lambda inst, v: setattr(inst, '_height_offset_px', v))
        type(mock_camera).latest_frame = property(fget=lambda inst: getattr(inst, '_latest_frame'))


        widget = CameraWidget(mock_camera)
        children = widget.centralWidget().children()
        groups = {'picture_buttons': children[1],
                  'pixel_widgets': children[2],
                  'timing_widgets': children[3],
                  'sensor_size_widgets': children[5],
                  }

        # check that picture buttons are correctly placed
        self.assertEqual(groups['picture_buttons'].layout().itemAt(0).widget(), widget.live_button)
        self.assertEqual(groups['picture_buttons'].layout().itemAt(1).widget(), widget.snapshot_button)

        # check that pixel widgets are placed correctly


        print(groups['pixel_widgets'].children()[1].layout().itemAt(1), widget.property_widgets['binning'])
        self.assertEqual(groups['pixel_widgets'].layout().itemAt(0).widget(), widget.binning_widget)
        self.assertEqual(groups['pixel_widgets'].layout().itemAt(1).widget(), widget.pixel_type_widget)

        # check that timing widgets are placed correctly
        self.assertEqual(groups['timing_widgets'].layout().itemAt(0).widget(), widget.exposure_time_ms_widget)
        self.assertEqual(groups['timing_widgets'].layout().itemAt(1).widget(), widget.frame_time_ms_widget)
        self.assertEqual(groups['timing_widgets'].layout().itemAt(2).widget(), widget.line_interval_us)

        # check that sensor size widgets are placed correctly
        self.assertEqual(groups['sensor_size_widgets'].layout().itemAt(0).widget(), widget.width_px_widget)
        self.assertEqual(groups['sensor_size_widgets'].layout().itemAt(1).widget(), widget.width_offset_px)
        self.assertEqual(groups['sensor_size_widgets'].layout().itemAt(2).widget(), widget.height_px)
        self.assertEqual(groups['sensor_size_widgets'].layout().itemAt(3).widget(), widget.height_offset_px)

if __name__ == "__main__":
    unittest.main()
    sys.exit(app.exec_())
