from view.widgets.device_widgets.filter_wheel_widget import FilterWheelWidget
from qtpy.QtWidgets import QApplication
import sys
from voxel.devices.filterwheel.simulated import FilterWheel
from voxel.devices.filter.simulated import Filter
from time import sleep
import threading


def move_filter():
    widget.filter = 'BP561'
    sleep(3)
    widget.filter = 'MB405/488/561/638'
    sleep(3)
    filter_wheel.filter = 'BP405'
    sleep(3)
    filter_wheel.filter = 'LP638'
    sleep(3)
    BP405_filter.enable()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    filter_wheel = FilterWheel(0,{'BP405': 0,
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
    widget.show()

    t1 = threading.Thread(target=move_filter)
    t1.start()

    sys.exit(app.exec_())
