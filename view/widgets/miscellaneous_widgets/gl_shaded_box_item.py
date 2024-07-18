from pyqtgraph.opengl import GLBarGraphItem
from OpenGL.GL import *  # noqa
import numpy as np
from qtpy.QtGui import QColor


class GLShadedBoxItem(GLBarGraphItem):
    """Subclass of GLBarGraphItem that allows gloptions to be passed in"""

    def __init__(self, pos, size, color, glOptions, parentItem=None, top_opacity_scale=1, side_opacity_scale=1):

        """

        :param pos: position of ite,
        :param size: size of item
        :param color: color of item
        :param glOptions:
        :param parentItem:
        :param top_opacity_scale: scale factor for opacity of top of item
        :param side_opacity_scale: scale factor for opacity of side of item
        """

        super().__init__(pos=pos, size=size, parentItem=parentItem)

        self.setGLOptions(glOptions)
        self.setColor(color)
        self.top_opacity_scale = top_opacity_scale
        self.side_opacity_scale = side_opacity_scale

    def paint(self):
        """Overwriting to make faces different opacity"""

        self.setupGLState()

        self.parseMeshData()

        if self.opts['drawFaces']:
            with self.shader():
                verts = self.vertexes
                norms = self.normals
                color = self.colors
                faces = self.faces
                if verts is None:
                    return

                alpha_scale = [self.side_opacity_scale, self.side_opacity_scale, self.top_opacity_scale,
                               self.top_opacity_scale, 1, 1]
                for i, alpha in zip(range(2, 12, 2),alpha_scale):
                    face = verts[i - 2:i, :]
                    glEnableClientState(GL_VERTEX_ARRAY)
                    try:
                        glVertexPointerf(face)

                        if self.colors is None:
                            color = self.opts['color']
                            if isinstance(color, QColor):
                                rgbf = list(color.getRgbF())
                                color = rgbf[:3] + [alpha*rgbf[3]]
                                glColor4f(*color)
                            else:
                                color = color[:3] + [alpha*color[3]]
                                glColor4f(*color)
                        else:
                            glEnableClientState(GL_COLOR_ARRAY)
                            color = color[:3] + [alpha*color[3]]
                            glColorPointerf(color)

                        glColor4f(*color)

                        if norms is not None:
                            glEnableClientState(GL_NORMAL_ARRAY)
                            glNormalPointerf(norms)

                        if faces is None:
                            glDrawArrays(GL_TRIANGLES, 0, np.product(face.shape[:-1]))
                        else:
                            faces = faces.astype(np.uint32).flatten()
                            glDrawElements(GL_TRIANGLES, faces.shape[0], GL_UNSIGNED_INT, faces)
                    finally:
                        glDisableClientState(GL_NORMAL_ARRAY)
                        glDisableClientState(GL_VERTEX_ARRAY)
                        glDisableClientState(GL_COLOR_ARRAY)

        if self.opts['drawEdges']:
            verts = self.edgeVerts
            edges = self.edges
            glEnableClientState(GL_VERTEX_ARRAY)
            try:
                glVertexPointerf(verts)

                if self.edgeColors is None:
                    color = self.opts['edgeColor']
                    if isinstance(color, QColor):
                        glColor4f(*color.getRgbF())
                    else:
                        glColor4f(*color)
                else:
                    glEnableClientState(GL_COLOR_ARRAY)
                    glColorPointerf(color)
                edges = edges.flatten()
                glDrawElements(GL_LINES, edges.shape[0], GL_UNSIGNED_INT, edges)
            finally:
                glDisableClientState(GL_VERTEX_ARRAY)
                glDisableClientState(GL_COLOR_ARRAY)
