import numpy as np
from OpenGL.GL import *  # noqa
from pyqtgraph.opengl import GLLinePlotItem
from qtpy.QtGui import QColor


class GLPathItem(GLLinePlotItem):
    """Subclass of GLLinePlotItem that creates arrow at end of path."""

    def __init__(self, parentItem=None, **kwds):
        """_summary_

        :param parentItem: _description_, defaults to None
        :type parentItem: _type_, optional
        """
        super().__init__(parentItem)

        self.arrow_size_percent = kwds.get("arrow_size", 6.0)
        self.arrow_aspect_ratio = kwds.get("arrow_aspect_ratio", 4)
        self.path_start_color = kwds.get("path_start_color", "magenta")
        self.path_end_color = kwds.get("path_end_color", "green")
        self.width = kwds.get("width", 1)

    def setData(self, **kwds):
        """_summary_"""
        kwds["width"] = self.width

        if "pos" in kwds.keys():
            path = kwds["pos"]
            # draw the end arrow
            # determine last line segment direction and draw arrowhead correctly
            if len(path) > 1:
                vector = path[-1] - path[-2]
                if vector[1] > 0:
                    # calculate arrow size based on vector
                    arrow_size = abs(vector[1]) * self.arrow_size_percent / 100
                    x = np.array(
                        [path[-1, 0] - arrow_size, path[-1, 0] + arrow_size, path[-1, 0], path[-1, 0] - arrow_size]
                    )
                    y = np.array(
                        [path[-1, 1], path[-1, 1], path[-1, 1] + arrow_size * self.arrow_aspect_ratio, path[-1, 1]]
                    )
                    z = np.array([path[-1, 2], path[-1, 2], path[-1, 2], path[-1, 2]])
                elif vector[1] < 0:
                    # calculate arrow size based on vector
                    arrow_size = abs(vector[1]) * self.arrow_size_percent / 100
                    x = np.array(
                        [path[-1, 0] + arrow_size, path[-1, 0] - arrow_size, path[-1, 0], path[-1, 0] + arrow_size]
                    )
                    y = np.array(
                        [path[-1, 1], path[-1, 1], path[-1, 1] - arrow_size * self.arrow_aspect_ratio, path[-1, 1]]
                    )
                    z = np.array([path[-1, 2], path[-1, 2], path[-1, 2], path[-1, 2]])
                elif vector[0] < 0:
                    # calculate arrow size based on vector
                    arrow_size = abs(vector[0]) * self.arrow_size_percent / 100
                    x = np.array(
                        [path[-1, 0], path[-1, 0], path[-1, 0] - arrow_size * self.arrow_aspect_ratio, path[-1, 0]]
                    )
                    y = np.array(
                        [path[-1, 1] + arrow_size, path[-1, 1] - arrow_size, path[-1, 1], path[-1, 1] + arrow_size]
                    )
                    z = np.array([path[-1, 2], path[-1, 2], path[-1, 2], path[-1, 2]])
                else:
                    # calculate arrow size based on vector
                    arrow_size = abs(vector[0]) * self.arrow_size_percent / 100
                    x = np.array(
                        [path[-1, 0], path[-1, 0], path[-1, 0] + arrow_size * self.arrow_aspect_ratio, path[-1, 0]]
                    )
                    y = np.array(
                        [path[-1, 1] - arrow_size, path[-1, 1] + arrow_size, path[-1, 1], path[-1, 1] - arrow_size]
                    )
                    z = np.array([path[-1, 2], path[-1, 2], path[-1, 2], path[-1, 2]])
                xyz = np.transpose(np.array([x, y, z]))
                kwds["pos"] = np.concatenate((path, xyz), axis=0)

            num_tiles = len(path)
            path_gradient = np.zeros((num_tiles, 4))
            # create gradient rgba for each position
            for tile in range(0, num_tiles):
                # fill in (rgb)a first with linear weighted average
                start = QColor(self.path_start_color).getRgbF()
                end = QColor(self.path_end_color).getRgbF()
                path_gradient[tile, :] = (num_tiles - tile) / num_tiles * np.array(start) + (
                    tile / num_tiles
                ) * np.array(end)
            colors = np.repeat([path_gradient[-1, :]], repeats=4, axis=0)
            kwds["color"] = np.concatenate((path_gradient, colors), axis=0)

        super().setData(**kwds)
