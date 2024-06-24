from pathlib import Path
import logging
from ruamel.yaml import YAML
import importlib
from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties, create_widget
from view.widgets.acquisition_widgets.volume_widget import VolumeWidget
from qtpy.QtCore import Slot
import inflection
from time import sleep
from qtpy.QtWidgets import QGridLayout, QWidget, QComboBox, QSizePolicy, QScrollArea, QApplication, QDockWidget, \
    QLabel, QVBoxLayout, QCheckBox, QHBoxLayout, QButtonGroup, QRadioButton, QPushButton
from qtpy.QtCore import Qt
from napari.qt.threading import thread_worker, create_worker

class AcquisitionView:
    """"Class to act as a general acquisition view model to voxel instrument"""

    def __init__(self, acquisition, instrument_view, config_path: Path, log_level='INFO'):
        """
        :param acquisition: voxel acquisition object
        :param config_path: path to config specifying UI setup
        :param instrument_view: view object relating to instrument. Needed to lock stage
        :param log_level:
        """
        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)

        self.instrument_view = instrument_view

        # Locks
        self.tiling_stage_locks = self.instrument_view.tiling_stage_locks
        self.scanning_stage_locks = self.instrument_view.scanning_stage_locks
        #self.focusing_stage_locks = self.instrument_view.focusing_stage_locks  #TODO: update acquisiiton widgets to include focusing stage
        self.daq_locks = self.instrument_view.daq_locks

        # Eventual threads
        self.grab_fov_positions_worker = None

        self.acquisition = acquisition
        self.instrument = self.acquisition.instrument
        self.config = YAML(typ='safe', pure=True).load(
            config_path)  # TODO: maybe bulldozing comments but easier

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
        self.main_window = QWidget()
        self.main_layout = QGridLayout()

        # Add start and stop button
        self.main_layout.addWidget(self.start_button, 0, 0, 1, 2)
        self.main_layout.addWidget(self.stop_button, 0, 2, 1, 2)

        # create scroll wheel for metadata widget
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.metadata_widget)
        scroll.setWindowTitle('Metadata')
        scroll.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        dock = QDockWidget(scroll.windowTitle(), self.main_window)
        dock.setWidget(scroll)
        dock.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        self.main_layout.addWidget(dock, 1, 3)

        # add volume widget
        self.main_layout.addWidget(self.volume_widget, 1, 0, 5, 3)

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
                dock.setWidget(scroll)
                self.main_layout.addWidget(dock, i + 2, 3)
        self.main_window.setLayout(self.main_layout)
        self.main_window.setWindowTitle('Acquisition View')
        self.main_window.show()

        # Set app events
        app = QApplication.instance()
        app.focusChanged.connect(self.toggle_grab_fov_positions)

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

        #TODO: Warn if no channel selected?

        # stop stage threads
        self.grab_fov_positions_worker.quit()
        self.instrument_view.grab_stage_positions_worker.quit()

        if self.grab_fov_positions_worker.is_running or self.instrument_view.grab_stage_positions_worker.is_running:
            sleep(0.1)

        # add tiles to acquisition config
        self.acquisition.config['acquisition']['tiles'] = self.volume_widget.create_tile_list()

        if self.instrument_view.grab_frames_worker.is_running:  # stop livestream if running
            self.instrument_view.dismantle_live()

        # write correct daq values if different from livestream
        for daq_name, daq in self.instrument.daqs.items():
            if daq_name in self.instrument.config.get('data_acquisition_tasks', {}).keys():
                daq.tasks = self.instrument.config['data_acquisition_tasks'][daq_name]['tasks']
                # Tasks should be added and written in acquisition?

        # disable acquisition view. Can't disable whole thing so stop button can be functional
        self.start_button.setEnabled(False)
        self.volume_widget.setEnabled(False)
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


    def acquisition_ended(self):
        """Re-enable UI's and threads after aquisition has ended"""

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

        # enable instrument view
        self.instrument_view.setDisabled(False)

        # restart stage threads
        self.instrument_view.setup_live_position()
        self.instrument_view.grab_stage_positions_worker.pause()
        self.setup_fov_position()

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

        # TODO: metadata label
        acquisition_properties = dict(self.acquisition.config['acquisition']['metadata'])
        metadata_widget = BaseDeviceWidget(acquisition_properties, acquisition_properties)
        metadata_widget.ValueChangedInside[str].connect(lambda name: self.acquisition.config['acquisition']['metadata'].
                                                        __setitem__(name, getattr(metadata_widget, name)))
        for name, widget in metadata_widget.property_widgets.items():
            widget.setToolTip('')  # reset tooltips
        metadata_widget.setWindowTitle(f'Metadata')
        metadata_widget.show()
        return metadata_widget

    def create_volume_widget(self):
        """Create widget to visualize acquisition grid"""

        specs = self.config['operation_widgets'].get('volume_widget', {})
        kwds = specs.get('init', {})
        coordinate_plane = [x.replace('-', '') for x in kwds.get('coordinate_plane', ['x', 'y', 'z'])] # remove polarity

        # Populate limits
        limits = {}
        # add tiling stages
        for name, stage in self.instrument.tiling_stages.items():
            if stage.instrument_axis in coordinate_plane:
                with self.tiling_stage_locks[name]:
                    limits.update({f'{stage.instrument_axis}': stage.limits_mm})
        # last axis should be scanning axis
        (scan_name, scan_stage), = self.instrument.scanning_stages.items()
        with self.scanning_stage_locks[scan_name]:
            limits.update({f'{scan_stage.instrument_axis}': scan_stage.limits_mm})
        if len([i for i in limits.keys() if i in coordinate_plane]) != 3:
            raise ValueError('Coordinate plane must match instrument axes in tiling_stages')
        kwds['limits'] = [limits[coordinate_plane[0]], limits[coordinate_plane[1]], limits[coordinate_plane[2]]]

        volume_widget = VolumeWidget(self.instrument_view, **kwds)
        volume_widget.fovMoved.connect(self.move_stage)
        volume_widget.fovStop.connect(self.stop_stage)

        return volume_widget

    def move_stage(self, fov_position):
        """Slot for moving stage when fov_position is changed internally by grid_widget"""

        stage_names = {stage.instrument_axis: name for name, stage in self.instrument.tiling_stages.items()}
        # Move stages
        for axis, position in zip(self.volume_widget.coordinate_plane[:2], fov_position[:2]):
            with self.tiling_stage_locks[stage_names[axis]]:
                self.instrument.tiling_stages[stage_names[axis]].move_absolute_mm(position, wait=False)
        (scan_name, scan_stage), = self.instrument.scanning_stages.items()
        with self.scanning_stage_locks[scan_name]:
            scan_stage.move_absolute_mm(fov_position[2], wait=False)

    def stop_stage(self):
        """Slot for stop stage"""

        # TODO: Should we do this? I'm worried that halting is pretty time sensitive but pausing
        #  grab_fov_positions_worker shouldn't take too long
        self.grab_fov_positions_worker.pause()
        while not self.grab_fov_positions_worker.is_paused:
            sleep(.0001)
        for name, stage in {**getattr(self.instrument, 'scanning_stages', {}),
                            **getattr(self.instrument, 'tiling_stages', {})}.items():  # combine stage
            stage.halt()
        self.grab_fov_positions_worker.resume()

    def setup_fov_position(self):
        """Set up live position thread"""

        self.grab_fov_positions_worker = self.grab_fov_positions()
        self.grab_fov_positions_worker.yielded.connect(lambda pos: setattr(self.volume_widget, 'fov_position', pos))
        self.grab_fov_positions_worker.start()

    @thread_worker
    def grab_fov_positions(self):
        """Grab stage position from all stage objects and yield positions"""

        while True:  # best way to do this or have some sort of break?
            sleep(.1)
            fov_pos = [None] * 3
            for name, stage in self.instrument.tiling_stages.items():
                with self.tiling_stage_locks[name]:
                    if stage.instrument_axis in self.volume_widget.coordinate_plane:
                        fov_index = self.volume_widget.coordinate_plane.index(stage.instrument_axis)
                        position = stage.position_mm
                        # FIXME: Sometimes tigerbox yields empty stage position so return None if this happens?
                        fov_pos[fov_index] = position if position is not None \
                            else self.volume_widget.fov_position[fov_index]
                (scan_name, scan_stage), = self.instrument.scanning_stages.items()
                with self.scanning_stage_locks[scan_name]:
                    position = scan_stage.position_mm
                    fov_pos[2] = position if position is not None else self.volume_widget.fov_position[2]

            yield fov_pos  # don't yield while locked

    def toggle_grab_fov_positions(self):
        """When focus on view has changed, resume or pause grabbing stage positions"""
        # TODO: Think about locking all device locks to make sure devices aren't being communicated with?
        # TODO: Update widgets with values from hardware? Things could've changed when using the acquisition widget
        try:
            if self.main_window.isActiveWindow() and self.grab_fov_positions_worker.is_paused:
                self.grab_fov_positions_worker.resume()
            elif not self.main_window.isActiveWindow() and self.grab_fov_positions_worker.is_running:
                self.grab_fov_positions_worker.pause()
        except RuntimeError:  # Pass error when window has been closed
            pass

    def create_operation_widgets(self, device_name: str, operation_name: str, operation_specs: dict):
        """Create widgets based on operation dictionary attributes from instrument or acquisition
         :param device_name: name of device correlating to operation
         :param operation_specs: dictionary describing set up of operation
         """

        operation_type = operation_specs['type']
        operation = getattr(self.acquisition, inflection.pluralize(operation_type))[device_name][operation_name]

        specs = self.config['operation_widgets'].get(device_name, {}).get(operation_name, {})
        if specs != {} and specs.get('type', '') == operation_type:
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
        # Add label to gui
        labeled = create_widget('V', QLabel(operation_name), gui)

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
