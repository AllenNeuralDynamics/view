from typing import Generator, Literal, Union, Optional, List
    
import numpy as np
import useq
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QLabel,
    QMainWindow,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from view.widgets.base_device_widget import create_widget
from view.widgets.miscellaneous_widgets.q_item_delegates import QSpinItemDelegate
from view.widgets.miscellaneous_widgets.q_start_stop_table_header import QStartStopTableHeader


class GridFromEdges(useq.GridFromEdges):
    """
    Subclassing useq.GridFromEdges to add row and column attributes and allow reversible order.
    """

    reverse = property()  # initialize property

    def __init__(self, reverse: bool = False, *args, **kwargs) -> None:
        """
        Initialize the GridFromEdges.

        :param reverse: Whether to reverse the order, defaults to False
        :type reverse: bool, optional
        """
        # rewrite property since pydantic doesn't allow to add attr
        setattr(type(self), "reverse", property(fget=lambda x: reverse))
        super().__init__(*args, **kwargs)

    @property
    def rows(self) -> int:
        """
        Get the number of rows.

        :return: The number of rows
        :rtype: int
        """
        dx, _ = self._step_size(self.fov_width, self.fov_height)
        return self._nrows(dx)

    @property
    def columns(self) -> int:
        """
        Get the number of columns.

        :return: The number of columns
        :rtype: int
        """
        _, dy = self._step_size(self.fov_width, self.fov_height)
        return self._ncolumns(dy)

    def iter_grid_positions(self, *args, **kwargs) -> Generator:
        """
        Iterate over grid positions.

        :yield: The grid positions
        :rtype: Generator
        """
        if not self.reverse:
            for tile in super().iter_grid_positions(*args, **kwargs):
                yield tile
        else:
            for tile in reversed(list(super().iter_grid_positions(*args, **kwargs))):
                yield tile


class GridWidthHeight(useq.GridWidthHeight):
    """
    Subclassing useq.GridWidthHeight to add row and column attributes and allow reversible order.
    """

    reverse = property()

    def __init__(self, reverse: bool = False, *args, **kwargs) -> None:
        """
        Initialize the GridWidthHeight.

        :param reverse: Whether to reverse the order, defaults to False
        :type reverse: bool, optional
        """
        # rewrite property since pydantic doesn't allow to add attr
        setattr(type(self), "reverse", property(fget=lambda x: reverse))
        super().__init__(*args, **kwargs)

    @property
    def rows(self) -> int:
        """
        Get the number of rows.

        :return: The number of rows
        :rtype: int
        """
        dx, _ = self._step_size(self.fov_width, self.fov_height)
        return self._nrows(dx)

    @property
    def columns(self) -> int:
        """
        Get the number of columns.

        :return: The number of columns
        :rtype: int
        """
        _, dy = self._step_size(self.fov_width, self.fov_height)
        return self._ncolumns(dy)

    def iter_grid_positions(self, *args, **kwargs) -> Generator:
        """
        Iterate over grid positions.

        :yield: The grid positions
        :rtype: Generator
        """
        if not self.reverse:
            for tile in super().iter_grid_positions(*args, **kwargs):
                yield tile
        else:
            for tile in reversed(list(super().iter_grid_positions(*args, **kwargs))):
                yield tile


class GridRowsColumns(useq.GridRowsColumns):
    """
    Subclass useq.GridRowsColumns to allow reversible order.
    """

    reverse = property()

    def __init__(self, reverse: bool = False, *args, **kwargs) -> None:
        """
        Initialize the GridRowsColumns.

        :param reverse: Whether to reverse the order, defaults to False
        :type reverse: bool, optional
        """
        setattr(type(self), "reverse", property(fget=lambda x: reverse))
        super().__init__(*args, **kwargs)

    def iter_grid_positions(self, *args, **kwargs) -> Generator:
        """
        Iterate over grid positions.

        :yield: The grid positions
        :rtype: Generator
        """
        if not self.reverse:
            for tile in super().iter_grid_positions(*args, **kwargs):
                yield tile
        else:
            for tile in reversed(list(super().iter_grid_positions(*args, **kwargs))):
                yield tile


class VolumePlanWidget(QMainWindow):
    """
    Widget to plan out volume. Grid aspect based on pymmcore GridPlanWidget.
    """

    valueChanged = Signal(object)

    def __init__(
        self,
        limits: Optional[List[List[float]]] = None,
        fov_dimensions: Optional[List[float]] = None,
        fov_position: Optional[List[float]] = None,
        coordinate_plane: Optional[List[str]] = None,
        unit: str = "um",
    ) -> None:
        """
        Initialize the VolumePlanWidget.

        :param limits: The limits for the volume, defaults to None
        :type limits: Optional[List[List[float]]], optional
        :param fov_dimensions: The dimensions of the field of view, defaults to None
        :type fov_dimensions: Optional[List[float]], optional
        :param fov_position: The position of the field of view, defaults to None
        :type fov_position: Optional[List[float]], optional
        :param coordinate_plane: The coordinate plane, defaults to None
        :type coordinate_plane: Optional[List[str]], optional
        :param unit: The unit of measurement, defaults to "um"
        :type unit: str, optional
        """
        super().__init__()

        layout = QVBoxLayout()
        self.button_group = QButtonGroup()
        self.button_group.setExclusive(True)

        self.limits = limits if limits else [[float("-inf"), float("inf")] for _ in range(3)]
        self._fov_dimensions = fov_dimensions if fov_dimensions else [1.0, 1.0, 0]
        self._fov_position = fov_position if fov_position else [0.0, 0.0, 0.0]
        self.coordinate_plane = [x.replace("-", "") for x in coordinate_plane] if coordinate_plane else ["x", "y", "z"]
        self.unit = unit

        # initialize property values
        self._grid_offset = [0, 0]
        self._mode = None
        self._apply_all = True
        self._tile_visibility = np.ones([1, 1], dtype=bool)  # init as True
        self._scan_starts = np.zeros([1, 1], dtype=float)
        self._scan_ends = np.zeros([1, 1], dtype=float)
        self.start = None  # tile to start at. If none, then default is first tile
        self.stop = None  # tile to end at. If none, then default is last tile

        self.rows = QSpinBox()
        self.rows.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
        self.rows.setRange(1, 1000)
        self.rows.setValue(1)
        self.rows.setSuffix(" fields")
        self.columns = QSpinBox()
        self.columns.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
        self.columns.setRange(1, 1000)
        self.columns.setValue(1)
        self.columns.setSuffix(" fields")
        # add to layout
        self.number_button = QRadioButton()
        self.number_button.clicked.connect(lambda: setattr(self, "mode", "number"))
        self.button_group.addButton(self.number_button)
        self.number_widget = create_widget("H", QLabel("Rows:"), self.rows, QLabel("Cols:"), self.columns)
        self.number_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(create_widget("H", self.number_button, self.number_widget))
        layout.addWidget(line())

        self.area_width = QDoubleSpinBox()
        self.area_width.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
        self.area_width.setRange(0.01, self.limits[0][1] - self.limits[0][0])
        self.area_width.setValue(0.01)  # width can't be zero
        self.area_width.setDecimals(2)
        self.area_width.setSuffix(f" {self.unit}")
        self.area_width.setSingleStep(0.1)

        self.area_height = QDoubleSpinBox()
        self.area_height.setValue(0.01)  # height can't be zero
        self.area_height.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
        self.area_width.setRange(0.01, self.limits[1][1] - self.limits[1][0])
        self.area_height.setDecimals(2)
        self.area_height.setSuffix(f" {self.unit}")
        self.area_height.setSingleStep(0.1)
        # add to layout
        self.area_button = QRadioButton()
        self.area_button.clicked.connect(lambda: setattr(self, "mode", "area"))
        self.button_group.addButton(self.area_button)
        self.area_widget = create_widget("H", QLabel("Width:"), self.area_width, QLabel("Height:"), self.area_height)
        self.area_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(create_widget("H", self.area_button, self.area_widget))
        layout.addWidget(line())

        for i in range(2):
            low = QDoubleSpinBox()
            low.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
            low.setSuffix(f" {self.unit}")
            low.setRange(*self.limits[i])
            low.setDecimals(3)
            low.setValue(0)
            setattr(self, f"dim_{i}_low", low)
            high = QDoubleSpinBox()
            high.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
            high.setSuffix(f" {self.unit}")
            high.setRange(*self.limits[i])
            high.setDecimals(3)
            high.setValue(0)
            setattr(self, f"dim_{i}_high", high)

        # create labels based on polarity
        polarity = [1 if "-" not in x else -1 for x in coordinate_plane]
        dim_0_low_label = QLabel("Left: ") if polarity[0] == 1 else QLabel("Right: ")
        dim_0_high_label = QLabel("Right: ") if polarity[0] == 1 else QLabel("Left: ")
        dim_1_low_label = QLabel("Bottom: ") if polarity[1] == 1 else QLabel("Top: ")
        dim_1_high_label = QLabel("Top: ") if polarity[0] == 1 else QLabel("Bottom: ")

        # add to layout
        self.bounds_button = QRadioButton()
        self.bounds_button.clicked.connect(lambda: setattr(self, "mode", "bounds"))
        self.button_group.addButton(self.bounds_button)
        self.bounds_widget = create_widget(
            "VH",
            dim_0_low_label,
            dim_0_high_label,
            self.dim_0_low,
            self.dim_0_high,
            dim_1_low_label,
            dim_1_high_label,
            self.dim_1_low,
            self.dim_1_high,
        )
        self.bounds_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(create_widget("H", self.bounds_button, self.bounds_widget))
        layout.addWidget(line())

        self.overlap = QDoubleSpinBox()
        self.overlap.setRange(-100, 100)
        self.overlap.setValue(0)
        self.overlap.setSuffix(" %")
        overlap_widget = create_widget("H", QLabel("Overlap: "), self.overlap)
        overlap_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(overlap_widget)

        self.order = QComboBox()
        self.order.addItems(["row_wise_snake", "column_wise_snake", "spiral", "row_wise", "column_wise"])
        self.reverse = QCheckBox("Reverse")
        order_widget = create_widget("H", QLabel("Order: "), self.order, self.reverse)
        order_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(order_widget)

        self.relative_to = QComboBox()
        # create items based on polarity
        item = f"{'top' if polarity[1] == 1 else 'bottom'} {'left' if polarity[0] == 1 else 'right'}"
        self.relative_to.addItems(["center", item])
        relative_to_widget = create_widget("H", QLabel("Relative to: "), self.relative_to)
        relative_to_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(relative_to_widget)

        self.anchor_widgets = [QCheckBox(), QCheckBox(), QCheckBox()]
        self.grid_offset_widgets = [QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()]
        for i in range(3):
            box = self.grid_offset_widgets[i]
            box.setSizePolicy(QSizePolicy.Policy(7), QSizePolicy.Policy(0))
            box.setValue(self.fov_position[i])
            box.setDecimals(6)
            box.setRange(*self.limits[i])
            box.setSuffix(f" {unit}")
            box.valueChanged.connect(
                lambda: setattr(
                    self,
                    "grid_offset",
                    [
                        self.grid_offset_widgets[0].value(),
                        self.grid_offset_widgets[1].value(),
                        self.grid_offset_widgets[2].value(),
                    ],
                )
            )
            box.setDisabled(True)

            self.anchor_widgets[i].toggled.connect(lambda enable, index=i: self.toggle_grid_position(enable, index))
        anchor_widget = create_widget(
            "VH",
            QWidget(),
            QLabel("Anchor Grid: "),
            self.grid_offset_widgets[0],
            self.anchor_widgets[0],
            self.grid_offset_widgets[1],
            self.anchor_widgets[1],
            self.grid_offset_widgets[2],
            self.anchor_widgets[2],
        )
        anchor_widget.layout().setAlignment(Qt.AlignLeft)
        layout.addWidget(anchor_widget)

        self.apply_all_box = QCheckBox("Apply to all: ")
        self.apply_all_box.setChecked(True)
        self.apply_all_box.toggled.connect(lambda checked: setattr(self, "apply_all", checked))
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
        self.reverse.toggled.connect(self._on_change)

        # create table portion
        self.table_columns = [
            "row, column",
            *[f"{x} [{unit}]" for x in self.coordinate_plane],
            f"{self.coordinate_plane[2]} max [{unit}]",
            "visibility",
        ]
        self.tile_table = QTableWidget()
        # configure and set header
        self.header = QStartStopTableHeader(
            self.tile_table
        )  # header object that allows user to specify start/stop tile
        self.header.startChanged.connect(lambda index: setattr(self, "start", index))
        self.header.stopChanged.connect(lambda index: setattr(self, "stop", index))

        self.tile_table.setVerticalHeader(self.header)

        self.tile_table.setColumnCount(len(self.table_columns))
        self.tile_table.setHorizontalHeaderLabels(self.table_columns)
        self.tile_table.resizeColumnsToContents()
        for i in range(1, len(self.table_columns)):  # skip first column
            column_name = self.tile_table.horizontalHeaderItem(i).text()
            delegate = QSpinItemDelegate()
            # table does not take ownership of the delegates, so they are removed from memory as they
            # are local variables causing a Segmentation fault. Need to be attributes
            setattr(self, f"table_column_{column_name}_delegate", delegate)
            self.tile_table.setItemDelegateForColumn(i, delegate)

        self.tile_table.itemChanged.connect(self.tile_table_changed)

        layout.addWidget(self.tile_table)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)

        self.mode = "number"  # initialize mode
        self.update_tile_table(self.value())  # initialize table

    def update_tile_table(self, value: Union[GridRowsColumns, GridFromEdges, GridWidthHeight]) -> None:
        """
        Update the tile table with the given value.

        :param value: The grid value to update the table with
        :type value: Union[GridRowsColumns, GridFromEdges, GridWidthHeight]
        """
        # check if order changed
        table_order = [
            [int(x) for x in self.tile_table.item(i, 0).text() if x.isdigit()]
            for i in range(self.tile_table.rowCount())
        ]
        value_order = [[t.row, t.col] for t in value]
        order_matches = np.array_equal(table_order, value_order)
        if not order_matches:
            self.refill_table()
            return

        # check if tile positions match
        table_pos = [
            [self.tile_table.item(j, i).data(Qt.EditRole) for i in range(1, 4)]
            for j in range(self.tile_table.rowCount())
        ]
        value_pos = self.tile_positions
        pos_matches = np.array_equal(table_pos, value_pos)
        if not pos_matches:
            self.refill_table()
            return

        # TODO: Fix this?
        # # check if visibility matches
        # table_vis = [self.tile_table.item(i, self.table_columns.index('visibility')).data(Qt.EditRole) for i in
        #              range(self.tile_table.rowCount())]
        # value_vis = [self._tile_visibility[t.row, t.col] for t in value]
        # vis_matches = (table_vis == value_vis).all()
        # if not vis_matches:
        #     self.refill_table()
        #     return

    def refill_table(self) -> None:
        """
        Refill the tile table with the current grid values.
        """
        value = self.value()
        self.tile_table.clearContents()
        self.tile_table.setRowCount(0)
        for tile in value:
            self.add_tile_to_table(tile.row, tile.col)
        self.header.blockSignals(True)  # don't trigger update
        if self.start is not None:
            self.header.set_start(self.start)
        if self.stop is not None:
            self.header.set_stop(self.stop)
        self.header.blockSignals(False)

    def add_tile_to_table(self, row: int, column: int) -> None:
        """
        Add a tile to the table at the specified row and column.

        :param row: The row index
        :type row: int
        :param column: The column index
        :type column: int
        """
        self.tile_table.blockSignals(True)
        # add new row to table
        table_row = self.tile_table.rowCount()
        self.tile_table.insertRow(table_row)

        kwargs = {
            "row, column": [row, column],
            f"{self.coordinate_plane[0]} [{self.unit}]": self.tile_positions[row, column][0],
            f"{self.coordinate_plane[1]} [{self.unit}]": self.tile_positions[row, column][1],
            f"{self.coordinate_plane[2]} [{self.unit}]": self._scan_starts[row, column],
            f"{self.coordinate_plane[2]} max [{self.unit}]": self._scan_ends[row, column],
        }
        items = {}
        for header_col, header in enumerate(self.table_columns[:-1]):
            item = QTableWidgetItem()
            if header == "row, column":
                item.setText(str([row, column]))
            else:
                value = float(kwargs[header])
                item.setData(Qt.EditRole, value)
            items[header] = item
            self.tile_table.setItem(table_row, header_col, item)

        # disable cells
        disable = list(kwargs.keys())
        if not self.apply_all or (row, column) == (0, 0):
            disable.remove(f"{self.coordinate_plane[2]} max [{self.unit}]")
            if self.anchor_widgets[2].isChecked() or not self.apply_all:
                disable.remove(f"{self.coordinate_plane[2]} [{self.unit}]")
        flags = QTableWidgetItem().flags()
        flags &= ~Qt.ItemIsEditable
        for var in disable:
            items[var].setFlags(flags)

        # add in QCheckbox for visibility
        visible = QCheckBox("Visible")
        visible.setChecked(bool(self._tile_visibility[row, column]))
        visible.toggled.connect(lambda checked: self.toggle_visibility(checked, row, column))
        visible.setEnabled(not all([self.apply_all, (row, column) != (0, 0)]))
        self.tile_table.setCellWidget(table_row, self.table_columns.index("visibility"), visible)

        self.tile_table.blockSignals(False)

    def toggle_visibility(self, checked: bool, row: int, column: int) -> None:
        """
        Toggle the visibility of a tile.

        :param checked: Whether the tile is visible
        :type checked: bool
        :param row: The row index
        :type row: int
        :param column: The column index
        :type column: int
        """
        self._tile_visibility[row, column] = checked
        if self.apply_all and [row, column] == [0, 0]:  # trigger update of all subsequent checkboxes
            for r in range(self.tile_table.rowCount()):
                self.tile_table.cellWidget(r, self.table_columns.index("visibility")).setChecked(checked)
            self.valueChanged.emit(self.value())  # emit value changes at end of changes

        elif not self.apply_all:
            self.valueChanged.emit(self.value())

    def tile_table_changed(self, item: QTableWidgetItem) -> None:
        """
        Handle changes to the tile table.

        :param item: The table widget item that changed
        :type item: QTableWidgetItem
        """
        row, column = [int(x) for x in self.tile_table.item(item.row(), 0).text() if x.isdigit()]
        col_title = self.table_columns[item.column()]
        titles = [f"{self.coordinate_plane[2]} [{self.unit}]", f"{self.coordinate_plane[2]} max [{self.unit}]"]
        if col_title in titles:
            value = item.data(Qt.EditRole)
            array = self._scan_starts if col_title == titles[0] else self._scan_ends
            array[row, column] = value

            if self.apply_all and [row, column] == [0, 0]:  # trigger update of all subsequent tiles
                for r in range(self.tile_table.rowCount()):
                    self.tile_table.item(r, item.column()).setData(Qt.EditRole, value)
                self.valueChanged.emit(self.value())  # emit value changes at end of changes

            elif not self.apply_all:
                self.valueChanged.emit(self.value())

            if col_title == f"{self.coordinate_plane[2]} [{self.unit}]":
                self.grid_offset_widgets[2].setValue(value)

    def toggle_grid_position(self, enable: bool, index: Literal[0, 1, 2]) -> None:
        """
        Toggle the grid position.

        :param enable: Whether to enable the grid position
        :type enable: bool
        :param index: The index of the grid position
        :type index: Literal[0, 1, 2]
        """
        self.grid_offset_widgets[index].setEnabled(enable)
        if not enable:  # Graph is not anchored
            self.grid_offset_widgets[index].setValue(self.fov_position[index])
        self._on_change()
        if not enable:
            self.refill_table()  # order, pos, and visibilty doesn't change, so update table to reconfigure editablility

    @property
    def apply_all(self) -> bool:
        """
        Get whether to apply all settings.

        :return: Whether to apply all settings
        :rtype: bool
        """
        return self._apply_all

    @apply_all.setter
    def apply_all(self, value: bool) -> None:
        """
        Set whether to apply all settings.

        :param value: Whether to apply all settings
        :type value: bool
        """
        self._apply_all = value

        # correctly configure anchor and grid_offset_widget
        self.anchor_widgets[2].setEnabled(value)
        self.grid_offset_widgets[2].setEnabled(value and self.anchor_widgets[2].isChecked())

        # update values if apply_all applied
        if value:
            self.blockSignals(True)  # emit signal only once
            self.toggle_visibility(self.tile_visibility[0, 0], 0, 0)
            tile_zero_row = self.tile_table.findItems("[0, 0]", Qt.MatchExactly)[0].row()
            start_i = self.table_columns.index(f"{self.coordinate_plane[2]} [{self.unit}]")
            end_i = self.table_columns.index(f"{self.coordinate_plane[2]} max [{self.unit}]")
            self.tile_table_changed(self.tile_table.item(tile_zero_row, start_i))
            self.tile_table_changed(self.tile_table.item(tile_zero_row, end_i))
            self.blockSignals(False)

        self._on_change()
        self.refill_table()  # order, pos, and visibilty doesn't change, so update table to reconfigure editablility

    @property
    def fov_position(self) -> List[float]:
        """
        Get the field of view position.

        :return: The field of view position
        :rtype: List[float]
        """
        return self._fov_position

    @fov_position.setter
    def fov_position(self, value: List[float]) -> None:
        """
        Set the field of view position.

        :param value: The field of view position
        :type value: List[float]
        :raises ValueError: If the value is not a list of length 3
        """
        if type(value) is not list and len(value) != 3:
            raise ValueError
        elif value != self._fov_position:
            self._fov_position = value
            for anchor, pos, val in zip(self.anchor_widgets, self.grid_offset_widgets, value):
                if not anchor.isChecked() and anchor.isEnabled():
                    self.blockSignals(True)  # only emit valueChanged once at end
                    pos.setValue(val)
                    self.blockSignals(False)

            self._on_change()

    @property
    def fov_dimensions(self) -> List[float]:
        """
        Get the field of view dimensions.

        :return: The field of view dimensions
        :rtype: List[float]
        """
        return self._fov_dimensions

    @fov_dimensions.setter
    def fov_dimensions(self, value: List[float]) -> None:
        """
        Set the field of view dimensions.

        :param value: The field of view dimensions
        :type value: List[float]
        :raises ValueError: If the value is not a list of length 2
        """
        if type(value) is not list and len(value) != 2:
            raise ValueError
        self.fov_dimensions = value
        self._on_change()

    @property
    def grid_offset(self) -> List[float]:
        """
        Get the grid offset.

        :return: The grid offset
        :rtype: List[float]
        """
        return self._grid_offset

    @grid_offset.setter
    def grid_offset(self, value: List[float]) -> None:
        """
        Set the grid offset.

        :param value: The grid offset
        :type value: List[float]
        :raises ValueError: If the value is not a list of length 3
        """
        if type(value) is not list and len(value) != 3:
            raise ValueError
        self._grid_offset = value
        self._scan_starts[:, :] = value[2]
        self._on_change()

    @property
    def tile_positions(self) -> List[List[float]]:
        """
        Get the tile positions.

        :return: The tile positions
        :rtype: List[List[float]]
        """
        value = self.value()
        coords = np.zeros((value.rows, value.columns, 3))
        if self._mode != "bounds":
            for tile in value:
                coords[tile.row, tile.col, :] = [
                    tile.x + self.grid_offset[0],
                    tile.y + self.grid_offset[1],
                    self._scan_starts[tile.row][tile.col],
                ]
        else:
            for tile in value:
                coords[tile.row, tile.col, :] = [tile.x, tile.y, self._scan_starts[tile.row][tile.col]]
        return coords

    @property
    def tile_visibility(self) -> np.ndarray:
        """
        Get the tile visibility.

        :return: The tile visibility
        :rtype: np.ndarray
        """
        return self._tile_visibility

    @property
    def scan_starts(self) -> np.ndarray:
        """
        Get the scan start positions.

        :return: The scan start positions
        :rtype: np.ndarray
        """
        return self._scan_starts

    @property
    def scan_ends(self) -> np.ndarray:
        """
        Get the scan end positions.

        :return: The scan end positions
        :rtype: np.ndarray
        """
        return self._scan_ends

    def _on_change(self) -> None:
        """
        Handle changes to the grid.

        :return: None
        """
        if (val := self.value()) is None:
            return  # pragma: no cover
        # update sizes of arrays
        if (val.rows, val.columns) != self._scan_starts.shape:
            self._tile_visibility = np.resize(self._tile_visibility, [val.rows, val.columns])
            self._scan_starts = np.resize(self._scan_starts, [val.rows, val.columns])
            self._scan_ends = np.resize(self._scan_ends, [val.rows, val.columns])
        self.update_tile_table(val)
        self.valueChanged.emit(val)

    @property
    def mode(self) -> Literal["number", "area", "bounds"]:
        """
        Get the grid mode.

        :return: The grid mode
        :rtype: Literal["number", "area", "bounds"]
        """
        return self._mode

    @mode.setter
    def mode(self, value: Literal["number", "area", "bounds"]) -> None:
        """
        Set the grid mode.

        :param value: The grid mode
        :type value: Literal["number", "area", "bounds"]
        :raises ValueError: If the value is not a valid mode
        """
        if value not in ["number", "area", "bounds"]:
            raise ValueError
        self._mode = value

        getattr(self, f"{value}_button").setChecked(True)

        for mode in ["number", "area", "bounds"]:
            getattr(self, f"{mode}_widget").setEnabled(value == mode)

        for i in range(3):
            anchor, pos = self.anchor_widgets[i], self.grid_offset_widgets[i]
            anchor_enable = value != "bounds" if i != 2 else value != "bounds" and self.apply_all
            anchor.setEnabled(anchor_enable)
            pos_enable = anchor_enable and anchor.isChecked()
            pos.setEnabled(pos_enable)

        self._on_change()

    def value(self) -> Union[GridRowsColumns, GridFromEdges, GridWidthHeight]:
        """
        Get the current grid value.

        :raises NotImplementedError: If the mode is not implemented
        :return: The current grid value
        :rtype: Union[GridRowsColumns, GridFromEdges, GridWidthHeight]
        """
        over = self.overlap.value()
        common = {
            "reverse": self.reverse.isChecked(),
            "overlap": (over, over),
            "mode": self.order.currentText(),
            "fov_width": self.fov_dimensions[0],
            "fov_height": self.fov_dimensions[1],
        }
        if self._mode == "number":
            return GridRowsColumns(
                rows=self.rows.value(),
                columns=self.columns.value(),
                relative_to="center" if self.relative_to.currentText() == "center" else "top_left",
                **common,
            )
        elif self._mode == "bounds":
            return GridFromEdges(
                top=self.dim_1_high.value(),
                left=self.dim_0_low.value(),
                bottom=self.dim_1_low.value(),
                right=self.dim_0_high.value(),
                **common,
            )
        elif self._mode == "area":
            return GridWidthHeight(
                width=self.area_width.value(),
                height=self.area_height.value(),
                relative_to="center" if self.relative_to.currentText() == "center" else "top_left",
                **common,
            )
        raise NotImplementedError


def line() -> QFrame:
    """
    Create a horizontal line.

    :return: A horizontal line frame
    :rtype: QFrame
    """
    frame = QFrame()
    frame.setFrameShape(QFrame.HLine)
    return frame