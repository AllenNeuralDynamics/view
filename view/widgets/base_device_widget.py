from qtpy.QtCore import Signal, Slot, QTimer
from qtpy.QtGui import QIntValidator, QDoubleValidator
from qtpy.QtWidgets import QWidget, QLabel, QComboBox, QHBoxLayout, QVBoxLayout, QMainWindow
from inspect import currentframe
from importlib import import_module
import enum
import types
import re
import logging
import inflection
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit
import inspect


class BaseDeviceWidget(QMainWindow):
    ValueChangedOutside = Signal((str,))
    ValueChangedInside = Signal((str,))

    def __init__(self, device_type, properties: dict):
        """Base widget for devices like camera, laser, stage, ect. Widget will scan properties of
        device object and create editable inputs for each if not in device_widgets class of device. If no device_widgets
        class is provided, then all properties are exposed
        :param device_type: type of class or dictionary of device object
        :param properties: dictionary contain properties displayed in widget as keys and initial values as values"""

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        super().__init__()
        self.device_type = device_type
        self.device_driver = import_module(self.device_type.__module__) if not hasattr(self.device_type, 'keys') \
            else types.SimpleNamespace()  # dummy driver if object is dictionary
        self.create_property_widgets(properties, 'property')

        widget = create_widget('V', **self.property_widgets)
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
            unit = f"[{getattr(attr, 'unit')}]" if getattr(attr, 'unit', None) is not None else ''
            input_widgets = {'label': QLabel(label_maker(name.split('.')[-1] + f'_{unit}'))}
            arg_type = type(value)
            search_name = arg_type.__name__ if arg_type.__name__ in dir(self.device_driver) else name

            # Create combo boxes if there are preset options
            if input_specs := self.check_driver_variables(search_name):
                widget_type = 'combo'
            # If no found options, create an editable text box
            else:
                input_specs = value
                widget_type = 'text'
            boxes = {}
            if not hasattr(value, 'keys') and type(value) != list or type(arg_type) == enum.EnumMeta:
                boxes[name] = self.create_attribute_widget(name, widget_type, input_specs)

            elif hasattr(value, 'keys') or type(value) == list:  # deal with dict like variables or lists
                for i, item in enumerate(input_specs):
                    k = item if hasattr(value, 'keys') else i   # key is index if list
                    v = input_specs[item] if hasattr(value, 'keys') else item

                    # create attribute
                    setattr(self, f"{name}.{k}", getattr(self, name)[k])
                    label = QLabel(label_maker(f'{k}_{unit}'))

                    # if value has an item that is a dictionary but the widget type is not a combo box,
                    # unique widgets should be made for this dictionary
                    if hasattr(v, 'keys') and widget_type != 'combo':
                        box = create_widget('V', **self.create_property_widgets(
                            {f'{name}.{k}.{kv}': vv for kv, vv in v.items()}, f'{name}.{k}'))  # creating unique keys for attributes so they don't get overwritten
                    elif type(v) == list:
                        box = create_widget('V', **self.create_property_widgets(
                            {f'{name}.{k}.{i}': vv for i, vv in enumerate(v)},
                            f'{name}.{k}'))  # creating unique keys for attributes so they don't get overwritten
                    else:
                        box = self.create_attribute_widget(f"{name}.{k}", widget_type, v)

                    boxes[str(k)] = create_widget('V', label, box)

            input_widgets = {**input_widgets, 'widget': create_widget('H', **boxes)}
            widgets[name] = create_widget(struct='H', **input_widgets)

            if attr is not None:  # if name is attribute of device
                widgets[name].setToolTip(attr.__doc__)  # Set tooltip to properties docstring
                if getattr(attr, 'fset', None) is None:  # Constant, unchangeable attribute
                    widgets[name].setDisabled(True)

        # Add attribute of grouped widgets for easy access
        setattr(self, f'{widget_group}_widgets', widgets)
        return widgets

    def create_attribute_widget(self, name, widget_type, values):
        """Create a widget and create corresponding attribute
                :param name: name of property
                :param widget_type: widget type (QLineEdit or QCombobox)
                :param values: input into widget"""

        # options = values.keys() if widget_type == 'combo' else values
        box = getattr(self, f'create_{widget_type}_box')(name, values)
        setattr(self, f"{name}_widget", box)  # add attribute for widget input for easy access

        return box

    def check_driver_variables(self, name: str):
        """Check if there is variable in device driver that has name of
        property to inform input widget type and values
        :param name: name of property to search for"""

        driver_vars = self.device_driver.__dict__
        for variable in driver_vars:
            x = re.search(variable, fr'\b{inflection.pluralize(name)}?\b', re.IGNORECASE)
            if x is not None:
                if type(driver_vars[variable]) in [dict, list]:
                    return driver_vars[variable]
                elif type(driver_vars[variable]) == enum.EnumMeta:  # if enum
                    enum_class = getattr(self.device_driver, name)
                    return {i.name: i.value for i in enum_class}

    def create_text_box(self, name, value):
        """Convenience function to build editable text boxes and add initial value and validator
                :param name: name to emit when text is edited is changed
                :param value: initial value to add to box"""

        # TODO: better way to handle weird types that will crash QT?
        value_type = type(value)
        textbox = QScrollableLineEdit(str(value))
        name_lst = name.split('.')
        parent_attr = pathGet(self.__dict__, name_lst[0:-1])
        if hasattr(parent_attr, 'keys'):  # name is a dictionary and key pair split by .
            # Must find dictionary each editing finish
            textbox.editingFinished.connect(lambda:
                                            pathGet(self.__dict__, name_lst[0:-1]).
                                            __setitem__(name_lst[-1], value_type(textbox.text())))
        elif type(parent_attr) == list:
            textbox.editingFinished.connect(lambda: parent_attr.__setitem__(int(name_lst[-1]),
                                                                            value_type(textbox.text())))
        textbox.editingFinished.connect(lambda: setattr(self, name, value_type(textbox.text())))
        textbox.editingFinished.connect(lambda: self.ValueChangedInside.emit(name))
        if issubclass(value_type, float) or issubclass(value_type, int):
            validator = QIntValidator() if issubclass(value_type, int) else QDoubleValidator()
            textbox.setValidator(validator)

        return textbox

    def create_combo_box(self, name, items):
        """Convenience function to build combo boxes and add items
        :param name: name to emit when combobox index is changed
        :param items: items to add to combobox"""

        options = items.keys() if hasattr(items, 'keys') else items
        box = QComboBox()
        box.addItems([str(x) for x in options])
        name_lst = name.split('.')
        if len(name_lst) != 1:  # name is a dictionary and key pair split by .
            box.currentTextChanged.connect(lambda value:
                                           pathGet(self.__dict__, name_lst[0:-1]).__setitem__(name_lst[-1], value))
        box.currentTextChanged.connect(lambda value: setattr(self, name, value))
        box.setCurrentText(str(getattr(self, name)))
        # emit signal when changed so outside listener can update. needs to be after changing attribute
        box.currentTextChanged.connect(lambda: self.ValueChangedInside.emit(name))
        return box

    @Slot(str)
    def update_property_widget(self, name):
        """Update property widget. Triggers when attribute has been changed outside of widget
        :param name: name of attribute and widget"""

        value = getattr(self, name, None)
        if not hasattr(value, 'keys') and type(value) != list:  # not a dictionary or list like value
            self._set_widget_text(name, value)
        elif hasattr(value, 'keys'):
            for k, v in value.items():  # multiple widgets to set values for
                setattr(self, f'{name}.{k}', v)
                self.update_property_widget(f'{name}.{k}')
        else:
            for i, item in enumerate(value):
                if hasattr(self, f'{name}.{i}'):  # can't handle added indexes yet
                    setattr(self, f'{name}.{i}', item)
                    self.update_property_widget(f'{name}.{i}')

    def _set_widget_text(self, name, value):
        """Set widget text if widget is QLineEdit or QCombobox
        :param name: widget name to set text to
        :param value: value of text"""

        if hasattr(self, f'{name}_widget'):
            widget = getattr(self, f'{name}_widget')
            widget.blockSignals(True)  # block signal indicating change since changing internally
            if hasattr(widget, 'setText'):
                widget.setText(str(value))
            elif hasattr(widget, 'setCurrentText'):
                widget.setCurrentText(str(value))
            widget.blockSignals(False)
        else:
            self.log.debug(f"{name} doesn't correspond to a widget")

    def __setattr__(self, name, value):
        """Overwrite __setattr__ to trigger update if property is changed"""

        self.__dict__[name] = value
        if currentframe().f_back.f_locals.get('self', None) != self:  # call from outside so update widgets
            self.ValueChangedOutside.emit(name)


# Convenience Functions
def create_widget(struct: str, *args, **kwargs):
    """Creates either a horizontal or vertical layout populated with widgets
    :param struct: specifies whether the layout will be horizontal, vertical, or combo
    :param kwargs: all widgets contained in layout"""

    layouts = {'H': QHBoxLayout(), 'V': QVBoxLayout()}
    widget = QWidget()
    if struct == 'V' or struct == 'H':
        layout = layouts[struct]
        for arg in [*kwargs.values(), *args]:
            try:
                layout.addWidget(arg)
            except TypeError:
                layout.addLayout(arg)

    elif struct == 'VH' or 'HV':
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

    possible_units = ['mm', 'um', 'px', 'mW', 'W', 'ms', 'C', 'V', 'us']
    label = string.split('_')
    label = [words.capitalize() for words in label]

    for i, word in enumerate(label):
        for unit in possible_units:
            if unit.lower() == word.lower():  # TODO: Consider using regular expression here for better results?
                label[i] = f'[{unit}]'

    label = " ".join(label)
    return label


def pathGet(iterable: dict or list, path: list):
    """Based on list of nested dictionary keys or list indices, return inner dictionary"""

    for k in path:
        k = int(k) if type(iterable)==list else k
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
