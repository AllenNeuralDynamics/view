from voxel.devices.camera.simulated import SimulatedCamera
from view.widgets.device_widgets.camera_widget import CameraWidget
from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot


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
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    for k, v in widget.property_widgets.items():
        instrument_value = getattr(device, k)
        setattr(widget, k, instrument_value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    camera_object = SimulatedCamera("")
    props = {
        "exposure_time_ms": 20.0,
        "pixel_type": "mono16",
        "width_px": 1152,
        "height_px": 1152,
        "um_px": 1.0
    }
    for k, v in props.items():
        setattr(camera_object, k, v)
    camera = CameraWidget(camera_object)
    camera.setWindowTitle("Camera")
    camera.show()

    camera.ValueChangedInside[str].connect(
        lambda value, dev=camera_object, widget=camera, : widget_property_changed(value, dev, widget)
    )

    sys.exit(app.exec_())
