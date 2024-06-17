from pymmcore_widgets import GridPlanWidget as GridPlanWidgetMMCore
from qtpy.QtWidgets import QSizePolicy, QWidget, QCheckBox, QDoubleSpinBox, \
    QPushButton, QLabel,  QGridLayout
from qtpy.QtCore import Signal
from typing import cast
import useq

class TilePlanWidget(GridPlanWidgetMMCore):
    """Widget to plan out grid. Pymmcore already has a great one"""

    clicked = Signal()
    fovStop = Signal()

    def __init__(self,
                 limits=[[float('-inf'), float('inf')], [float('-inf'), float('inf')], [float('-inf'), float('inf')]],
                 fov_dimensions: list[float] = [1.0, 1.0, 0],
                 fov_position: list[float] = [0.0, 0.0, 0.0],
                 coordinate_plane : list[str] = ['x', 'y', 'z'],
                 unit: str = 'um'):
        """:param limits: list of limits ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
           :param unit: unit of all size values"""

        super().__init__()
        # TODO: should these be properties? or should we assume they stay constant?

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
            dec = len(str(limit[0])[str(limit[0]).index('.') + 1:]) if '.' in str(limit[0]) else 0
            box.setDecimals(dec)
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
        # FIXME: I don't like overwriting this but I don't know what else to do
        over = self.overlap.value()
        _order = cast("OrderMode", self.order.currentEnum())
        common = {
            "overlap": (over, over),
            "mode": _order.value,
            "fov_width": self._fov_width,
            "fov_height": self._fov_height,
        }
        if self._mode.value == 'number':
            return useq.GridRowsColumns(
                rows=self.rows.value(),
                columns=self.columns.value(),
                relative_to=cast("RelativeTo", self.relative_to.currentEnum()).value,
                **common,
            )
        elif self._mode.value == 'bounds':
            return useq.GridFromEdges(
                top=self.top.value(),
                left=self.left.value(),
                bottom=self.bottom.value(),
                right=self.right.value(),
                **common,
            )
        elif self._mode.value == 'area':
            return useq.GridWidthHeight(
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
