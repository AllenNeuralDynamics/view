from qtpy.QtWidgets import QApplication, QMessageBox, QPushButton, QFileDialog
import sys
from view.instrument_view import InstrumentView
from view.acquisition_view import AcquisitionView
from exaspim_control.exa_spim_instrument import ExASPIM
from exaspim_control.exa_spim_acquisition import ExASPIMAcquisition
from pathlib import Path
import os
import inflection
from ruamel.yaml import YAML
import numpy as np
from pathlib import Path, WindowsPath

RESOURCES_DIR = (Path(os.path.dirname(os.path.realpath(__file__))))
ACQUISITION_YAML = RESOURCES_DIR / 'acquisition.yaml'
INSTRUMENT_YAML = RESOURCES_DIR / 'instrument.yaml'
GUI_YAML = RESOURCES_DIR / 'gui_config.yaml'


class SimulatedInstrumentView(InstrumentView):
    """View for ExASPIM Instrument"""

    def __init__(self, instrument, config_path: Path, log_level='INFO'):

        super().__init__(instrument, config_path, log_level)
        app.aboutToQuit.connect(self.update_config_on_quit)

        self.config_save_to = self.instrument.config_path

    def update_config_on_quit(self):
        """Add functionality to close function to save device properties to instrument config"""

        return_value = self.update_config_query()
        if return_value == QMessageBox.Ok:
            self.instrument.update_current_state_config()
            self.instrument.save_config(self.config_save_to)

    def update_config(self, device_name, device_specs):
        """Update setting in instrument config if already there
        :param device_name: name of device
        :param device_specs: dictionary dictating how device should be set up"""

        device_type = inflection.pluralize(device_specs['type'])
        for key in device_specs.get('settings', {}).keys():
            device_object = getattr(self.instrument, device_type)[device_name]
            device_specs.get('settings')[key] = getattr(device_object, key)
            for subdevice_name, subdevice_specs in device_specs.get('subdevices', {}).items():
                self.update_config(subdevice_name, subdevice_specs)

    def update_config_query(self):
        """Pop up message asking if configuration would like to be saved"""
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(f"Do you want to update the instrument configuration file at {self.config_save_to} "
                       f"to current instrument state?")
        msgBox.setWindowTitle("Updating Configuration")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        save_elsewhere = QPushButton('Change Directory')
        msgBox.addButton(save_elsewhere, QMessageBox.DestructiveRole)

        save_elsewhere.pressed.connect(lambda: self.select_directory(True, msgBox))

        return msgBox.exec()

    def select_directory(self, pressed, msgBox):
        """Select directory"""

        fname = QFileDialog()
        folder = fname.getSaveFileName(directory=str(self.instrument.config_path))
        if folder[0] != '':  # user pressed cancel
            msgBox.setText(f"Do you want to update the instrument configuration file at {folder[0]} "
                           f"to current instrument state?")
            self.config_save_to = folder[0]


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # create yaml handler
    yaml = YAML()
    yaml.representer.add_representer(np.int32, lambda obj, val: obj.represent_int(int(val)))
    yaml.representer.add_representer(np.str_, lambda obj, val: obj.represent_str(str(val)))
    yaml.representer.add_representer(np.float64, lambda obj, val: obj.represent_float(float(val)))
    yaml.representer.add_representer(Path, lambda obj, val: obj.represent_str(str(val)))
    yaml.representer.add_representer(WindowsPath, lambda obj, val: obj.represent_str(str(val)))

    # instrument
    instrument = ExASPIM(INSTRUMENT_YAML, yaml_handler=yaml)
    # acquisition
    acquisition = ExASPIMAcquisition(instrument, ACQUISITION_YAML, yaml_handler=yaml)

    instrument_view = SimulatedInstrumentView(instrument, GUI_YAML)
    acquisition_view = AcquisitionView(acquisition, instrument_view)
    sys.exit(app.exec_())