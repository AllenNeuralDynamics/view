import logging
import importlib
from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties, create_widget
from view.widgets.acquisition_widgets.volume_widget import VolumeWidget
from view.widgets.acquisition_widgets.metadata_widget import MetadataWidget
from qtpy.QtCore import Slot, Qt
import inflection
from time import sleep
from qtpy.QtWidgets import QGridLayout, QWidget, QComboBox, QSizePolicy, QScrollArea, QDockWidget, \
    QLabel, QPushButton, QSplitter, QLineEdit, QSpinBox, QDoubleSpinBox, QProgressBar, QSlider, QApplication, \
    QMessageBox, QPushButton, QFileDialog
from qtpy.QtGui import QFont
from napari.qt.threading import thread_worker, create_worker
from view.widgets.miscellaneous_widgets.q__dock_widget_title_bar import QDockWidgetTitleBar
from view.widgets.miscellaneous_widgets.q_scrollable_float_slider import QScrollableFloatSlider
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit
from pathlib import Path

class AcquisitionView(QWidget):
    """"Class to act as a general acquisition view model to voxel instrument"""

    def __init__(self, acquisition, instrument_view, log_level='INFO'):
        """
        :param acquisition: voxel acquisition object
        :param config_path: path to config specifying UI setup
        :param instrument_view: view object relating to instrument. Needed to lock stage
        :param log_level:
        """

        super().__init__()

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)

        self.instrument_view = instrument_view
        self.acquisition = acquisition
        self.instrument = self.acquisition.instrument
        self.config = instrument_view.config

        # tile list
        self.tiles = []

        # Eventual threads
        self.grab_fov_positions_worker = None
        self.property_workers = []

        # create workers for latest image taken by cameras
        for camera_name, camera in self.instrument.cameras.items():
            worker = self.grab_property_value(camera, 'latest_frame', camera_name)
            worker.yielded.connect(self.instrument_view.update_layer)
            worker.start()
            worker.pause()  # start and pause, so we can resume when acquisition starts and pause when over
            self.property_workers.append(worker)

        for device_name, operation_dictionary in self.acquisition.config['acquisition']['operations'].items():
            for operation_name, operation_specs in operation_dictionary.items():
                self.create_operation_widgets(device_name, operation_name, operation_specs)

        # setup additional widgets
        self.metadata_widget = self.create_metadata_widget()
        self.volume_widget = self.create_volume_widget()
        self.start_button = self.create_start_button()
        self.stop_button = self.create_stop_button()

        # setup stage thread
        self.setup_fov_position()

        # Set up main window
        self.main_layout = QGridLayout()

        # Add start and stop button
        self.main_layout.addWidget(self.start_button, 0, 0, 1, 2)
        self.main_layout.addWidget(self.stop_button, 0, 2, 1, 2)

        # add volume widget
        self.main_layout.addWidget(self.volume_widget, 1, 0, 5, 3)

        # splitter for operation widgets
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # create scroll wheel for metadata widget
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.metadata_widget)
        scroll.setWindowTitle('Metadata')
        scroll.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        dock = QDockWidget(scroll.windowTitle(), self)
        dock.setWidget(scroll)
        dock.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        dock.setTitleBarWidget(QDockWidgetTitleBar(dock))
        dock.setWidget(scroll)
        dock.setMinimumHeight(25)
        splitter.addWidget(dock)

        # create dock widget for operations
        for i, operation in enumerate(['writer', 'transfer', 'process', 'routine']):
            if hasattr(self, f'{operation}_widgets'):
                stack = self.stack_device_widgets(operation)
                stack.setFixedWidth(self.metadata_widget.size().width() - 20)
                scroll = QScrollArea()
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll.setWidget(stack)
                scroll.setFixedWidth(self.metadata_widget.size().width())
                dock = QDockWidget(stack.windowTitle())
                dock.setTitleBarWidget(QDockWidgetTitleBar(dock))
                dock.setWidget(scroll)
                dock.setMinimumHeight(25)
                splitter.addWidget(dock)
        self.main_layout.addWidget(splitter, 1, 3)
        self.setLayout(self.main_layout)
        self.setWindowTitle('Acquisition View')
        self.show()

        # Set app events
        app = QApplication.instance()
        app.aboutToQuit.connect(self.update_config_on_quit)  # query if config should be saved and where
        self.config_save_to = self.acquisition.config_path
        app.lastWindowClosed.connect(self.close)  # shut everything down when closing

    def create_start_button(self):
        """Create button to start acquisition"""

        start = QPushButton('Start')
        start.clicked.connect(self.start_acquisition)
        start.setStyleSheet("background-color: green")
        return start

    def create_stop_button(self):
        """Create button to stop acquisition"""

        stop = QPushButton('Stop')
        stop.clicked.connect(self.acquisition.stop_acquisition)
        stop.setStyleSheet("background-color: red")
        stop.setDisabled(True)

        return stop

    def start_acquisition(self):
        """Start acquisition"""

        # add tiles to acquisition config
        self.update_tiles()

        if self.instrument_view.grab_frames_worker.is_running:  # stop livestream if running
            self.instrument_view.dismantle_live()

        # write correct daq values if different from livestream
        for daq_name, daq in self.instrument.daqs.items():
            if daq_name in self.config['acquisition_view'].get('data_acquisition_tasks', {}).keys():
                daq.tasks = self.instrument.config['acquisition_view']['data_acquisition_tasks'][daq_name]['tasks']
                # Tasks should be added and written in acquisition?

        # anchor grid in volume widget
        for anchor in self.volume_widget.anchor_widgets:
            anchor.setChecked(True)
        self.volume_widget.table.setDisabled(True)
        self.volume_widget.channel_plan.setDisabled(True)
        self.volume_widget.scan_plan_widget.setDisabled(True)
        self.volume_widget.scan_plan_widget.stacked_widget.setDisabled(True)
        self.volume_widget.tile_plan_widget.setDisabled(True)

        # disable acquisition view. Can't disable whole thing so stop button can be functional
        self.start_button.setEnabled(False)
        self.metadata_widget.setEnabled(False)
        for operation in enumerate(['writer', 'transfer', 'process', 'routine']):
            if hasattr(self, f'{operation}_widgets'):
                device_widgets = {f'{inflection.pluralize(operation)} {device_name}': create_widget('V', **widgets)
                                  for device_name, widgets in getattr(self, f'{operation}_widgets').items()}
                for widget in device_widgets.values():
                    widget.setDisabled(True)
        self.stop_button.setEnabled(True)

        # disable instrument view
        self.instrument_view.setDisabled(True)

        # Start acquisition
        self.acquisition_thread = create_worker(self.acquisition.run)
        self.acquisition_thread.start()
        self.acquisition_thread.finished.connect(self.acquisition_ended)

        # start all workers
        for worker in self.property_workers:
            worker.resume()
            sleep(1)

    def acquisition_ended(self):
        """Re-enable UI's and threads after acquisition has ended"""

        # enable acquisition view
        self.start_button.setEnabled(True)
        self.volume_widget.setEnabled(True)
        self.metadata_widget.setEnabled(True)
        for operation in enumerate(['writer', 'transfer', 'process', 'routine']):
            if hasattr(self, f'{operation}_widgets'):
                device_widgets = {f'{inflection.pluralize(operation)} {device_name}': create_widget('V', **widgets)
                                  for device_name, widgets in getattr(self, f'{operation}_widgets').items()}
                for widget in device_widgets.values():
                    widget.setDisabled(False)
        self.stop_button.setEnabled(False)

        # unanchor grid in volume widget
        for anchor in self.volume_widget.anchor_widgets:
            anchor.setChecked(False)
        self.volume_widget.table.setEnabled(True)
        self.volume_widget.channel_plan.setEnabled(True)
        self.volume_widget.scan_plan_widget.setEnabled(True)
        self.volume_widget.scan_plan_widget.stacked_widget.setEnabled(True)
        self.volume_widget.tile_plan_widget.setEnabled(True)

        # enable instrument view
        self.instrument_view.setDisabled(False)

        # restart stage threads
        self.setup_fov_position()

        for worker in self.property_workers:
            worker.pause()

    def stack_device_widgets(self, device_type):
        """Stack like device widgets in layout and hide/unhide with combo box
        :param device_type: type of device being stacked"""

        device_widgets = {f'{inflection.pluralize(device_type)} {device_name}': create_widget('V', **widgets)
                          for device_name, widgets in getattr(self, f'{device_type}_widgets').items()}

        overlap_layout = QGridLayout()
        overlap_layout.addWidget(QWidget(), 1, 0)  # spacer widget
        for name, widget in device_widgets.items():
            widget.setVisible(False)
            overlap_layout.addWidget(widget, 2, 0)

        visible = QComboBox()
        visible.currentTextChanged.connect(lambda text: self.hide_devices(text, device_widgets))
        visible.addItems(device_widgets.keys())
        visible.setCurrentIndex(0)
        overlap_layout.addWidget(visible, 0, 0)

        overlap_widget = QWidget()
        overlap_widget.setWindowTitle(inflection.pluralize(device_type))
        overlap_widget.setLayout(overlap_layout)

        return overlap_widget

    def hide_devices(self, text, device_widgets):
        """Hide device widget if not selected in combo box
        :param text: selected text of combo box
        :param device_widgets: dictionary of widget groups"""

        for name, widget in device_widgets.items():
            if name != text:
                widget.setVisible(False)
            else:
                widget.setVisible(True)

    def create_metadata_widget(self):
        """Create custom widget for metadata in config"""

        metadata_widget = MetadataWidget(self.acquisition.metadata)
        metadata_widget.ValueChangedInside[str].connect(lambda name: setattr(self.acquisition.metadata, name,
                                                                             getattr(metadata_widget, name)))
        for name, widget in metadata_widget.property_widgets.items():
            widget.setToolTip('')  # reset tooltips
        metadata_widget.setWindowTitle(f'Metadata')
        return metadata_widget

    def create_volume_widget(self):
        """Create widget to visualize acquisition grid"""

        kwds = {
            'fov_dimensions': self.config['acquisition_view']['fov_dimensions'],
            'coordinate_plane': self.config['acquisition_view'].get('coordinate_plane', ['x', 'y', 'z']),
            'unit': self.config['acquisition_view'].get('unit', 'mm'),
            'properties': self.config['acquisition_view'].get('properties', {})

        }

        # Populate limits
        coordinate_plane = [x.replace('-', '') for x in kwds['coordinate_plane']]  # remove polarity
        limits = {}
        # add tiling stages
        for name, stage in self.instrument.tiling_stages.items():
            if stage.instrument_axis in coordinate_plane:
                limits.update({f'{stage.instrument_axis}': stage.limits_mm})
        # last axis should be scanning axis
        (scan_name, scan_stage), = self.instrument.scanning_stages.items()
        limits.update({f'{scan_stage.instrument_axis}': scan_stage.limits_mm})
        if len([i for i in limits.keys() if i in coordinate_plane]) != 3:
            raise ValueError('Coordinate plane must match instrument axes in tiling_stages')
        kwds['limits'] = [limits[coordinate_plane[0]], limits[coordinate_plane[1]], limits[coordinate_plane[2]]]
        kwds['channels'] = self.instrument.config['instrument']['channels']

        volume_widget = VolumeWidget(self.instrument_view, **kwds)
        volume_widget.fovMoved.connect(self.move_stage)
        volume_widget.fovStop.connect(self.stop_stage)
        volume_widget.tilesChanged.connect(self.update_tiles)
        self.instrument_view.snapshotTaken.connect(volume_widget.handle_snapshot)  # connect snapshot signal
        self.instrument_view.contrastChanged.connect(volume_widget.adjust_contrast)
        return volume_widget

    def update_tiles(self):
        """Update config with the latest tiles"""

        self.acquisition.config['acquisition']['tiles'] = self.volume_widget.create_tile_list()

    def move_stage(self, fov_position):
        """Slot for moving stage when fov_position is changed internally by grid_widget"""

        stage_names = {stage.instrument_axis: name for name, stage in self.instrument.tiling_stages.items()}
        # Move stages
        for axis, position in zip(self.volume_widget.coordinate_plane[:2], fov_position[:2]):
            self.instrument.tiling_stages[stage_names[axis]].move_absolute_mm(position, wait=False)
        (scan_name, scan_stage), = self.instrument.scanning_stages.items()
        scan_stage.move_absolute_mm(fov_position[2], wait=False)

    def stop_stage(self):
        """Slot for stop stage"""

        for name, stage in {**getattr(self.instrument, 'scanning_stages', {}),
                            **getattr(self.instrument, 'tiling_stages', {})}.items():  # combine stage
            stage.halt()

    def setup_fov_position(self):
        """Set up live position thread"""

        self.grab_fov_positions_worker = self.grab_fov_positions()
        self.grab_fov_positions_worker.yielded.connect(lambda pos: setattr(self.volume_widget, 'fov_position', pos))
        self.grab_fov_positions_worker.start()

    @thread_worker
    def grab_fov_positions(self):
        """Grab stage position from all stage objects and yield positions"""

        while True:  # best way to do this or have some sort of break?
            fov_pos = self.volume_widget.fov_position
            for name, stage in {**self.instrument.tiling_stages, **self.instrument.scanning_stages}.items():
                if stage.instrument_axis in self.volume_widget.coordinate_plane:
                    index = self.volume_widget.coordinate_plane.index(stage.instrument_axis)
                    try:
                        pos = stage.position_mm
                        fov_pos[index] = pos if pos is not None else fov_pos[index]
                    except ValueError as e:  # Tigerbox sometime coughs up garbage. Locking issue?
                        pass
                    sleep(.1)
            yield fov_pos

    def create_operation_widgets(self, device_name: str, operation_name: str, operation_specs: dict):
        """Create widgets based on operation dictionary attributes from instrument or acquisition
         :param device_name: name of device correlating to operation
         :param operation_specs: dictionary describing set up of operation
         """

        operation_type = operation_specs['type']
        operation = getattr(self.acquisition, inflection.pluralize(operation_type))[device_name][operation_name]

        specs = self.config['acquisition_view']['operation_widgets'].get(device_name, {}).get(operation_name, {})
        if specs.get('type', '') == operation_type and 'driver' in specs.keys() and 'module' in specs.keys():
            gui_class = getattr(importlib.import_module(specs['driver']), specs['module'])
            gui = gui_class(operation, **specs.get('init', {}))  # device gets passed into widget
        else:
            properties = scan_for_properties(operation)
            gui = BaseDeviceWidget(type(operation), properties)  # create label

        # if gui is BaseDeviceWidget or inherits from it
        if type(gui) == BaseDeviceWidget or BaseDeviceWidget in type(gui).__bases__:
            # Hook up widgets to device_property_changed
            gui.ValueChangedInside[str].connect(
                lambda value, op=operation, widget=gui:
                self.operation_property_changed(value, op, widget))

            updating_props = specs.get('updating_properties', [])
            for prop_name in updating_props:
                descriptor = getattr(type(operation), prop_name)
                unit = getattr(descriptor, 'unit', None)
                # if operation is percentage, change property widget to QProgressbar
                if unit in ['%', 'percent', 'percentage']:
                    widget = getattr(gui, f'{prop_name}_widget')
                    progress_bar = QProgressBar()
                    progress_bar.setMaximum(100)
                    progress_bar.setMinimum(0)
                    widget.parentWidget().layout().replaceWidget(getattr(gui, f'{prop_name}_widget'), progress_bar)
                    widget.deleteLater()
                    setattr(gui, f'{prop_name}_widget', progress_bar)
                worker = self.grab_property_value(operation, prop_name, getattr(gui, f'{prop_name}_widget'))
                worker.yielded.connect(self.update_property_value)
                worker.start()
                worker.pause()  # start and pause, so we can resume when acquisition starts and pause when over
                self.property_workers.append(worker)

        # Add label to gui
        font = QFont()
        font.setBold(True)
        label = QLabel(operation_name)
        label.setFont(font)
        labeled = create_widget('V', label, gui)

        # add ui to widget dictionary
        if not hasattr(self, f'{operation_type}_widgets'):
            setattr(self, f'{operation_type}_widgets', {device_name: {}})
        elif not getattr(self, f'{operation_type}_widgets').get(device_name, False):
            getattr(self, f'{operation_type}_widgets')[device_name] = {}
        getattr(self, f'{operation_type}_widgets')[device_name][operation_name] = labeled

        # TODO: Do we need this?
        for subdevice_name, suboperation_dictionary in operation_specs.get('subdevices', {}).items():
            for suboperation_name, suboperation_specs in suboperation_dictionary.items():
                self.create_operation_widgets(subdevice_name, suboperation_name, suboperation_specs)

        labeled.setWindowTitle(f'{device_name} {operation_type} {operation_name}')
        labeled.show()

    def update_acquisition_layer(self, args):
        """Update viewer with latest frame taken during acquisition
        :param args: tuple containing image and camera name
        """

        (image, camera_name) = args
        if image is not None:
            # TODO: How to get current channel
            layer_name = f"{camera_name}"
            if layer_name in self.instrument_view.viewer.layers:
                layer = self.instrument_view.viewer.layers[layer_name]
                layer.data = image
            else:
                layer = self.instrument_view.viewer.add_image(image, name=layer_name)

    @thread_worker
    def grab_property_value(self, device, property_name, widget):
        """Grab value of property and yield"""

        while True:  # best way to do this or have some sort of break?
            sleep(1)
            value = getattr(device, property_name)
            yield value, widget

    def update_property_value(self, args):
        """Update stage position in stage widget
        :param args: tuple containing the name of stage and position of stage"""

        (value, widget) = args
        try:
            if type(widget) in [QLineEdit, QScrollableLineEdit]:
                widget.setText(str(value))
            elif type(widget) in [QSpinBox, QDoubleSpinBox, QSlider, QScrollableFloatSlider]:
                widget.setValue(value)
            elif type(widget) == QComboBox:
                index = widget.findText(value)
                widget.setCurrentIndex(index)
            elif type(widget) == QProgressBar:
                widget.setValue(round(value))
        except (RuntimeError, AttributeError):  # Pass when window's closed or widget doesn't have position_mm_widget
            pass

    @Slot(str)
    def operation_property_changed(self, attr_name: str, operation, widget):
        """Slot to signal when operation widget has been changed
        :param widget: widget object relating to operation
        :param operation: operation object
        :param attr_name: name of attribute"""

        name_lst = attr_name.split('.')
        self.log.debug(f'widget {attr_name} changed to {getattr(widget, name_lst[0])}')
        value = getattr(widget, name_lst[0])
        try:  # Make sure name is referring to same thing in UI and operation
            dictionary = getattr(operation, name_lst[0])
            for k in name_lst[1:]:
                dictionary = dictionary[k]
            setattr(operation, name_lst[0], value)
            self.log.info(f'Device changed to {getattr(operation, name_lst[0])}')
            # Update ui with new operation values that might have changed
            # WARNING: Infinite recursion might occur if operation property not set correctly
            for k, v in widget.property_widgets.items():
                if getattr(widget, k, False):
                    operation_value = getattr(operation, k)
                    setattr(widget, k, operation_value)

        except (KeyError, TypeError) as e:
            self.log.warning(f"{attr_name} can't be mapped into operation properties due to {e}")
            pass

    def update_config_on_quit(self):
        """Add functionality to close function to save device properties to instrument config"""

        return_value = self.update_config_query()
        if return_value == QMessageBox.Ok:
            self.acquisition.update_current_state_config()
            self.acquisition.save_config(self.config_save_to)

    def update_config_query(self):
        """Pop up message asking if configuration would like to be saved"""
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(f"Do you want to update the acquisition configuration file at {self.config_save_to} "
                       f"to current acquisition state?")
        msgBox.setWindowTitle("Updating Configuration")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        save_elsewhere = QPushButton('Change Directory')
        msgBox.addButton(save_elsewhere, QMessageBox.DestructiveRole)

        save_elsewhere.pressed.connect(lambda: self.select_directory(True, msgBox))

        return msgBox.exec()

    def select_directory(self, pressed, msgBox):
        """Select directory"""

        fname = QFileDialog()
        folder = fname.getSaveFileName(directory=str(self.acquisition.config_path))
        if folder[0] != '':  # user pressed cancel
            msgBox.setText(f"Do you want to update the instrument configuration file at {folder[0]} "
                           f"to current instrument state?")
            self.config_save_to = Path(folder[0])

    def close(self):
        """Close operations and end threads"""

        for worker in self.property_workers:
            worker.quit()
        self.grab_fov_positions_worker.quit()
        for device_name, operation_dictionary in self.acquisition.config['acquisition']['operations'].items():
            for operation_name, operation_specs in operation_dictionary.items():
                operation_type = operation_specs['type']
                operation = getattr(self.acquisition, inflection.pluralize(operation_type))[device_name][operation_name]
                try:
                    operation.close()
                except AttributeError:
                    self.log.debug(f'{device_name} {operation_name} does not have close function')
        self.acquisition.close()
