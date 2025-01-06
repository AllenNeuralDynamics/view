import unittest
from view.widgets.acquisition_widgets.volume_plan_widget import VolumePlanWidget
from qtpy.QtTest import QTest, QSignalSpy
from qtpy.QtWidgets import QApplication
from qtpy.QtCore import Qt
import sys
import numpy as np

app = QApplication(sys.argv)


class VolumePlanWidgetTests(unittest.TestCase):
    """_summary_"""

    def test_toggle_mode(self):
        """_summary_"""
        plan = VolumePlanWidget()
        plan.show()

        valueChanged_spy = QSignalSpy(plan.valueChanged)

        # check clicking radio button works
        QTest.mouseClick(plan.area_button, Qt.LeftButton)
        self.assertTrue(plan.area_button.isChecked())
        self.assertEqual(plan.mode, "area")
        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())
        self.assertTrue(plan.area_widget.isEnabled())
        self.assertFalse(plan.number_widget.isEnabled())
        self.assertFalse(plan.bounds_widget.isEnabled())

        QTest.mouseClick(plan.number_button, Qt.LeftButton)
        self.assertEqual(plan.mode, "number")
        self.assertEqual(len(valueChanged_spy), 2)  # triggered twice
        self.assertTrue(valueChanged_spy.isValid())
        self.assertFalse(plan.area_widget.isEnabled())
        self.assertTrue(plan.number_widget.isEnabled())
        self.assertFalse(plan.bounds_widget.isEnabled())

        QTest.mouseClick(plan.bounds_button, Qt.LeftButton)
        self.assertEqual(plan.mode, "bounds")
        self.assertEqual(len(valueChanged_spy), 3)  # triggered thrice
        self.assertTrue(valueChanged_spy.isValid())
        self.assertFalse(plan.area_widget.isEnabled())
        self.assertFalse(plan.number_widget.isEnabled())
        self.assertTrue(plan.bounds_widget.isEnabled())

        plan.close()

    def test_number_mode(self):
        """_summary_"""
        plan = VolumePlanWidget()
        plan.show()
        plan.mode = "number"

        valueChanged_spy = QSignalSpy(plan.valueChanged)

        plan.rows.setValue(2)

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())
        # check tile position and table
        self.assertTrue(len(plan.tile_positions[0]) == 1)
        self.assertTrue(len(plan.tile_positions) == 2)
        self.assertTrue(plan.tile_table.rowCount() == 2)
        # check scan_start, scan_end, and tile_visibility shape are updated

        self.assertTrue(plan.tile_visibility.shape == (2, 1))
        self.assertTrue(plan.scan_starts.shape == (2, 1))
        self.assertTrue(plan.scan_ends.shape == (2, 1))

        plan.columns.setValue(2)

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 2)  # triggered twice
        self.assertTrue(valueChanged_spy.isValid())
        # check tile position and table
        self.assertTrue(len(plan.tile_positions) == 2)
        self.assertTrue(len(plan.tile_positions[0]) == 2)
        self.assertTrue(plan.tile_table.rowCount() == 4)
        # check scan_start, scan_end, and tile_visibility shape are updated
        self.assertTrue(plan.tile_visibility.shape == (2, 2))
        self.assertTrue(plan.scan_starts.shape == (2, 2))
        self.assertTrue(plan.scan_ends.shape == (2, 2))

        # check tile pos is as expected
        expected_tile_pos = [[[-0.5, 0.5, 0.0], [0.5, 0.5, 0.0]], [[-0.5, -0.5, 0.0], [0.5, -0.5, 0.0]]]
        actual_tile_pos = plan.tile_positions
        self.assertTrue(np.array_equal(expected_tile_pos, actual_tile_pos))

        plan.relative_to.setCurrentIndex(1)
        expected_tile_pos = [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], [[0.0, -1.0, 0.0], [1.0, -1.0, 0.0]]]
        actual_tile_pos = plan.tile_positions
        self.assertTrue(np.array_equal(expected_tile_pos, actual_tile_pos))

    def test_area_mode(self):
        """_summary_"""
        plan = VolumePlanWidget()
        plan.show()
        plan.mode = "area"

        valueChanged_spy = QSignalSpy(plan.valueChanged)

        plan.area_height.setValue(2)

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())

        # check tile position and table
        self.assertTrue(len(plan.tile_positions[0]) == 1)
        self.assertTrue(len(plan.tile_positions) == 2)
        self.assertTrue(plan.tile_table.rowCount() == 2)
        # check scan_start, scan_end, and tile_visibility shape are updated

        self.assertTrue(plan.tile_visibility.shape == (2, 1))
        self.assertTrue(plan.scan_starts.shape == (2, 1))
        self.assertTrue(plan.scan_ends.shape == (2, 1))

        plan.area_width.setValue(2)

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 2)  # triggered twice
        self.assertTrue(valueChanged_spy.isValid())
        # check tile position and table
        self.assertTrue(len(plan.tile_positions) == 2)
        self.assertTrue(len(plan.tile_positions[0]) == 2)
        self.assertTrue(plan.tile_table.rowCount() == 4)
        # check scan_start, scan_end, and tile_visibility shape are updated
        self.assertTrue(plan.tile_visibility.shape == (2, 2))
        self.assertTrue(plan.scan_starts.shape == (2, 2))
        self.assertTrue(plan.scan_ends.shape == (2, 2))

        # check tile pos is as expected
        expected_tile_pos = [[[-0.5, 0.5, 0.0], [0.5, 0.5, 0.0]], [[-0.5, -0.5, 0.0], [0.5, -0.5, 0.0]]]
        actual_tile_pos = plan.tile_positions
        self.assertTrue(np.array_equal(expected_tile_pos, actual_tile_pos))

        plan.relative_to.setCurrentIndex(1)
        expected_tile_pos = [[[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]], [[0.0, -1.0, 0.0], [1.0, -1.0, 0.0]]]
        actual_tile_pos = plan.tile_positions
        self.assertTrue(np.array_equal(expected_tile_pos, actual_tile_pos))

        # check if height and width are non-integer multiple values of fov
        plan.area_height.setValue(1.5)
        plan.area_width.setValue(1.5)
        # check tile position and table
        self.assertTrue(len(plan.tile_positions) == 2)
        self.assertTrue(len(plan.tile_positions[0]) == 2)
        self.assertTrue(plan.tile_table.rowCount() == 4)
        # check scan_start, scan_end, and tile_visibility shape are updated
        self.assertTrue(plan.tile_visibility.shape == (2, 2))
        self.assertTrue(plan.scan_starts.shape == (2, 2))
        self.assertTrue(plan.scan_ends.shape == (2, 2))

    def test_bounds_mode(self):
        """_summary_"""
        plan = VolumePlanWidget()
        plan.show()
        plan.mode = "bounds"

        valueChanged_spy = QSignalSpy(plan.valueChanged)

        plan.dim_1_low.setValue(0)
        plan.dim_1_high.setValue(1)

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())

        # check tile position and table
        self.assertTrue(len(plan.tile_positions[0]) == 1)
        self.assertTrue(len(plan.tile_positions) == 2)
        self.assertTrue(plan.tile_table.rowCount() == 2)
        # check scan_start, scan_end, and tile_visibility shape are updated

        self.assertTrue(plan.tile_visibility.shape == (2, 1))
        self.assertTrue(plan.scan_starts.shape == (2, 1))
        self.assertTrue(plan.scan_ends.shape == (2, 1))

        plan.dim_0_low.setValue(0)
        plan.dim_0_high.setValue(1)

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 2)  # triggered twice
        self.assertTrue(valueChanged_spy.isValid())
        # check tile position and table
        self.assertTrue(len(plan.tile_positions) == 2)
        self.assertTrue(len(plan.tile_positions[0]) == 2)
        self.assertTrue(plan.tile_table.rowCount() == 4)
        # check scan_start, scan_end, and tile_visibility shape are updated
        self.assertTrue(plan.tile_visibility.shape == (2, 2))
        self.assertTrue(plan.scan_starts.shape == (2, 2))
        self.assertTrue(plan.scan_ends.shape == (2, 2))

        # check tile pos is as expected
        expected_tile_pos = [[[0.0, 1.0, 0.0], [1.0, 1.0, 0.0]], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]]
        actual_tile_pos = plan.tile_positions
        self.assertTrue(np.array_equal(expected_tile_pos, actual_tile_pos))

    def test_update_fov_position(self):
        """_summary_"""
        plan = VolumePlanWidget()
        plan.show()
        valueChanged_spy = QSignalSpy(plan.valueChanged)

        plan.fov_position = [1, 2, 3]

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())

        self.assertEqual(plan.grid_offset_widgets[0].value(), 1)
        self.assertEqual(plan.grid_offset_widgets[1].value(), 2)
        self.assertEqual(plan.grid_offset_widgets[2].value(), 3)
        self.assertEqual(plan.grid_offset, [1, 2, 3])

        # check that if fov stays the same, valueChanged is not triggered
        plan.fov_position = [1, 2, 3]

        # check value change is emitted once
        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())

        # check if anchors are checked
        plan.anchor_widgets[0].setChecked(True)
        plan.anchor_widgets[1].setChecked(True)
        plan.anchor_widgets[2].setChecked(True)

        plan.fov_position = [0, 0, 0]

        self.assertEqual(plan.grid_offset_widgets[0].value(), 1)
        self.assertEqual(plan.grid_offset_widgets[1].value(), 2)
        self.assertEqual(plan.grid_offset_widgets[2].value(), 3)
        self.assertEqual(plan.grid_offset, [1, 2, 3])

    def test_grid_offset_widgets(self):
        """_summary_"""
        plan = VolumePlanWidget()
        plan.show()
        valueChanged_spy = QSignalSpy(plan.valueChanged)

        # test dimension 0
        plan.grid_offset_widgets[0].setValue(1)

        self.assertEqual(len(valueChanged_spy), 1)  # triggered once
        self.assertTrue(valueChanged_spy.isValid())
        self.assertEqual(plan.grid_offset, [1, 0, 0])
        expected_tiles = np.array([[[1, 0, 0]]])
        actual_tiles = plan.tile_positions

        self.assertTrue(np.array_equal(expected_tiles, actual_tiles))

        # test dimension 1
        plan.grid_offset_widgets[1].setValue(2)

        self.assertEqual(len(valueChanged_spy), 2)  # triggered twice
        self.assertTrue(valueChanged_spy.isValid())
        self.assertEqual(plan.grid_offset, [1, 2, 0])
        expected_tiles = [[[1, 2, 0]]]
        actual_tiles = plan.tile_positions
        self.assertTrue(np.array_equal(expected_tiles, actual_tiles))

        # test dimension 2
        plan.grid_offset_widgets[2].setValue(3)

        self.assertEqual(len(valueChanged_spy), 3)  # triggered thrice
        self.assertTrue(valueChanged_spy.isValid())
        self.assertEqual(plan.grid_offset, [1, 2, 3])
        expected_tiles = [[[1, 2, 3]]]
        actual_tiles = plan.tile_positions
        self.assertTrue(np.array_equal(expected_tiles, actual_tiles))


if __name__ == "__main__":
    unittest.main()
    sys.exit(app.exec_())
