from pymmcore_widgets import GridPlanWidget as GridPlanWidgetMMCore
from qtpy.QtWidgets import QSizePolicy, QWidget, QCheckBox, QDoubleSpinBox, \
    QPushButton, QLabel, QGridLayout
from qtpy.QtCore import Signal, Qt
from typing import cast
import useq
from view.widgets.base_device_widget import create_widget
from typing import Iterator

class TilePlanWidget(GridPlanWidgetMMCore):
    """Widget to plan out grid. Pymmcore already has a great one"""

    clicked = Signal()
    fovStop = Signal()

    def __init__(self,
                 limits=[[float('-inf'), float('inf')], [float('-inf'), float('inf')], [float('-inf'), float('inf')]],
                 fov_dimensions: list[float] = [1.0, 1.0, 0],
                 fov_position: list[float] = [0.0, 0.0, 0.0],
                 coordinate_plane: list[str] = ['x', 'y', 'z'],
                 unit: str = 'um'):
        """:param limits: list of limits ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
           :param unit: unit of all size values"""

        self.reverse = QCheckBox('Reverse')  # initialize reverse checkbox since value is referenced in parent init

        super().__init__()
        # ability to reverse path order
        self.reverse.stateChanged.connect(self._on_change)
        layout = self.order.parent().layout().children()[-1].children()[0]
        # hide previous heading
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if type(widget) == QLabel:
                if widget.text() == 'Order:':
                    widget.setVisible(False)
        widget = create_widget('H', QLabel("Order:"), self.order, self.reverse)
        widget.layout().setAlignment(Qt.AlignLeft)
        layout.addRow(widget)

        # sort limits
        limits = [[min(limit), max(limit)] for limit in limits]

        # customize area widgets
        self.area_width.setRange(0.01, limits[0][-1] - limits[0][0])
        self.area_width.setSuffix(f" {unit}")
        self.area_height.setRange(0.01, limits[1][-1] - limits[1][0])
        self.area_height.setSuffix(f" {unit}")

        # customize bound widgets
        self.left.setRange(limits[0][0], limits[0][-1])
        self.left.setSuffix(f" {unit}")
        self.right.setRange(limits[0][0], limits[0][-1])
        self.right.setSuffix(f" {unit}")
        self.top.setRange(limits[1][0], limits[1][-1])
        self.top.setSuffix(f" {unit}")
        self.bottom.setRange(limits[1][0], limits[1][-1])
        self.bottom.setSuffix(f" {unit}")

        self.setMinimumHeight(360)
        self.setMinimumWidth(400)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        # Add extra checkboxes/inputs/buttons to customize grid
        layout = QGridLayout()

        layout.addWidget(QLabel('Anchor Grid:'), 2, 0)

        self.anchor_widgets = [QCheckBox(), QCheckBox(), QCheckBox()]
        self.grid_position_widgets = [QDoubleSpinBox(), QDoubleSpinBox(), QDoubleSpinBox()]
        for i, axis, box, anchor in zip(range(0, 3), coordinate_plane, self.grid_position_widgets, self.anchor_widgets):
            box.setValue(fov_position[i])
            limit = limits[i]
            box.setDecimals(6)
            box.setRange(*limit)
            box.setSuffix(f" {unit}")
            box.valueChanged.connect(lambda: setattr(self, 'grid_position', [self.grid_position_widgets[0].value(),
                                                                             self.grid_position_widgets[1].value(),
                                                                             self.grid_position_widgets[2].value()]))
            box.setDisabled(True)
            layout.addWidget(box, 1, i + 1)

            anchor.toggled.connect(lambda enable, index=i: self.toggle_grid_position(enable, index))
            layout.addWidget(anchor, 2, i + 1)

        self.stop_stage = QPushButton("HALT FOV")
        self.stop_stage.clicked.connect(lambda: self.fovStop.emit())
        layout.addWidget(self.stop_stage, 3, 0, 1, 4)

        widget = QWidget()
        widget.setLayout(layout)
        self.widget().layout().addWidget(widget)

        self.fov_dimensions = fov_dimensions
        self.grid_position = [0.0, 0.0, 0.0]
        self.fov_position = fov_position
        self.coordinate_plane = coordinate_plane

        self.show()

    def toggle_grid_position(self, enable, index):
        """If grid is anchored, allow user to input grid position"""

        self.grid_position_widgets[index].setEnabled(enable)
        if not enable:  # Graph is not anchored
            self.grid_position_widgets[index].setValue(self.fov_position[index])

    @property
    def fov_position(self):
        return self._fov_position

    @fov_position.setter
    def fov_position(self, value):
        self._fov_position = value
        for i, anchor in enumerate(self.anchor_widgets):
            if not anchor.isChecked() and anchor.isEnabled():
                self.grid_position_widgets[i].setValue(value[i])

    @property
    def fov_dimensions(self):
        return [self.fovWidth(), self.fovHeight()]

    @fov_dimensions.setter
    def fov_dimensions(self, value):
        self.setFovWidth(value[0])
        self.area_width.setSingleStep(value[0])
        self.setFovHeight(value[1])
        self.area_height.setSingleStep(value[1])

    @property
    def grid_position(self):
        return self._grid_position

    @grid_position.setter
    def grid_position(self, value):
        self._grid_position = value
        self._on_change()

    @property
    def tile_positions(self):
        """Returns 2d list of tile positions based on widget values"""

        coords = [[None] * self.value().columns for _ in range(self.value().rows)]
        if self._mode != "bounds":
            for tile in self.value():
                coords[tile.row][tile.col] = [tile.x + self._grid_position[0], tile.y + self._grid_position[1]]
        else:
            for tile in self.value():
                coords[tile.row][tile.col] = [tile.x, tile.y]
        return coords

    def value(self):
        """Overwriting value so Area mode doesn't multiply width and height by 1000"""

        over = self.overlap.value()
        _order = cast("OrderMode", self.order.currentEnum())
        common = {
            "reverse": self.reverse.isChecked(),
            "overlap": (over, over),
            "mode": _order.value,
            "fov_width": self._fov_width,
            "fov_height": self._fov_height,
        }
        if self._mode.value == 'number':
            return GridRowsColumns(
                rows=self.rows.value(),
                columns=self.columns.value(),
                relative_to=cast("RelativeTo", self.relative_to.currentEnum()).value,
                **common,
            )
        elif self._mode.value == 'bounds':
            return GridFromEdges(
                top=self.top.value(),
                left=self.left.value(),
                bottom=self.bottom.value(),
                right=self.right.value(),
                **common,
            )
        elif self._mode.value == 'area':
            return GridWidthHeight(
                width=self.area_width.value(),
                height=self.area_height.value(),
                relative_to=cast("RelativeTo", self.relative_to.currentEnum()).value,
                **common,
            )
        raise NotImplementedError

    def mousePressEvent(self, a0) -> None:
        """overwrite to emit a clicked signal"""
        self.clicked.emit()
        super().mousePressEvent(a0)


class GridFromEdges(useq.GridFromEdges):
    """Add row and column attributes and allow reversible order"""
    reverse = property()  # initialize property

    def __init__(self, reverse=False, *args, **kwargs):
        # rewrite property since pydantic doesn't allow to add attr
        setattr(type(self), 'reverse', property(fget=lambda x: reverse))
        super().__init__(*args, **kwargs)

    @property
    def rows(self):
        return self._nrows(self.fov_height)

    @property
    def columns(self):
        return self._ncolumns(self.fov_width)

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
        return self._nrows(self.fov_height)

    @property
    def columns(self):
        return self._ncolumns(self.fov_width)

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

