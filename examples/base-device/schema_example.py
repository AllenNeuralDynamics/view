import sys

from aind_data_schema.core import acquisition
from qtpy.QtCore import Slot
from qtpy.QtWidgets import QApplication

from view.widgets.base_device_widget import BaseDeviceWidget


@Slot(str)
def widget_property_changed(name):
    """_summary_

    :param name: _description_
    :type name: _type_
    """
    name_lst = name.split(".")
    print(name, " changed to ", getattr(base, name_lst[0]))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    acquisition_properties = {k: "" for k in acquisition.Acquisition.model_fields.keys()}

    base = BaseDeviceWidget(acquisition.Acquisition.model_fields, acquisition_properties)
    base.ValueChangedInside[str].connect(widget_property_changed)

    # Format widgets better
    for name, widget in base.property_widgets.items():
        widget.setToolTip(acquisition.Acquisition.model_fields[name].description)

    base.show()

    sys.exit(app.exec_())
