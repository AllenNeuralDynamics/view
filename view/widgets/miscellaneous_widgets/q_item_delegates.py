from qtpy.QtWidgets import QStyledItemDelegate, QTextEdit, QSpinBox, QComboBox, QDoubleSpinBox


class QTextItemDelegate(QStyledItemDelegate):
    """QStyledItemDelegate acting like QTextEdit"""

    def createEditor(self, parent, options, index):
        return QTextEdit(parent)

    def setEditorData(self, editor, index):
        editor.setText(index.data())

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

    def __init__(self, minimum=float('-inf'), maximum=float('inf'), step=.0001, parent=None):
        super().__init__(parent)
        self.minimum = minimum
        self.maximum = maximum
        self.step = step

    def createEditor(self, parent, options, index):
        box = QSpinBox(parent) if type(self.step) == int else QDoubleSpinBox(parent)
        box.setRange(self.minimum, self.maximum)
        box.setSingleStep(self.step)
        return box

    def setEditorData(self, editor, index):
        editor.setValue(int(index.data()))

    def setModelData(self, editor, model, index):
        model.setData(index, editor.value())
