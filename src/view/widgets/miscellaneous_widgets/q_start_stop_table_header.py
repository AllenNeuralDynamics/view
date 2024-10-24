from qtpy.QtWidgets import QTableWidgetItem, QHeaderView, QMenu, QAction, QStyle
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QMouseEvent


class QStartStopTableHeader(QHeaderView):
    """QTableWidgetItem to be used to select certain tiles to start at"""

    sectionRightClicked = Signal(QMouseEvent)
    startChanged = Signal(int)
    stopChanged = Signal(int)

    def __init__(self, parent):
        super().__init__(Qt.Vertical, parent)

        self.start = None
        self.stop = None
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sectionRightClicked.connect(self.menu_popup)

    def mousePressEvent(self, event, **kwargs):
        """Detect click event and set correct setting
        :param **kwargs:
        """
        super().mousePressEvent(event, **kwargs)

        if event.button() == Qt.RightButton:
            self.sectionRightClicked.emit(event)

    def menu_popup(self, event: QMouseEvent):
        """
        Function to set tile start or stop
        :param event: mousePressEvent of click
        :return:
        """

        index = self.logicalIndexAt(event.pos())

        start_act = QAction("Set Start", self)
        start_act.triggered.connect(lambda trigger: self.set_start(index))

        stop_act = QAction("Set Stop", self)
        stop_act.triggered.connect(lambda trigger: self.set_stop(index))

        clear_act = QAction("Clear", self)
        clear_act.triggered.connect(lambda trigger: self.clear(index))

        menu = QMenu(self)
        if self.stop is None or (self.stop is not None and self.stop > index):
            menu.addAction(start_act)
        if self.start is None or (self.start is not None and self.start < index):
            menu.addAction(stop_act)
        if index in [self.start, self.stop]:
            menu.addAction(clear_act)
        menu.popup(self.mapToGlobal(event.pos()))

    def set_start(self, index: int):
        """
        Set start tile
        :param index: index to set to start at
        :return:
        """

        if self.start is not None:
            self.clear(self.start)

        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)
        item = QTableWidgetItem()
        item.setIcon(icon)
        self.parent().setVerticalHeaderItem(index, item)
        self.start = index

        self.startChanged.emit(index)

    def set_stop(self, index: int):
        """
        Set stop tile
        :param index: index to set to stop at
        :return:
        """

        if self.stop is not None:
            self.clear(self.stop)

        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
        item = QTableWidgetItem()
        item.setIcon(icon)
        self.parent().setVerticalHeaderItem(index, item)
        self.stop = index

        self.stopChanged.emit(index)

    def clear(self, index: int):
        """
        Clear index of start or stop
        :param index:
        :return:
        """


        if index == self.stop:
            self.stop = None
        elif index == self.start:
            self.start = None

        item = QTableWidgetItem()
        item.setText(str(index+1))
        self.parent().setVerticalHeaderItem(index, item)
