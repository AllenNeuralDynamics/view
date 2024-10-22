from qtpy.QtWidgets import QTabWidget, QTabBar, QToolButton, QMenu, QWidget, QAction, QPushButton
import typing

class QAddTabWidget(QTabWidget):
    """QTabWidget that is able to delete and add tabs"""

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # create tab bar
        tab_bar = QAddTabBar()
        tab_bar.setMovable(True)
        self.setTabBar(tab_bar)

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

    def insertTab(self, index: int, widget: typing.Optional[QWidget], a2: typing.Optional[str]) -> int:
        """
        Overwrite to add removal button to tab
        :param index: index to insert tab
        :param widget: Widget to set tab as
        :param a2: tab title
        :return: index of tab
        """
        
        super().insertTab(index, widget, a2)

        tab = self.widget(index)
        tab_bar = self.tabBar()

        # add button to remove channel
        button = QPushButton('x')
        button.setMaximumWidth(20)
        button.setMaximumHeight(20)
        tab_bar.setTabButton(index, QTabBar.RightSide, button)
        button.pressed.connect(lambda: self.removeTab(self.indexOf(tab)))

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
