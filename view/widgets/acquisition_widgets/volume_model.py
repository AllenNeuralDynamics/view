#@Micah subclasssed BoxItem that exposes linewidth arg
from view.pyqtgl.pyqtgl_widgets import GLThickBoxItem, GLOrthoViewWidget
from pyqtgraph.opengl import GLViewWidget, GLSurfacePlotItem, GLLinePlotItem, GLTextItem
from qtpy.QtWidgets import QMessageBox, QCheckBox
from qtpy.QtCore import Signal, Qt
from qtpy.QtGui import QColor, QMatrix4x4, QVector3D, QQuaternion, QFont
from math import tan, radians, sqrt
import numpy as np
from scipy import spatial


# TODO: Use this else where to. Consider moving it so we don't have to copy paste?
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
                 coordinate_plane: list[str] = ['x', 'y', 'z'],
                 fov_dimensions: list[float] = [1.0, 1.0],
                 fov_position: list[float] = [0.0, 0.0, 0.0],
                 view_color: str = 'yellow'):
        # @Micah view_color is now not used
        """GLViewWidget to display proposed grid of acquisition
        :param coordinate_plane: coordinate plane displayed on widget.
        Needed to move stage to correct coordinate position?
        :param fov_dimensions: dimensions of field of view in coordinate plane
        :param fov_position: position of fov
        :param view_color: optional color of fov box"""

        super().__init__(rotationMethod='quaternion')

        self.coordinate_plane = [x.replace('-', '') for x in coordinate_plane]
        self.polarity = [1 if '-' not in x else -1 for x in coordinate_plane]
        self.fov_dimensions = fov_dimensions
        self.fov_position = fov_position
        self.view_plane = (self.coordinate_plane[0], self.coordinate_plane[1])  # plane currently being viewed
        
        self.scan_volumes = np.zeros([1, 1])  # 2d list detailing volume of tiles
        self.grid_coords = np.zeros([1, 1, 3])  # 2d list detailing start position of tiles
        self.start_tile_coord = np.zeros([1, 1, 3])
        self.end_tile_coord = np.zeros([1, 1, 3])

        self.grid_BoxItems = []   # 2D list detailing box items in grid
        self.grid_FaceItems = []   # list of 2D lists detailing face items in grid
        self.tile_visibility = np.array([[True]])  # 2d list detailing visibility of tiles
        # @Micah added way more visualization inputs, should we hardcode or change init function?
        self.path_line_opacity = 1.0
        self.tile_line_opacity = 1.0
        self.tile_face_opacity = 0.075
        self.fov_line_opacity = 1.0
        self.fov_face_opacity = 0.15
        self.path_line_width = 2.0
        self.tile_line_width = 2.0
        self.fov_line_width = 2.0
        self.arrow_size = max(self.fov_dimensions)/24
        self.arrow_aspect_ratio = 4.0
        # @Micah we might be able to handle below more cleanly
        # color input for faces is different than lines
        # but maybe something like from pyqtgraph.mkColor solves this
        self.tile_line_color = QColor(0, 255, 255, 255)  # cyan
        self.fov_line_color = QColor(255, 255, 0, 255)  # yellow
        self.tile_face_color = [0, 1, 1]  # cyan
        self.fov_face_color = [1, 1, 0]  # yellow
        self.path_start_color = [1, 0, 1]  # magenta
        self.path_end_color = [0, 1, 0]  # green

        # data except width set externally since tiles are assumed out of order
        self.path = GLLinePlotItem(width=self.path_line_width)
        self.addItem(self.path)

        # add indicators of start and end and hide since no tiles yet
        # @Micah commenting out for now
        # self.start = GLTextItem(text='Start', font=QFont('Helvetica', 7))
        # self.start.setVisible(False)
        # self.end = GLTextItem(text='End', font=QFont('Helvetica', 7))
        # self.end.setVisible(False)
        # self.addItem(self.start)
        # self.addItem(self.end)

        # @Micah should we collapse these FOV calls into a sub function?
        # initialize fov
        self.fov_view = GLThickBoxItem(width=self.fov_line_width)
        self.fov_view.setColor(QColor(self.fov_line_color))
        self.fov_view.setSize(*self.fov_dimensions)
        self.fov_view.setTransform(QMatrix4x4(1, 0, 0, self.fov_position[0]*self.polarity[0],
                                              0, 1, 0, self.fov_position[1]*self.polarity[1],
                                              0, 0, 1, self.fov_position[2]*self.polarity[2],
                                              0, 0, 0, 1))
        self.addItem(self.fov_view)

        self.fov_view_face = self._draw_face(
            size_x=self.fov_dimensions[0],
            size_y=self.fov_dimensions[1],
            pos_x=self.fov_position[0]*self.polarity[0],
            pos_y=self.fov_position[1]*self.polarity[1],
            pos_z=self.fov_position[2]*self.polarity[2],
            face_color=self.fov_face_color,
            face_opacity=self.fov_face_opacity
        )

        self.addItem(self.fov_view_face)

        self.valueChanged[str].connect(self.update_model)
        self.resized.connect(self._update_opts)

        self._update_opts()

    def update_model(self, attribute_name):
        """Update attributes of grid
        :param attribute_name: name of attribute to update"""

        if attribute_name == 'fov_position':
            # update fov_pos
            self.fov_view.setTransform(QMatrix4x4(1, 0, 0, self.fov_position[0]*self.polarity[0],
                                                0, 1, 0, self.fov_position[1]*self.polarity[1],
                                                0, 0, 1, self.fov_position[2]*self.polarity[2],
                                                0, 0, 0, 1))
            self.fov_view_face.setTransform(QMatrix4x4(1, 0, 0, self.fov_position[0]*self.polarity[0],
                                                0, 1, 0, self.fov_position[1]*self.polarity[1],
                                                0, 0, 1, self.fov_position[2]*self.polarity[2],
                                                0, 0, 0, 1))

        else:
            self.fov_view.setSize(x=self.fov_dimensions[0],
                                  y=self.fov_dimensions[1],
                                  z=0.0)
            # plot with xy corner starting at 0,0
            self.fov_view_face.setData(x=np.array([0, self.fov_dimensions[0]]),
                                       y=np.array([0, self.fov_dimensions[1]]),
                                       z=np.zeros(shape=(2, 2)))

            # faster to remove every box than parse which ones have changes
            for box in self.grid_BoxItems:
                self.removeItem(box)
            self.grid_BoxItems = []
            for box in self.grid_FaceItems:
                for face in box:
                    self.removeItem(face)
            self.grid_FaceItems = []

            total_rows = len(self.grid_coords)
            total_columns = len(self.grid_coords[0])

            for row in range(total_rows):
                for column in range(total_columns):

                    coord = self.grid_coords[row][column]

                    # @Micah need to pass in rows and columns to adjust XZ and YZ face opacity
                    # because visualization is additive blending.

                    self._draw_box(
                        rows=total_rows,
                        columns=total_columns,
                        size_x=self.fov_dimensions[0],
                        size_y=self.fov_dimensions[1],
                        size_z=self.scan_volumes[row, column],
                        pos_x=coord[0]*self.polarity[0],
                        pos_y=coord[1]*self.polarity[1],
                        pos_z=coord[2]*self.polarity[2],
                        face_color=self.tile_face_color,
                        face_opacity=self.tile_face_opacity,
                        visibility=self.tile_visibility[row, column]
                    )

        self._update_opts()

    def _draw_face(self, size_x: float, size_y: float,
                   pos_x: float, pos_y: float, pos_z: float,
                   face_color, face_opacity):
        """Draw 2D face using GLSurfacePlotItem
        :param size_x: x size of box face
        :param size_y: y size of box face
        :param pos_x: x position of box face
        :param pos_y: y position of box face
        :param pos_z: z position of box face
        :param face_color: face color of box
        :param face_opacity: face opacity of box"""

        # create color matrix
        colors = np.zeros((2, 2, 4), dtype=float)  # 2x2 for square
        colors[:, :, 0] = face_color[0]
        colors[:, :, 1] = face_color[1]
        colors[:, :, 2] = face_color[2]
        colors[:, :, 3] = face_opacity

        face = GLSurfacePlotItem(
            x=np.array([0, size_x]),  # plot with xy corner starting at 0,0
            y=np.array([0, size_y]),
            z=np.zeros(shape=(2, 2)),
            colors=colors.reshape(2*2, 4),  # 2x2 for square
            # no shader so rotation independent colors
            shader=None,
            smooth=False,
            # additive blending insead of translucent
            glOptions='additive')

        face.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                     0, 1, 0, pos_y,
                                     0, 0, 1, pos_z,
                                     0, 0, 0, 1))
        return face

    def _draw_box(self, size_x: float, size_y: float, size_z: float,
                  pos_x: float, pos_y: float, pos_z: float,
                  face_color, face_opacity, visibility,
                  rows, columns):
        """Draw 3D box using GLSurfacePlotItem
        :param rows: total rows in grid
        :param columns: total columns in grid
        :param size_x: x size of box
        :param size_y: y size of box
        :param size_z: y size of box
        :param pos_x: x position of box
        :param pos_y: y position of box
        :param pos_z: z position of box
        :param face_color: face color of box
        :param face_opacity: face opacity of box
        :param visibility: visibility of box"""

        FaceItems = []

        # draw xy faces
        # create color matrix
        colors = np.zeros((2, 2, 4), dtype=float)  # 2x2 for square
        colors[:, :, 0] = face_color[0]
        colors[:, :, 1] = face_color[1]
        colors[:, :, 2] = face_color[2]
        colors[:, :, 3] = face_opacity

        face = GLSurfacePlotItem(
            x=np.array([0, size_x]),  # plot with xy corner starting at 0,0
            y=np.array([0, size_y]),
            z=np.zeros(shape=(2, 2)),
            colors=colors.reshape(2*2, 4),  # 2x2 for square
            # no shader so rotation independent colors
            shader=None,
            smooth=False,
            # additive blending insead of translucent
            glOptions='additive')

        face.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                     0, 1, 0, pos_y,
                                     0, 0, 1, pos_z,
                                     0, 0, 0, 1))
        face.setVisible(visibility)
        self.addItem(face)
        FaceItems.append(face)

        face = GLSurfacePlotItem(
            x=np.array([0, size_x]),  # plot with xy corner starting at 0,0
            y=np.array([0, size_y]),
            z=np.zeros(shape=(2, 2)) + size_z,
            colors=colors.reshape(2*2, 4),  # 2x2 for square
            # no shader so rotation independent colors
            shader=None,
            smooth=False,
            # additive blending insead of translucent
            glOptions='additive')

        face.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                     0, 1, 0, pos_y,
                                     0, 0, 1, pos_z,
                                     0, 0, 0, 1))
        face.setVisible(visibility)
        self.addItem(face)
        FaceItems.append(face)

        # draw xz faces
        # create color matrix
        colors = np.zeros((2, 2, 4), dtype=float)  # 2x2 for square
        colors[:, :, 0] = face_color[0]
        colors[:, :, 1] = face_color[1]
        colors[:, :, 2] = face_color[2]
        # adjust for additive blending based on number of xz faces
        colors[:, :, 3] = face_opacity/rows

        z = np.zeros(shape=(2, 2))
        z[0, 0] = size_z
        z[1, 0] = size_z
        z[0, 1] = 0
        z[1, 1] = 0
        # plot centered at 0,0,0 so translation is easy to calculate
        face = GLSurfacePlotItem(
            x=np.array([0, size_x]),
            y=np.array([size_y, size_y]),
            z=z,
            colors=colors.reshape(2*2, 4),
            # no shader so rotation independent colors
            shader=None,
            smooth=False,
            # additive blending insead of translucent
            glOptions='additive')

        face.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                     0, 1, 0, pos_y,
                                     0, 0, 1, pos_z,
                                     0, 0, 0, 1))
        face.setVisible(visibility)
        self.addItem(face)
        FaceItems.append(face)

        z = np.zeros(shape=(2, 2))
        z[0, 0] = size_z
        z[1, 0] = size_z
        z[0, 1] = 0
        z[1, 1] = 0
        # plot centered at 0,0,0 so translation is easy to calculate
        face = GLSurfacePlotItem(
            x=np.array([0, size_x]),
            y=np.array([0, 0]),
            z=z,
            colors=colors.reshape(2*2, 4),
            # no shader so rotation independent colors
            shader=None,
            smooth=False,
            # additive blending insead of translucent
            glOptions='additive')

        face.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                     0, 1, 0, pos_y,
                                     0, 0, 1, pos_z,
                                     0, 0, 0, 1))
        face.setVisible(visibility)
        self.addItem(face)
        FaceItems.append(face)

        # draw yz faces
        # create color matrix
        colors = np.zeros((2, 2, 4), dtype=float)  # 2x2 for square
        colors[:, :, 0] = face_color[0]
        colors[:, :, 1] = face_color[1]
        colors[:, :, 2] = face_color[2]
        # adjust for additive blending based on number of yz faces
        colors[:, :, 3] = face_opacity/columns

        z = np.zeros(shape=(2, 2))
        z[0, 0] = size_z
        z[1, 0] = 0
        z[0, 1] = size_z
        z[1, 1] = 0
        # plot centered at 0,0,0 so translation is easy to calculate
        face = GLSurfacePlotItem(
            x=np.array([0, 0]),
            y=np.array([0, size_y]),
            z=z,
            colors=colors.reshape(2*2, 4),
            # no shader so rotation independent colors
            shader=None,
            smooth=False,
            # additive blending insead of translucent
            glOptions='additive')

        face.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                     0, 1, 0, pos_y,
                                     0, 0, 1, pos_z,
                                     0, 0, 0, 1))
        face.setVisible(visibility)
        self.addItem(face)
        FaceItems.append(face)

        z = np.zeros(shape=(2, 2))
        z[0, 0] = size_z
        z[1, 0] = 0
        z[0, 1] = size_z
        z[1, 1] = 0
        # plot centered at 0,0,0 so translation is easy to calculate
        face = GLSurfacePlotItem(
            x=np.array([size_x, size_x]),
            y=np.array([0, size_y]),
            z=z,
            colors=colors.reshape(2*2, 4),
            # no shader so rotation independent colors
            shader=None,
            smooth=False,
            # additive blending insead of translucent
            glOptions='additive')

        face.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                     0, 1, 0, pos_y,
                                     0, 0, 1, pos_z,
                                     0, 0, 0, 1))
        face.setVisible(visibility)
        self.addItem(face)
        FaceItems.append(face)

        # @Micah this is a list of lists
        # to keep track of which faces are part of which box
        # use this in set_path_pos() to grab and updaet color
        # for the first and last tile
        self.grid_FaceItems.append(FaceItems)

        # draw wireframe box
        box = GLThickBoxItem(width=2)
        box.setSize(size_x, size_y, size_z)
        box.setTransform(QMatrix4x4(1, 0, 0, pos_x,
                                    0, 1, 0, pos_y,
                                    0, 0, 1, pos_z,
                                    0, 0, 0, 1))
        box.setColor(self.tile_line_color)
        box.setVisible(visibility)
        self.addItem(box)
        self.grid_BoxItems.append(box)

    def toggle_path_visibility(self, visible):
        """Slot for a radio button to toggle visibility of path"""

        if visible:
            self.path.setVisible(True)
            # @Micah commenting out for now
            # if len(self.grid_BoxItems) > 1:
            #     self.start.setVisible(True)
            #     self.end.setVisible(True)
        else:
            self.path.setVisible(False)
            # @Micah commenting out for now
            # self.start.setVisible(False)
            # self.end.setVisible(False)

    def set_path_pos(self, coord_order: list):
        """Set the pos of path in correct order
        coord_order: ordered list of coords for path"""
        path = np.array([[((coord[i]*pol) + (.5 * fov)) if x in self.view_plane else 0. for i, fov, pol, x in
                 zip([0, 1, 2], self.fov_dimensions, self.polarity, self.coordinate_plane)] for coord in coord_order])
        num_tiles = len(path)
        path_gradient = np.zeros((num_tiles, 4))
        # create gradient rgba for each position
        for tile in range(0, num_tiles):
            # fill in (rgb)a first with linear weighted average
            path_gradient[tile, 0:3] = \
                (num_tiles - tile)/num_tiles*np.array(self.path_start_color) + \
                (tile/num_tiles)*np.array(self.path_end_color)
        # fill in rgb(a) last
        path_gradient[:, 3] = self.path_line_opacity
        # update path positions and colors
        # self.path.setData(pos=path, color=path_gradient)
        # draw the end arrow
        # determine last line segment direction and draw arrowhead correctly
        if num_tiles > 1:
            vector = path[-1] - path[-2]
            if vector[1] > 0:
                x = np.array([path[-1, 0]-self.arrow_size,
                              path[-1, 0]+self.arrow_size,
                              path[-1, 0],
                              path[-1, 0]-self.arrow_size])
                y = np.array([path[-1, 1],
                              path[-1, 1],
                              path[-1, 1]+self.arrow_size*self.arrow_aspect_ratio,
                              path[-1, 1]])
                z = np.array([path[-1, 2],
                              path[-1, 2],
                              path[-1, 2],
                              path[-1, 2]])
            elif vector[1] < 0:
                x = np.array([path[-1, 0]+self.arrow_size,
                              path[-1, 0]-self.arrow_size,
                              path[-1, 0],
                              path[-1, 0]+self.arrow_size])
                y = np.array([path[-1, 1],
                              path[-1, 1],
                              path[-1, 1]-self.arrow_size*self.arrow_aspect_ratio,
                              path[-1, 1]])
                z = np.array([path[-1, 2],
                              path[-1, 2],
                              path[-1, 2],
                              path[-1, 2]])
            elif vector[0] < 0:
                x = np.array([path[-1, 0],
                              path[-1, 0],
                              path[-1, 0]-self.arrow_size*self.arrow_aspect_ratio,
                              path[-1, 0]])
                y = np.array([path[-1, 1]+self.arrow_size,
                              path[-1, 1]-self.arrow_size,
                              path[-1, 1],
                              path[-1, 1]+self.arrow_size])
                z = np.array([path[-1, 2],
                              path[-1, 2],
                              path[-1, 2],
                              path[-1, 2]])
            elif vector[0] > 0:
                x = np.array([path[-1, 0],
                              path[-1, 0],
                              path[-1, 0]+self.arrow_size*self.arrow_aspect_ratio,
                              path[-1, 0]])
                y = np.array([path[-1, 1]-self.arrow_size,
                              path[-1, 1]+self.arrow_size,
                              path[-1, 1],
                              path[-1, 1]-self.arrow_size])
                z = np.array([path[-1, 2],
                              path[-1, 2],
                              path[-1, 2],
                              path[-1, 2]])
            xyz = np.transpose(np.array([x, y, z]))
            colors = np.repeat([path_gradient[-1, :]], repeats=4, axis=0)
            self.path.setData(pos=np.concatenate((path, xyz), axis=0),
                                color=np.concatenate((path_gradient, colors), axis=0))

        # @Micah commenting out for now
        # if len(coord_order) > 1 and self.path.visible():
        #     self.start.setData(pos=path[0])
        #     self.end.setData(pos=path[-1])
        #     self.start.setVisible(True)
        #     self.end.setVisible(True)

        # else:
        #     self.start.setVisible(False)
        #     self.end.setVisible(False)

    def _update_opts(self):
        """Update view of widget. Note that x/y notation refers to horizontal/vertical dimensions of grid view"""

        view_plane = self.view_plane
        view_pol = [self.polarity[self.coordinate_plane.index(view_plane[0])],
                     self.polarity[self.coordinate_plane.index(view_plane[1])]]
        coords = self.grid_coords.reshape([-1, 3]) # flatten array
        #@Micah changing these to sqrt(2)/2 for more accuracy
        # set rotation
        if view_plane == (self.coordinate_plane[0], self.coordinate_plane[1]):
            self.opts['rotation'] = QQuaternion(-1, 0, 0, 0)
        else:
            self.opts['rotation'] = QQuaternion(-sqrt(2.0)/2.0, 0, -sqrt(2.0)/2.0, 0) if \
                view_plane == (self.coordinate_plane[2], self.coordinate_plane[1]) else QQuaternion(-sqrt(2.0)/2.0, sqrt(2.0)/2.0, 0, 0)
            # take into account end of tile and account for difference in size if z included in view
            dimensions = self.scan_volumes.flatten() # flatten array
            coords = np.concatenate((coords, [[x,
                                               y,
                                              (z + sz)] for (x,y,z), sz in zip(coords, dimensions)]))


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
            horz_dist = ((extrema[f'{x}_max'] - extrema[f'{x}_min']) + (fov[x] * 2)) / 2 * tan(radians(self.opts['fov']))
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
                        * tan(radians(self.opts['fov'])) * (self.size().width() / self.size().height())
        #@Micah in ortho mode it seems to scale properly with x1200... not sure how to explain why though
        # not sure if this actually works, and whether it needs to be copied to other places in the fx
        self.opts['distance'] = horz_dist*1200 if horz_dist > vert_dist else vert_dist*1200
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
                       f"{[round(x, 2)*t for x, t in zip(self.fov_position, self.polarity)]} to "
                       f"{[round(x, 2) for x in new_fov_pos]}?")
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
            horz_dist = self.opts['distance'] / tan(radians(self.opts['fov']))
            vert_dist = self.opts['distance'] / tan(radians(self.opts['fov'])) * (
                    self.size().height() / self.size().width())
            horz_scale = ((event.x() * 2 * horz_dist) / self.size().width())
            vert_scale = ((event.y() * 2 * vert_dist) / self.size().height())

            # create dictionaries of from fov and pos
            fov = {'x': self.fov_dimensions[0]*self.polarity[0],
                   'y': self.fov_dimensions[1]*self.polarity[1],
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
            return_value, checkbox = self.move_fov_query([new_pos['x']*self.polarity[0],
                                                          new_pos['y']*self.polarity[1],
                                                          new_pos['z']*self.polarity[2]])

            if return_value == QMessageBox.Ok:
                if not checkbox:    # Move to exact location
                    pos = new_pos
                else:   # move to the nearest tile
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
