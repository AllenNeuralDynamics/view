import os
import sys
from pathlib import Path

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication

from view.widgets.base_device_widget import BaseDeviceWidget
from voxel.acquisition import Acquisition
from voxel.instruments import Instrument

RESOURCES_DIR = Path(os.path.dirname(os.path.realpath(__file__))) / "resources"
ACQUISITION_YAML = RESOURCES_DIR / "test_acquisition.yaml"
INSTRUMENT_YAML = RESOURCES_DIR / "simulated_instrument.yaml"


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
        if isinstance(attr, property):  # and attr.fset is not None:
            prop_dict[attr_name] = getattr(device, attr_name)

    return prop_dict


def set_up_guis(devices, device_type):
    """_summary_

    :param devices: _description_
    :type devices: _type_
    :param device_type: _description_
    :type device_type: _type_
    :return: _description_
    :rtype: _type_
    """
    guis = {}
    for name, device in devices.items():
        properties = scan_for_properties(device)
        # TODO: better way to find out what module
        guis[name] = BaseDeviceWidget(type(device), properties)
        guis[name].setWindowTitle(f"{device_type} {name}")
        guis[name].ValueChangedInside[str].connect(
            lambda value, dev=device, widget=guis[name],: widget_property_changed(value, dev, widget)
        )
        guis[name].show()
    return guis


@Slot(str)
def widget_property_changed(name, device, widget):
    """_summary_

    :param name: _description_
    :type name: _type_
    :param device: _description_
    :type device: _type_
    :param widget: _description_
    :type widget: _type_
    """
    name_lst = name.split(".")
    print("widget", name, " changed to ", getattr(widget, name_lst[0]))
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    print("Device", name, " changed to ", getattr(device, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # instrument
    instrument = Instrument(INSTRUMENT_YAML)

    laser_ui = set_up_guis(instrument.lasers, "laser")
    combiner_ui = set_up_guis(instrument.combiners, "combiner")
    camera_ui = set_up_guis(instrument.cameras, "camera")

    # acquisition
    acquisition = Acquisition(instrument, ACQUISITION_YAML)

    sys.exit(app.exec_())
