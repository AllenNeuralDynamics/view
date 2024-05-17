from view.widgets.base_device_widget import BaseDeviceWidget
from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot
from voxel.instruments import Instrument
from voxel.acquisition import Acquisition
from pathlib import Path
import os

RESOURCES_DIR = (
        Path(os.path.dirname(os.path.realpath(__file__))) / "resources"
)
ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'
INSTRUMENT_YAML = RESOURCES_DIR / 'simulated_instrument.yaml'

def scan_for_properties(device):
    """Scan for properties with setters and getters in class and return dictionary
    :param device: object to scan through for properties
    """

    prop_dict = {}
    for attr_name in dir(device):
        attr = getattr(type(device), attr_name, None)
        if isinstance(attr, property):  # and attr.fset is not None:
            prop_dict[attr_name] = getattr(device, attr_name)

    return prop_dict


def set_up_guis(devices, device_type):
    guis = {}
    for name, device in devices.items():
        properties = scan_for_properties(device)
        # TODO: better way to find out what module
        guis[name] = BaseDeviceWidget(type(device), properties)
        guis[name].setWindowTitle(f'{device_type} {name}')
        guis[name].ValueChangedInside[str].connect(
            lambda value, dev=device, widget=guis[name],: widget_property_changed(value, dev, widget))
        guis[name].show()
    return guis


@Slot(str)
def widget_property_changed(name, device, widget):
    """Slot to signal when widget has been changed
    :param name: name of attribute and widget"""

    name_lst = name.split('.')
    print('widget', name, ' changed to ', getattr(widget, name_lst[0]))
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    # if len(name_lst) == 1:  # name refers to attribute
    #     setattr(device, name, value)
    # else:  # name is a dictionary and key pair split by .
    #     dictionary = getattr(device, name_lst[0])
    #     # new = {k:getattr(widget, f'{name_lst[0]}.{k}') for k in dictionary.keys()}
    #     # print(new)
    #     for k in dictionary.keys():
    #         print(k, dir(widget))
    #         print(k, getattr(widget, f'{name_lst[0]}.{k}_'))

    print('Device', name, ' changed to ', getattr(device, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # instrument
    instrument = Instrument(INSTRUMENT_YAML)

    laser_ui = set_up_guis(instrument.lasers, 'laser')
    combiner_ui = set_up_guis(instrument.combiners, 'combiner')
    camera_ui = set_up_guis(instrument.cameras, 'camera')

    # acquisition
    acquisition = Acquisition(instrument, ACQUISITION_YAML)

    # simulated_camera = Camera('camera')
    # camera_properties = scan_for_properties(simulated_camera)
    # print(camera_properties)
    # base = BaseDeviceWidget(Camera, "examples.resources.simulated_camera", camera_properties)
    # base.ValueChangedInside[str].connect(widget_property_changed)

    # t1 = threading.Thread(target=device_change, args=())
    # t1.start()

    sys.exit(app.exec_())
