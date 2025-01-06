import sys
import threading
from time import sleep

from qtpy.QtWidgets import QApplication
from tigerasi.tiger_controller import TigerController

from view.widgets.device_widgets.filter_wheel_widget import FilterWheelWidget
from voxel.devices.filter.asi import Filter
from voxel.devices.filterwheel.asi import FilterWheel


def move_filter():
    """_summary_"""
    filter_wheel.filter = "BP405"
    sleep(3)
    filter_wheel.filter = "LP638"
    sleep(3)
    BP405_filter.enable()


def widget_property_changed(name, device, widget):
    """_summary_

    :param name: _description_
    :type name: _type_
    :param device: _description_
    :type device: _type_
    :param widget: _description_
    :type widget: _type_
    """
    print("widget property changed")
    name_lst = name.split(".")
    print("widget", name, " changed to ", getattr(widget, name_lst[0]))
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    print("Device", name, " changed to ", getattr(device, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    stage = TigerController("COM4")
    filter_wheel = FilterWheel(
        stage,
        0,
        {
            "BP405": 0,
            "BP488": 1,
            "BP561": 2,
            "LP638": 3,
            "MB405/488/561/638": 4,
            "Empty1": 5,
            "Empty2": 6,
        },
    )

    BP405_filter = Filter(filter_wheel, "BP405")
    BP561_filter = Filter(filter_wheel, "BP561")
    LP638_filter = Filter(filter_wheel, "LP638")
    BP488_filter = Filter(filter_wheel, "BP488")

    widget = FilterWheelWidget(filter_wheel)
    widget.ValueChangedInside[str].connect(
        lambda value, dev=filter_wheel, gui=widget: widget_property_changed(value, dev, widget)
    )
    widget.show()

    t1 = threading.Thread(target=move_filter)
    t1.start()

    sys.exit(app.exec_())
