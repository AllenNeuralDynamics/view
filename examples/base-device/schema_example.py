from view.widgets.base_device_widget import BaseDeviceWidget
from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot
from aind_data_schema.core import acquisition


@Slot(str)
def widget_property_changed(name):
    """Slot to signal when widget has been changed
    :param name: name of attribute and widget"""

    name_lst = name.split('.')
    print(name, ' changed to ', getattr(base, name_lst[0]))
    # if len(name_lst) == 1:  # name refers to attribute
    #     setattr(writer, name, value)
    # else:  # name is a dictionary and key pair split by .
    #     getattr(writer, name_lst[0]).__setitem__(name_lst[1], value)
    # print(name, ' changed to ', getattr(writer, name_lst[0]))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    acquisition_properties = {k:'' for k in acquisition.Acquisition.model_fields.keys()}
    base = BaseDeviceWidget(acquisition.Acquisition.model_fields, acquisition_properties)
    base.ValueChangedInside[str].connect(widget_property_changed)

    # Format widgets better
    for name, widget in base.property_widgets.items():
        widget.setToolTip(acquisition.Acquisition.model_fields[name].description)

    base.show()

    sys.exit(app.exec_())
