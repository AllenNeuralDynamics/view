from qtpy.QtCore import Signal
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QLabel


class QClickableLabel(QLabel):
    """
    QLabel that emits signal when clicked.
    """

    clicked = Signal()

    def mousePressEvent(self, ev: QMouseEvent, **kwargs) -> None:
        """_summary_

        :param ev: _description_
        :type ev: QMouseEvent
        """
        self.clicked.emit()
        super().mousePressEvent(ev, **kwargs)