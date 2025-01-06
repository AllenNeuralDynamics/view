from qtpy.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox, QStyledItemDelegate, QTextEdit


class QTextItemDelegate(QStyledItemDelegate):
    """
    QStyledItemDelegate acting like QTextEdit.
    """

    def createEditor(self, parent, options, index):
        """_summary_

        :param parent: _description_
        :type parent: _type_
        :param options: _description_
        :type options: _type_
        :param index: _description_
        :type index: _type_
        :return: _description_
        :rtype: _type_
        """
        return QTextEdit(parent)

    def setEditorData(self, editor, index):
        """_summary_

        :param editor: _description_
        :type editor: _type_
        :param index: _description_
        :type index: _type_
        """
        editor.setText(str(index.data()))

    def setModelData(self, editor, model, index):
        """_summary_

        :param editor: _description_
        :type editor: _type_
        :param model: _description_
        :type model: _type_
        :param index: _description_
        :type index: _type_
        """
        model.setData(index, editor.toPlainText())


class QComboItemDelegate(QStyledItemDelegate):
    """
    QStyledItemDelegate acting like QComboBox.
    """

    def __init__(self, items: list, parent=None):
        """_summary_

        :param items: _description_
        :type items: list
        :param parent: _description_, defaults to None
        :type parent: _type_, optional
        """
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, options, index):
        """_summary_

        :param parent: _description_
        :type parent: _type_
        :param options: _description_
        :type options: _type_
        :param index: _description_
        :type index: _type_
        :return: _description_
        :rtype: _type_
        """
        return QComboBox(parent)

    def setEditorData(self, editor, index):
        """_summary_

        :param editor: _description_
        :type editor: _type_
        :param index: _description_
        :type index: _type_
        """
        editor.addItems(self.items)

    def setModelData(self, editor, model, index):
        """_summary_

        :param editor: _description_
        :type editor: _type_
        :param model: _description_
        :type model: _type_
        :param index: _description_
        :type index: _type_
        """
        model.setData(index, editor.currentText())


class QSpinItemDelegate(QStyledItemDelegate):
    """
    QStyledItemDelegate acting like QSpinBox.
    """

    def __init__(self, minimum=None, maximum=None, step=None, parent=None):
        """_summary_

        :param minimum: _description_, defaults to None
        :type minimum: _type_, optional
        :param maximum: _description_, defaults to None
        :type maximum: _type_, optional
        :param step: _description_, defaults to None
        :type step: _type_, optional
        :param parent: _description_, defaults to None
        :type parent: _type_, optional
        """
        super().__init__(parent)
        self.minimum = minimum if minimum is not None else -2147483647
        self.maximum = maximum if maximum is not None else 2147483647
        self.step = step if step is not None else 0.01

    def createEditor(self, parent, options, index):
        """_summary_

        :param parent: _description_
        :type parent: _type_
        :param options: _description_
        :type options: _type_
        :param index: _description_
        :type index: _type_
        :return: _description_
        :rtype: _type_
        """
        box = QSpinBox(parent) if type(self.step) == int else QDoubleSpinBox(parent)

        box.setMinimum(self.minimum)
        box.setMaximum(self.maximum)
        if type(box) == QDoubleSpinBox:
            box.setDecimals(5)
        box.setSingleStep(self.step)
        return box

    def setEditorData(self, editor, index):
        """_summary_

        :param editor: _description_
        :type editor: _type_
        :param index: _description_
        :type index: _type_
        """
        value = int(index.data()) if type(self.step) == int else float(index.data())
        editor.setValue(value)

    def setModelData(self, editor, model, index):
        """_summary_

        :param editor: _description_
        :type editor: _type_
        :param model: _description_
        :type model: _type_
        :param index: _description_
        :type index: _type_
        """
        value = int(editor.value()) if type(self.step) == int else float(editor.value())
        model.setData(index, value)
