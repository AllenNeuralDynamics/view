import numpy as np
import pyqtgraph.opengl as gl
from OpenGL.GL import *  # noqa
from PyQt6 import QtGui
from PyQt6.QtGui import QColor
from pyqtgraph import mkColor


class GLOrthoViewWidget(gl.GLViewWidget):
    """
    **Bases:** :class:`GLGraphicsItem <pyqtgraph.opengl.GLViewWidget>`
    """
    # override projectionMatrix is overrided to enable true ortho projection
    def projectionMatrix(self, region=None, projection='ortho'):
        assert projection in ['ortho', 'frustum']
        if region is None:
            dpr = self.devicePixelRatio()
            region = (0, 0, self.width() * dpr, self.height() * dpr)

        x0, y0, w, h = self.getViewport()
        dist = self.opts['distance']
        fov = self.opts['fov']
        nearClip = dist * 0.001
        farClip = dist * 1000.

        r = nearClip * np.tan(fov * 0.5 * np.pi / 180.)
        t = r * h / w

        # note that x0 and width in these equations must
        # be the values used in viewport
        left = r * ((region[0] - x0) * (2.0 / w) - 1)
        right = r * ((region[0] + region[2] - x0) * (2.0 / w) - 1)
        bottom = t * ((region[1] - y0) * (2.0 / h) - 1)
        top = t * ((region[1] + region[3] - y0) * (2.0 / h) - 1)

        tr = QtGui.QMatrix4x4()
        if projection == 'ortho':
            tr.ortho(left, right, bottom, top, nearClip, farClip)
        elif projection == 'frustum':
            tr.frustum(left, right, bottom, top, nearClip, farClip)
        return tr


class GLThickBoxItem(gl.GLBoxItem):
    """
    **Bases:** :class:`GLGraphicsItem <pyqtgraph.opengl.GLBoxItem>`
    Displays a wire-frame box with user-defined line thickness.
    """
    def __init__(self, size=None, color=None, width=None, glOptions='translucent', parentItem=None):
        super().__init__(parentItem=parentItem)
        self.width = width

    # override paint to add line thickness argument
    def paint(self):
        #glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        #glEnable( GL_BLEND )
        #glEnable( GL_ALPHA_TEST )
        ##glAlphaFunc( GL_ALWAYS,0.5 )
        #glEnable( GL_POINT_SMOOTH )
        #glDisable( GL_DEPTH_TEST )
        self.setupGLState()
        glLineWidth(self.width)  # added line for thickness setting
        super().paint()
        # glBegin( GL_LINES )
        # glColor4f(*self.color().getRgbF())
        # x,y,z = self.size()
        # glVertex3f(0, 0, 0)
        # glVertex3f(0, 0, z)
        # glVertex3f(x, 0, 0)
        # glVertex3f(x, 0, z)
        # glVertex3f(0, y, 0)
        # glVertex3f(0, y, z)
        # glVertex3f(x, y, 0)
        # glVertex3f(x, y, z)
        #
        # glVertex3f(0, 0, 0)
        # glVertex3f(0, y, 0)
        # glVertex3f(x, 0, 0)
        # glVertex3f(x, y, 0)
        # glVertex3f(0, 0, z)
        # glVertex3f(0, y, z)
        # glVertex3f(x, 0, z)
        # glVertex3f(x, y, z)
        #
        # glVertex3f(0, 0, 0)
        # glVertex3f(x, 0, 0)
        # glVertex3f(0, y, 0)
        # glVertex3f(x, y, 0)
        # glVertex3f(0, 0, z)
        # glVertex3f(x, 0, z)
        # glVertex3f(0, y, z)
        # glVertex3f(x, y, z)
        # glEnd()


class GLThickAxisItem(gl.GLAxisItem):
    """
    **Bases:** :class:`GLGraphicsItem <pyqtgraph.opengl.GLAxisItem>`
    Displays three lines indicating origin and orientation of local coordinate system.
    Line thickness and color are user-defined.
    """
    def __init__(self,
                 size=None,
                 width=1,
                 xcolor=QColor(255, 0, 0),
                 ycolor=QColor(0, 255, 0),
                 zcolor=QColor(0, 0, 255),
                 antialias=True,
                 glOptions='translucent',
                 parentItem=None):
        super().__init__(parentItem=parentItem)
        self.width = width
        self.__xcolor = mkColor(xcolor)
        self.__ycolor = mkColor(ycolor)
        self.__zcolor = mkColor(zcolor)

    # override paint to add line thickness and color arguments
    def paint(self):
        # override paint to add line thickness arg
        #glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        #glEnable( GL_BLEND )
        #glEnable( GL_ALPHA_TEST )
        self.setupGLState()

        if self.antialias:
            glEnable(GL_LINE_SMOOTH)
            glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        glLineWidth(self.width)  # added line for thickness setting
        glBegin( GL_LINES )

        x,y,z = self.size()
        glColor4f(*self.__zcolor.getRgbF())  # z
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, z)

        glColor4f(*self.__ycolor.getRgbF())  # y
        glVertex3f(0, 0, 0)
        glVertex3f(0, y, 0)

        glColor4f(*self.__xcolor.getRgbF())  # x
        glVertex3f(0, 0, 0)
        glVertex3f(x, 0, 0)
        glEnd()
