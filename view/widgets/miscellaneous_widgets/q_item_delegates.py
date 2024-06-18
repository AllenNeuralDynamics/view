from qtpy.QtWidgets import QStyledItemDelegate, QTextEdit, QSpinBox, QComboBox, QDoubleSpinBox
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit

class QTextItemDelegate(QStyledItemDelegate):
    """QStyledItemDelegate acting like QTextEdit"""

    def createEditor(self, parent, options, index):
        return QTextEdit(parent)

    def setEditorData(self, editor, index):
        editor.setText(str(index.data()))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText())


class QComboItemDelegate(QStyledItemDelegate):
    """QStyledItemDelegate acting like QComboBox"""

    def __init__(self, items: list, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, options, index):
        return QComboBox(parent)

    def setEditorData(self, editor, index):
        editor.addItems(self.items)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText())


class QSpinItemDelegate(QStyledItemDelegate):
    """QStyledItemDelegate acting like QSpinBox"""

    def __init__(self, minimum=None, maximum=None, step=None, parent=None):
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.step = step if step is not None else .01

    def createEditor(self, parent, options, index):
        box = QScrollableLineEdit(parent) if type(self.step) == int else QDoubleSpinBox(parent)
        if self.minimum is not None:
            box.setMinimum(self.minimum)
        if self.maximum is not None:
            box.setMaximum(self.maximum)
        if type(box) == QDoubleSpinBox:
            box.setDecimals(5)
        box.setSingleStep(self.step)
        return box

    def setEditorData(self, editor, index):
        value = int(index.data()) if type(self.step) == int else float(index.data())
        editor.setValue(value)

    def setModelData(self, editor, model, index):
        value = int(editor.value()) if type(self.step) == int else float(editor.value())
        model.setData(index, value)
