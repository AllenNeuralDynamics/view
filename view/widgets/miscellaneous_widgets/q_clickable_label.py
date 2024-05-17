from qtpy.QtWidgets import QLabel
from qtpy.QtCore import Signal

class QClickableLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, ev):
        self.clicked.emit()
        super().mousePressEvent(ev)