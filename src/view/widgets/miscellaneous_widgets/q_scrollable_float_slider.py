from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import QSlider


class QScrollableFloatSlider(QSlider):
    """
    QSlider that will emit signal if scrolled with mouse wheel and allow float values.
    """

    sliderMoved = Signal(float)  # redefine slider move to emit float

    def __init__(self, decimals=0, *args, **kwargs):
        """_summary_

        :param decimals: _description_, defaults to 0
        :type decimals: int, optional
        """
        super().__init__(*args, **kwargs)
        self.divisor = 10**decimals

    def value(self):
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        return float(super().value()) / self.divisor

    def setMinimum(self, value):
        """_summary_

        :param value: _description_
        :type value: _type_
        :return: _description_
        :rtype: _type_
        """
        return super().setMinimum(int(value * self.divisor))

    def setMaximum(self, value):
        """_summary_

        :param value: _description_
        :type value: _type_
        :return: _description_
        :rtype: _type_
        """
        return super().setMaximum(int(value * self.divisor))

    def maximum(self):
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        return super().maximum() / self.divisor

    def minimum(self):
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        return super().minimum() / self.divisor

    def setSingleStep(self, value):
        """_summary_

        :param value: _description_
        :type value: _type_
        :return: _description_
        :rtype: _type_
        """
        return super().setSingleStep(value * self.divisor)

    def singleStep(self):
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        return float(super().singleStep()) / self.divisor

    def setValue(self, value):
        """_summary_

        :param value: _description_
        :type value: _type_
        """
        super().setValue(int(value * self.divisor))

    def wheelEvent(self, event):
        """_summary_

        :param event: _description_
        :type event: _type_
        """
        super().wheelEvent(event)
        value = self.value()
        self.sliderMoved.emit(value)
        self.sliderReleased.emit()

    def mouseMoveEvent(self, event):
        """_summary_

        :param event: _description_
        :type event: _type_
        """
        super().mouseMoveEvent(event)
        if event.buttons() == Qt.MouseButton.LeftButton:
            value = self.value()
            self.sliderMoved.emit(value)

    def mousePressEvent(self, event):
        """_summary_

        :param event: _description_
        :type event: _type_
        """
        super().mousePressEvent(event)
        value = self.value()
        self.sliderMoved.emit(value)
