import numpy as np
from pyqtgraph.opengl import GLViewWidget
from PyQt6 import QtGui

class GLOrthoViewWidget(GLViewWidget):
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