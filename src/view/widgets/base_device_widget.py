from qtpy.QtCore import Signal, Slot, QTimer
from qtpy.QtGui import QIntValidator, QDoubleValidator
from qtpy.QtWidgets import (
    QWidget,
    QLabel,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QMainWindow,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QSlider,
    QCheckBox
)
from inspect import currentframe
from importlib import import_module
import enum
import types
import re
import logging
import inflection
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit
from view.widgets.miscellaneous_widgets.q_scrollable_float_slider import QScrollableFloatSlider
import inspect
from schema import Schema, SchemaError
from typing import Literal

class BaseDeviceWidget(QMainWindow):
    ValueChangedOutside = Signal((str,))
    ValueChangedInside = Signal((str,))

    def __init__(self, device_type: object = None, properties: dict = {}):
        """Base widget for devices like camera, laser, stage, ect. Widget will scan properties of
        device object and create editable inputs for each if not in device_widgets class of device. If no device_widgets
        class is provided, then all properties are exposed
        :param device_type: type of class or dictionary of device object
        :param properties: dictionary contain properties displayed in widget as keys and initial values as values"""

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        super().__init__()
        self.device_type = device_type
        self.device_driver = (
            import_module(self.device_type.__module__)
            if hasattr(self.device_type, "__module__")
            else types.SimpleNamespace()
        )  # dummy driver if object is dictionary
        self.create_property_widgets(properties, "property")

        widget = create_widget("V", **self.property_widgets)
        self.setCentralWidget(widget)
        self.ValueChangedOutside[str].connect(self.update_property_widget)  # Trigger update when property value changes

    def create_property_widgets(self, properties: dict, widget_group):
        """Create input widgets based on properties
        :param properties: dictionary containing properties within a class and mapping to values
        :param widget_group: attribute name for dictionary of widgets"""

        widgets = {}
        for name, value in properties.items():
            setattr(self, name, value)  # Add device properties as widget properties
            attr = getattr(self.device_type, name, None)
            unit = f"[{getattr(attr, 'unit')}]" if getattr(attr, "unit", None) is not None else ""
            arg_type = type(value)
            search_name = arg_type.__name__ if arg_type.__name__ in dir(self.device_driver) else name.split(".")[-1]

            boxes = {"label": QLabel(label_maker(name.split(".")[-1] + f"_{unit}"))}
            if dict not in type(value).__mro__ and list not in type(value).__mro__ or type(arg_type) == enum.EnumMeta:
                # create schema validator so entries must adhere to specific format. Check to bypass ruamel types
                if float in type(value).__mro__:  # set type to float
                    setattr(self, f"{name}_schema", Schema(float))
                elif int in type(value).__mro__ and bool not in type(value).__mro__:
                    setattr(self, f"{name}_schema", Schema(int))
                elif str in type(value).__mro__:
                    setattr(self, f"{name}_schema", Schema(str))
                elif bool in type(value).__mro__:
                    setattr(self, f"{name}_schema", Schema(bool))
                else:
                    setattr(self, f"{name}_schema", Schema(type(value)))
                # Create combo boxes if there are preset options
                if input_specs := self.check_driver_variables(search_name):
                    boxes[name] = self.create_attribute_widget(name, "combo", input_specs)
                # If no found options, create an editable text box or checkbox
                else:
                    box_type = 'text' if bool not in type(value).__mro__ else 'check'
                    boxes[name] = self.create_attribute_widget(name, box_type, value)

            elif dict in type(value).__mro__:  # deal with dict like variables
                setattr(self, f"{name}_schema", Schema(create_dict_schema(value)))
                boxes[name] = create_widget(
                    "V", **self.create_property_widgets({f"{name}.{k}": v for k, v in value.items()}, name)
                )
            elif list in type(value).__mro__:  # deal with list like variables
                setattr(self, f"{name}_schema", Schema(create_list_schema(value)))
                boxes[name] = create_widget(
                    "H", **self.create_property_widgets({f"{name}.{i}": v for i, v in enumerate(value)}, name)
                )
            orientation = "H"
            if "." in name:  # see if parent list and format index label and input vertically
                parent = pathGet(self.__dict__, name.split(".")[0:-1])
                if list in type(parent).__mro__:
                    orientation = "V"
            widgets[name] = create_widget(orientation, **boxes)

            if attr is not None:  # if name is attribute of device
                widgets[name].setToolTip(attr.__doc__)  # Set tooltip to properties docstring
                if getattr(attr, "fset", None) is None:  # Constant, unchangeable attribute
                    widgets[name].setDisabled(True)

        # Add attribute of grouped widgets for easy access
        setattr(self, f"{widget_group}_widgets", widgets)
        return widgets

    def create_attribute_widget(self, name, widget_type: Literal["combo", "text", "check"], values):
        """Create a widget and create corresponding attribute
                :param name: name of property
                :param widget_type: widget type ('combo', 'text', 'check')
                :param values: input into widget"""

        # options = values.keys() if widget_type == 'combo' else values
        box = getattr(self, f"create_{widget_type}_box")(name, values)
        setattr(self, f"{name}_widget", box)  # add attribute for widget input for easy access

        return box

    def check_driver_variables(self, name: str):
        """Check if there is variable in device driver that has name of
        property to inform input widget type and values
        :param name: name of property to search for"""

        driver_vars = self.device_driver.__dict__
        for variable in driver_vars:
            search_name = inflection.pluralize(name.replace(".", "_"))
            x = re.search(variable, rf"\b{search_name}?\b", re.IGNORECASE)
            if x is not None:
                if type(driver_vars[variable]) in [dict, list]:
                    return driver_vars[variable]
                elif type(driver_vars[variable]) == enum.EnumMeta:  # if enum
                    enum_class = driver_vars[variable]
                    return {i.name: i.value for i in enum_class}

    def create_text_box(self, name, value) -> QScrollableLineEdit:
        """Convenience function to build editable text boxes and add initial value and validator
        :param name: name to emit when text is edited is changed
        :param value: initial value to add to box"""

        # TODO: better way to handle weird types that will crash QT?
        value_type = type(value)
        textbox = QScrollableLineEdit(str(value))
        textbox.editingFinished.connect(lambda: self.textbox_edited(name))
        if float in value_type.__mro__:
            validator = QDoubleValidator()
            validator.setNotation(QDoubleValidator.StandardNotation)
            validator.setDecimals(2)
            textbox.setValidator(validator)
            textbox.setValue(round(value, 2))
        elif int in value_type.__mro__:
            validator = QIntValidator()
            textbox.setValidator(validator)
        return textbox

    def textbox_edited(self, name):
        """
        Correctly set attribute after textbox has been edited
        :param name: name of property that was edited
        :return:
        """

        name_lst = name.split(".")
        parent_attr = pathGet(self.__dict__, name_lst[0:-1])
        value = getattr(self, name + "_widget").text()
        value_type = type(getattr(self, name + "_schema").schema())
        if dict in type(parent_attr).__mro__:  # name is a dictionary
            parent_attr[name_lst[-1]] = value_type(value)
        elif list in type(parent_attr).__mro__:
            parent_attr[int(name_lst[-1])] = value_type(value)
        setattr(self, name, value_type(value))
        self.ValueChangedInside.emit(name)

    def create_check_box(self, name, value: bool) -> QCheckBox:
        """Convenience function to build checkboxes
        :param name: name to emit when text is edited is changed
        :param value: initial value to add to box
        """

        checkbox = QCheckBox()
        checkbox.setChecked(value)
        checkbox.toggled.connect(lambda state: self.check_box_toggled(name, state))
        return checkbox

    def check_box_toggled(self, name: str, state: bool):
        """
        Correctly set attribute after combobox has been toggles
        :param name: name of property that was edited
        :param state: state of checkbox
        :return:
        """

        name_lst = name.split(".")
        parent_attr = pathGet(self.__dict__, name_lst[0:-1])
        if dict in type(parent_attr).__mro__:  # name is a dictionary
            parent_attr[name_lst[-1]] = state
        elif list in type(parent_attr).__mro__:
            parent_attr[int(name_lst[-1])] = state
        setattr(self, name, state)
        self.ValueChangedInside.emit(name)

    def create_combo_box(self, name, items):
        """Convenience function to build combo boxes and add items
        :param name: name to emit when combobox index is changed
        :param items: items to add to combobox"""

        options = items.keys() if hasattr(items, "keys") else items
        box = QComboBox()
        box.addItems([str(x) for x in options])
        box.currentTextChanged.connect(lambda value: self.combo_box_changed(value, name))
        box.setCurrentText(str(getattr(self, name)))

        return box

    def combo_box_changed(self, value, name):
        """
        Correctly set attribute after combobox index has been changed
        :param value: new value combobox has been changed to
        :param name: name of property that was edited
        :return:
        """

        name_lst = name.split(".")

        parent_attr = pathGet(self.__dict__, name_lst[0:-1])
        value_type = type(getattr(self, name + "_schema").schema())

        if dict in type(parent_attr).__mro__:  # name is a dict
            parent_attr[str(name_lst[-1])] = value_type(value)
        elif list in type(parent_attr).__mro__:  # name is a list

            parent_attr[int(name_lst[-1])] = value_type(value)
        setattr(self, name, value_type(value))
        self.ValueChangedInside.emit(name)

    @Slot(str)
    def update_property_widget(self, name):
        """Update property widget. Triggers when attribute has been changed outside of widget
        :param name: name of attribute and widget"""

        value = getattr(self, name, None)
        if dict not in type(value).__mro__ and list not in type(value).__mro__:  # not a dictionary or list like value
            self._set_widget_text(name, value)
        elif dict in type(value).__mro__:
            for k, v in value.items():  # multiple widgets to set values for
                setattr(self, f"{name}.{k}", v)
                self.update_property_widget(f"{name}.{k}")
        else:
            for i, item in enumerate(value):
                if hasattr(self, f"{name}.{i}"):  # can't handle added indexes yet
                    setattr(self, f"{name}.{i}", item)
                    self.update_property_widget(f"{name}.{i}")

    def _set_widget_text(self, name, value):
        """Set widget text if widget is QLineEdit or QCombobox
        :param name: widget name to set text to
        :param value: value of text"""

        if hasattr(self, f"{name}_widget"):
            widget = getattr(self, f"{name}_widget")
            widget.blockSignals(True)  # block signal indicating change since changing internally
            if hasattr(widget, "setText") and hasattr(widget, "validator"):
                if widget.validator() is None:
                    widget.setText(str(value))
                elif type(widget.validator()) == QIntValidator:
                    widget.setValue(round(value))
                elif type(widget.validator()) == QDoubleValidator:
                    widget.setValue(str(round(value, widget.validator().decimals())))
            elif type(widget) in [QSpinBox, QDoubleSpinBox, QSlider, QScrollableFloatSlider]:
                widget.setValue(value)
            elif type(widget) == QComboBox:
                widget.setCurrentText(str(value))
            elif hasattr(widget, 'setChecked'):
                widget.setChecked(value)
            widget.blockSignals(False)
        else:
            self.log.warning(f"{name} doesn't correspond to a widget")

    def __setattr__(self, name, value):
        """Overwrite __setattr__ to trigger update if property is changed"""
        # check that values adhere to schema of correlating variable
        if f"{name}_schema" in self.__dict__.keys():
            schema = getattr(self, f"{name}_schema")
            valid = check_if_valid(schema, value)
            if not valid:
                self.log.warning(
                    f"Attribute {name} cannot be set to {value} since it does not adhere to the schema" f" {schema}"
                )
                return
        self.__dict__[name] = value
        if currentframe().f_back.f_locals.get("self", None) != self:  # call from outside so update widgets
            self.ValueChangedOutside.emit(name)


# Convenience Functions
def create_dict_schema(dictionary: dict):
    """
    Helper function to create a schema for a dictionary object
    :param dictionary: dictionary to create schema from
    :return: schema of dictionary
    """
    schema = {}
    for key, value in dictionary.items():
        if dict in type(value).__mro__:
            schema[key] = create_dict_schema(value)
        elif list in type(value).__mro__:
            schema[key] = create_list_schema(value)
        else:
            schema[key] = type(value)

    return schema


def create_list_schema(list_ob: dict):
    """
    Helper function to create a schema for a list object
    :param list_ob: list to create schema from
    :return: schema of list_ob
    """
    schema = []
    for value in list_ob:
        if dict in type(value).__mro__:
            schema.append(create_dict_schema(value))
        elif list in type(value).__mro__:
            schema.append(create_list_schema(value))
        else:
            schema.append(type(value))
    return schema


def check_if_valid(schema, item):
    try:
        schema.validate(item)
        return True
    except SchemaError:
        return False


def create_widget(struct: str, *args, **kwargs):
    """Creates either a horizontal or vertical layout populated with widgets
    :param struct: specifies whether the layout will be horizontal, vertical, or combo
    :param kwargs: all widgets contained in layout
    :return QWidget()"""

    layouts = {"H": QHBoxLayout(), "V": QVBoxLayout()}
    widget = QWidget()
    if struct == "V" or struct == "H":
        layout = layouts[struct]
        for arg in [*kwargs.values(), *args]:
            try:
                layout.addWidget(arg)
            except TypeError:
                layout.addLayout(arg)

    elif struct == "VH" or "HV":
        bin0 = {}
        bin1 = {}
        j = 0
        for v in [*kwargs.values(), *args]:
            bin0[str(v)] = v
            j += 1
            if j == 2:
                j = 0
                bin1[str(v)] = create_widget(struct=struct[0], **bin0)
                bin0 = {}
        return create_widget(struct=struct[1], **bin1)

    layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(layout)
    return widget


def label_maker(string):
    """Removes underscores from variable names and capitalizes words
    :param string: string to make label out of
    """

    possible_units = ["mm", "um", "px", "mW", "W", "ms", "C", "V", "us", "s", "ms", "uL", "min", "g", "mL"]
    label = string.split("_")
    label = [words.capitalize() for words in label]

    for i, word in enumerate(label):
        for unit in possible_units:
            if unit.lower() == word.lower():  # TODO: Consider using regular expression here for better results?
                label[i] = f"[{unit}]"

    label = " ".join(label)
    return label


def pathGet(iterable: dict or list, path: list):
    """Based on list of nested dictionary keys or list indices, return inner dictionary"""

    for k in path:
        k = int(k) if type(iterable) == list else k
        iterable = iterable.__getitem__(k)
    return iterable


def scan_for_properties(device):
    """Scan for properties with setters and getters in class and return dictionary
    :param device: object to scan through for properties
    """

    prop_dict = {}
    for attr_name in dir(device):
        try:
            attr = getattr(type(device), attr_name, None)
            if isinstance(attr, property) or isinstance(inspect.unwrap(attr), property):
                prop_dict[attr_name] = getattr(device, attr_name, None)
        except ValueError:  # Some attributes in processes raise ValueError if not started
            pass

    return prop_dict


def disable_button(button, pause=1000):
    """Function to disable button clicks for a period of time to avoid crashing gui"""

    button.setEnabled(False)
    QTimer.singleShot(pause, lambda: button.setDisabled(False))
