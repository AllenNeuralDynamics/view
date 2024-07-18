from pyqtgraph.opengl import GLBoxItem
from OpenGL.GL import *  # noqa

class GLTileItem(GLBoxItem):
    """ Subclass of GLBoxItem that allows for determining line width"""
    def __init__(self, width=None, size=None, parentItem=None):

        super().__init__(size=size, parentItem=parentItem)

        self.width = width

    # override paint to add line thickness argument
    def paint(self):

        self.setupGLState()
        glLineWidth(self.width)  # added line for thickness setting

        super().paint()