import sys

from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication

from view.widgets.device_widgets.laser_widget import LaserWidget
from voxel.devices.laser.simulated import SimulatedLaser


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
    name_lst = name.split('.')
    print('widget', name, ' changed to ', getattr(widget, name_lst[0]))
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    print('Device', name, ' changed to ', getattr(device, name_lst[0]))
    for k, v in widget.property_widgets.items():
        instrument_value = getattr(device, k)
        print(k, instrument_value)
        setattr(widget, k, instrument_value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    laser_object = SimulatedLaser(id='', wavelength=488)
    laser = LaserWidget(laser_object, color='blue', advanced_user=False)
    laser.show()

    laser.ValueChangedInside[str].connect(
        lambda value, dev=laser_object, widget=laser, : widget_property_changed(value, dev, widget))
    laser.setWindowTitle('Laser')
    sys.exit(app.exec_())
