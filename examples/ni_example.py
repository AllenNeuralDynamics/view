from voxel.devices.daq.ni import DAQ
from view.widgets.device_widgets.ni_widget import NIWidget
from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot
from pathlib import Path
from ruamel.yaml import YAML
import os

RESOURCES_DIR = (Path(os.path.dirname(os.path.realpath(__file__))))
INSTRUMENT_YAML = RESOURCES_DIR / 'resources/simulated_instrument.yaml'
GUI_YAML = RESOURCES_DIR / 'resources/gui_config.yaml'


@Slot(str)
def widget_property_changed(name, device, widget):
    """Slot to signal when widget has been changed
    :param name: name of attribute and widget"""

    name_lst = name.split('.')
    # print('widget', name, ' changed to ', getattr(widget, name_lst[0]))
    # value = getattr(widget, name_lst[0])
    # setattr(device, name_lst[0], value)
    # print('Device', name, ' changed to ', getattr(device, name_lst[0]))
    # for k, v in widget.property_widgets.items():
    #     instrument_value = getattr(device, k)
    #     print(k, instrument_value)
        #setattr(widget, k, instrument_value)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # set up daq
    config = YAML(typ='safe', pure=True).load(INSTRUMENT_YAML)

    daq_tasks = config['instrument']['devices']['PCIe-6738']['properties']['tasks']
    ao_task = daq_tasks['ao_task']
    co_task = daq_tasks['co_task']

    daq_object = DAQ("Dev2")
    daq_object.tasks = daq_tasks
    daq_object.add_task('ao')
    daq_object.add_task('co')
    daq_object.generate_waveforms('ao', '488')
    daq_object.write_ao_waveforms()

    gui_config = YAML(typ='safe', pure=True).load(GUI_YAML)

    exposed = gui_config['instrument_view']['device_widgets']['PCIe-6738']['init']['exposed_branches']
    daq_widget = NIWidget(daq_object, exposed)
    daq_widget.show()
    daq_widget.ValueChangedInside[str].connect(
        lambda value, dev=daq_object, widget=daq_widget,: widget_property_changed(value, dev, widget))

    sys.exit(app.exec_())
