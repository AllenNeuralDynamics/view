from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties
from qtpy.QtWidgets import QWidget
from typing import Callable

class MetadataWidget(BaseDeviceWidget):
    """Widget for handling metadata class"""
    def __init__(self, metadata_class, advanced_user: bool = True) -> None:
        """
        :param metadata_class: class to create widget out of
        :param advanced_user: future use argument to determine what should be shown
        """

        properties = scan_for_properties(metadata_class)
        self.metadata_class = metadata_class
        super().__init__(type(metadata_class), properties)

        self.metadata_class = metadata_class
        self.property_widgets.get('acquisition_name_format',
                                  QWidget()).hide()  # hide until BaseClassWidget can handle lists

        # wrap property setters that are in acquisition_name_format so acquisition name update when changed
        for name in getattr(self, 'acquisition_name_format', []) + \
                    ['date_format' if hasattr(self, 'date_format') else None] + \
                    ['delimiter' if hasattr(self, 'delimiter') else None]:
            if name is not None:
                prop = getattr(type(metadata_class), name)
                prop_setter = getattr(prop, 'fset')
                filter_getter = getattr(prop, 'fget')
                setattr(type(metadata_class), name,
                        property(filter_getter, self.name_property_change_wrapper(prop_setter)))

    def name_property_change_wrapper(self, func: Callable) -> Callable:
        """Wrapper function that emits a signal when property setters that are in acquisition_name_format is called
        :param func: function to wrap
        :return: wrapped input function
        """
        def wrapper(object, value):
            func(object, value)
            self.acquisition_name = self.metadata_class.acquisition_name
            self.update_property_widget('acquisition_name')

        return wrapper
