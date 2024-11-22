from voxel.writers.imaris import ImarisWriter
from view.widgets.acquisition_widgets.writer_widget import WriterWidget
from view.widgets.base_device_widget import scan_for_properties
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
    writer_props = {
        'compression': 'lz4shuffle',
        'data_type': 'uint16'
        }

    writer_class = ImarisWriter('D:\\')
    for k, v in writer_props.items():
        setattr(writer_class, k, v)

    writer_widget = WriterWidget(writer_class)

    writer_widget.show()
    writer_widget.ValueChangedInside[str].connect(
        lambda value, dev=writer_class, widget=writer_widget, : widget_property_changed(value, dev, widget))
    sys.exit(app.exec_())
