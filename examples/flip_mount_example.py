from voxel.devices.flip_mount.simulated import SimulatedFlipMount
from view.widgets.device_widgets.flip_mount_widget import FlipMountWidget
from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot


@Slot(str)
def widget_property_changed(name, device, widget):
    """Slot to signal when widget has been changed
    :param name: name of attribute and widget"""

    name_lst = name.split('.')
    print('widget',  name_lst[0], ' changed to ', getattr(widget, name_lst[0]))
    value = getattr(widget, name_lst[0])
    setattr(device, name_lst[0], value)
    print('Device',  name_lst[0], ' changed to ', getattr(device, name_lst[0]))
    for k, v in widget.property_widgets.items():
        instrument_value = getattr(device, k)
        print(k, instrument_value)
        setattr(widget, k, instrument_value)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    flip_mount_props = {
        'flip_time_ms': 1000,
        'position': 'up'
    }

    flip_mount_class = SimulatedFlipMount(
        id='flip_mount',
        conn='COM1',
        positions={'up': 0, 'down': 1},
    )

    for k, v in flip_mount_props.items():
        setattr(flip_mount_class, k, v)

    flip_mount_widget = FlipMountWidget(flip_mount_class)

    flip_mount_widget.show()
    flip_mount_widget.ValueChangedInside[str].connect(
        lambda value, dev=flip_mount_class, widget=flip_mount_widget, : widget_property_changed(value, dev, widget))
    sys.exit(app.exec_())
