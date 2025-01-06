import sys

from voxel.writers.imaris import ImarisWriter
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication

from view.widgets.base_device_widget import BaseDeviceWidget


def scan_for_properties(device):
    """_summary_

    :param device: _description_
    :type device: _type_
    :return: _description_
    :rtype: _type_
    """
    prop_dict = {}
    for attr_name in dir(device):
        attr = getattr(type(device), attr_name, None)
        if isinstance(attr, property) and getattr(device, attr_name, None) is not None:
            prop_dict[attr_name] = getattr(device, attr_name)

    return prop_dict


@Slot(str)
def widget_property_changed(name):
    """_summary_

    :param name: _description_
    :type name: _type_
    """
    name_lst = name.split(".")
    value = getattr(base, name_lst[0])
    if len(name_lst) == 1:  # name refers to attribute
        setattr(writer, name, value)
    else:  # name is a dictionary and key pair split by .
        getattr(writer, name_lst[0]).__setitem__(name_lst[1], value)
    print(name, " changed to ", getattr(writer, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    writer = ImarisWriter()
    writer.compression = "lz4shuffle"
    writer.data_type = "uint16"
    writer.path = "."
    writer.color = "#00ff92"
    writer_properties = scan_for_properties(writer)

    base = BaseDeviceWidget(Writer, writer_properties)
    base.ValueChangedInside[str].connect(widget_property_changed)
    base.data_type = "uint8"

    sys.exit(app.exec_())
