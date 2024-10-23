from qtpy.QtWidgets import QTabWidget, QTabBar, QToolButton, QMenu, QWidget, QAction, QMessageBox
from qtpy.QtCore import Signal

class QAddTabWidget(QTabWidget):
    """QTabWidget that is able to delete and add tabs"""

    tabClosed = Signal(int)

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.setTabsClosable(True)

        # create tab bar
        tab_bar = QAddTabBar()
        tab_bar.setMovable(True)
        self.setTabBar(tab_bar)
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self.removeTab)  # if close button clicked, remove tab

        # add tab with button to add channels
        self.add_tool = QToolButton()
        self.add_tool.setText('+')
        self._menu = QMenu()
        self.add_tool.setMenu(self._menu)

        action = QAction('add tab', self)
        action.triggered.connect(lambda clicked: self.insertTab(0, QWidget(), ''))
        self._menu.addAction(action)
        self.add_tool.setPopupMode(QToolButton.InstantPopup)
        self.insertTab(0, QWidget(), '')  # insert dummy qwidget
        tab_bar.setTabButton(0, QTabBar.RightSide, self.add_tool)

    def removeTab(self, index: int) -> False or None:
        """
        Overwrited to ask user if they want to close tab
        :param index: index to close
        :return: false if tab was not removed
        """

        tab_text = self.tabText(index)

        msg = QMessageBox()
        msg.setText(f'Would you like to remove the {tab_text} tab')
        msg.setWindowTitle(f'Remove {tab_text} Tab?')
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        remove = msg.exec_()
        if remove == QMessageBox.StandardButton.Yes:
            super().removeTab(index)
            self.tabClosed.emit(index)
        else:
            return False

    def setMenu(self, menu: QMenu) -> None:
        """
        Set menu on add_tool
        :param menu: QMenu to set
        """

        self._menu = menu
        self.add_tool.setMenu(self._menu)

    def menu(self) -> QMenu:
        """
        Returns menu being used in add_tool
        :return: menu
        """
        return self._menu


class QAddTabBar(QTabBar):

    """TODO: Fill in docstring"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.tabMoved.connect(self.tab_index_check)

    def tab_index_check(self, prev_index: int, curr_index: int) -> None:
        """
        Keep last tab as last tab
        :param prev_index: previous index of tab
        :param curr_index: index tab was moved to
        """

        if prev_index == self.count() - 1:
            self.moveTab(curr_index, prev_index)

    def mouseMoveEvent(self, ev) -> None:
        """
        Make last tab immovable
        :param ev: qmouseevent that triggered call
        :return:
        """
        index = self.currentIndex()
        if index == self.count() - 1:  # last tab is immovable
            return
        super().mouseMoveEvent(ev)
