from pathlib import Path
import logging
from ruamel.yaml import YAML
import importlib
from instrument_widgets.base_device_widget import BaseDeviceWidget, scan_for_properties
from instrument_widgets.acquisition_widgets.grid_widget import GridWidget
from qtpy.QtCore import Slot
import inflection
from threading import Lock, Thread
from time import sleep
from napari.qt.threading import thread_worker, create_worker


class AcquisitionView:
    """"Class to act as a general acquisition view model to voxel instrument"""

    def __init__(self, acquisition, config_path: Path, log_level='INFO'):

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)

        # Locks
        self.stage_lock = Lock()

        # Eventual widgets
        self.grid_widget = None
        self.metadata_widget = None

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
        self.create_metadata_widget()
        self.create_grid_plan_widget()

        # setup stage thread
        self.setup_live_position()

    def create_grid_plan_widget(self):
        """Create widget to visualize acquisition grid"""

        specs = self.config['operation_widgets'].get('grid_widget', {})
        kwds = specs.get('init', {})
        coordinate_plane = kwds.get('coordinate_plane', ['x', 'y'])
        stages = {stage.instrument_axis: stage for stage in self.instrument.tiling_stages.values()}
        with self.stage_lock:
            kwds['limits'] = {axis: stages[axis].limits for axis in coordinate_plane}
        self.grid_widget = GridWidget(**kwds)  # TODO: Try and tie it to camera?
        self.grid_widget.fovMoved.connect(self.move_stage)
        self.grid_widget.show()

    def move_stage(self, fov_position):
        """Slot for moving stage when fov_position is changed internally by grid_widget"""

        #self.grab_fov_positions_worker.yielded.disconnect()
        stages = {stage.instrument_axis: stage for stage in self.instrument.tiling_stages.values()}
        # Move stages
        for axis, position in zip(self.grid_widget.coordinate_plane, fov_position):
            with self.stage_lock:
                stages[axis].move_absolute(position, wait='False')



    def create_metadata_widget(self):
        """Create custom widget for metadata in config"""

        acquisition_properties = dict(self.acquisition.config['acquisition']['metadata'])
        self.metadata_widget = BaseDeviceWidget(acquisition_properties, acquisition_properties)
        self.metadata_widget.ValueChangedInside[str].connect(lambda name:
                                                             self.acquisition.config['acquisition'][
                                                                 'metadata'].__setitem__(name,
                                                                                         getattr(self.metadata_widget,
                                                                                                 name)))
        for name, widget in self.metadata_widget.property_widgets.items():
            widget.setToolTip('')  # reset tooltips
        self.metadata_widget.setWindowTitle(f'Metadata')
        self.metadata_widget.show()

    def setup_live_position(self):
        """Set up live position thread"""

        self.grab_fov_positions_worker = self.grab_fov_positions()
        self.grab_fov_positions_worker.yielded.connect(lambda pos: setattr(self.grid_widget, 'fov_position', pos))
        self.grab_fov_positions_worker.start()

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
            gui = BaseDeviceWidget(type(operation), properties)

        # if gui is BaseDeviceWidget or inherits from it
        if type(gui) == BaseDeviceWidget or BaseDeviceWidget in type(gui).__bases__:
            # Hook up widgets to device_property_changed
            gui.ValueChangedInside[str].connect(
                lambda value, op=operation, widget=gui:
                self.operation_property_changed(value, op, widget))

        # add ui to widget dictionary
        if not hasattr(self, f'{operation_type}_widgets'):
            setattr(self, f'{operation_type}_widgets', {device_name: {}})
        elif not getattr(self, f'{operation_type}_widgets').get(device_name, False):
            getattr(self, f'{operation_type}_widgets')[device_name] = {}
        getattr(self, f'{operation_type}_widgets')[device_name][operation_name] = gui

        # TODO: Do we need this?
        for subdevice_name, suboperation_dictionary in operation_specs.get('subdevices', {}).items():
            for suboperation_name, suboperation_specs in suboperation_dictionary.items():
                self.create_operation_widgets(subdevice_name, suboperation_name, suboperation_specs)

        gui.setWindowTitle(f'{device_name} {operation_type} {operation_name}')
        gui.show()

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

    @thread_worker
    def grab_fov_positions(self):
        """Grab stage position from all stage objects and yeild positions"""

        while True:  # best way to do this or have some sort of break?
            sleep(.1)
            fov_pos = [None]*2
            for name, stage in self.instrument.tiling_stages.items():  # combine stage
                with self.stage_lock:
                    if stage.instrument_axis in self.grid_widget.coordinate_plane:
                        fov_index = self.grid_widget.coordinate_plane.index(stage.instrument_axis)
                        fov_pos[fov_index] = stage.position[stage.instrument_axis]  # don't yield while locked

            yield fov_pos
