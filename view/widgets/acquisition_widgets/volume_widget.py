from qtpy.QtWidgets import QWidget, QCheckBox, QHBoxLayout, QLabel, QButtonGroup, QRadioButton, \
    QGridLayout, QTableWidgetItem, QTableWidget, QSplitter, QFrame, QStyle, QPushButton, QVBoxLayout
from view.widgets.miscellaneous_widgets.q_item_delegates import QSpinItemDelegate
from view.widgets.acquisition_widgets.scan_plan_widget import ScanPlanWidget
from view.widgets.acquisition_widgets.volume_model import VolumeModel
from view.widgets.acquisition_widgets.tile_plan_widget import TilePlanWidget
from view.widgets.acquisition_widgets.channel_plan_widget import ChannelPlanWidget
from view.widgets.base_device_widget import create_widget
from qtpy.QtCore import Qt
import numpy as np
import useq
from view.widgets.base_device_widget import label_maker
import inspect

class VolumeWidget(QWidget):
    """Widget to combine scanning, tiling, channel, and model together to ease acquisition setup"""

    def __init__(self,
                 instrument_view,
                 channels: dict,
                 settings: dict,
                 limits=[[float('-inf'), float('inf')], [float('-inf'), float('inf')], [float('-inf'), float('inf')]],
                 coordinate_plane: list[str] = ['x', 'y', 'z'],
                 fov_dimensions: list[float] = [1.0, 1.0, 0],
                 fov_position: list[float] = [0.0, 0.0, 0.0],
                 view_color: str = 'yellow',
                 unit: str = 'um',
                 ):
        """
        :param channels: dictionary defining channels for instrument
        :param settings: allowed setting for devices
        :param limits: list of limits ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
        :param coordinate_plane: list describing instrument coordinate plane ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
        :param fov_dimensions: list of fov_dims which correspond to tiling dimensions
        :param fov_position: list describing fov pos ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
        :param view_color: color of fov in volume model
        :param unit: unit ALL values will be in
        """
        super().__init__()

        self.instrument_view = instrument_view
        self.coordinate_plane = [x.replace('-', '') for x in coordinate_plane]
        self.unit = unit
        self.layout = QGridLayout()

        # create model and add extra checkboxes/inputs/buttons to customize volume model
        self.volume_model = VolumeModel(coordinate_plane, fov_dimensions, fov_position, view_color)
        self.fovMoved = self.volume_model.fovMoved  # expose for ease of access

        checkboxes = QHBoxLayout()
        self.path_show = QCheckBox('Show Path')
        self.path_show.setChecked(True)
        self.path_show.toggled.connect(self.volume_model.toggle_path_visibility)
        checkboxes.addWidget(self.path_show)

        checkboxes.addWidget(QLabel('Plane View: '))
        view_plane = QButtonGroup(self)
        for view in [f'({self.coordinate_plane[0]}, {self.coordinate_plane[2]})',
                     f'({self.coordinate_plane[2]}, {self.coordinate_plane[1]})',
                     f'({self.coordinate_plane[0]}, {self.coordinate_plane[1]})']:
            button = QRadioButton(view)
            button.clicked.connect(lambda clicked, b=button: self.view_plane_change(b))
            view_plane.addButton(button)
            button.setChecked(True)
            checkboxes.addWidget(button)
        extended_model = create_widget('V', self.volume_model, checkboxes)

        # create tile plan widgets
        self.tile_plan_widget = TilePlanWidget(limits, fov_dimensions, fov_position, self.coordinate_plane, unit)
        self.fovStop = self.tile_plan_widget.fovStop  # expose for ease of access
        self.tile_starts = self.tile_plan_widget.grid_position_widgets  # expose for ease of access
        self.anchor_widgets = self.tile_plan_widget.anchor_widgets  # expose for ease of access

        # create scan widgets
        self.scan_plan_widget = ScanPlanWidget(limits[2], unit)

        # create widget containing volume model, scan plan, and tile plan
        top_widget = QWidget()
        layout = QGridLayout()
        layout.addWidget(self.tile_plan_widget, 0, 0)
        layout.addWidget(extended_model, 0, 2, 3, 2)
        layout.addWidget(self.scan_plan_widget, 1, 0)
        layout.addWidget(self.scan_plan_widget.group_box, 2, 0)
        top_widget.setLayout(layout)

        # create splitter for model and table
        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(20)
        splitter.addWidget(top_widget)

        # create channel plan widget
        self.channel_plan = ChannelPlanWidget(instrument_view, channels, settings, unit)
        self.channel_plan.channelAdded.connect(self.channel_added)
        self.channel_plan.apply_to_all = True

        # setup table
        self.columns = ['row, column', *[f'{x} [{unit}]' for x in self.coordinate_plane],
                        f'{self.coordinate_plane[2]} max [{unit}]']
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.resizeColumnsToContents()
        # add spinbox validator for columns

        for i in range(1, self.table.columnCount()):  # skip first column
            column_name = self.table.horizontalHeaderItem(i).text()
            delegate = QSpinItemDelegate()
            # table does not take ownership of the delegates, so they are removed from memory as they
            # are local variables causing a Segmentation fault. Need to be attributes
            setattr(self, f'table_column_{column_name}_delegate', delegate)
            self.table.setItemDelegateForColumn(i, delegate)

        self.table.itemChanged.connect(self.table_changed)
        self.table.currentCellChanged.connect(self.toggle_z_show)

        # add table and channel plan to layout
        widget = QWidget()  # dummy widget to move table down in layout
        widget.setMinimumHeight(25)
        extended_table = create_widget('V', widget, self.table)
        table = QSplitter(Qt.Horizontal)
        table.addWidget(extended_table)
        table.addWidget(self.channel_plan)
        table.setHandleWidth(20)
        splitter.addWidget(table)

        # format table handle. Must do after all widgets are added
        handle = table.handle(1)
        layout = QHBoxLayout(handle)
        line = QFrame(handle)
        line.setStyleSheet('QFrame {border: 1px dotted grey;}')
        line.setFixedHeight(50)
        line.setFrameShape(QFrame.VLine)
        layout.addWidget(line)

        # format splitter handle. Must do after all widgets are added
        handle = splitter.handle(1)
        layout = QHBoxLayout(handle)
        line = QFrame(handle)
        line.setStyleSheet('QFrame {border: 1px dotted grey;}')
        line.setFixedWidth(50)
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)

        self.layout.addWidget(splitter, 0, 0, 1, 3)

        # hook up tile_plan_widget signals for scan_plan_constructions, volume_model path, and tile start
        self.tile_plan_widget.valueChanged.connect(self.tile_plan_changed)
        self.tile_starts[2].disconnect()  # disconnect to only trigger update graph once
        self.tile_starts[2].valueChanged.connect(lambda value: self.scan_plan_widget.z_plan_widgets[0, 0].start.setValue(value))
        self.anchor_widgets[2].toggled.connect(lambda checked: self.disable_scan_start_widgets(not checked))
        self.disable_scan_start_widgets(True)

        # hook up scan_plan_widget signals to update grid and channel plan when tiles are changed
        self.scan_plan_widget.scanChanged.connect(self.update_model)
        self.scan_plan_widget.apply_all.toggled.connect(self.toggle_apply_all)
        self.scan_plan_widget.tileAdded.connect(self.tile_added)

        self.limits = limits
        self.fov_dimensions = fov_dimensions[:2] + [0]  # add 0 if not already included
        self.fov_position = fov_position

        # initialize first tile and add to layout
        self.scan_plan_widget.scan_plan_construction(self.tile_plan_widget.value())
        self.scan_plan_widget.z_plan_widgets[0, 0].start.valueChanged.connect(self.update_scan_start)

        self.setLayout(self.layout)
        self.show()

    @property
    def fov_position(self):
        return self._fov_position

    @fov_position.setter
    def fov_position(self, value):
        """Update all relevant widgets with new fov_position value"""
        self._fov_position = value
        # update tile plan widget
        self.tile_plan_widget.fov_position = value
        # update scan plan
        tile_anchor = self.tile_plan_widget.anchor_widgets[2]
        if not tile_anchor.isChecked() and tile_anchor.isEnabled():
            self.scan_plan_widget.z_plan_widgets[0, 0].start.setValue(value[2])
        # update model
        self.volume_model.fov_position = value

    @property
    def fov_dimensions(self):
        return self._fov_dimensions

    @fov_dimensions.setter
    def fov_dimensions(self, value):
        """Update all relevant widgets with new fov_position value"""
        self._fov_dimensions = value

        # update tile plan widget
        self.tile_plan_widget.fov_dimensions = value
        # update volume model
        self.volume_model.fov_dimensions = value

    def tile_plan_changed(self, value: useq.GridFromEdges | useq.GridRowsColumns | useq.GridWidthHeight):
        """When tile plan has been changed, trigger scan plan construction and update volume model path
        :param value: latest tile plan value"""

        self.scan_plan_widget.scan_plan_construction(value)
        self.volume_model.set_path_pos([self.volume_model.grid_coords[t.row][t.col] for t in value])

        # update scanning coords of table
        for tile in value:
            table_row = self.table.findItems(str([tile.row, tile.col]), Qt.MatchExactly)[0].row()
            scan_dim_0 = self.table.item(table_row, 1)
            scan_dim_1 = self.table.item(table_row, 2)
            self.undercover_update_item(float(self.tile_plan_widget.tile_positions[tile.row][tile.col][0]), scan_dim_0)
            self.undercover_update_item(float(self.tile_plan_widget.tile_positions[tile.row][tile.col][1]), scan_dim_1)

    def update_model(self):
        """When scan changes, update model"""

        # When scan changes, update model
        setattr(self.volume_model, '_scan_volumes', self.scan_plan_widget.scan_volumes)
        setattr(self.volume_model, '_tile_visibility', self.scan_plan_widget.tile_visibility)
        setattr(self.volume_model, 'grid_coords', np.dstack((self.tile_plan_widget.tile_positions,
                                                             self.scan_plan_widget.scan_starts)))

        # update table
        table_order = [[int(x) for x in self.table.item(i, 0).text() if x.isdigit()] for i in
                       range(self.table.rowCount())]
        scan_order = [[t.row, t.col] for t in self.tile_plan_widget.value()]
        if table_order != scan_order and len(scan_order) != 0:
            # clear table and add back tiles in the correct order if
            self.table.clearContents()
            self.table.setRowCount(0)
            for tile in self.tile_plan_widget.value():
                self.add_tile_to_table(tile.row, tile.col)

        # update channel plan
        self.channel_plan.tile_volumes = self.scan_plan_widget.scan_volumes
        for tab_index in range(self.channel_plan.count() - 1):  # skip add tab
            channel = self.channel_plan.tabText(tab_index)
            self.channel_plan.add_channel_rows(channel, scan_order)

        if not self.anchor_widgets[2].isChecked():  # disable start widget for any new widgets
            self.disable_scan_start_widgets(True)
        self.table.resizeColumnsToContents()

        # if mode changed from bounds, make sure tile anchor is disabled if apply all is checked
        if self.tile_plan_widget._mode.value != 'bounds':
            self.anchor_widgets[2].setDisabled(not self.scan_plan_widget.apply_all.isChecked())

    def channel_added(self, channel):
        """Update new channel with tiles"""

        scan_order = [[t.row, t.col] for t in self.tile_plan_widget.value()]
        self.channel_plan.add_channel_rows(channel, scan_order)

    def add_tile_to_table(self, row, column):
        """Add tile to table with relevant info"""

        self.table.blockSignals(True)
        z = self.scan_plan_widget.z_plan_widgets[row, column]
        kwargs = {'row, column': [row, column],
                  f'{self.coordinate_plane[0]} [{self.unit}]': self.tile_plan_widget.tile_positions[row][column][0],
                  f'{self.coordinate_plane[1]} [{self.unit}]': self.tile_plan_widget.tile_positions[row][column][1],
                  f'{self.coordinate_plane[2]} [{self.unit}]': z.value()[0],
                  f'{self.coordinate_plane[2]} max [{self.unit}]': z.value()[-1]}
        table_row = self.table.rowCount()
        self.table.insertRow(table_row)
        items = {}
        for header_col, header in enumerate(self.columns):
            item = QTableWidgetItem()
            if header == 'row, column':
                item.setText(str(kwargs[header]))
            else:
                value = float(kwargs[header])
                item.setData(Qt.EditRole, value)
            items[header] = item
            self.table.setItem(table_row, header_col, item)

        # disable cells
        disable = list(kwargs.keys())
        if not self.scan_plan_widget.apply_to_all or (row, column) == (0, 0):
            disable.remove(f'{self.coordinate_plane[2]} max [{self.unit}]')
            if self.anchor_widgets[2].isChecked():
                disable.remove(f'{self.coordinate_plane[2]} [{self.unit}]')
        flags = QTableWidgetItem().flags()
        flags &= ~Qt.ItemIsEditable
        for var in disable:
            items[var].setFlags(flags)

        self.table.blockSignals(False)

    def tile_added(self, row, column):
        """Connect new tile to proper signals. Only do when tile added to scan, not to table, to avoid connect signals
        multiple times"""

        # connect z widget signals to trigger update
        z = self.scan_plan_widget.z_plan_widgets[row, column]
        z.valueChanged.connect(lambda value: self.change_table(value, row, column))

    def view_plane_change(self, button):
        """Update view plane and remap path
        :param button: button that was clicked"""

        view_plane = tuple(x for x in button.text() if x.isalpha())
        setattr(self.volume_model, 'view_plane', view_plane)

        if view_plane == (self.coordinate_plane[0], self.coordinate_plane[1]):
            value = self.tile_plan_widget.value()
            self.volume_model.set_path_pos([self.volume_model.grid_coords[t.row][t.col] for t in value])
            if not self.volume_model.path.visible() and self.path_show.isChecked():
                self.volume_model.toggle_path_visibility(True)
        else:  # hide path if not in tiling view plane
            self.volume_model.toggle_path_visibility(False)

    def change_table(self, value, row, column):
        """If z widget is changed, update table"""

        item = self.table.findItems(str([row, column]), Qt.MatchExactly)[0]
        tile_start = self.table.item(item.row(), self.table.columnCount() - 2)
        tile_end = self.table.item(item.row(), self.table.columnCount() - 1)
        self.undercover_update_item(float(value[0]), tile_start)
        self.undercover_update_item(float(value[-1]), tile_end)

        # If volume has changed, update channel table steps and step size accordingly
        if (self.channel_plan.apply_to_all and [row, column] == [0, 0]) or not self.channel_plan.apply_to_all:  # only update once if apply_all
            for channel in self.channel_plan.channels:
                self.channel_plan.cell_edited(item.row(), 0, channel)

    def table_changed(self, item):
        """Update corresponding z widget with correct values """

        self.table.blockSignals(True)
        row, column = [int(x) for x in self.table.item(item.row(), 0).text() if x.isdigit()]

        z = self.scan_plan_widget.z_plan_widgets[row, column]
        z.blockSignals(True)

        min_item = self.table.item(item.row(), self.table.columnCount() - 2)
        max_item = self.table.item(item.row(), self.table.columnCount() - 1)
        min_value = min_item.data(Qt.EditRole)
        max_value = max_item.data(Qt.EditRole)
        if min_value > max_value:
            self.undercover_update_item(min_value, max_item)

        if item.column() == self.table.columnCount() - 1:  # max edited
            value = float(item.data(Qt.EditRole))
            if z.mode().value == 'top_bottom':
                z.top.setValue(value)
            elif z.mode().value == 'range_around':
                z.range.setValue(z.start.value() - (value / 2))
            elif z.mode().value == 'above_below':
                z.below.setValue(value)

        elif item.column() == self.table.columnCount() - 2:  # start edited
            value = float(item.data(Qt.EditRole))
            if z.mode().value == 'top_bottom':
                z.start.setValue(value)
            elif z.mode().value == 'range_around':
                z.range.setValue(abs(z.start.value() - (value / 2)))
            elif z.mode().value == 'above_below':
                z.above.setValue(value)

        z.blockSignals(False)
        self.table.blockSignals(False)

        # If volume has changed, update channel table steps and step size accordingly
        if (self.channel_plan.apply_to_all and [row, column] == [0, 0]) or not self.channel_plan.apply_to_all:  # only update once if apply_all
            for channel in self.channel_plan.channels:
                self.channel_plan.cell_edited(item.row(), 0, channel)

    def undercover_update_item(self, value, item):
        """Update table with latest z value"""
        
        self.table.blockSignals(True)
        item.setData(Qt.EditRole, value)
        self.table.blockSignals(False)

    def update_scan_start(self, value):
        """If apply all is checked and tile 0,0 start is updated, update tile_start widget in the scan dimension"""

        if self.scan_plan_widget.apply_to_all:
            self.tile_starts[2].blockSignals(True)  # block so it doesn't trigger update of start
            self.tile_starts[2].setValue(value)
            self.tile_starts[2].blockSignals(False)

    def disable_scan_start_widgets(self, disable):
        """Disable all scan start widgets if tile_plan_widget.grid_position_widgets[2] is checked"""

        for i, j in np.ndindex(self.scan_plan_widget.z_plan_widgets.shape):
            self.scan_plan_widget.z_plan_widgets[i][j].start.setDisabled(disable)

        tile_start_col = self.table.columnCount() - 2
        tile_range = range(self.table.rowCount()) if not self.scan_plan_widget.apply_to_all else range(1)
        for i in tile_range:
            item = self.table.item(i, tile_start_col)
            if item is not None:
                self.toggle_item_flags(self.table.item(i, tile_start_col), not disable)

    def toggle_apply_all(self, checked):
        """Enable/disable all channel plan cells when apply all is toggled"""

        # disable tilestart and anchor widget it apply all isn't checked
        self.tile_starts[2].setEnabled(checked if self.anchor_widgets[2].isChecked() else False)
        self.anchor_widgets[2].setEnabled(checked)

        # toggle edit ability for table items
        tile_start_col = self.table.columnCount() - 2
        tile_end_col = self.table.columnCount() - 1
        for i in range(self.table.rowCount()):
            self.toggle_item_flags(self.table.item(i, tile_end_col), not checked)
            self.toggle_item_flags(self.table.item(i, tile_start_col), not checked)
        tile_start_state = False if (checked == True and not self.anchor_widgets[2].isChecked()) else True
        self.toggle_item_flags(self.table.item(0, tile_start_col), tile_start_state)
        self.toggle_item_flags(self.table.item(0, tile_end_col), True)  # 0,0 z end always enabled

        self.scan_plan_widget.stacked_widget.setCurrentWidget(self.scan_plan_widget.z_plan_widgets[0, 0])

        if not checked:
            self.scan_plan_widget.group_box.setTitle(f'Tile Volume '
                                                     f'{self.scan_plan_widget.stacked_widget.currentWidget().windowTitle()}')
            self.table.blockSignals(True)
            self.table.setCurrentCell(0, 0)
            self.table.blockSignals(False)

        if checked:  # set tile 0,0 visible
            self.scan_plan_widget.group_box.setTitle(f'Tile Volume')
            setattr(self.volume_model, 'grid_coords', np.dstack((self.tile_plan_widget.tile_positions,
                                                                 self.scan_plan_widget.scan_starts)))
        # update channel plan
        self.channel_plan.apply_to_all = checked

    def toggle_item_flags(self, item, enable):
        """Change flags for enabling/disabling items in channel_plan table"""

        self.table.blockSignals(True)

        flags = QTableWidgetItem().flags()
        if not enable:
            flags &= ~Qt.ItemIsEditable
        else:
            flags |= Qt.ItemIsEditable
            flags |= Qt.ItemIsEnabled
            flags |= Qt.ItemIsSelectable
        item.setFlags(flags)

        self.table.blockSignals(False)

    def toggle_z_show(self, current_row, current_column, previous_row, previous_column):
        """If apply all is not checked, show corresponding z widget for selected row"""

        if not self.scan_plan_widget.apply_to_all:
            current_row = 0 if current_row == -1 else current_row

            show_row, show_col = [int(x) for x in self.table.item(current_row, 0).text() if x.isdigit()]
            z = self.scan_plan_widget.z_plan_widgets[show_row, show_col]
            self.scan_plan_widget.stacked_widget.setCurrentWidget(z)

    def create_tile_list(self):
        """Return a list of tiles for a scan"""

        tiles = []

        if self.channel_plan.channel_order.currentText() == 'per Tile':
            for tile in self.tile_plan_widget.value():
                for ch in self.channel_plan.channels:
                    tiles.append(self.write_tile(ch, tile))
        elif self.channel_plan.channel_order.currentText() == 'per Volume':
            for ch in self.channel_plan.channels:
                for tile in self.tile_plan_widget.value():
                    tiles.append(self.write_tile(ch, tile))

        return tiles

    def write_tile(self, channel, tile):
        """Write dictionary describing tile parameters"""

        row, column = tile.row, tile.col
        table_row = self.table.findItems(str([row, column]), Qt.MatchExactly)[0].row()

        tile_dict = {
            'channel': channel,
            'position': {k: self.table.item(table_row, j + 1).value() for j, k in
                         enumerate(self.columns[1:-1])},
            'tile_number': table_row,
        }

        # load channel plan values
        for device_type, devices in self.channel_plan.possible_channels[channel].items():
            for device_name in devices:
                tile_dict[device_name] = {}
                for setting in self.channel_plan.settings.get(device_type, []):
                    column_name = label_maker(f'{device_name}_{setting}')
                    if getattr(self.channel_plan, column_name, None) is not None:
                        array = getattr(self.channel_plan, column_name)[channel]
                        input_type = self.channel_plan.column_data_types[column_name]
                        if input_type != inspect._empty:
                            tile_dict[device_name][setting] = input_type(array[row, column])
                        else:
                            tile_dict[device_name][setting] = array[row, column]

        for name in ['steps', 'step_size', 'prefix']:
            array = getattr(self.channel_plan, name)[channel]
            tile_dict[name] = array[row, column]

        return tile_dict
