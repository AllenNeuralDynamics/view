from view.widgets.examples.resources.imaris import Writer
from view.widgets.base_device_widget import BaseDeviceWidget
from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot


def scan_for_properties(device):
    """Scan for properties with setters and getters in class and return dictionary
    :param device: object to scan through for properties
    """

    prop_dict = {}
    for attr_name in dir(device):
        attr = getattr(type(device), attr_name, None)
        if isinstance(attr, property) and getattr(device, attr_name, None) is not None:
            prop_dict[attr_name] = getattr(device, attr_name)

    return prop_dict

@Slot(str)
def widget_property_changed(name):
    """Slot to signal when widget has been changed
    :param name: name of attribute and widget"""

    name_lst = name.split('.')
    value = getattr(base, name_lst[0])
    if len(name_lst) == 1:  # name refers to attribute
        setattr(writer, name, value)
    else:  # name is a dictionary and key pair split by .
        getattr(writer, name_lst[0]).__setitem__(name_lst[1], value)
    print(name, ' changed to ', getattr(writer, name_lst[0]))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    writer = Writer()
    writer.compression = 'lz4shuffle'
    writer.data_type = 'uint16'
    writer.path = r"C:\Users\micah.woodard\Downloads"
    writer.color = "#00ff92"
    writer_properties = scan_for_properties(writer)

    base = BaseDeviceWidget(Writer, writer_properties)
    base.ValueChangedInside[str].connect(widget_property_changed)
    base.data_type = 'uint8'

    sys.exit(app.exec_())
