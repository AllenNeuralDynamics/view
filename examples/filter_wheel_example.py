from view.widgets.device_widgets.filter_wheel_widget import FilterWheelWidget
from qtpy.QtWidgets import QApplication
import sys
from voxel.devices.filterwheel.asi import FilterWheel
from voxel.devices.filter.asi import Filter
from time import sleep
import threading
from tigerasi.tiger_controller import TigerController

def move_filter():
    filter_wheel.filter = 'BP405'
    sleep(3)
    filter_wheel.filter = 'LP638'
    sleep(3)
    BP405_filter.enable()

def widget_property_changed(name, device, widget):
    """Slot to signal when widget has been changed
    :param name: name of attribute and widget"""

    print('widget property changed')
    name_lst = name.split('.')
    print('widget', name, ' changed to ', getattr(widget, name_lst[0]))
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    print('Device', name, ' changed to ', getattr(device, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    stage = TigerController('COM4')
    filter_wheel = FilterWheel(stage,0, {'BP405': 0,
                                'BP488': 1,
                                'BP561': 2,
                                'LP638': 3,
                                'MB405/488/561/638': 4,
                                'Empty1': 5,
                                'Empty2': 6,})

    BP405_filter = Filter(filter_wheel, 'BP405')
    BP561_filter = Filter(filter_wheel, 'BP561')
    LP638_filter = Filter(filter_wheel, 'LP638')
    BP488_filter = Filter(filter_wheel, 'BP488')


    widget = FilterWheelWidget(filter_wheel)
    widget.ValueChangedInside[str].connect(lambda value, dev=filter_wheel, gui=widget: widget_property_changed(value, dev, widget))
    widget.show()

    t1 = threading.Thread(target=move_filter)
    t1.start()

    sys.exit(app.exec_())
