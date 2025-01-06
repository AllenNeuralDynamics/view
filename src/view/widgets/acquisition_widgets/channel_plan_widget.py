import inspect
from math import isnan

import numpy as np
import pint
from inflection import singularize
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAction,
    QComboBox,
    QMenu,
    QPushButton,
    QSpinBox,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QToolButton,
    QWidget,
)

from view.widgets.base_device_widget import label_maker
from view.widgets.miscellaneous_widgets.q_item_delegates import QComboItemDelegate, QSpinItemDelegate, QTextItemDelegate
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit


class ChannelPlanWidget(QTabWidget):
    """
    Widget defining parameters per tile per channel.
    """

    channelAdded = Signal([str])
    channelChanged = Signal()

    def __init__(self, instrument_view, channels: dict, properties: dict, unit: str = "um"):
        """_summary_

        :param instrument_view: _description_
        :type instrument_view: _type_
        :param channels: _description_
        :type channels: dict
        :param properties: _description_
        :type properties: dict
        :param unit: _description_, defaults to 'um'
        :type unit: str, optional
        """
        super().__init__()

        self.possible_channels = channels
        self.channels = []
        self.properties = properties
        self.column_data_types = {"step size [um]": float, "steps": int, "prefix": str}

        # setup units for step size and step calculation
        unit_registry = pint.UnitRegistry()
        self.unit = getattr(unit_registry, unit)  # TODO: How to check if unit is in pint?
        self.micron = unit_registry.um

        self.steps = {}  # dictionary of number of steps for each tile in each channel
        self.step_size = {}  # dictionary of step size for each tile in each channel
        self.prefix = {}  # dictionary of prefix for each tile in each channel

        self._tile_volumes = np.zeros([1, 1], dtype=float)  # array of tile starts and ends. Constant for every channel

        self.tab_bar = ChannelPlanTabBar()
        self.tab_bar.setMovable(True)
        self.setTabBar(self.tab_bar)

        self.channel_order = QComboBox()
        self.channel_order.addItems(
            [
                "per Tile",
                "per Volume",
            ]
        )
        self.setCornerWidget(self.channel_order)
        self.mode = self.channel_order.currentText()
        self.channel_order.currentTextChanged.connect(lambda value: setattr(self, "mode", value))

        # initialize column dictionaries and column delgates
        self.initialize_tables(instrument_view)

        # add tab with button to add channels
        self.add_tool = QToolButton()
        self.add_tool.setText("+")
        menu = QMenu()
        for channel in self.possible_channels:
            action = QAction(str(channel), self)
            action.triggered.connect(lambda clicked, ch=channel: self.add_channel(ch))
            menu.addAction(action)
        self.add_tool.setMenu(menu)
        self.add_tool.setPopupMode(QToolButton.InstantPopup)
        self.insertTab(0, QWidget(), "")  # insert dummy qwidget
        self.tab_bar.setTabButton(0, QTabBar.RightSide, self.add_tool)

        # reorder channels if tabbar moved
        self.tab_bar.tabMoved.connect(
            lambda: setattr(self, "channels", [self.tabText(ch) for ch in range(self.count() - 1)])
        )
        self._apply_all = True  # external flag to dictate behaviour of added tab

    def initialize_tables(self, instrument_view) -> None:
        """_summary_

        :param instrument_view: _description_
        :type instrument_view: _type_
        """
        # TODO: Checks here if prop or device isn't part of the instrument? Or go in instrument validation?
        for channel in self.possible_channels:

            setattr(self, f"{channel}_table", QTableWidget())
            table = getattr(self, f"{channel}_table")
            table.cellChanged.connect(self.cell_edited)

            columns = ["step size [um]", "steps", "prefix"]
            delegates = [QSpinItemDelegate(), QSpinItemDelegate(minimum=0, step=1), QTextItemDelegate()]
            for device_type, properties in self.properties.items():
                if device_type in self.possible_channels[channel].keys():
                    for device_name in self.possible_channels[channel][device_type]:
                        device_widget = getattr(instrument_view, f"{singularize(device_type)}_widgets")[device_name]
                        device_object = getattr(instrument_view.instrument, device_type)[device_name]
                        for prop in properties:
                            # select delegate to use based on type
                            column_name = label_maker(f"{device_name}_{prop}")
                            descriptor = getattr(type(device_object), prop)
                            if not isinstance(descriptor, property) or getattr(descriptor, "fset", None) is None:
                                self.column_data_types[column_name] = None
                                continue
                            # try and correctly type properties based on setter
                            fset = getattr(descriptor, "fset")
                            input_type = list(inspect.signature(fset).parameters.values())[-1].annotation
                            self.column_data_types[column_name] = input_type if input_type != inspect._empty else None
                            setattr(self, column_name, {})
                            columns.append(column_name)
                            prop_widget = getattr(device_widget, f"{prop}_widget")
                            if type(prop_widget) in [QScrollableLineEdit, QSpinBox]:
                                minimum = getattr(descriptor, "minimum", float("-inf"))
                                maximum = getattr(descriptor, "maximum", float("inf"))
                                step = getattr(descriptor, "step", 0.1)
                                delegates.append(QSpinItemDelegate(minimum=minimum, maximum=maximum, step=step))
                                setattr(self, column_name + "_value_function", prop_widget.value)
                            elif type(getattr(device_widget, f"{prop}_widget")) == QComboBox:
                                widget = getattr(device_widget, f"{prop}_widget")
                                items = [widget.itemText(i) for i in range(widget.count())]
                                delegates.append(QComboItemDelegate(items=items))
                                setattr(self, column_name + "_value_function", prop_widget.currentText)
                            else:  # TODO: How to handle dictionary values
                                delegates.append(QTextItemDelegate())
                                setattr(self, column_name + "_value_function", prop_widget.text)
                elif dict in type(properties).__mro__:  # TODO: how to validate the GUI yaml?
                    column_name = label_maker(device_type)
                    setattr(self, column_name, {})
                    setattr(self, column_name + "_initial_value", properties.get("initial_value", None))
                    columns.append(column_name)
                    if properties["delegate"] == "spin":
                        minimum = properties.get("minimum", None)
                        maximum = properties.get("maximum", None)
                        step = properties.get("step", 0.1 if properties["type"] == "float" else 1)
                        delegates.append(QSpinItemDelegate(minimum=minimum, maximum=maximum, step=step))
                        self.column_data_types[column_name] = float if properties["type"] == "float" else int
                    elif properties["delegate"] == "combo":
                        items = properties["items"]
                        delegates.append(QComboItemDelegate(items=items))
                        type_mapping = {"int": int, "float": float, "str": str}
                        self.column_data_types[column_name] = type_mapping[properties["type"]]
                    else:
                        delegates.append(QTextItemDelegate())
                        self.column_data_types[column_name] = str

            columns.append("row, column")

            for i, delegate in enumerate(delegates):
                # table does not take ownership of the delegates, so they are removed from memory as they
                # are local variables causing a Segmentation fault. Need to be attributes
                setattr(self, f"{columns[i]}_{channel}_delegate", delegate)
                table.setItemDelegateForColumn(i, delegate)
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels(columns)
            table.resizeColumnsToContents()
            table.setColumnHidden(len(columns) - 1, True)  # hide row, column since it will only be used internally

            table.verticalHeader().hide()

    @property
    def apply_all(self) -> bool:
        """_summary_

        :return: _description_
        :rtype: bool
        """
        return self._apply_all

    @apply_all.setter
    def apply_all(self, value: bool) -> None:
        """_summary_

        :param value: _description_
        :type value: bool
        """
        if self._apply_all != value:
            for channel in self.channels:
                table = getattr(self, f"{channel}_table")

                for i in range(1, table.rowCount()):  # skip first row
                    for j in range(table.columnCount() - 1):  # skip last column
                        item = table.item(i, j)
                        self.enable_item(item, not value)
                        if value:
                            item.setData(Qt.EditRole, table.item(0, j).data(Qt.EditRole))
        self._apply_all = value

    @property
    def tile_volumes(self) -> np.ndarray:
        """_summary_

        :return: _description_
        :rtype: np.ndarray
        """
        return self._tile_volumes

    @tile_volumes.setter
    def tile_volumes(self, value: np.ndarray) -> None:
        """_summary_

        :param value: _description_
        :type value: np.ndarray
        """
        self._tile_volumes = value
        for channel in self.channels:
            table = getattr(self, f"{channel}_table")
            for i in range(table.columnCount() - 1):  # skip row, column
                header = table.horizontalHeaderItem(i).text()
                if header == "step size [um]":
                    getattr(self, "step_size")[channel] = np.resize(getattr(self, "step_size")[channel], value.shape)
                else:
                    getattr(self, header)[channel] = np.resize(getattr(self, header)[channel], value.shape)
            self.step_size[channel] = np.resize(self.step_size[channel], value.shape)
            self.steps[channel] = np.resize(self.steps[channel], value.shape)
            self.prefix[channel] = np.resize(self.prefix[channel], value.shape)
            self._tile_volumes = value
            for row in range(table.rowCount()):
                tile_index = [int(x) for x in table.item(row, table.columnCount() - 1).text() if x.isdigit()]
                if tile_index[0] < value.shape[0] and tile_index[1] < value.shape[1]:
                    self.update_steps(tile_index, row, channel)

    def enable_item(self, item: QTableWidgetItem, enable: bool) -> None:
        """_summary_

        :param item: _description_
        :type item: QTableWidgetItem
        :param enable: _description_
        :type enable: bool
        """
        flags = QTableWidgetItem().flags()
        if not enable:
            flags &= ~Qt.ItemIsEditable
        else:
            flags |= Qt.ItemIsEditable
            flags |= Qt.ItemIsEnabled
            flags |= Qt.ItemIsSelectable
        item.setFlags(flags)

    def add_channel(self, channel: str) -> None:
        """_summary_

        :param channel: _description_
        :type channel: str
        """
        table = getattr(self, f"{channel}_table")

        for i in range(3, table.columnCount() - 1):  # skip steps, step_size, prefix, row/col
            column_name = table.horizontalHeaderItem(i).text()
            delegate = getattr(self, f"{column_name}_{channel}_delegate", None)
            if delegate is not None:  # Skip if prop did not have setter
                array = getattr(self, f"{column_name}")
                if type(delegate) == QSpinItemDelegate:
                    array[channel] = np.zeros(self._tile_volumes.shape)
                elif type(delegate) == QComboItemDelegate:
                    array[channel] = np.empty(self._tile_volumes.shape, dtype="U100")
                else:
                    array[channel] = np.empty(self._tile_volumes.shape, dtype="U100")

                if getattr(self, column_name + "_initial_value", None) is not None:  # get initial value
                    array[channel][:, :] = getattr(self, column_name + "_initial_value")
                elif getattr(self, column_name + "_value_function", None) is not None:
                    # call value function to get current set point
                    array[channel][:, :] = getattr(self, column_name + "_value_function")()

        self.steps[channel] = np.zeros(self._tile_volumes.shape, dtype=int)
        self.step_size[channel] = np.zeros(self._tile_volumes.shape, dtype=float)
        self.prefix[channel] = np.zeros(self._tile_volumes.shape, dtype="U100")

        self.insertTab(0, table, channel)
        self.setCurrentIndex(0)

        # add button to remove channel
        button = QPushButton("x")
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

    def add_channel_rows(self, channel: str, order: list) -> None:
        """_summary_

        :param channel: _description_
        :type channel: str
        :param order: _description_
        :type order: list
        """
        table = getattr(self, f"{channel}_table")
        table.blockSignals(True)
        table.clearContents()
        table.setRowCount(0)

        arrays = [self.step_size[channel]]
        delegates = [getattr(self, f"step size [um]_{channel}_delegate")]
        # iterate through columns to find relevant arrays to update
        for i in range(1, table.columnCount() - 1):  # skip row, column
            arrays.append(getattr(self, table.horizontalHeaderItem(i).text())[channel])
            delegates.append(getattr(self, f"{table.horizontalHeaderItem(i).text()}_{channel}_delegate"))
        for tile in order:
            table_row = table.rowCount()
            table.insertRow(table_row)
            item = QTableWidgetItem(str(tile))
            table.setItem(table_row, table.columnCount() - 1, item)
            for column, array in enumerate(arrays):
                item = QTableWidgetItem()
                item.setTextAlignment(Qt.AlignHCenter)  # change the alignment
                if type(delegates[column]) == QSpinItemDelegate:
                    item.setData(Qt.EditRole, float(array[*tile]))
                else:
                    item.setData(Qt.EditRole, str(array[*tile]))
                table.setItem(table_row, column, item)
                if table_row != 0:  # first row/tile always enabled
                    self.enable_item(item, not self.apply_all)
        table.blockSignals(False)

    def remove_channel(self, channel: str) -> None:
        """_summary_

        :param channel: _description_
        :type channel: str
        """
        self.channels.remove(channel)

        table = getattr(self, f"{channel}_table")
        index = self.indexOf(table)

        self.removeTab(index)

        # remove key from attributes
        for i in range(table.columnCount() - 1):  # skip row, column
            header = table.horizontalHeaderItem(i).text()
            if header == "step size [um]":
                del getattr(self, "step_size")[channel]
            else:
                del getattr(self, header)[channel]

        # add channel back to add_tool
        menu = self.add_tool.menu()
        action = QAction(channel, self)
        action.triggered.connect(lambda clicked, ch=channel: self.add_channel(ch))
        menu.addAction(action)
        self.add_tool.setMenu(menu)

        self.channelChanged.emit()

    def cell_edited(self, row: int, column: int, channel: str = None) -> None:
        """_summary_

        :param row: _description_
        :type row: int
        :param column: _description_
        :type column: int
        :param channel: _description_, defaults to None
        :type channel: str, optional
        """
        channel = self.tabText(self.currentIndex()) if channel is None else channel
        table = getattr(self, f"{channel}_table")

        table.blockSignals(True)  # block signals so updating cells doesn't trigger cell edit again
        tile_index = [int(x) for x in table.item(row, table.columnCount() - 1).text() if x.isdigit()]

        if column in [0, 1]:
            step_size, steps = (
                self.update_steps(tile_index, row, channel)
                if column == 0
                else self.update_step_size(tile_index, row, channel)
            )
            table.item(row, 0).setData(Qt.EditRole, step_size)
            table.item(row, 1).setData(Qt.EditRole, steps)

        # FIXME: I think this is would be considered unexpected behavior
        array = getattr(self, table.horizontalHeaderItem(column).text(), self.step_size)[channel]
        value = table.item(row, column).data(Qt.EditRole)
        if self.apply_all:
            array[:, :] = value
            for i in range(1, table.rowCount()):
                item_0 = table.item(0, column)
                table.item(i, column).setData(Qt.EditRole, item_0.data(Qt.EditRole))
                if column == 0:  # update steps as well
                    table.item(i, column + 1).setData(Qt.EditRole, int(steps))
                elif column == 1:  # update step_size as well
                    table.item(i, column - 1).setData(Qt.EditRole, float(step_size))
        else:
            array[*tile_index] = value
        table.blockSignals(False)
        self.channelChanged.emit()

    def update_steps(self, tile_index: list[int], row: int, channel: str) -> list[float, int]:
        """_summary_

        :param tile_index: _description_
        :type tile_index: list[int]
        :param row: _description_
        :type row: int
        :param channel: _description_
        :type channel: str
        :return: _description_
        :rtype: list[float, int]
        """
        volume_um = (self.tile_volumes[*tile_index] * self.unit).to(self.micron)
        index = tile_index if not self.apply_all else [slice(None), slice(None)]
        steps = volume_um / (float(getattr(self, f"{channel}_table").item(row, 0).data(Qt.EditRole)) * self.micron)
        if steps != 0 and not isnan(steps) and steps not in [float("inf"), float("-inf")]:
            step_size = float(
                round(volume_um / steps, 4) / self.micron
            )  # make dimensionless again for simplicity in code
            steps = int(round(steps))
        else:
            steps = 0
            step_size = 0
        self.steps[channel][*index] = steps

        return step_size, steps

    def update_step_size(self, tile_index: list[int], row: int, channel: str) -> list[float, int]:
        """_summary_

        :param tile_index: _description_
        :type tile_index: list[int]
        :param row: _description_
        :type row: int
        :param channel: _description_
        :type channel: str
        :return: _description_
        :rtype: list[float, int]
        """
        volume_um = (self.tile_volumes[*tile_index] * self.unit).to(self.micron)
        index = tile_index if not self.apply_all else [slice(None), slice(None)]
        # make dimensionless again for simplicity in code
        step_size = (volume_um / float(getattr(self, f"{channel}_table").item(row, 1).data(Qt.EditRole))) / self.micron
        if step_size != 0 and not isnan(step_size) and step_size not in [float("inf"), float("-inf")]:
            steps = int(round(volume_um / (step_size * self.micron)))
            step_size = float(round(step_size, 4))
        else:
            steps = 0
            step_size = 0
        self.step_size[channel][*index] = step_size
        return step_size, steps


class ChannelPlanTabBar(QTabBar):
    """
    Tab bar that will keep add channel tab at end.
    """

    def __init__(self):
        """_summary_"""
        super(ChannelPlanTabBar, self).__init__()
        self.tabMoved.connect(self.tab_index_check)

    def tab_index_check(self, prev_index: int, curr_index: int) -> None:
        """_summary_

        :param prev_index: _description_
        :type prev_index: int
        :param curr_index: _description_
        :type curr_index: int
        """
        if prev_index == self.count() - 1:
            self.moveTab(curr_index, prev_index)

    def mouseMoveEvent(self, ev) -> None:
        """_summary_

        :param ev: _description_
        :type ev: _type_
        """
        index = self.currentIndex()
        if index == self.count() - 1:  # last tab is immovable
            return
        super().mouseMoveEvent(ev)
