from math import radians, sqrt, tan
from typing import List, Optional, Tuple

import numpy as np
from pyqtgraph import makeRGBA
from pyqtgraph.opengl import GLImageItem
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QMatrix4x4, QQuaternion, QVector3D, QKeyEvent, QMouseEvent, QWheelEvent
from qtpy.QtWidgets import QButtonGroup, QCheckBox, QGridLayout, QLabel, QMessageBox, QPushButton, QRadioButton, QWidget
from scipy import spatial

from view.widgets.miscellaneous_widgets.gl_ortho_view_widget import GLOrthoViewWidget
from view.widgets.miscellaneous_widgets.gl_path_item import GLPathItem
from view.widgets.miscellaneous_widgets.gl_shaded_box_item import GLShadedBoxItem


class SignalChangeVar:
    """
    Descriptor class to emit a signal when a variable is changed.
    """

    def __set_name__(self, owner: type, name: str) -> None:
        """
        Set the name of the variable.

        :param owner: The owner class
        :type owner: type
        :param name: The name of the variable
        :type name: str
        """
        self.name = f"_{name}"

    def __set__(self, instance: object, value: object) -> None:
        """
        Set the value of the variable and emit a signal.

        :param instance: The instance of the class
        :type instance: object
        :param value: The value to set
        :type value: object
        """
        setattr(instance, self.name, value)  # initially setting attr
        instance.valueChanged.emit(self.name[1:])

    def __get__(self, instance: object, owner: type) -> object:
        """
        Get the value of the variable.

        :param instance: The instance of the class
        :type instance: object
        :param owner: The owner class
        :type owner: type
        :return: The value of the variable
        :rtype: object
        """
        return getattr(instance, self.name)


class VolumeModel(GLOrthoViewWidget):
    """
    Widget to display configured acquisition grid. Note that the x and y refer to the tiling
    dimensions and z is the scanning dimension.
    """

    fov_dimensions = SignalChangeVar()
    fov_position = SignalChangeVar()
    grid_coords = SignalChangeVar()
    view_plane = SignalChangeVar()
    scan_volumes = SignalChangeVar()
    tile_visibility = SignalChangeVar()
    valueChanged = Signal((str))
    fovMove = Signal((list))
    fovHalt = Signal()

    def __init__(
        self,
        unit: str = "mm",
        limits: Optional[List[Tuple[float, float]]] = None,
        fov_dimensions: Optional[List[float]] = None,
        fov_position: Optional[List[float]] = None,
        coordinate_plane: Optional[List[str]] = None,
        fov_color: str = "yellow",
        fov_line_width: int = 2,
        fov_opacity: float = 0.15,
        path_line_width: int = 2,
        path_arrow_size: float = 6.0,
        path_arrow_aspect_ratio: int = 4,
        path_start_color: str = "magenta",
        path_end_color: str = "green",
        active_tile_color: str = "cyan",
        active_tile_opacity: float = 0.075,
        inactive_tile_color: str = "red",
        inactive_tile_opacity: float = 0.025,
        tile_line_width: int = 2,
        limits_line_width: int = 2,
        limits_color: str = "white",
        limits_opacity: float = 0.1,
    ) -> None:
        """
        Initialize the VolumeModel.

        :param unit: Unit of measurement, defaults to "mm"
        :type unit: str, optional
        :param limits: Limits for the volume, defaults to None
        :type limits: list[[float, float], [float, float], [float, float]], optional
        :param fov_dimensions: Dimensions of the field of view, defaults to None
        :type fov_dimensions: list[float, float, float], optional
        :param fov_position: Position of the field of view, defaults to None
        :type fov_position: list[float, float, float], optional
        :param coordinate_plane: Coordinate plane, defaults to None
        :type coordinate_plane: list[str, str, str], optional
        :param fov_color: Color of the field of view, defaults to "yellow"
        :type fov_color: str, optional
        :param fov_line_width: Line width of the field of view, defaults to 2
        :type fov_line_width: int, optional
        :param fov_opacity: Opacity of the field of view, defaults to 0.15
        :type fov_opacity: float, optional
        :param path_line_width: Line width of the path, defaults to 2
        :type path_line_width: int, optional
        :param path_arrow_size: Arrow size of the path, defaults to 6.0
        :type path_arrow_size: float, optional
        :param path_arrow_aspect_ratio: Arrow aspect ratio of the path, defaults to 4
        :type path_arrow_aspect_ratio: int, optional
        :param path_start_color: Start color of the path, defaults to "magenta"
        :type path_start_color: str, optional
        :param path_end_color: End color of the path, defaults to "green"
        :type path_end_color: str, optional
        :param active_tile_color: Color of the active tile, defaults to "cyan"
        :type active_tile_color: str, optional
        :param active_tile_opacity: Opacity of the active tile, defaults to 0.075
        :type active_tile_opacity: float, optional
        :param inactive_tile_color: Color of the inactive tile, defaults to "red"
        :type inactive_tile_color: str, optional
        :param inactive_tile_opacity: Opacity of the inactive tile, defaults to 0.025
        :type inactive_tile_opacity: float, optional
        :param tile_line_width: Line width of the tile, defaults to 2
        :type tile_line_width: int, optional
        :param limits_line_width: Line width of the limits, defaults to 2
        :type limits_line_width: int, optional
        :param limits_color: Color of the limits, defaults to "white"
        :type limits_color: str, optional
        :param limits_opacity: Opacity of the limits, defaults to 0.1
        :type limits_opacity: float, optional
        """
        super().__init__(rotationMethod="quaternion")

        # initialize attributes
        self.unit = unit
        self.coordinate_plane = [x.replace("-", "") for x in coordinate_plane] if coordinate_plane else ["x", "y", "z"]
        self.polarity = [1 if "-" not in x else -1 for x in coordinate_plane]
        self.fov_dimensions = fov_dimensions[:2] + [0] if fov_dimensions else [1.0, 1.0, 0]  # add 0 in the scanning dim
        self.fov_position = fov_position if fov_position else [0.0, 0.0, 0.0]
        self.view_plane = (self.coordinate_plane[0], self.coordinate_plane[1])  # plane currently being viewed

        self.scan_volumes = np.zeros([1, 1])  # 2d list detailing volume of tiles
        self.grid_coords = np.zeros([1, 1, 3])  # 2d list detailing start position of tiles
        self.start_tile_coord = np.zeros([1, 1, 3])
        self.end_tile_coord = np.zeros([1, 1, 3])
        self.grid_box_items = []  # 2D list detailing box items in grid
        self.tile_visibility = np.array([[True]])  # 2d list detailing visibility of tiles

        # tile aesthetic properties
        self.active_tile_color = active_tile_color
        self.active_tile_opacity = active_tile_opacity
        self.inactive_tile_color = inactive_tile_color
        self.inactive_tile_opacity = inactive_tile_opacity
        self.tile_line_width = tile_line_width

        # limits aesthetic properties
        if not limits:
            limits = [[float("-inf"), float("inf")] for _ in range(3)]
        self.limits_line_width = limits_line_width
        self.limits_color = limits_color
        self.limits_opacity = limits_opacity

        # position data set externally since tiles are assumed out of order
        self.path = GLPathItem(
            width=path_line_width,
            arrow_size=path_arrow_size,
            arrow_aspect_ratio=path_arrow_aspect_ratio,
            path_start_color=path_start_color,
            path_end_color=path_end_color,
        )
        self.addItem(self.path)

        # initialize dict of fov_images
        self.fov_images = {}

        # initialize fov
        self.fov_view = GLShadedBoxItem(
            width=fov_line_width,
            pos=np.array([[self.fov_position]]),
            size=np.array(self.fov_dimensions),
            color=fov_color,
            opacity=fov_opacity,
            glOptions="additive",
        )
        self.fov_view.setTransform(
            QMatrix4x4(
                1,
                0,
                0,
                self.fov_position[0] * self.polarity[0],
                0,
                1,
                0,
                self.fov_position[1] * self.polarity[1],
                0,
                0,
                1,
                self.fov_position[2] * self.polarity[2],
                0,
                0,
                0,
                1,
            )
        )
        self.addItem(self.fov_view)

        if limits != [[float("-inf"), float("inf")], [float("-inf"), float("inf")], [float("-inf"), float("inf")]]:
            size = [((max(limits[i]) - min(limits[i])) + self.fov_dimensions[i]) for i in range(3)]
            stage_limits = GLShadedBoxItem(
                width=self.limits_line_width,
                pos=np.array(
                    [
                        [
                            [
                                min([x * self.polarity[0] for x in limits[0]]),
                                min([y * self.polarity[1] for y in limits[1]]),
                                min([z * self.polarity[2] for z in limits[2]]),
                            ]
                        ]
                    ]
                ),
                size=np.array(size),
                color=self.limits_color,
                opacity=self.limits_opacity,
                glOptions="additive",
            )
            self.addItem(stage_limits)

        self.valueChanged[str].connect(self.update_model)
        self.resized.connect(self._update_opts)

        self._update_opts()

        # Add widgets for toggling view plane, path visibility, and halt stage
        self.widgets = QWidget()
        layout = QGridLayout()

        path_show = QCheckBox("Show Path")
        path_show.setChecked(True)
        path_show.toggled.connect(self.path.setVisible)
        layout.addWidget(path_show, 0, 0)

        layout.addWidget(QLabel("Plane View: "), 0, 1)
        view_plane = QButtonGroup()
        for i, view in enumerate(
            [
                f"({self.coordinate_plane[0]}, {self.coordinate_plane[2]})",
                f"({self.coordinate_plane[2]}, {self.coordinate_plane[1]})",
                f"({self.coordinate_plane[0]}, {self.coordinate_plane[1]})",
            ]
        ):
            button = QRadioButton(view)
            button.clicked.connect(lambda clicked, b=button: self.toggle_view_plane(b))
            view_plane.addButton(button)
            button.setChecked(True)
            layout.addWidget(button, 0, i + 2)

        halt = QPushButton("HALT STAGE")
        halt.pressed.connect(self.fovHalt.emit)
        layout.addWidget(halt, 1, 0, 1, 5)

        self.widgets.setLayout(layout)
        self.widgets.setMaximumHeight(70)
        self.widgets.show()

    def update_model(self, attribute_name: str) -> None:
        """
        Update the model based on the changed attribute.

        :param attribute_name: The name of the changed attribute
        :type attribute_name: str
        """
        # update color of tiles based on z position
        flat_coords = self.grid_coords.reshape([-1, 3])  # flatten array
        flat_dims = self.scan_volumes.flatten()  # flatten array
        coords = np.concatenate((flat_coords, [[x, y, (z + sz)] for (x, y, z), sz in zip(flat_coords, flat_dims)]))
        extrema = [
            [min(coords[:, 0]), max(coords[:, 0])],
            [min(coords[:, 1]), max(coords[:, 1])],
            [min(coords[:, 2]), max(coords[:, 2])],
        ]
        in_grid = not any(
            [pos > pos_max or pos < pos_min for (pos_min, pos_max), pos in zip(extrema, self.fov_position)]
        )

        if attribute_name == "fov_position":
            # update fov_pos
            self.fov_view.setTransform(
                QMatrix4x4(
                    1,
                    0,
                    0,
                    self.fov_position[0] * self.polarity[0],
                    0,
                    1,
                    0,
                    self.fov_position[1] * self.polarity[1],
                    0,
                    0,
                    1,
                    self.fov_position[2] * self.polarity[2],
                    0,
                    0,
                    0,
                    1,
                )
            )

            color = self.grid_box_items[0].color() if len(self.grid_box_items) != 0 else None
            if (not in_grid and color != self.inactive_tile_color) or (in_grid and color != self.active_tile_color):
                new_color = self.inactive_tile_color if not in_grid else self.active_tile_color
                for box in self.grid_box_items:
                    box.setColor(color=new_color)

        else:
            self.fov_view.setSize(x=self.fov_dimensions[0], y=self.fov_dimensions[1], z=0.0)

            # faster to remove every box than parse which ones have changes
            for box in self.grid_box_items:
                self.removeItem(box)
            self.grid_box_items = []

            total_rows = len(self.grid_coords)
            total_columns = len(self.grid_coords[0])

            for row in range(total_rows):
                for column in range(total_columns):

                    coord = [x * pol for x, pol in zip(self.grid_coords[row][column], self.polarity)]
                    size = [*self.fov_dimensions[:2], self.scan_volumes[row, column]]

                    # scale opacity for viewing
                    if self.view_plane == (self.coordinate_plane[0], self.coordinate_plane[1]):
                        opacity = self.active_tile_opacity
                    elif self.view_plane == (self.coordinate_plane[2], self.coordinate_plane[1]):
                        opacity = self.active_tile_opacity / total_columns
                    else:
                        opacity = self.active_tile_opacity / total_rows

                    box = GLShadedBoxItem(
                        width=self.tile_line_width,
                        pos=np.array([[coord]]),
                        size=np.array(size),
                        color=self.active_tile_color if in_grid else self.inactive_tile_color,
                        opacity=opacity,
                        glOptions="additive",
                    )
                    box.setVisible(self.tile_visibility[row, column])
                    self.addItem(box)
                    self.grid_box_items.append(box)

        self._update_opts()

    def toggle_view_plane(self, button: QRadioButton) -> None:
        """
        Toggle the view plane based on the selected button.

        :param button: The radio button that was clicked
        :type button: QRadioButton
        """
        view_plane = tuple(x for x in button.text() if x.isalpha())
        self.view_plane = view_plane

    def set_path_pos(self, coord_order: List[List[float]]) -> None:
        """
        Set the path position based on the coordinate order.

        :param coord_order: The order of coordinates
        :type coord_order: list
        """
        path = np.array(
            [
                [
                    ((coord[i] * pol) + (0.5 * fov))
                    for i, fov, pol, x in zip([0, 1, 2], self.fov_dimensions, self.polarity, self.coordinate_plane)
                ]
                for coord in coord_order
            ]
        )
        self.path.setData(pos=path)

    def add_fov_image(self, image: np.ndarray, levels: List[float]) -> None:
        """
        Add a field of view image.

        :param image: The image to add
        :type image: np.ndarray
        :param levels: The levels for the image
        :type levels: list[float]
        """
        image_rgba = makeRGBA(image, levels=levels)
        image_rgba[0][:, :, 3] = 200

        gl_image = GLImageItem(image_rgba[0], glOptions="additive")
        x, y, z = self.fov_position
        gl_image.setTransform(
            QMatrix4x4(
                self.fov_dimensions[0] / image.shape[0],
                0,
                0,
                x * self.polarity[0],
                0,
                self.fov_dimensions[1] / image.shape[1],
                0,
                y * self.polarity[1],
                0,
                0,
                1,
                z * self.polarity[2],
                0,
                0,
                0,
                1,
            )
        )
        self.addItem(gl_image)
        self.fov_images[image.tobytes()] = gl_image

        if self.view_plane != (self.coordinate_plane[0], self.coordinate_plane[1]):
            gl_image.setVisible(False)

    def adjust_glimage_contrast(self, image: np.ndarray, contrast_levels: List[float]) -> None:
        """
        Adjust the contrast of a GL image.

        :param image: The image to adjust
        :type image: np.ndarray
        :param contrast_levels: The contrast levels
        :type contrast_levels: list[float]
        """
        if image.tobytes() in self.fov_images.keys():  # check if image has been deleted
            glimage = self.fov_images[image.tobytes()]
            self.removeItem(glimage)
            self.add_fov_image(image, contrast_levels)

    def toggle_fov_image_visibility(self, visible: bool) -> None:
        """
        Toggle the visibility of the field of view images.

        :param visible: Whether the images should be visible
        :type visible: bool
        """
        for image in self.fov_images.values():
            image.setVisible(visible)

    def _update_opts(self) -> None:
        """
        Update the options for the view.
        """
        view_plane = self.view_plane
        view_pol = [
            self.polarity[self.coordinate_plane.index(view_plane[0])],
            self.polarity[self.coordinate_plane.index(view_plane[1])],
        ]
        coords = self.grid_coords.reshape([-1, 3])  # flatten array
        dimensions = self.scan_volumes.flatten()  # flatten array

        # set rotation
        root = sqrt(2.0) / 2.0
        if view_plane == (self.coordinate_plane[0], self.coordinate_plane[1]):
            self.opts["rotation"] = QQuaternion(-1, 0, 0, 0)
        else:
            self.opts["rotation"] = (
                QQuaternion(-root, 0, -root, 0)
                if view_plane == (self.coordinate_plane[2], self.coordinate_plane[1])
                else QQuaternion(-root, root, 0, 0)
            )
            # take into account end of tile and account for difference in size if z included in view
            coords = np.concatenate((coords, [[x, y, (z + sz)] for (x, y, z), sz in zip(coords, dimensions)]))

        extrema = {
            f"{self.coordinate_plane[0]}_min": min(coords[:, 0]),
            f"{self.coordinate_plane[0]}_max": max(coords[:, 0]),
            f"{self.coordinate_plane[1]}_min": min(coords[:, 1]),
            f"{self.coordinate_plane[1]}_max": max(coords[:, 1]),
            f"{self.coordinate_plane[2]}_min": min(coords[:, 2]),
            f"{self.coordinate_plane[2]}_max": max(coords[:, 2]),
        }

        fov = {plane: fov for plane, fov in zip(self.coordinate_plane, self.fov_dimensions)}
        pos = {axis: dim for axis, dim in zip(self.coordinate_plane, self.fov_position)}
        distances = {
            self.coordinate_plane[0]
            + self.coordinate_plane[1]: [
                sqrt((pos[view_plane[0]] - x) ** 2 + (pos[view_plane[1]] - y) ** 2) for x, y, z in coords
            ],
            self.coordinate_plane[0]
            + self.coordinate_plane[2]: [
                sqrt((pos[view_plane[0]] - x) ** 2 + (pos[view_plane[1]] - z) ** 2) for x, y, z in coords
            ],
            self.coordinate_plane[2]
            + self.coordinate_plane[1]: [
                sqrt((pos[view_plane[0]] - z) ** 2 + (pos[view_plane[1]] - y) ** 2) for x, y, z in coords
            ],
        }
        max_index = distances["".join(view_plane)].index(max(distances["".join(view_plane)], key=abs))
        furthest_tile = {
            self.coordinate_plane[0]: coords[max_index][0],
            self.coordinate_plane[1]: coords[max_index][1],
            self.coordinate_plane[2]: coords[max_index][2],
        }
        center = {}

        # Horizontal sizing, if fov_position is within grid or farthest distance is between grid tiles
        x = view_plane[0]
        if extrema[f"{x}_min"] <= pos[x] <= extrema[f"{x}_max"] or abs(furthest_tile[x] - pos[x]) < abs(
            extrema[f"{x}_max"] - extrema[f"{x}_min"]
        ):
            center[x] = (((extrema[f"{x}_min"] + extrema[f"{x}_max"]) / 2) + (fov[x] / 2 * view_pol[0])) * view_pol[0]
            horz_dist = (
                ((extrema[f"{x}_max"] - extrema[f"{x}_min"]) + (fov[x] * 2)) / 2 * tan(radians(self.opts["fov"]))
            )
        else:
            center[x] = (((pos[x] + furthest_tile[x]) / 2) + (fov[x] / 2 * view_pol[0])) * view_pol[0]
            horz_dist = (abs(pos[x] - furthest_tile[x]) + (fov[x] * 2)) / 2 * tan(radians(self.opts["fov"]))
        # Vertical sizing, if fov_position is within grid or farthest distance is between grid tiles
        y = view_plane[1]
        scaling = self.size().width() / self.size().height()
        if extrema[f"{y}_min"] <= pos[y] <= extrema[f"{y}_max"] or abs(furthest_tile[y] - pos[y]) < abs(
            extrema[f"{y}_max"] - extrema[f"{y}_min"]
        ):
            center[y] = (((extrema[f"{y}_min"] + extrema[f"{y}_max"]) / 2) + (fov[y] / 2 * view_pol[1])) * view_pol[1]
            # View doesn't scale when changing vertical size so take into account the dif between the height and width
            vert_dist = (
                ((extrema[f"{y}_max"] - extrema[f"{y}_min"]) + (fov[y] * 2))
                / 2
                * tan(radians(self.opts["fov"]))
                * scaling
            )
        else:
            center[y] = (((pos[y] + furthest_tile[y]) / 2) + (fov[y] / 2 * view_pol[1])) * view_pol[1]
            vert_dist = (abs(pos[y] - furthest_tile[y]) + (fov[y] * 2)) / 2 * tan(radians(self.opts["fov"])) * scaling
        # @Micah in ortho mode it seems to scale properly with x1200... not sure how to explain why though
        # not sure if this actually works, and whether it needs to be copied to other places in the fx
        self.opts["distance"] = horz_dist * 1200 if horz_dist > vert_dist else vert_dist * 1200

        self.opts["center"] = QVector3D(
            center.get(self.coordinate_plane[0], 0),
            center.get(self.coordinate_plane[1], 0),
            center.get(self.coordinate_plane[2], 0),
        )

        self.update()

    def move_fov_query(self, new_fov_pos: List[float]) -> Tuple[int, bool]:
        """
        Query the user to move the field of view.

        :param new_fov_pos: The new position of the field of view
        :type new_fov_pos: list[float]
        :return: The result of the query and whether to move to the nearest tile
        :rtype: tuple[int, bool]
        """
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(
            f"Do you want to move the field of view from "
            f"{[round(x, 2) for x in self.fov_position]} [{self.unit}] to "
            f"{[round(x, 2) for x in new_fov_pos]} [{self.unit}]?"
        )
        msgBox.setWindowTitle("Moving FOV")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        checkbox = QCheckBox("Move to nearest tile")
        checkbox.setChecked(True)
        msgBox.setCheckBox(checkbox)

        return msgBox.exec(), checkbox.isChecked()

    def delete_fov_image_query(self, fov_image_pos: List[float]) -> int:
        """
        Query the user to delete a field of view image.

        :param fov_image_pos: The position of the field of view image
        :type fov_image_pos: list[float]
        :return: The result of the query
        :rtype: int
        """
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(f"Do you want to delete image at {fov_image_pos} [{self.unit}]?")
        msgBox.setWindowTitle("Deleting FOV Image")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        return msgBox.exec()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events.

        :param event: The mouse event
        :type event: QMouseEvent
        """
        plane = list(self.view_plane) + [ax for ax in self.coordinate_plane if ax not in self.view_plane]
        view_pol = [
            self.polarity[self.coordinate_plane.index(plane[0])],
            self.polarity[self.coordinate_plane.index(plane[1])],
            self.polarity[self.coordinate_plane.index(plane[2])],
        ]
        # Translate mouseclick x, y into view widget coordinate plane.
        horz_dist = (self.opts["distance"] / tan(radians(self.opts["fov"]))) / 1200
        vert_dist = (
            self.opts["distance"] / tan(radians(self.opts["fov"])) * (self.size().height() / self.size().width())
        ) / 1200
        horz_scale = (event.x() * 2 * horz_dist) / self.size().width()
        vert_scale = (event.y() * 2 * vert_dist) / self.size().height()

        # create dictionaries of from fov and pos
        fov = {axis: fov for axis, fov in zip(self.coordinate_plane, self.fov_dimensions)}
        pos = {axis: dim for axis, dim in zip(self.coordinate_plane, self.fov_position)}

        center = {
            self.coordinate_plane[0]: self.opts["center"].x(),
            self.coordinate_plane[1]: self.opts["center"].y(),
            self.coordinate_plane[2]: self.opts["center"].z(),
        }
        h_ax = self.view_plane[0]
        v_ax = self.view_plane[1]

        new_pos = {
            plane[0]: ((center[h_ax] - horz_dist + horz_scale) - 0.5 * fov[plane[0]]) * view_pol[0],
            plane[1]: ((center[v_ax] + vert_dist - vert_scale) - 0.5 * fov[plane[1]]) * view_pol[1],
            plane[2]: pos[plane[2]] * view_pol[2],
        }
        move_to = [new_pos[ax] for ax in self.coordinate_plane]
        if event.button() == Qt.LeftButton:
            return_value, checkbox = self.move_fov_query(move_to)

            if return_value == QMessageBox.Ok:
                if not checkbox:  # Move to exact location
                    pos = move_to
                else:  # move to the nearest tile
                    flattened = self.grid_coords.reshape([-1, 3])
                    tree = spatial.KDTree(self.grid_coords.reshape([-1, 3]))
                    distance, index = tree.query(move_to)
                    tile = flattened[index]
                    pos = [tile[0], tile[1], tile[2]]
                self.fovMove.emit(pos)

            else:
                return

        elif event.button() == Qt.RightButton:
            delete_key = None
            for key, image in self.fov_images.items():
                coords = [image.transform()[i, 3] for i in range(3)]
                if (
                    coords[0] - self.fov_dimensions[0] <= coords[0] <= coords[0] + self.fov_dimensions[0]
                    and coords[1] - self.fov_dimensions[1] <= coords[1] <= coords[1] + self.fov_dimensions[1]
                ):
                    return_value = self.delete_fov_image_query(coords)
                    if return_value == QMessageBox.Ok:
                        self.removeItem(image)
                        delete_key = key
                    break
            if delete_key is not None:
                del self.fov_images[delete_key]

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Override mouseMoveEvent so user can't change view.

        :param event: The mouse event
        :type event: QMouseEvent
        """
        pass

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Override wheelEvent so user can't change view.

        :param event: The wheel event
        :type event: QWheelEvent
        """
        pass

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Override keyPressEvent so user can't change view.

        :param event: The key event
        :type event: QKeyEvent
        """
        pass

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        """
        Override keyReleaseEvent so user can't change view.

        :param event: The key event
        :type event: QKeyEvent
        """
        pass
