from qtpy.QtWidgets import QLabel
from qtpy.QtCore import Signal
from qtpy.QtGui import QMouseEvent

class QClickableLabel(QLabel):
    """QLabel that emits signal when clicked"""

    clicked = Signal()

    def mousePressEvent(self, ev: QMouseEvent, **kwargs) -> None:
        """
        Overwriting to emit signal
        :param ev: mouse click event
        """
        self.clicked.emit()
        super().mousePressEvent(ev, **kwargs)