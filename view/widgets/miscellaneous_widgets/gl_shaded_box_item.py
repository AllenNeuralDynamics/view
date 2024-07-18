from pyqtgraph.opengl import GLMeshItem
import numpy as np
from qtpy.QtGui import QColor


class GLShadedBoxItem(GLMeshItem):
    """Subclass of GLMeshItem creates a rectangular mesh item"""

    def __init__(self, pos=None, size=None, color =None, opacity= 1, glOptions=None, parentItem=None):
        """

        :param pos: position of ite,
        :param size: size of item
        :param color: color of item
        :param glOptions:
        :param parentItem:
        """

        nCubes = np.prod(pos.shape[:-1])
        cubeVerts = np.mgrid[0:2, 0:2, 0:2].reshape(3, 8).transpose().reshape(1, 8, 3)
        cubeFaces = np.array([
            [0, 1, 2], [3, 2, 1],
            [4, 5, 6], [7, 6, 5],
            [0, 1, 4], [5, 4, 1],
            [2, 3, 6], [7, 6, 3],
            [0, 2, 4], [6, 4, 2],
            [1, 3, 5], [7, 5, 3]]).reshape(1, 12, 3)
        size = size.reshape((nCubes, 1, 3))
        pos = pos.reshape((nCubes, 1, 3))
        vertexes = (cubeVerts * size + pos)[0]
        faces = (cubeFaces + (np.arange(nCubes) * 8).reshape(nCubes, 1, 1))[0]

        if isinstance(color, str):
            rgbf = list(QColor(color).getRgbF())
            color = rgbf[:3] + [opacity*rgbf[3]]

        colors = np.array([color for i in range(12)])

        super().__init__(vertexes=vertexes, faces=faces, faceColors=colors,
                     drawEdges=True, edgeColor=(0, 0, 0, 1), glOptions=glOptions, parentItem=parentItem)


