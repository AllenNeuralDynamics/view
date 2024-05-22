from voxel.devices.camera.simulated import Camera
from view.widgets.device_widgets.camera_widget import CameraWidget
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
        if isinstance(attr, property):  # and attr.fset is not None:
            prop_dict[attr_name] = getattr(device, attr_name)

    return prop_dict


@Slot(str)
def widget_property_changed(name, device, widget):
    """Slot to signal when widget has been changed
    :param name: name of attribute and widget"""

    name_lst = name.split('.')
    #print('widget', name, ' changed to ', getattr(widget, name_lst[0]))
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    #print('Device', name, ' changed to ', getattr(device, name_lst[0]))
    for k, v in widget.property_widgets.items():
        instrument_value = getattr(device, k)
        # print(k, instrument_value)
        setattr(widget, k, instrument_value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    camera_object = Camera('')
    props = {'exposure_time_ms': 20.0,
     'pixel_type': 'mono16',
     'width_px': 1152,
     'height_px': 1152,
     'trigger':
         {'mode': 'off',
          'source': 'external',
          'polarity': 'rising'}}
    for k, v in props.items():
        setattr(camera_object, k, v)
    camera = CameraWidget(camera_object)
    camera.show()

    camera.ValueChangedInside[str].connect(
        lambda value, dev=camera_object, widget=camera,: widget_property_changed(value, dev, widget))

    sys.exit(app.exec_())
    # app = QApplication(sys.argv)
    # simulated_camera = Camera('camera')
    # camera_properties = scan_for_properties(simulated_camera)
    # print(camera_properties)
    # base = BaseDeviceWidget(Camera, "examples.resources.simulated_camera", camera_properties)
    # base.ValueChangedInside[str].connect(widget_property_changed)
    # base.show()
    #
    # t1 = threading.Thread(target=device_change, args=())
    # t1.start()
    #
    # sys.exit(app.exec_())
