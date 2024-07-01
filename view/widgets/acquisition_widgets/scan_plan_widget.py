from pymmcore_widgets import ZPlanWidget as ZPlanWidgetMMCore
from qtpy.QtWidgets import QWidget, QDoubleSpinBox, QLabel, QHBoxLayout, QCheckBox, QSizePolicy, QStackedWidget, \
    QGroupBox, QDoubleSpinBox
from qtpy.QtCore import Qt, Signal
import useq
import enum
import numpy as np
from superqt.utils import signals_blocked
import inspect

class Mode(enum.Enum):
    """Recognized ZPlanWidget modes."""

    TOP_BOTTOM = "top_bottom"
    RANGE_AROUND = "range_around"
    ABOVE_BELOW = "above_below"


class ScanPlanWidget(QWidget):
    """Widget that organizes a matrix of ZPlanWidget and displays info on table"""

    scanChanged = Signal()
    tileAdded = Signal(int, int)
    rowRemoved = Signal(int)
    columnRemoved = Signal(int)

    def __init__(self, z_limits: [float] = None, unit: str = 'um'):

        super().__init__()

        # initialize values
        self.z_limits = z_limits
        self.unit = unit
        self._grid_position = 0.0

        self.z_plan_widgets = np.empty([0, 1], dtype=object)
        self._tile_visibility = np.ones([1, 1], dtype=bool)  # init as True
        self._scan_starts = np.zeros([0, 1], dtype=float)
        self._scan_volumes = np.zeros([0, 1], dtype=float)

        self.stacked_widget = QStackedWidget()
        # put widget into group box to display info in title
        self.group_box = QGroupBox()
        layout = QHBoxLayout()
        layout.addWidget(self.stacked_widget)
        self.group_box.setLayout(layout)
        self.group_box.setTitle(f'Tile Volume')
        self.group_box.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.stacked_widget.currentChanged.connect(lambda index: self.group_box.setTitle(
            f'Tile Volume {self.stacked_widget.currentWidget().windowTitle()}') if not self.apply_all.isChecked()
                                                                else self.group_box.setTitle(f'Tile Volume'))

        checkbox_layout = QHBoxLayout()
        self.apply_all = QCheckBox('Apply to All')
        self.apply_all.setChecked(True)
        self.apply_to_all = True
        self.apply_all.toggled.connect(self.toggle_apply_all)
        self.apply_all.toggled.connect(lambda checked: setattr(self, 'apply_to_all', checked))
        checkbox_layout.addWidget(self.apply_all)
        self.setLayout(checkbox_layout)

        self.show()

    @property
    def scan_starts(self):
        """Return the start position of grid"""
        return self._scan_starts

    @property
    def tile_visibility(self):
        """Return the start position of grid"""
        return self._tile_visibility

    @property
    def scan_volumes(self):
        """Return the volume of grid"""
        return self._scan_volumes

    def update_scan(self, widget_value, attr, row, column):
        """If z widget is changed, update scan_start, scan_volumes, and tile_visibility accordingly
        :param widget_value: value coming from widget
        :param attr: name of widget that sent the signal
        :param row: row of widget
        :param column: column of widget"""

        z0 = self.z_plan_widgets[row, column]
        value = z0.value()
        if self.apply_all.isChecked() and (row, column) == (0, 0):
            # update scan start, volume, and tile visibility
            self._scan_starts[:, :] = min(value)
            self._scan_volumes[:, :] = max(value) - min(value)
            self._tile_visibility[:, :] = not z0.hide.isChecked()

            for i, j in np.ndindex(self.z_plan_widgets.shape):
                if (i, j) == (0, 0):
                    continue
                z = self.z_plan_widgets[i, j]
                if type(getattr(z, attr)) == QCheckBox:
                    getattr(z, attr).setChecked(widget_value)
                else:
                    getattr(z, attr).setValue(widget_value)
                z._on_change()  # update widget
        else:
            self._scan_starts[row, column] = min(value)
            self._scan_volumes[row, column] = max(value) - min(value)
            self._tile_visibility[row, column] = not z0.hide.isChecked()

        self.scanChanged.emit()

    def toggle_apply_all(self, checked):
        """If apply all is toggled, disable/enable tab widget accordingly and reconstruct gui coords.
        Also change visible z plan widget"""

        for row, column in np.ndindex(self.z_plan_widgets.shape):
            z = self.z_plan_widgets[row][column]

            if (row, column) == (0, 0):
                z0 = self.z_plan_widgets[0, 0]
                value = z0.value()
                self._scan_starts[:, :] = min(value)
                self._scan_volumes[:, :] = max(value) - min(value)
                self._tile_visibility[:, :] = not z0.hide.isChecked()
            else:
                # if not checked, enable all widgets and connect signals: else, disable all and disconnect signals
                self.toggle_signals(z, checked)
                z.setEnabled(not checked)

            if checked and (row, column) != (0, 0):  # if checked, update all widgets with 0, 0 value
                for name in ['start', 'top', 'step', 'steps', 'range', 'above', 'below']:
                    widget_value = getattr(self.z_plan_widgets[0, 0], name).value()
                    getattr(z, name).setValue(widget_value)
                z._on_change()  # update widget

    def toggle_mode(self, action):
        """Toggle mode of widgets if 0,0 has changed and apply all is checked"""

        if self.apply_all.isChecked():
            for i, j in np.ndindex(self.z_plan_widgets.shape):
                if (i, j) == (0, 0):
                    continue
                z = self.z_plan_widgets[i, j]
                z.setMode(self.z_plan_widgets[0, 0].mode())  # set mode to the same as 0, 0 to update correctly

    def scan_plan_construction(self, value: useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight):
        """Create new z_plan widget for each new tile """

        if self.z_plan_widgets.shape[0] != value.rows or self.z_plan_widgets.shape[1] != value.columns:
            old_row = self.z_plan_widgets.shape[0]
            old_col = self.z_plan_widgets.shape[1]

            rows = value.rows
            cols = value.columns
            # close old row and column widget
            if rows - old_row < 0:
                for i in range(rows, old_row):
                    for j in range(old_col):
                        self.stacked_widget.removeWidget(self.z_plan_widgets[i, j])
                        self.z_plan_widgets[i, j].close()

            if cols - old_col < 0:
                for j in range(cols, old_col):
                    for i in range(old_row):
                        self.stacked_widget.removeWidget(self.z_plan_widgets[i, j])
                        self.z_plan_widgets[i, j].close()

            # resize array to new size
            for array, name in zip([self.z_plan_widgets, self.tile_visibility, self.scan_starts, self.scan_volumes],
                                   ['z_plan_widgets', '_tile_visibility', '_scan_starts', '_scan_volumes']):

                v = array[0, 0] if array.shape != (0, 1) else 0  # initialize array with value from first tile
                if rows > old_row:  # add row
                    add_on = [[v] * array.shape[1]] * (rows - old_row)
                    setattr(self, name, np.concatenate((array, add_on), axis=0))
                elif rows < old_row:  # remove row
                    setattr(self, name, np.delete(array, [old_row - x for x in range(1, (old_row - rows) + 1)], axis=0))
                if cols > old_col:  # add column
                    add_on = [[v] * (cols - old_col) for _ in range(array.shape[0])]
                    setattr(self, name, np.concatenate((array, add_on), axis=1))
                elif cols < old_col:  # remove col
                    setattr(self, name, np.delete(array, [old_col - x for x in range(1, (old_col - cols) + 1)], axis=1))

            # update new rows and columns with widgets
            if rows - old_row > 0:
                for i in range(old_row, rows):
                    for j in range(cols):  # take care of any new column values
                        self.create_z_plan_widget(i, j)
            if cols - old_col > 0:
                for i in range(old_row):  # if new rows, already taken care of in previous loop
                    for j in range(old_col, cols):
                        self.create_z_plan_widget(i, j)

        self.scanChanged.emit()

    def create_z_plan_widget(self, row, column):
        """Function to create and connect ZPlanWidget"""

        z = ZPlanWidget(self.z_limits, self.unit)
        self.z_plan_widgets[row, column] = z
        z.setWindowTitle(f'({row}, {column})')
        z.setMode(self.z_plan_widgets[0, 0].mode())
        # connect signals for each input
        for name in ['start', 'top', 'step', 'steps', 'range', 'above', 'below']:
            widget = getattr(z, name)
            if type(widget) == QDoubleSpinBox:
                widget.setDecimals(6)
            if (row, column) != (0, 0):  # update widget with appropriate values
                widget.setValue(getattr(self.z_plan_widgets[0, 0], name).value())
            widget.valueChanged.connect(lambda value, attr=name: self.update_scan(value, attr, row, column))
        z.hide.toggled.connect(lambda value: self.update_scan(value, 'hide', row, column))
        z.hide.setChecked(not self._tile_visibility[row, column])

        if self.apply_all.isChecked() and (row, column) != (0, 0):  # block signals from widget
            self.toggle_signals(z, True)
            z.setEnabled(False)
        elif (row, column) == (0, 0):
            z._mode_group.triggered.connect(self.toggle_mode)

        # update minimum value of end if start changes
        z.top.setMinimum(z.start.value())
        z.start.valueChanged.connect(lambda value: z.top.setMinimum(value))

        self.stacked_widget.addWidget(z)
        self.tileAdded.emit(row, column)

        return z

    def toggle_signals(self, z, block):
        """Set signals block or unblocked for start, range, above, and hide
        :param z: z widget to toggle signals from
        :param block: boolean signifying block or unblock"""

        for name in ['start', 'top', 'step', 'steps', 'range', 'above', 'below']:
            getattr(z, name).blockSignals(block)


class ZPlanWidget(ZPlanWidgetMMCore):
    """Widget to plan out scanning dimension"""

    clicked = Signal()

    def __init__(self, z_limits: [float] = None, unit: str = 'um', parent: QWidget | None = None):
        """:param z_limits: list containing max and min values of z dimension
           :param unit: unit of all size values"""

        self.start = QDoubleSpinBox()

        super().__init__(parent)

        z_limits = z_limits if z_limits is not None else [float('-inf'), float('inf')]

        for i in range(self._grid_layout.count()):
            widget = self._grid_layout.itemAt(i).widget()

            if type(widget) == QLabel:
                if widget.text() == 'Bottom:':
                    widget.setText('')
                elif widget.text() == 'Top:':
                    widget.setText('End:')
                elif widget.text() == '\u00b5m':
                    widget.setText(unit)

        self._set_row_visible(0, False)  # hide steps row
        self._bottom_to_top.hide()
        self._top_to_bottom.hide()
        self.layout().children()[-1].itemAt(2).widget().hide()  # Direction label

        # Add start box
        self.start.valueChanged.connect(self._on_change)
        self.start.setSingleStep(.1)
        self.start.setRange(z_limits[0], z_limits[1])
        self._grid_layout.addWidget(QLabel("Start:"), 4, 0, Qt.AlignmentFlag.AlignRight)
        self._grid_layout.addWidget(self.start, 4, 1)
        # Add hide checkbox
        self.hide = QCheckBox('Hide')
        self._grid_layout.addWidget(self.hide, 7, 0)

        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

    def value(self):
        """Overwrite to change how z plan is calculated. Return a list of start and end positions"""

        if self._mode.value == 'top_bottom':
            return [self.start.value(), self.top.value()]
        elif self._mode.value == 'range_around':
            return [self.start.value() + self.range.value() / 2, self.start.value() - self.range.value() / 2]
        elif self._mode.value == 'above_below':
            return [self.start.value() + self.above.value(), self.start.value() - self.below.value()]

    def _on_change(self, update_steps: bool = True):
        """Overwrite to change setting step behaviour"""
        val = self.value()
        # update range readout
        self._range_readout.setText(f"Range: {self.currentZRange():.2f} \u00b5m")
        # update steps readout
        if update_steps:
            self.steps.blockSignals(True)
            if val is None:
                self.steps.setValue(0)
            else:
                self.steps.setValue(len(val))
            self.steps.blockSignals(False)
        self.valueChanged.emit(val)

    def _on_steps_changed(self, steps: int) -> None:
        """Overwrite to round step to stay within z range"""
        if steps:
            with signals_blocked(self.step):
                self.step.setValue(self.currentZRange() / steps)
        self._on_change(update_steps=False)
