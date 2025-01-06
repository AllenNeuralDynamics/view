from typing import Callable

from qtpy.QtWidgets import QWidget

from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties


class MetadataWidget(BaseDeviceWidget):
    """
    Widget for handling metadata class.
    """

    def __init__(self, metadata_class, advanced_user: bool = True) -> None:
        """_summary_

        :param metadata_class: _description_
        :type metadata_class: _type_
        :param advanced_user: _description_, defaults to True
        :type advanced_user: bool, optional
        """
        properties = scan_for_properties(metadata_class)
        self.metadata_class = metadata_class
        super().__init__(type(metadata_class), properties)

        self.metadata_class = metadata_class
        self.property_widgets.get(
            "acquisition_name_format", QWidget()
        ).hide()  # hide until BaseClassWidget can handle lists

        # wrap property setters that are in acquisition_name_format so acquisition name update when changed
        for name in (
            getattr(self, "acquisition_name_format", [])
            + ["date_format" if hasattr(self, "date_format") else None]
            + ["delimiter" if hasattr(self, "delimiter") else None]
        ):
            if name is not None:
                prop = getattr(type(metadata_class), name)
                prop_setter = getattr(prop, "fset")
                filter_getter = getattr(prop, "fget")
                setattr(
                    type(metadata_class), name, property(filter_getter, self.name_property_change_wrapper(prop_setter))
                )

    def name_property_change_wrapper(self, func: Callable) -> Callable:
        """_summary_

        :param func: _description_
        :type func: Callable
        :return: _description_
        :rtype: Callable
        """

        def wrapper(object, value):
            """_summary_

            :param object: _description_
            :type object: _type_
            :param value: _description_
            :type value: _type_
            """
            func(object, value)
            self.acquisition_name = self.metadata_class.acquisition_name
            self.update_property_widget("acquisition_name")

        return wrapper
