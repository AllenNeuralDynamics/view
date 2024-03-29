from pathlib import Path
import logging
from ruamel.yaml import YAML
import importlib
from device_widgets.base_device_widget import BaseDeviceWidget, create_widget, pathGet, label_maker, \
    scan_for_properties, disable_button
from qtpy.QtCore import Slot
import inflection


class AcquisitionView:
    """"Class to act as a general acquisition view model to voxel instrument"""

    def __init__(self, acquisition, config_path: Path, log_level='INFO'):

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)

        self.acquisition = acquisition
        self.config = YAML(typ='safe', pure=True).load(
            config_path)  # TODO: maybe bulldozing comments but easier, also do we need a config for this

        for device_name, operation_dictionary in self.acquisition.config['acquisition']['operations'].items():
            for operation_name, operation_specs in operation_dictionary.items():
                self.create_operation_widgets(device_name, operation_name, operation_specs)

        # setup additional widgets
        self.create_metadata_widget()

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
