from qtpy.QtWidgets import QTabWidget, QTabBar, QWidget, QPushButton, \
    QMenu, QToolButton, QAction, QTableWidget, QTableWidgetItem, QComboBox, QSpinBox
from view.widgets.miscellaneous_widgets.q_item_delegates import QSpinItemDelegate, QTextItemDelegate, QComboItemDelegate
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit
from view.widgets.base_device_widget import label_maker
import numpy as np
from qtpy.QtCore import Signal, Qt
from inflection import singularize
from math import isnan

class ChannelPlanWidget(QTabWidget):
    """Widget defining parameters per tile per channel """

    channelAdded = Signal([str])

    def __init__(self, instrument_view, channels: dict, settings: dict, unit: str = 'um'):
        """
        :param channels: dictionary defining channels for instrument
        :param settings: allowed setting for devices
        """

        super().__init__()

        self.possible_channels = channels
        self.channels = []
        self.settings = settings
        self.unit = unit

        self.steps = {}  # dictionary of number of steps for each tile in each channel
        self.step_size = {}  # dictionary of step size for each tile in each channel
        self.prefix = {}  # dictionary of prefix for each tile in each channel

        self._tile_volumes = np.zeros([0, 0], dtype=float)  # array of tile starts and ends. Constant for every channel

        self.tab_bar = ChannelPlanTabBar()
        self.tab_bar.setMovable(True)
        self.setTabBar(self.tab_bar)

        self.channel_order = QComboBox()
        self.channel_order.addItems(['per Tile', 'per Volume', ])
        self.setCornerWidget(self.channel_order)
        self.mode = self.channel_order.currentText()
        self.channel_order.currentTextChanged.connect(lambda value: setattr(self, 'mode', value))

        # initialize column dictionaries and column delgates
        self.initialize_tables(instrument_view)

        # add tab with button to add channels
        self.add_tool = QToolButton()
        self.add_tool.setText('+')
        menu = QMenu()
        for channel in self.possible_channels:
            action = QAction(str(channel), self)
            action.triggered.connect(lambda clicked, ch=channel: self.add_channel(ch))
            menu.addAction(action)
        self.add_tool.setMenu(menu)
        self.add_tool.setPopupMode(QToolButton.InstantPopup)
        self.insertTab(0, QWidget(), '')  # insert dummy qwidget
        self.tab_bar.setTabButton(0, QTabBar.RightSide, self.add_tool)

        # reorder channels if tabbar moved
        self.tab_bar.tabMoved.connect(lambda:
                                      setattr(self, 'channels', [self.tabText(ch) for ch in range(self.count() - 1)]))
        self._apply_to_all = True  # external flag to dictate behaviour of added tab

    def initialize_tables(self, instrument_view):
        """Initialize table for all channels with proper columns and delegates"""

        # TODO: Checks here if setting or device isn't part of the instrument? Or go in instrument validation?

        for channel in self.possible_channels:

            setattr(self, f'{channel}_table', QTableWidget())
            table = getattr(self, f'{channel}_table')
            table.cellChanged.connect(self.cell_edited)

            columns = ['step size [um]', 'steps', 'prefix']
            delegate_type = [QSpinItemDelegate(minimum=0), QSpinItemDelegate(minimum=0, step=1), QTextItemDelegate()]
            for device_type, device_names in self.possible_channels[channel].items():
                for device_name in device_names:
                    device_widget = getattr(instrument_view, f'{singularize(device_type)}_widgets')[device_name]
                    device_object = getattr(instrument_view.instrument, device_type)[device_name]
                    for setting in self.settings.get(device_type, []):
                        column_name = label_maker(f'{device_name}_{setting}')
                        setattr(self, column_name, {})
                        columns.append(column_name)
                        # select delegate to use based on type
                        with getattr(instrument_view, f'{singularize(device_type)}_locks')[device_name]:  # lock device
                            # value = getattr(device_object, setting)
                            descriptor = getattr(type(device_object), setting)
                        if type(getattr(device_widget, f'{setting}_widget')) in [QScrollableLineEdit, QSpinBox]:
                            minimum = getattr(descriptor, 'minimum', float('-inf'))
                            maximum = getattr(descriptor, 'maximum', float('inf'))
                            step = getattr(descriptor, 'step', .001)
                            delegate_type.append(QSpinItemDelegate(minimum=minimum, maximum=maximum, step=step))
                        elif type(getattr(device_widget, f'{setting}_widget')) == QComboBox:
                            widget = getattr(device_widget, f'{setting}_widget')
                            items = [widget.itemText(i) for i in range(widget.count())]
                            delegate_type.append(QComboItemDelegate(items=items))
                        else:  # TODO: How to handle dictionary values
                            delegate_type.append(QTextItemDelegate())
            columns.append('row, column')

            for i, delegate in enumerate(delegate_type):
                # table does not take ownership of the delegates, so they are removed from memory as they
                # are local variables causing a Segmentation fault. Need to be attributes
                setattr(self, f'{columns[i]}_{channel}_delegate', delegate)
                table.setItemDelegateForColumn(i, delegate)
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.resizeColumnsToContents()
            table.setColumnHidden(len(columns) - 1, True)  # hide row, column since it will only be used internally

            table.verticalHeader().hide()

    @property
    def apply_to_all(self):
        return self._apply_to_all

    @apply_to_all.setter
    def apply_to_all(self, value):
        """When apply all is toggled, update existing channels"""

        if self._apply_to_all != value:
            for channel in self.channels:
                table = getattr(self, f'{channel}_table')

                for i in range(1, table.rowCount()):  # skip first row
                    for j in range(table.columnCount() - 1):  # skip last column
                        item = table.item(i, j)
                        self.enable_item(item, not value)
                        if value:
                            item.setData(Qt.EditRole, table.item(0, j).data(Qt.EditRole))
        self._apply_to_all = value

    @property
    def tile_volumes(self):
        return self._tile_volumes

    @tile_volumes.setter
    def tile_volumes(self, value: np.array):
        """When tile dims is updated, update size of channel arrays"""

        for channel in self.channels:
            table = getattr(self, f'{channel}_table')
            for i in range(table.columnCount() - 1):  # skip row, column
                header = table.horizontalHeaderItem(i).text()
                getattr(self, header)[channel] = np.resize(getattr(self, header)[channel], value.shape)
            self.step_size[channel] = np.resize(self.step_size[channel], value.shape)
            self.steps[channel] = np.resize(self.steps[channel], value.shape)
            self.prefix[channel] = np.resize(self.prefix[channel], value.shape)

        self._tile_volumes = value

    def enable_item(self, item, enable):
        """Change flags for enabling/disabling items in channel_plan table"""

        flags = QTableWidgetItem().flags()
        if not enable:
            flags &= ~Qt.ItemIsEditable
        else:
            flags |= Qt.ItemIsEditable
            flags |= Qt.ItemIsEnabled
            flags |= Qt.ItemIsSelectable
        item.setFlags(flags)

    def add_channel(self, channel):
        """Add channel to acquisition"""

        table = getattr(self, f'{channel}_table')
        table.cellChanged.connect(self.cell_edited)

        for device_type, devices in self.possible_channels[channel].items():
            for device in devices:
                for setting in self.settings.get(device_type, []):
                    column_name = label_maker(f'{device}_{setting}')
                    delegate = getattr(self, f'{column_name}_{channel}_delegate')
                    if type(delegate) == QSpinItemDelegate:
                        getattr(self, f'{column_name}')[channel] = np.zeros(self._tile_volumes.shape)
                    elif type(delegate) == QComboItemDelegate:
                        getattr(self, f'{column_name}')[channel] = np.empty(self._tile_volumes.shape)
                        getattr(self, f'{column_name}')[channel][:, :] = delegate.items[0]
                    else:
                        getattr(self, f'{column_name}')[channel] = np.empty(self._tile_volumes.shape)

        self.steps[channel] = np.zeros(self._tile_volumes.shape, dtype=int)
        self.step_size[channel] = np.zeros(self._tile_volumes.shape, dtype=float)
        self.prefix[channel] = np.zeros(self._tile_volumes.shape, dtype=str)

        self.insertTab(0, table, channel)
        self.setCurrentIndex(0)

        # add button to remove channel
        button = QPushButton('x')
        button.setMaximumWidth(20)
        button.setMaximumHeight(20)
        button.pressed.connect(lambda: self.remove_channel(channel))
        self.tab_bar.setTabButton(0, QTabBar.RightSide, button)

        # remove channel from add_tool menu
        menu = self.add_tool.menu()
        for action in menu.actions():
            if action.text() == channel:
                menu.removeAction(action)
        self.add_tool.setMenu(menu)

        self.channels = [channel] + self.channels

        self.channelAdded.emit(channel)

    def add_channel_rows(self, channel, order: list):
        """Add rows to channel table in specific order of tiles
        :param order: list of tile order e.g. [[0,0], [0,1]]"""

        table = getattr(self, f'{channel}_table')
        table.blockSignals(True)
        table.clearContents()
        table.setRowCount(0)

        arrays = [self.steps[channel]]
        delegates = [getattr(self, f'step size [um]_{channel}_delegate')]
        # iterate through columns to find relevant arrays to update
        for i in range(1, table.columnCount() - 1):  # skip row, column
            arrays.append(getattr(self, table.horizontalHeaderItem(i).text())[channel])
            delegates.append(getattr(self, f'{table.horizontalHeaderItem(i).text()}_{channel}_delegate'))

        for tile in order:
            table_row = table.rowCount()
            table.insertRow(table_row)
            item = QTableWidgetItem(str(tile))
            table.setItem(table_row, table.columnCount() - 1, item)
            for column, array in enumerate(arrays):
                item = QTableWidgetItem()
                if type(delegates[column]) == QSpinItemDelegate:
                    item.setData(Qt.EditRole, float(array[*tile]))
                else:
                    item.setData(Qt.EditRole, str(array[*tile]))
                table.setItem(table_row, column, item)
                if table_row != 0:  # first row/tile always enabled
                    self.enable_item(item, not self.apply_to_all)
        table.blockSignals(False)

    def remove_channel(self, channel):
        """Remove channel from acquisition"""

        self.channels.remove(channel)

        table = getattr(self, f'{channel}_table')
        index = self.indexOf(table)

        self.removeTab(index)

        # remove key from attributes
        for i in range(table.columnCount() - 1):  # skip row, column
            header = table.horizontalHeaderItem(i).text()
            del getattr(self, header)[channel]

        # add channel back to add_tool
        menu = self.add_tool.menu()
        action = QAction(channel, self)
        action.triggered.connect(lambda clicked, ch=channel: self.add_channel(ch))
        menu.addAction(action)
        self.add_tool.setMenu(menu)

    def cell_edited(self, row, column):
        """Update table based on cell edit"""

        channel = self.tabText(self.currentIndex())
        table = getattr(self, f'{channel}_table')

        table.blockSignals(True)  # block signals so updating cells doesn't trigger cell edit again
        tile_index = [int(x) for x in table.item(row, table.columnCount() - 1).text() if x.isdigit()]

        if column in [0, 1]:
            volume = self.tile_volumes[*tile_index]
            index = tile_index if not self.apply_to_all else [slice(None), slice(None)]
            if column == 0:  # step_size changed so round to fit in volume
                steps = volume / float(table.item(row, 0).data(Qt.EditRole))
                if steps != 0 and not isnan(steps):
                    step_size = round(volume / steps, 4)
                    steps = round(steps)
                else:
                    steps = 0
                    step_size = 0
                self.steps[channel][*index] = steps
            else:  # step number changed
                step_size = volume / float(table.item(row, 1).data(Qt.EditRole))
                if step_size != 0 and not isnan(step_size):
                    steps = round(volume / step_size)
                    step_size = round(step_size, 4)
                else:
                    steps = 0
                    step_size = 0
                self.step_size[channel][*index] = step_size

            table.item(row, 0).setData(Qt.EditRole,float(step_size))
            table.item(row, 1).setData(Qt.EditRole,int(steps))

        array = getattr(self, table.horizontalHeaderItem(column).text())[channel]
        value = table.item(row, column).data(Qt.EditRole)
        if self.apply_to_all:
            array[:, :] = value
            for i in range(1, table.rowCount()):
                item_0 = table.item(0, column)
                table.item(i, column).setData(Qt.EditRole,item_0.data(Qt.EditRole))
                if column == 0:  # update steps as well
                    table.item(i, column + 1).setData(Qt.EditRole, steps)
                elif column == 1:  # update step_size as well
                    table.item(i, column - 1).setData(Qt.EditRole, step_size)
        else:
            array[*tile_index] = value

        table.blockSignals(False)


class ChannelPlanTabBar(QTabBar):
    """TabBar that will keep add channel tab at end"""

    def __init__(self):

        super(ChannelPlanTabBar, self).__init__()
        self.tabMoved.connect(self.tab_index_check)

    def tab_index_check(self, prev_index, curr_index):
        """Keep last tab as last tab"""

        if prev_index == self.count() - 1:
            self.moveTab(curr_index, prev_index)

    def mouseMoveEvent(self, ev):
        """Make last tab immovable"""
        index = self.currentIndex()
        if index == self.count() - 1:  # last tab is immovable
            return
        super().mouseMoveEvent(ev)
