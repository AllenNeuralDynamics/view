from typing import Literal

import numpy as np
from pyqtgraph.opengl import GLViewWidget
from qtpy.QtGui import QMatrix4x4


class GLOrthoViewWidget(GLViewWidget):
    """
    Class inheriting from GLViewWidget that only allows specification of orthogonal or frustum view.
    """

    # override projectionMatrix is overrided to enable true ortho projection
    def projectionMatrix(self, region=None, projection: Literal["ortho", "frustum"] = "ortho") -> QMatrix4x4:
        """_summary_

        :param region: _description_, defaults to None
        :type region: _type_, optional
        :param projection: _description_, defaults to 'ortho'
        :type projection: Literal[&#39;ortho&#39;, &#39;frustum&#39;], optional
        :return: _description_
        :rtype: QMatrix4x4
        """
        assert projection in ["ortho", "frustum"]
        if region is None:
            dpr = self.devicePixelRatio()
            region = (0, 0, self.width() * dpr, self.height() * dpr)

        x0, y0, w, h = self.getViewport()
        dist = self.opts["distance"]
        fov = self.opts["fov"]
        nearClip = dist * 0.001
        farClip = dist * 1000.0

        r = nearClip * np.tan(fov * 0.5 * np.pi / 180.0)
        t = r * h / w

        # note that x0 and width in these equations must
        # be the values used in viewport
        left = r * ((region[0] - x0) * (2.0 / w) - 1)
        right = r * ((region[0] + region[2] - x0) * (2.0 / w) - 1)
        bottom = t * ((region[1] - y0) * (2.0 / h) - 1)
        top = t * ((region[1] + region[3] - y0) * (2.0 / h) - 1)

        tr = QMatrix4x4()
        if projection == "ortho":
            tr.ortho(left, right, bottom, top, nearClip, farClip)
        elif projection == "frustum":
            tr.frustum(left, right, bottom, top, nearClip, farClip)
        return tr
