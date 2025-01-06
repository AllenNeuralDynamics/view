import sys
import threading
from time import sleep

from voxel.devices.camera.simulated import Camera
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
        if isinstance(attr, property):  # and attr.fset is not None:
            prop_dict[attr_name] = getattr(device, attr_name)

    return prop_dict


def device_change():
    """_summary_"""
    for i in range(0, 100):
        if i == 25:
            print("changing exposure_time_ms")
            base.exposure_time_ms = 2500.0
        if i == 50:
            print("changing pixel_type")
            base.pixel_type = "mono16"
        if i == 75:
            print("changing roi")
            # Need to change whole dictionary to trigger update. DOES NOT WORK changing one item
            base.roi = {"width_px": 1016, "height_px": 2032, "width_offset_px": 0, "height_offest_px": 0}
        if i == 99:
            print("changing sensor_height_px")
            base.sensor_height_px = 10640 / 2
        sleep(0.1)


@Slot(str)
def widget_property_changed(name):
    """_summary_

    :param name: _description_
    :type name: _type_
    """
    name_lst = name.split(".")
    print(name, " changed to ", getattr(base, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    simulated_camera = Camera("camera")
    camera_properties = scan_for_properties(simulated_camera)
    print(camera_properties)
    base = BaseDeviceWidget(Camera, camera_properties)
    base.ValueChangedInside[str].connect(widget_property_changed)
    base.show()

    t1 = threading.Thread(target=device_change, args=())
    t1.start()

    sys.exit(app.exec_())
