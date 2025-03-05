import sys
from time import sleep

from qtpy.QtWidgets import QApplication

from view.widgets.device_widgets.filter_wheel_widget import FilterWheelWidget
from voxel.devices.filter.simulated import Filter
from voxel.devices.filterwheel.simulated import SimulatedFilterWheel


def move_filter():
    """_summary_"""
    widget.filter = "BP561"
    sleep(3)
    widget.filter = "MB405/488/561/638"
    sleep(3)
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
    name_lst = name.split(".")
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    print("Device", name, " changed to ", getattr(device, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    filter_wheel = SimulatedFilterWheel(
        0,
        {
            "BP405": 0,
            "BP488": 1,
            "BP561": 2,
            "LP638": 3,
            "MB405/488/561/638": 4,
            "Empty1": 5,
            "Empty2": 6,
            "Empty3": 7,
            "Empty4": 8,
        },
    )

    BP405_filter = Filter(filter_wheel, "BP405")
    BP561_filter = Filter(filter_wheel, "BP561")
    LP638_filter = Filter(filter_wheel, "LP638")
    BP488_filter = Filter(filter_wheel, "BP488")

    colors = {
        "BP405": "#C875C4",
        "BP488": "#1F77B4",
        "BP561": "#2CA02C",
        "LP638": "#D62768",
        "MB405/488/561/638": "#17BECF",
        "Empty1": "#262930",
        "Empty2": "#262930",
        "Empty3": "#262930",
        "Empty4": "#262930",
    }

    widget = FilterWheelWidget(filter_wheel, colors)
    widget.ValueChangedInside[str].connect(
        lambda value, dev=filter_wheel, widget=widget, : widget_property_changed(value, dev, widget)
    )
    widget.show()
    sys.exit(app.exec_())
