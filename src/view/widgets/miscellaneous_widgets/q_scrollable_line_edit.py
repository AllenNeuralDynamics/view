from qtpy.QtWidgets import QLineEdit
from qtpy.QtGui import QIntValidator, QDoubleValidator
import typing

class QScrollableLineEdit(QLineEdit):
    """Widget inheriting from QLineEdit that allows value to be scrollable"""

    def wheelEvent(self, event):
        super().wheelEvent(event)
        if self.validator() is not None and type(self.validator()) in [QIntValidator, QDoubleValidator]:
            if type(self.validator()) == QDoubleValidator:
                dec = len(self.text()[self.text().index('.') + 1:]) if '.' in self.text() else 0
                change = 10 ** (-dec) if event.angleDelta().y() > 0 else -10 ** (-dec)
                new_value = float(f"%.{dec}f" % float(float(self.text()) + change))
            else:  # QIntValidator
                new_value = int(self.text()) + 1 if event.angleDelta().y() > 0 else int(self.text()) - 1
            if self.validator().bottom() <= new_value <= self.validator().top():
                self.setText(str(new_value))
                self.editingFinished.emit()


    def value(self):
        """Get float or integer of text"""
        return float(self.text())

    def setValue(self, value):
        """Set number as text"""
        self.setText(str(value))
