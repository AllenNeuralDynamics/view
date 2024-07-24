from pyqtgraph.opengl import GLViewWidget, GLBoxItem, GLLinePlotItem, GLTextItem, GLImageItem
from qtpy.QtWidgets import QMessageBox, QCheckBox
from qtpy.QtCore import Signal, Qt
from qtpy.QtGui import QMatrix4x4, QVector3D, QQuaternion
from math import tan, radians, sqrt
import numpy as np
from scipy import spatial
from pyqtgraph import makeRGBA
from view.widgets.miscellaneous_widgets.gl_ortho_view_widget import GLOrthoViewWidget
from view.widgets.miscellaneous_widgets.gl_shaded_box_item import GLShadedBoxItem
from view.widgets.miscellaneous_widgets.gl_tile_item import GLTileItem
from view.widgets.miscellaneous_widgets.gl_path_item import GLPathItem


class SignalChangeVar:

    def __set_name__(self, owner, name):
        self.name = f"_{name}"

    def __set__(self, instance, value):
        setattr(instance, self.name, value)  # initially setting attr
        instance.valueChanged.emit(self.name[1:])

    def __get__(self, instance, value):
        return getattr(instance, self.name)


class VolumeModel(GLOrthoViewWidget):
    """Widget to display configured acquisition grid.  Note that the x and y refer to the tiling
    dimensions and z is the scanning dimension """

    fov_dimensions = SignalChangeVar()
    fov_position = SignalChangeVar()
    grid_coords = SignalChangeVar()
    view_plane = SignalChangeVar()
    scan_volumes = SignalChangeVar()
    tile_visibility = SignalChangeVar()
    valueChanged = Signal((str))
    fovMoved = Signal((list))

    def __init__(self,
                 unit: str = 'mm',
                 coordinate_plane: list[str] = ['x', 'y', 'z'],
                 fov_dimensions: list[float] = [1.0, 1.0, 0],
                 fov_position: list[float] = [0.0, 0.0, 0.0],
                 fov_color: str = 'yellow',
                 fov_line_width: int = 2,
                 fov_opacity: float = .15,
                 path_line_width: int = 2,
                 path_arrow_size: float = .04,
                 path_arrow_aspect_ratio: int = 4,
                 path_start_color: str = 'magenta',
                 path_end_color: str = 'green',
                 tile_color: str = 'cyan',
                 tile_opacity: float = .075,
                 tile_line_width: int = 2):

        """
        GLViewWidget to display proposed grid of acquisition

        :param unit: unit of the volume model.
        :param coordinate_plane: coordinate plane displayed on widget.
        :param fov_dimensions: dimensions of field of view in coordinate plane
        :param fov_position: position of fov
        :param fov_line_width: width of fov outline
        :param fov_line_width: width of fov outline
        :param fov_opacity: opacity of fov face where 1 is fully opaque
        :param path_line_width: width of path line
        :param path_arrow_size: size of arrow at the end of path
        :param path_arrow_aspect_ratio: aspect ratio of arrow
        :param path_start_color: start color of path
        :param path_end_color: end color of path
        :param tile_color: color of tiles
        :param tile_opacity: opacity of tile faces where 1 is fully opaque
        :param tile_line_width: width of tiles
        """

        super().__init__(rotationMethod='quaternion')
        self.makeCurrent()
        self.unit = unit
        self.coordinate_plane = [x.replace('-', '') for x in coordinate_plane]
        self.polarity = [1 if '-' not in x else -1 for x in coordinate_plane]
        self.fov_dimensions = fov_dimensions
        self.fov_position = fov_position
        self.view_plane = (self.coordinate_plane[0], self.coordinate_plane[1])  # plane currently being viewed

        self.scan_volumes = np.zeros([1, 1])  # 2d list detailing volume of tiles
        self.grid_coords = np.zeros([1, 1, 3])  # 2d list detailing start position of tiles
        self.start_tile_coord = np.zeros([1, 1, 3])
        self.end_tile_coord = np.zeros([1, 1, 3])

        self.grid_box_items = []  # 2D list detailing box items in grid
        self.grid_tile_items = []  # list of 2D lists detailing face items in grid
        self.tile_visibility = np.array([[True]])  # 2d list detailing visibility of tiles
        # tile aesthetic properties
        self.tile_color = tile_color
        self.tile_opacity = tile_opacity
        self.tile_line_width = tile_line_width

        # position data set externally since tiles are assumed out of order
        self.path = GLPathItem(width=path_line_width,
                               arrow_size=path_arrow_size,
                               arrow_aspect_ratio=path_arrow_aspect_ratio,
                               path_start_color=path_start_color,
                               path_end_color=path_end_color)
        self.addItem(self.path)

        # initialize dict of fov_images
        self.fov_images = {}

        # initialize fov
        self.fov_view = GLTileItem(width=fov_line_width)
        self.fov_view.setColor(fov_color)
        self.fov_view.setSize(*self.fov_dimensions)
        self.fov_view.setTransform(QMatrix4x4(1, 0, 0, self.fov_position[0] * self.polarity[0],
                                              0, 1, 0, self.fov_position[1] * self.polarity[1],
                                              0, 0, 1, self.fov_position[2] * self.polarity[2],
                                              0, 0, 0, 1))
        self.addItem(self.fov_view)

        self.fov_view_face = GLShadedBoxItem(pos=np.array([[self.fov_position]]),
                                             size=np.array(self.fov_dimensions),
                                             color=fov_color,
                                             opacity=fov_opacity,
                                             glOptions='additive')
        self.addItem(self.fov_view_face)

        self.valueChanged[str].connect(self.update_model)
        self.resized.connect(self._update_opts)

        self._update_opts()

    def update_model(self, attribute_name):
        """Update attributes of grid
        :param attribute_name: name of attribute to update"""

        if attribute_name == 'fov_position':
            # update fov_pos
            self.fov_view.setTransform(QMatrix4x4(1, 0, 0, self.fov_position[0] * self.polarity[0],
                                                  0, 1, 0, self.fov_position[1] * self.polarity[1],
                                                  0, 0, 1, self.fov_position[2] * self.polarity[2],
                                                  0, 0, 0, 1))
            self.fov_view_face.setTransform(QMatrix4x4(1, 0, 0, self.fov_position[0] * self.polarity[0],
                                                       0, 1, 0, self.fov_position[1] * self.polarity[1],
                                                       0, 0, 1, self.fov_position[2] * self.polarity[2],
                                                       0, 0, 0, 1))

        else:
            self.fov_view.setSize(x=self.fov_dimensions[0],
                                  y=self.fov_dimensions[1],
                                  z=0.0)
            self.fov_view_face.setTransform(QMatrix4x4(1, 0, 0, self.fov_position[0] * self.polarity[0],
                                                       0, 1, 0, self.fov_position[1] * self.polarity[1],
                                                       0, 0, 1, self.fov_position[2] * self.polarity[2],
                                                       0, 0, 0, 1))

            # faster to remove every box than parse which ones have changes
            for box in self.grid_box_items:
                self.removeItem(box)
            self.grid_box_items = []

            for tile in self.grid_tile_items:
                self.removeItem(tile)
            self.grid_tile_items = []

            total_rows = len(self.grid_coords)
            total_columns = len(self.grid_coords[0])

            for row in range(total_rows):
                for column in range(total_columns):
                    coord = [x*pol for x, pol in zip(self.grid_coords[row][column], self.polarity)]

                    size = [*self.fov_dimensions[:2], self.scan_volumes[row, column]]

                    tile = GLTileItem(width=self.tile_line_width)
                    tile.setSize(*size)
                    tile.setTransform(QMatrix4x4(1, 0, 0, coord[0],
                                                0, 1, 0, coord[1],
                                                0, 0, 1, coord[2],
                                                0, 0, 0, 1))
                    tile.setColor(self.tile_color)
                    tile.setVisible(self.tile_visibility[row, column])
                    self.addItem(tile)
                    self.grid_tile_items.append(tile)

                    # scale opacity for viewing
                    if self.view_plane == (self.coordinate_plane[0], self.coordinate_plane[1]):
                        opacity = self.tile_opacity
                    elif self.view_plane == (self.coordinate_plane[2], self.coordinate_plane[1]):
                        opacity = self.tile_opacity/total_columns
                    else:
                        opacity = self.tile_opacity / total_rows

                    box = GLShadedBoxItem(pos=np.array([[coord]]),
                                          size=np.array(size),
                                          color=self.tile_color,
                                          opacity=opacity,
                                          glOptions='additive',
                                          )
                    self.addItem(box)
                    self.grid_box_items.append(box)


        self._update_opts()

    def toggle_path_visibility(self, visible):
        """Slot for a radio button to toggle visibility of path"""

        if visible:
            self.path.setVisible(True)

        else:
            self.path.setVisible(False)

    def set_path_pos(self, coord_order: list):
        """Set the pos of path in correct order
        coord_order: ordered list of coords for path"""

        path = np.array([[((coord[i] * pol) + (.5 * fov)) if x in self.view_plane else 0. for i, fov, pol, x in
                          zip([0, 1, 2], self.fov_dimensions, self.polarity, self.coordinate_plane)] for coord in
                         coord_order])
        self.path.setData(pos=path)

    def add_fov_image(self, image: np.array, coords: list, levels: list):
        """add image to model assuming image has same fov dimensions and orientation
        :param image: numpy array of image to display in model
        :param coords: list of coordinates corresponding to the coordinate plane of model,
        :param levels: levels for passed in image"""

        image_rgba = makeRGBA(image, levels=levels)
        image_rgba[0][:, :, 3] = 200

        gl_image = GLImageItem(image_rgba[0],
                               glOptions='translucent')
        x, y, z = coords
        gl_image.setTransform(QMatrix4x4(self.fov_dimensions[0]/image.shape[0], 0, 0, x * self.polarity[0],
                                         0, self.fov_dimensions[1]/image.shape[1], 0, y * self.polarity[1],
                                         0, 0, 1, 0,    # 0 since tiling plane will display scan plan at 0
                                         0, 0, 0, 1))
        self.addItem(gl_image)
        self.fov_images[image.tobytes()] = gl_image

        if self.view_plane != (self.coordinate_plane[0], self.coordinate_plane[1]):
            gl_image.setVisible(False)

    def adjust_glimage_contrast(self, image, contrast_levels):
        """
        Adjust image in model contrast levels
        :param image: numpy array of image key in fov_images
        :param contrast_levels: levels for passed in image
        :return:
        """

        glimage = self.fov_images[image.tobytes()]
        coords = [glimage.transform()[i, 3] for i in range(3)]
        self.removeItem(glimage)
        self.add_fov_image(image, coords, contrast_levels)

    def toggle_fov_image_visibility(self, visible: bool):
        """Function to hide all fov_images
        :param visible: boolean for if fov_images should be visible"""

        for image in self.fov_images:
            image.setVisible(visible)

    def _update_opts(self):
        """Update view of widget. Note that x/y notation refers to horizontal/vertical dimensions of grid view"""

        view_plane = self.view_plane
        view_pol = [self.polarity[self.coordinate_plane.index(view_plane[0])],
                    self.polarity[self.coordinate_plane.index(view_plane[1])]]
        coords = self.grid_coords.reshape([-1, 3])  # flatten array

        # set rotation
        root = sqrt(2.0) / 2.0
        if view_plane == (self.coordinate_plane[0], self.coordinate_plane[1]):
            self.opts['rotation'] = QQuaternion(-1, 0, 0, 0)
        else:
            self.opts['rotation'] = QQuaternion(-root, 0, -root, 0) if \
                view_plane == (self.coordinate_plane[2], self.coordinate_plane[1]) else QQuaternion(-root, root, 0, 0)
            # take into account end of tile and account for difference in size if z included in view
            dimensions = self.scan_volumes.flatten()  # flatten array
            coords = np.concatenate((coords, [[x,
                                               y,
                                               (z + sz)] for (x, y, z), sz in zip(coords, dimensions)]))

        extrema = {'x_min': min([x for x, y, z in coords]), 'x_max': max([x for x, y, z in coords]),
                   'y_min': min([y for x, y, z in coords]), 'y_max': max([y for x, y, z in coords]),
                   'z_min': min([z for x, y, z in coords]), 'z_max': max([z for x, y, z in coords])}

        fov = {**{axis: dim for axis, dim in zip(['x', 'y'], self.fov_dimensions)}, 'z': 0}
        pos = {axis: dim for axis, dim in zip(['x', 'y', 'z'], self.fov_position)}
        distances = {'xy': [sqrt((pos[view_plane[0]] - x) ** 2 + (pos[view_plane[1]] - y) ** 2) for x, y, z in coords],
                     'xz': [sqrt((pos[view_plane[0]] - x) ** 2 + (pos[view_plane[1]] - z) ** 2) for x, y, z in coords],
                     'zy': [sqrt((pos[view_plane[0]] - z) ** 2 + (pos[view_plane[1]] - y) ** 2) for x, y, z in coords]}
        max_index = distances[''.join(view_plane)].index(max(distances[''.join(view_plane)], key=abs))
        furthest_tile = {'x': coords[max_index][0],
                         'y': coords[max_index][1],
                         'z': coords[max_index][2]}
        center = {}

        # Horizontal sizing, if fov_position is within grid or farthest distance is between grid tiles
        x = view_plane[0]
        if extrema[f'{x}_min'] <= pos[x] <= extrema[f'{x}_max'] or \
                abs(furthest_tile[x] - pos[x]) < abs(extrema[f'{x}_max'] - extrema[f'{x}_min']):
            center[x] = (((extrema[f'{x}_min'] + extrema[f'{x}_max']) / 2) + (fov[x] / 2 * view_pol[0])) * view_pol[0]
            horz_dist = ((extrema[f'{x}_max'] - extrema[f'{x}_min']) + (fov[x] * 2)) / 2 * tan(
                radians(self.opts['fov']))
        else:
            center[x] = (((pos[x] + furthest_tile[x]) / 2) + (fov[x] / 2 * view_pol[0])) * view_pol[0]
            horz_dist = (abs(pos[x] - furthest_tile[x]) + (fov[x] * 2)) / 2 * tan(radians(self.opts['fov']))
        # Vertical sizing, if fov_position is within grid or farthest distance is between grid tiles
        y = view_plane[1]
        if extrema[f'{y}_min'] <= pos[y] <= extrema[f'{y}_max'] or \
                abs(furthest_tile[y] - pos[y]) < abs(extrema[f'{y}_max'] - extrema[f'{y}_min']):
            center[y] = (((extrema[f'{y}_min'] + extrema[f'{y}_max']) / 2) + (fov[y] / 2 * view_pol[1])) * view_pol[1]
            # View doesn't scale when changing vertical size so take into account the dif between the height and width
            vert_dist = ((extrema[f'{y}_max'] - extrema[f'{y}_min']) + (fov[y] * 2)) / 2 \
                        * tan(radians(self.opts['fov'])) * (self.size().width() / self.size().height())

        else:
            center[y] = (((pos[y] + furthest_tile[y]) / 2) + (fov[y] / 2 * view_pol[1])) * view_pol[1]
            vert_dist = (abs(pos[y] - furthest_tile[y]) + (fov[y] * 2)) / 2 \
                        * (self.size().width() / self.size().height())
        # @Micah in ortho mode it seems to scale properly with x1200... not sure how to explain why though
        # not sure if this actually works, and whether it needs to be copied to other places in the fx
        self.opts['distance'] = horz_dist * 1200 if horz_dist > vert_dist else vert_dist * 1200
        self.opts['center'] = QVector3D(
            center.get('x', 0),
            center.get('y', 0),
            center.get('z', 0))
        self.update()

    def move_fov_query(self, new_fov_pos):
        """Message box asking if user wants to move fov position"""

        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(f"Do you want to move the field of view from "
                       f"{[round(x, 2) * t for x, t in zip(self.fov_position, self.polarity)]} [{self.unit}] to "
                       f"{[round(x, 2) for x in new_fov_pos]} [{self.unit}]?")
        msgBox.setWindowTitle("Moving FOV")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        checkbox = QCheckBox('Move to nearest tile')
        checkbox.setChecked(True)
        msgBox.setCheckBox(checkbox)

        return msgBox.exec(), checkbox.isChecked()

    def mousePressEvent(self, event):
        """Override mouseMoveEvent so user can't change view
        and allow user to move fov easier"""

        plane = self.view_plane
        if event.button() == Qt.LeftButton:
            # Translate mouseclick x, y into view widget coordinate plane.
            horz_dist = (self.opts['distance'] / tan(radians(self.opts['fov'])))/1200
            vert_dist = (self.opts['distance'] / tan(radians(self.opts['fov'])) * (
                    self.size().height() / self.size().width()))/1200
            horz_scale = ((event.x() * 2 * horz_dist) / self.size().width())
            vert_scale = ((event.y() * 2 * vert_dist) / self.size().height())

            # create dictionaries of from fov and pos
            fov = {'x': self.fov_dimensions[0] * self.polarity[0],
                   'y': self.fov_dimensions[1] * self.polarity[1],
                   'z': 0}
            pos = {axis: dim for axis, dim in zip(self.coordinate_plane, self.fov_position)}

            transform_dict = {grid: stage for grid, stage in zip(['x', 'y', 'z'], self.coordinate_plane)}
            other_dim = [dim for dim in transform_dict if dim not in plane][0]
            transform = [transform_dict[plane[0]], transform_dict[plane[1]], transform_dict[other_dim]]

            center = {'x': self.opts['center'].x(), 'y': self.opts['center'].y(), 'z': self.opts['center'].z()}
            h_ax = self.view_plane[0]
            v_ax = self.view_plane[1]

            new_pos = {transform[0]: (center[h_ax] - horz_dist + horz_scale) - .5 * fov[transform[0]],
                       transform[1]: (center[v_ax] + vert_dist - vert_scale) - .5 * fov[transform[1]],
                       transform[2]: pos[transform[2]]}
            return_value, checkbox = self.move_fov_query([new_pos['x'] * self.polarity[0],
                                                          new_pos['y'] * self.polarity[1],
                                                          new_pos['z'] * self.polarity[2]])

            if return_value == QMessageBox.Ok:
                if not checkbox:  # Move to exact location
                    pos = new_pos
                else:  # move to the nearest tile
                    flattened = self.grid_coords.reshape([-1, 3])
                    tree = spatial.KDTree(self.grid_coords.reshape([-1, 3]))
                    distance, index = tree.query([new_pos['x'], new_pos['y'], new_pos['z']])
                    tile = flattened[index]
                    pos = {'x': tile[0], 'y': tile[1], 'z': tile[2]}
                self.fov_position = [pos['x'], pos['y'], pos['z']]
                self.view_plane = plane  # make sure grid plane remains the same
                self.fovMoved.emit([pos['x'], pos['y'], pos['z']])

            else:
                return

    def mouseMoveEvent(self, event):
        """Override mouseMoveEvent so user can't change view"""
        pass

    def wheelEvent(self, event):
        """Override wheelEvent so user can't change view"""
        pass

    def keyPressEvent(self, event):
        """Override keyPressEvent so user can't change view"""
        pass

    def keyReleaseEvent(self, event):
        """Override keyPressEvent so user can't change view"""
        pass
