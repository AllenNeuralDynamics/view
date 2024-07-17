from pyqtgraph.opengl import GLBarGraphItem
from OpenGL.GL import *  # noqa

class GLShadedBoxItem(GLBarGraphItem):
    """Subclass of GLBarGraphItem that allows gloptions to be passed in"""

    def __init__(self, pos, size, color, glOptions,  parentItem=None):

        super().__init__(pos=pos, size=size, parentItem=parentItem)

        self.setGLOptions(glOptions)
        self.setColor(color)


