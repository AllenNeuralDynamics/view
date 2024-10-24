from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QSlider


class QScrollableFloatSlider(QSlider):
    """QSlider that will emit signal if scrolled with mouse wheel and allow float values"""
    sliderMoved = Signal(float)  # redefine slider move to emit float

    def __init__(self, decimals=0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.divisor = 10 ** decimals

    def value(self):
        return float(super().value()) / self.divisor

    def setMinimum(self, value):
        return super().setMinimum(int(value * self.divisor))

    def setMaximum(self, value):
        return super().setMaximum(int(value * self.divisor))

    def maximum(self):
        return super().maximum() / self.divisor

    def minimum(self):
        return super().minimum() / self.divisor

    def setSingleStep(self, value):
        return super().setSingleStep(value * self.divisor)

    def singleStep(self):
        return float(super().singleStep()) / self.divisor

    def setValue(self, value):
        super().setValue(int(value * self.divisor))

    def wheelEvent(self, event):
        super().wheelEvent(event)
        value = self.value()
        self.sliderMoved.emit(value)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if event.buttons() == Qt.MouseButton.LeftButton:
            value = self.value()
            self.sliderMoved.emit(value)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        value = self.value()
        self.sliderMoved.emit(value)
