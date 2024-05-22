from view.widgets.device_widgets.filter_wheel_widget import FilterWheelWidget
from qtpy.QtWidgets import QApplication
import sys
from voxel.devices.filterwheel.simulated import FilterWheel

if __name__ == "__main__":
    app = QApplication(sys.argv)
    filter_wheel = FilterWheel(0,{'BP405': 0,
                                'BP488': 1,
                                'BP561': 2,
                                'LP638': 3,
                                'MB405/488/561/638': 4,
                                'Empty1': 5,
                                'Empty2': 6,})
    widget = FilterWheelWidget(filter_wheel)
    widget.show()
    #filterwheel.set_index('561')
    sys.exit(app.exec_())
