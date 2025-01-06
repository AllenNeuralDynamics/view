import numpy as np
from OpenGL.GL import *  # noqa
from pyqtgraph.opengl import GLMeshItem
from qtpy.QtGui import QColor


class GLShadedBoxItem(GLMeshItem):
    """
    Subclass of GLMeshItem creates a rectangular mesh item.
    """

    def __init__(
        self,
        pos: np.ndarray,
        size: np.ndarray,
        color: str = "cyan",
        width: float = 1,
        opacity: float = 1,
        *args,
        **kwargs,
    ):
        """_summary_

        :param pos: _description_
        :type pos: np.ndarray
        :param size: _description_
        :type size: np.ndarray
        :param color: _description_, defaults to 'cyan'
        :type color: str, optional
        :param width: _description_, defaults to 1
        :type width: float, optional
        :param opacity: _description_, defaults to 1
        :type opacity: float, optional
        """
        self._size = size
        self._width = width
        self._opacity = opacity
        self._color = color
        colors = np.array([self._convert_color(color) for i in range(12)])

        self._pos = pos
        self._vertexes, self._faces = self._create_box(pos, size)

        super().__init__(
            vertexes=self._vertexes,
            faces=self._faces,
            faceColors=colors,
            drawEdges=True,
            edgeColor=(0, 0, 0, 1),
            *args,
            **kwargs,
        )

    def _create_box(self, pos: np.ndarray, size: np.ndarray) -> (np.ndarray, np.ndarray):
        """_summary_

        :param self: _description_
        :type self: _type_
        :param np: _description_
        :type np: _type_
        :return: _description_
        :rtype: _type_
        """
        nCubes = np.prod(pos.shape[:-1])
        cubeVerts = np.mgrid[0:2, 0:2, 0:2].reshape(3, 8).transpose().reshape(1, 8, 3)
        cubeFaces = np.array(
            [
                [0, 1, 2],
                [3, 2, 1],
                [4, 5, 6],
                [7, 6, 5],
                [0, 1, 4],
                [5, 4, 1],
                [2, 3, 6],
                [7, 6, 3],
                [0, 2, 4],
                [6, 4, 2],
                [1, 3, 5],
                [7, 5, 3],
            ]
        ).reshape(1, 12, 3)
        size = size.reshape((nCubes, 1, 3))
        pos = pos.reshape((nCubes, 1, 3))
        vertexes = (cubeVerts * size + pos)[0]
        faces = (cubeFaces + (np.arange(nCubes) * 8).reshape(nCubes, 1, 1))[0]

        return vertexes, faces

    def color(self) -> str or list[float, float, float, float]:
        """_summary_

        :return: _description_
        :rtype: str or list[float, float, float, float]
        """
        return self._color

    def setColor(self, color: str or list[float, float, float, float]) -> None:
        """_summary_

        :param color: _description_
        :type color: strorlist[float, float, float, float]
        """
        self._color = color
        colors = np.array([self._convert_color(self._color) for i in range(12)])
        self.setMeshData(vertexes=self._vertexes, faces=self._faces, faceColors=colors)

    def _convert_color(self, color: str) -> list[float, float, float, float]:
        """_summary_

        :param color: _description_
        :type color: str
        :return: _description_
        :rtype: list[float, float, float, float]
        """
        if isinstance(color, str):
            rgbf = list(QColor(color).getRgbF())
            color = rgbf[:3] + [self._opacity * rgbf[3]]
        return color

    def size(self) -> np.ndarray:
        """_summary_

        :return: _description_
        :rtype: np.ndarray
        """
        return self._size

    def setSize(self, x: float, y: float, z: float) -> None:
        """_summary_

        :param x: _description_
        :type x: float
        :param y: _description_
        :type y: float
        :param z: _description_
        :type z: float
        """
        self._size = np.array([x, y, z])
        self._vertexes, self._faces = self._create_box(self._pos, self._size)
        colors = np.array([self._convert_color(self._color) for i in range(12)])
        self.setMeshData(vertexes=self._vertexes, faces=self._faces, faceColors=colors)

    def paint(self) -> None:
        """_summary_"""
        super().paint()

        self.setupGLState()
        glLineWidth(self._width)  # added line for thickness setting

        glBegin(GL_LINES)

        glColor4f(*self._convert_color(self._color))

        x, y, z = [self._pos[0, 0, i] + x for i, x in enumerate(self.size())]
        x_pos, y_pos, z_pos = self._pos[0, 0, :]

        glVertex3f(x_pos, y_pos, z_pos)
        glVertex3f(x_pos, y_pos, z)
        glVertex3f(x, y_pos, z_pos)
        glVertex3f(x, y_pos, z)
        glVertex3f(x_pos, y, z_pos)
        glVertex3f(x_pos, y, z)
        glVertex3f(x, y, z_pos)
        glVertex3f(x, y, z)

        glVertex3f(x_pos, y_pos, z_pos)
        glVertex3f(x_pos, y, z_pos)
        glVertex3f(x, y_pos, z_pos)
        glVertex3f(x, y, z_pos)
        glVertex3f(x_pos, y_pos, z)
        glVertex3f(x_pos, y, z)
        glVertex3f(x, y_pos, z)
        glVertex3f(x, y, z)

        glVertex3f(x_pos, y_pos, z_pos)
        glVertex3f(x, y_pos, z_pos)
        glVertex3f(x_pos, y, z_pos)
        glVertex3f(x, y, z_pos)
        glVertex3f(x_pos, y_pos, z)
        glVertex3f(x, y_pos, z)
        glVertex3f(x_pos, y, z)
        glVertex3f(x, y, z)

        glEnd()
