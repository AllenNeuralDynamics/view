from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, scan_for_properties
from qtpy.QtWidgets import QPushButton, QStyle, QWidget
from qtpy.QtCore import Qt


class MetadataWidget(BaseDeviceWidget):

    def __init__(self, metadata_class, advanced_user: bool = True):
        """Widget for handling metadata class"""

        properties = scan_for_properties(metadata_class)
        self.metadata_class = metadata_class
        super().__init__(type(metadata_class), properties)

        self.metadata_class = metadata_class
        self.property_widgets.get('acquisition_name_format',
                                  QWidget()).hide()  # hide until BaseClassWidget can handle lists

        # wrap property setters that are in acquisition_name_format so acquisition name update when changed
        for name in getattr(self, 'acquisition_name_format', []):
            prop = getattr(type(metadata_class), name)
            prop_setter = getattr(prop, 'fset')
            filter_getter = getattr(prop, 'fget')
            setattr(type(metadata_class),name, property(filter_getter, self.name_property_change_wrapper(prop_setter)))

    def name_property_change_wrapper(self, func):
        """Wrapper function that emits a signal when property setters that are in acquisition_name_format is called"""
        def wrapper(object, value):
            func(object, value)
            self.acquisition_name = self.metadata_class.acquisition_name
            self.update_property_widget('acquisition_name')
        return wrapper
