from qtpy.QtWidgets import QWidget, QCheckBox, QHBoxLayout, QLabel, QButtonGroup, QRadioButton, \
    QGridLayout, QTableWidgetItem, QTableWidget, QSizePolicy
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

class VolumeWidget(QWidget):
    """Widget to combine scanning, tiling, channel, and model together to ease acquisition setup"""

    def __init__(self,
                 instrument,
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
        :param tile_specs: list of parameters defining tiles
        :param limits: list of limits ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
        :param coordinate_plane: list describing instrument coordinate plane ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
        :param fov_dimensions: list of fov_dims which correspond to tiling dimensions
        :param fov_position: list describing fov pos ordered in [tile_dim[0], tile_dim[1], scan_dim[0]]
        :param view_color: color of fov in volume model
        :param unit: unit ALL values will be in
        """
        super().__init__()

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
        for view in [f'({coordinate_plane[0]}, {coordinate_plane[2]})',
                     f'({coordinate_plane[2]}, {coordinate_plane[1]})',
                     f'({coordinate_plane[0]}, {coordinate_plane[1]})']:
            button = QRadioButton(view)
            button.clicked.connect(lambda clicked, b=button: self.grid_plane_change(b))
            view_plane.addButton(button)
            button.setChecked(True)
            checkboxes.addWidget(button)
        extended_model = create_widget('V', self.volume_model, checkboxes)
        self.layout.addWidget(extended_model, 0, 1, 3, 2)

        # create tile plan widgets
        self.tile_plan_widget = TilePlanWidget(limits, fov_dimensions, fov_position, coordinate_plane, unit)
        self.fovStop = self.tile_plan_widget.fovStop  # expose for ease of access
        self.tile_starts = self.tile_plan_widget.grid_position_widgets  # expose for ease of access
        self.anchor_widgets = self.tile_plan_widget.anchor_widgets  # expose for ease of access
        self.layout.addWidget(self.tile_plan_widget, 0, 0)

        # create scan widgets
        self.scan_plan_widget = ScanPlanWidget(limits[2], unit)
        self.layout.addWidget(self.scan_plan_widget, 1, 0)

        # create channel plan widget
        self.channel_plan = ChannelPlanWidget(instrument, channels, settings)
        self.channel_plan.channelAdded.connect(self.channel_added)
        self.channel_plan.apply_to_all = True

        # setup table
        self.columns = ['row, column', *[f'{x} [{unit}]' for x in coordinate_plane],
                        f'{coordinate_plane[2]} max [{unit}]']
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.resizeColumnsToContents()
        # add spinbox validator for columns

        for i in range(1,self.table.columnCount()): # skip first column
            column_name = self.table.horizontalHeaderItem(i).text()
            delegate = QSpinItemDelegate()
            # table does not take ownership of the delegates, so they are removed from memory as they
            # are local variables causing a Segmentation fault. Need to be attributes
            setattr(self, f'table_column_{column_name}_delegate', delegate)
            self.table.setItemDelegateForColumn(i, delegate)

        self.table.itemChanged.connect(self.table_changed)
        self.table.currentCellChanged.connect(self.toggle_z_show)
        #self.table.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Expanding)

        # add table and channel plan to layout
        widget = QWidget()  # dummy widget to move table down in layout
        widget.setMinimumHeight(25)
        extended_table = create_widget('V', widget, self.table)
        self.layout.addWidget(create_widget('H', extended_table, self.channel_plan), 3, 0, 1, 3)

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
        self.coordinate_plane = coordinate_plane
        self.fov_dimensions = fov_dimensions[:2] + [0]  # add 0 if not already included
        self.fov_position = fov_position

        # initialize first tile and add to layout
        self.scan_plan_widget.scan_plan_construction(self.tile_plan_widget.value())
        self.layout.addWidget(self.scan_plan_widget.z_plan_widgets[0, 0], 2, 0)
        self.scan_plan_widget.z_plan_widgets[0, 0].setVisible(True)
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
            self.scan_plan_widget.z_plan_widgets[0,0].start.setValue(value[2])
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
        self.volume_model.path.setData(pos=
                                       [[self.volume_model.grid_coords[t.row][t.col][i] + .5 * self.fov_dimensions[i]
                                         if self.coordinate_plane[i] in self.volume_model.grid_plane else 0. for i in
                                         range(3)] for t in value])  # update path

        #update scanning coords of table
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

        current_row = 0 if self.scan_plan_widget.apply_to_all or self.table.currentRow() == -1 \
            else self.table.currentRow()

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

            show_row, show_col = [int(x) for x in self.table.item(current_row, 0).text() if x.isdigit()]
            self.scan_plan_widget.z_plan_widgets[show_row, show_col].setVisible(True)

        # update channel plan
        self.channel_plan.tile_volumes = self.scan_plan_widget.scan_volumes
        for tab_index in range(self.channel_plan.count() - 1):  # skip add tab
            channel = self.channel_plan.tabText(tab_index)
            self.channel_plan.add_channel_rows(channel, scan_order)

        if not self.anchor_widgets[2].isChecked():  # disable start widget for any new widgets
            self.disable_scan_start_widgets(True)

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
                  f'{self.coordinate_plane[2]} [{self.unit}]': min(z.value()),
                  f'{self.coordinate_plane[2]} max [{self.unit}]': max(z.value())}

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

        # add new tile to layout
        self.layout.addWidget(self.scan_plan_widget.z_plan_widgets[row, column], 2, 0)
        self.scan_plan_widget.z_plan_widgets[row, column].setVisible(False)

    def tile_added(self, row, column):
        """Connect new tile to proper signals. Only do when tile added to scan, not to table, to avoid connect signals
        multiple times"""

        # connect z widget signals to trigger update
        z = self.scan_plan_widget.z_plan_widgets[row, column]
        z.valueChanged.connect(lambda value: self.change_table(value, row, column))


    def grid_plane_change(self, button):
        """Update grid plane and remap path
        :param button: button that was clicked"""

        grid_plane = tuple(x for x in button.text() if x.isalpha())
        setattr(self.volume_model, 'grid_plane', grid_plane)

        if grid_plane == (self.coordinate_plane[0], self.coordinate_plane[1]):
            self.volume_model.path.setData(pos=[[
                self.volume_model.grid_coords[t.row][t.col][i] + .5 * self.fov_dimensions[i]
                if self.coordinate_plane[i] in self.volume_model.grid_plane else 0. for i in range(3)]
                for t in self.tile_plan_widget.value()])  # update path
            if not self.volume_model.path.visible() and self.path_show.isChecked():
                self.volume_model.toggle_path_visibility(True)
        else:   # hide path if not in tiling grid plane
            self.volume_model.toggle_path_visibility(False)
    def change_table(self, value, row, column):
        """If z widget is changed, update table"""

        item = self.table.findItems(str([row, column]), Qt.MatchExactly)[0]
        tile_start = self.table.item(item.row(), self.table.columnCount() - 2)
        tile_end = self.table.item(item.row(), self.table.columnCount() - 1)

        self.undercover_update_item(float(min(value)), tile_start)
        self.undercover_update_item(float(max(value)), tile_end)

    def table_changed(self, item):
        """Update corresponding z widget with correct values """

        self.table.blockSignals(True)
        row, column = [int(x) for x in self.table.item(item.row(), 0).text() if x.isdigit()]

        z = self.scan_plan_widget.z_plan_widgets[row, column]
        z.blockSignals(True)

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

    def undercover_update_item(self, value, item):
        """Update table with latest z value"""

        self.table.blockSignals(True)
        item.setData(Qt.EditRole,value)
        self.table.blockSignals(False)

    def update_scan_start(self, value):
        """If apply all is checked and tile 0,0 start is updated, update tile_start widget in the scan dimension"""

        if self.scan_plan_widget.apply_to_all:
            self.tile_starts[2].setValue(value)

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
        for i in range(self.table.rowCount()):  # skip first row
            self.toggle_item_flags(self.table.item(i, tile_end_col), not checked)
            #TODO: only enable start column if apply all isn't checked or anchor is checked
            self.toggle_item_flags(self.table.item(i, tile_start_col), not checked)
        self.toggle_item_flags(self.table.item(0, tile_end_col), not checked)   # 0,0 z end always enabled

        if not checked:
            self.table.blockSignals(True)
            self.table.setCurrentCell(0, 0)
            self.table.blockSignals(False)

        if checked:     # set tile 0,0 visible
            current_row = 0 if self.table.currentRow() == -1 else self.table.currentRow()
            hide_row, hide_col = [int(x) for x in self.table.item(current_row, 0).text() if x.isdigit()]
            self.scan_plan_widget.z_plan_widgets[hide_row, hide_col].setVisible(False)

            self.scan_plan_widget.z_plan_widgets[0, 0].setVisible(True)
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
            previous_row = 0 if previous_row == -1 else previous_row

            hide_row, hide_col = [int(x) for x in self.table.item(previous_row, 0).text() if x.isdigit()]
            self.scan_plan_widget.z_plan_widgets[hide_row, hide_col].setVisible(False)

            show_row, show_col = [int(x) for x in self.table.item(current_row, 0).text() if x.isdigit()]
            self.scan_plan_widget.z_plan_widgets[show_row, show_col].setVisible(True)

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
            f'position_{self.unit}': {k[0]: self.table.item(table_row, j + 1).data(Qt.EditRole) for j, k in enumerate(self.columns[1:-1])},
            'tile_number': table_row,
        }

        # load channel plan values
        for device_type, devices in self.channel_plan.possible_channels[channel].items():
            for device in devices:
                tile_dict[device] = {}
                for setting in self.channel_plan.settings.get(device_type, []):
                    array = getattr(self.channel_plan, label_maker(f'{device}_{setting}'))[channel]
                    tile_dict[device][setting] = array[row, column]

        for name in ['steps', 'step_size', 'prefix']:
            array = getattr(self.channel_plan, name)[channel]
            tile_dict[name] = array[row, column]

        return tile_dict
