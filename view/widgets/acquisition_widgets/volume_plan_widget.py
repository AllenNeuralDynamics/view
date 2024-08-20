#from pymmcore_widgets.useq_widgets._grid import
import useq
from view.widgets.base_device_widget import create_widget
from view.widgets.miscellaneous_widgets.q_item_delegates import QSpinItemDelegate
import numpy as np
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QLabel,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
    QComboBox,
    QMainWindow,
    QFrame,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
)


class VolumePlanWidget(QMainWindow):
    """Widget to plan out volume. Grid aspect based on pymmcore GridPlanWidget"""

    valueChanged = Signal(object)

    def __init__(self,
                 limits=[[float('-inf'), float('inf')] for _ in range(3)],
                 fov_dimensions: list[float] = [1.0, 1.0, 0],
                 fov_position: list[float] = [0.0, 0.0, 0.0],
                 coordinate_plane: list[str] = ['x', 'y', 'z'],
                 unit: str = 'um'):
        """

        :param limits:
        :param fov_dimensions:
        :param fov_position:
        :param coordinate_plane:
        :param unit:
        """
        super().__init__()

        layout = QVBoxLayout()
        self.button_group = QButtonGroup()
        self.button_group.setExclusive(True)

        self.limits = sorted(limits)
        self._fov_dimensions = fov_dimensions
        self._fov_position = fov_position
        self.coordinate_plane = [x.replace('-', '') for x in coordinate_plane]
        self.unit = unit

        # initialize property values
        self._grid_offset = [0, 0]
        self._mode = 'number'
        self._apply_all = True
        self._tile_visibility = np.ones([1, 1], dtype=bool)  # init as True
        self._scan_starts = np.zeros([0, 1], dtype=float)
        self._scan_ends = np.zeros([0, 1], dtype=float)

        self.rows = QSpinBox()
        self.rows.setSizePolicy(7, 0)
        self.rows.setRange(1, 1000)
        self.rows.setValue(1)
        self.rows.setSuffix(" fields")
        self.columns = QSpinBox()
        self.columns.setSizePolicy(7, 0)
        self.columns.setRange(1, 1000)
        self.columns.setValue(1)
        self.columns.setSuffix(" fields")
        # add to layout
        number_button = QRadioButton()
        number_button.clicked.connect(lambda: setattr(self, 'mode', 'number'))
        number_button.setChecked(True)
        self.button_group.addButton(number_button)
        number_widget = create_widget('H', number_button,
                                      QLabel('Rows:'), self.rows,
                                      QLabel('Cols:'), self.columns)
        number_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(number_widget)
        layout.addWidget(line())

        self.area_width = QDoubleSpinBox()
        self.area_width.setSizePolicy(7, 0)
        self.area_width.setRange(*self.limits[0])
        self.area_width.setDecimals(2)
        self.area_width.setSuffix(f" {self.unit}")
        self.area_width.setSingleStep(0.1)

        self.area_height = QDoubleSpinBox()
        self.area_height.setSizePolicy(7, 0)
        self.area_height.setRange(*self.limits[1])
        self.area_height.setDecimals(2)
        self.area_height.setSuffix(f" {self.unit}")
        self.area_height.setSingleStep(0.1)
        # add to layout
        area_button = QRadioButton()
        area_button.clicked.connect(lambda: setattr(self, 'mode', 'area'))
        self.button_group.addButton(area_button)
        area_widget = create_widget('H', area_button,
                                    QLabel('Width:'), self.area_width,
                                    QLabel('Height:'), self.area_height)
        area_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(area_widget)
        layout.addWidget(line())

        for i in range(2):
            low = QDoubleSpinBox()
            low.setSizePolicy(7, 0)
            low.setSuffix(f" {self.unit}")
            low.setRange(*self.limits[i])
            low.setDecimals(3)
            low.setValue(0)
            setattr(self, f'dim_{i}_low', low)
            high = QDoubleSpinBox()
            high.setSizePolicy(7, 0)
            high.setSuffix(f" {self.unit}")
            high.setRange(*self.limits[i])
            high.setDecimals(3)
            high.setValue(0)
            setattr(self, f'dim_{i}_high', high)

        # create labels based on polarity
        polarity = [1 if '-' not in x else -1 for x in coordinate_plane]
        dim_0_low_label = QLabel('Left: ') if polarity[0] == 1 else QLabel('Right: ')
        dim_0_high_label = QLabel('Right: ') if polarity[0] == 1 else QLabel('Left: ')
        dim_1_low_label = QLabel('Bottom: ') if polarity[1] == 1 else QLabel('Top: ')
        dim_1_high_label = QLabel('Top: ') if polarity[0] == 1 else QLabel('Bottom: ')

        # add to layout
        bound_button = QRadioButton()
        bound_button.clicked.connect(lambda: setattr(self, 'mode', 'bounds'))
        self.button_group.addButton(bound_button)
        bound_widget = create_widget('VH', bound_button, QWidget(),
                                     dim_0_low_label, dim_0_high_label, self.dim_0_low, self.dim_0_high,
                                     dim_1_low_label, dim_1_high_label, self.dim_1_low, self.dim_1_high)
        bound_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(bound_widget)
        layout.addWidget(line())

        self.overlap = QDoubleSpinBox()
        self.overlap.setRange(-100, 100)
        self.overlap.setValue(0)
        self.overlap.setSuffix(" %")
        overlap_widget = create_widget('H', QLabel('Overlap: '), self.overlap)
        overlap_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(overlap_widget)

        self.order = QComboBox()
        self.order.addItems(["row_wise_snake", "column_wise_snake", "spiral", "row_wise", "column_wise"])
        self.reverse = QCheckBox('Reverse')
        order_widget = create_widget('H', QLabel('Order: '), self.order, self.reverse)
        order_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(order_widget)

        self.relative_to = QComboBox()
        # create items based on polarity
        item = f"{'top' if polarity[1] == 1 else 'bottom'} {'left' if polarity[0] == 1 else 'right'}"
        self.relative_to.addItems(['center', item])
        relative_to_widget = create_widget('H', QLabel('Relative to: '), self.relative_to)
        relative_to_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(relative_to_widget)

        self.anchor_widgets = [QCheckBox(), QCheckBox(), QCheckBox()]
        self.grid_offset_widgets = [QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()]
        for i in range(3):
            box = self.grid_offset_widgets[i]
            box.setSizePolicy(7, 0)
            box.setValue(fov_position[i])
            box.setDecimals(6)
            box.setRange(*self.limits[i])
            box.setSuffix(f" {unit}")
            box.valueChanged.connect(lambda: setattr(self, 'grid_position', [self.grid_offset_widgets[0].value(),
                                                                             self.grid_offset_widgets[1].value(),
                                                                             self.grid_offset_widgets[2].value()]))
            box.setDisabled(True)

            self.anchor_widgets[i].toggled.connect(lambda enable, index=i: self.toggle_grid_position(enable, index))
        anchor_widget = create_widget('VH', QWidget(), QLabel('Anchor Grid: '),
                                      self.grid_offset_widgets[0], self.anchor_widgets[0],
                                      self.grid_offset_widgets[1], self.anchor_widgets[1],
                                      self.grid_offset_widgets[2], self.anchor_widgets[2], )
        anchor_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(anchor_widget)

        self.apply_all_box = QCheckBox('Apply to all: ')
        self.apply_all_box.setChecked(True)
        self.apply_all_box.toggled.connect(lambda checked: setattr(self, 'apply_all', checked))
        layout.addWidget(self.apply_all_box)

        # connect widgets to trigger on_change when toggled
        self.dim_1_high.valueChanged.connect(self._on_change)
        self.dim_0_high.valueChanged.connect(self._on_change)
        self.dim_1_low.valueChanged.connect(self._on_change)
        self.dim_0_low.valueChanged.connect(self._on_change)
        self.rows.valueChanged.connect(self._on_change)
        self.columns.valueChanged.connect(self._on_change)
        self.area_width.valueChanged.connect(self._on_change)
        self.area_height.valueChanged.connect(self._on_change)
        self.overlap.valueChanged.connect(self._on_change)
        self.order.currentIndexChanged.connect(self._on_change)
        self.relative_to.currentIndexChanged.connect(self._on_change)

        # create table portion
        self.table_columns = ['row, column', *[f'{x} [{unit}]' for x in self.coordinate_plane],
                        f'{self.coordinate_plane[2]} max [{unit}]', 'visibility']
        self.tile_table = QTableWidget()
        self.tile_table.setColumnCount(len(self.table_columns))
        self.tile_table.setHorizontalHeaderLabels(self.table_columns)
        self.tile_table.resizeColumnsToContents()
        for i in range(1, len(self.table_columns)):  # skip first column
            column_name = self.tile_table.horizontalHeaderItem(i).text()
            delegate = QSpinItemDelegate()
            # table does not take ownership of the delegates, so they are removed from memory as they
            # are local variables causing a Segmentation fault. Need to be attributes
            setattr(self, f'table_column_{column_name}_delegate', delegate)
            self.tile_table.setItemDelegateForColumn(i, delegate)

        self.tile_table.itemChanged.connect(self.tile_table_changed)
        layout.addWidget(self.tile_table)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)

    def update_tile_table(self, value):
        """Update tile table when value changes
        ":param value: new value
        """

        # update table
        # table_order = [[int(x) for x in self.tile_table.item(i, 0).text() if x.isdigit()] for i in
        #                range(self.tile_table.rowCount())]
        # value_order = [[t.row, t.col] for t in value]
        # if table_order != value_order and len(value_order) != 0:
        # clear table and add back tiles in the correct order if
        self.tile_table.clearContents()
        self.tile_table.setRowCount(0)
        for tile in value:
            self.add_tile_to_table(tile.row, tile.col)

    def add_tile_to_table(self, row, column):
        """
        Add a configured tile into tile_table
        :param row: row of tile
        :param column: column of value
        :return:
        """

        self.tile_table.blockSignals(True)
        # add new row to table
        table_row = self.tile_table.rowCount()
        self.tile_table.insertRow(table_row)

        kwargs = {'row, column': [row, column],
                  f'{self.coordinate_plane[0]} [{self.unit}]': self.tile_positions[row][column][0],
                  f'{self.coordinate_plane[1]} [{self.unit}]': self.tile_positions[row][column][1],
                  f'{self.coordinate_plane[2]} [{self.unit}]': self._scan_starts[row, column],
                  f'{self.coordinate_plane[2]} max [{self.unit}]': self._scan_ends[row, column]}
        items = {}
        for header_col, header in enumerate(self.table_columns[:-1]):
            item = QTableWidgetItem()
            if header == 'row, column':
                item.setText(str([row, column]))
            else:
                value = float(kwargs[header])
                item.setData(Qt.EditRole, value)
            items[header] = item
            self.tile_table.setItem(table_row, header_col, item)

        # disable cells
        disable = list(kwargs.keys())
        if not self.apply_all or (row, column) == (0, 0):
            disable.remove(f'{self.coordinate_plane[2]} max [{self.unit}]')
            if self.anchor_widgets[2].isChecked():
                disable.remove(f'{self.coordinate_plane[2]} [{self.unit}]')
        flags = QTableWidgetItem().flags()
        flags &= ~Qt.ItemIsEditable
        for var in disable:
            items[var].setFlags(flags)

        # add in QCheckbox for visibility
        visible = QCheckBox('Visible')
        visible.setChecked(self._tile_visibility[row, column])
        visible.toggled.connect(lambda checked: self._tile_visibility.itemset((row, column), checked))
        visible.toggled.connect(lambda checked, val=self.value(): self.valueChanged.emit(val))
        visible.setEnabled(not all([self.apply_all, (row, column) != (0, 0)]))
        self.tile_table.setCellWidget(table_row, self.table_columns.index('visibility'), visible)

        self.tile_table.blockSignals(False)

    def tile_table_changed(self, item):
        """
        Update values if item is changed
        :param item: item that has been changed
        :return:
        """

        row, column = [int(x) for x in self.tile_table.item(item.row(), 0).text() if x.isdigit()]
        column_title = self.table_columns[item.row()]

        if column_title == f'{self.coordinate_plane[2]} [{self.unit}]':
            self._scan_starts[row, column] = item.data(Qt.EditRole)
            self.valueChanged.emit(self.value())
        elif column_title == f'{self.coordinate_plane[2]} max [{self.unit}]':
            self._scan_ends[row, column] = item.data(Qt.EditRole)
            self.valueChanged.emit(self.value())
    def toggle_grid_position(self, enable, index):
        """If grid is anchored, allow user to input grid position"""

        self.grid_offset_widgets[index].setEnabled(enable)
        if not enable:  # Graph is not anchored
            self.grid_offset_widgets[index].setValue(self.fov_position[index])
        self._on_change()
    @property
    def apply_all(self):
        return self._apply_all

    @apply_all.setter
    def apply_all(self, value: bool):
        self._apply_all = value
        self._on_change()

    @property
    def fov_position(self):
        return self._fov_position

    @fov_position.setter
    def fov_position(self, value):
        self._fov_position = value
        for i, anchor in enumerate(self.anchor_widgets):
            if not anchor.isChecked() and anchor.isEnabled():
                self.grid_offset_widgets[i].setValue(value[i])

    @property
    def fov_dimensions(self):
        return self._fov_dimensions

    @fov_dimensions.setter
    def fov_dimensions(self, value):
        if type(value) is not list and len(value) != 2:
            raise ValueError
        self.fov_dimensions = value
        self._on_change()

    @property
    def grid_offset(self):
        return self._grid_offset

    @grid_offset.setter
    def grid_offset(self, value):
        if type(value) is not list and len(value) != 3:
            raise ValueError
        self._grid_offset = value
        self._on_change()

    @property
    def tile_positions(self):
        """Returns 2d list of tile positions based on widget values"""

        coords = [[None] * self.value().columns for _ in range(self.value().rows)]
        if self._mode != "bounds":
            for tile in self.value():
                coords[tile.row][tile.col] = [tile.x + self.grid_offset[0], tile.y + self.grid_offset[1]]
        else:
            for tile in self.value():
                coords[tile.row][tile.col] = [tile.x, tile.y]
        return coords

    def _on_change(self) -> None:

        if (val := self.value()) is None:
            return  # pragma: no cover
        # update sizes of arrays
        if [val.rows, val.rows] != self._scan_starts.shape[:2]:
            self._tile_visibility = np.resize(self._tile_visibility, [val.rows, val.rows])
            self._scan_starts = np.resize(self._scan_starts, [val.rows, val.rows])
            self._scan_ends = np.resize(self._scan_ends, [val.rows, val.rows])
        self.update_tile_table(val)
        self.valueChanged.emit(val)

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        if value not in ['number', 'area', 'bounds']:
            raise ValueError
        self._mode = value
        self._on_change()

    def value(self):
        """Overwriting value so Area mode doesn't multiply width and height by 1000,
        pass in reverse variable, and have a customized relative enum value"""

        over = self.overlap.value()
        common = {
            "reverse": self.reverse.isChecked(),
            "overlap": (over, over),
            "mode": self.order.currentText(),
            "fov_width": self.fov_dimensions[0],
            "fov_height": self.fov_dimensions[1],
        }
        if self._mode == 'number':
            return GridRowsColumns(
                rows=self.rows.value(),
                columns=self.columns.value(),
                relative_to='center' if self.relative_to.currentText() else "top_left",
                **common,
            )
        elif self._mode == 'bounds':
            return GridFromEdges(
                top=self.dim_1_high.value(),
                left=self.dim_0_low.value(),
                bottom=self.dim_1_low.value(),
                right=self.dim_0_high.value(),
                **common,
            )
        elif self._mode == 'area':
            return GridWidthHeight(
                width=self.area_width.value(),
                height=self.area_height.value(),
                relative_to='center' if self.relative_to.currentText() else "top_left",
                **common,
            )
        raise NotImplementedError


def line():
    frame = QFrame()
    frame.setFrameShape(QFrame.HLine)
    return frame


class GridFromEdges(useq.GridFromEdges):
    """Add row and column attributes and allow reversible order"""
    reverse = property()  # initialize property

    def __init__(self, reverse=False, *args, **kwargs):
        # rewrite property since pydantic doesn't allow to add attr
        setattr(type(self), 'reverse', property(fget=lambda x: reverse))
        super().__init__(*args, **kwargs)

    @property
    def rows(self):
        dx, _ = self._step_size(self.fov_width, self.fov_height)
        return self._nrows(dx)

    @property
    def columns(self):
        _, dy = self._step_size(self.fov_width, self.fov_height)
        return self._ncolumns(dy)

    def iter_grid_positions(self, *args, **kwargs):
        """Rewrite to reverse order"""

        if not self.reverse:
            for tile in super().iter_grid_positions(*args, **kwargs):
                yield tile
        else:
            for tile in reversed(list(super().iter_grid_positions(*args, **kwargs))):
                yield tile


class GridWidthHeight(useq.GridWidthHeight):
    """Add row and column attributes and allow reversible order"""
    reverse = property()

    def __init__(self, reverse=False, *args, **kwargs):
        setattr(type(self), 'reverse', property(fget=lambda x: reverse))
        super().__init__(*args, **kwargs)

    @property
    def rows(self):
        dx, _ = self._step_size(self.fov_width, self.fov_height)
        return self._nrows(dx)

    @property
    def columns(self):
        _, dy = self._step_size(self.fov_width, self.fov_height)
        return self._ncolumns(dy)

    def iter_grid_positions(self, *args, **kwargs):
        """Rewrite to reverse order"""

        if not self.reverse:
            for tile in super().iter_grid_positions(*args, **kwargs):
                yield tile
        else:
            for tile in reversed(list(super().iter_grid_positions(*args, **kwargs))):
                yield tile


class GridRowsColumns(useq.GridRowsColumns):
    """ Allow reversible order"""
    reverse = property()

    def __init__(self, reverse=False, *args, **kwargs):
        setattr(type(self), 'reverse', property(fget=lambda x: reverse))
        super().__init__(*args, **kwargs)

    def iter_grid_positions(self, *args, **kwargs):
        """Rewrite to reverse order"""

        if not self.reverse:
            for tile in super().iter_grid_positions(*args, **kwargs):
                yield tile
        else:
            for tile in reversed(list(super().iter_grid_positions(*args, **kwargs))):
                yield tile
