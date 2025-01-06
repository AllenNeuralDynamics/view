import os
import sys
from pathlib import Path, WindowsPath

import inflection
import numpy as np
from exaspim_control.exa_spim_acquisition import ExASPIMAcquisition
from exaspim_control.exa_spim_instrument import ExASPIM
from qtpy.QtWidgets import QApplication, QFileDialog, QMessageBox, QPushButton
from ruamel.yaml import YAML

from view.acquisition_view import AcquisitionView
from view.instrument_view import InstrumentView

RESOURCES_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
ACQUISITION_YAML = RESOURCES_DIR / "acquisition.yaml"
INSTRUMENT_YAML = RESOURCES_DIR / "instrument.yaml"
GUI_YAML = RESOURCES_DIR / "gui_config.yaml"


class SimulatedInstrumentView(InstrumentView):
    """_summary_"""

    def __init__(self, instrument, config_path: Path, log_level="INFO"):
        """_summary_

        :param instrument: _description_
        :type instrument: _type_
        :param config_path: _description_
        :type config_path: Path
        :param log_level: _description_, defaults to 'INFO'
        :type log_level: str, optional
        """
        super().__init__(instrument, config_path, log_level)
        app.aboutToQuit.connect(self.update_config_on_quit)

        self.config_save_to = self.instrument.config_path

    def update_config_on_quit(self):
        """_summary_"""
        return_value = self.update_config_query()
        if return_value == QMessageBox.Ok:
            self.instrument.update_current_state_config()
            self.instrument.save_config(self.config_save_to)

    def update_config(self, device_name, device_specs):
        """_summary_

        :param device_name: _description_
        :type device_name: _type_
        :param device_specs: _description_
        :type device_specs: _type_
        """
        device_type = inflection.pluralize(device_specs["type"])
        for key in device_specs.get("settings", {}).keys():
            device_object = getattr(self.instrument, device_type)[device_name]
            device_specs.get("settings")[key] = getattr(device_object, key)
            for subdevice_name, subdevice_specs in device_specs.get("subdevices", {}).items():
                self.update_config(subdevice_name, subdevice_specs)

    def update_config_query(self):
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(
            f"Do you want to update the instrument configuration file at {self.config_save_to} "
            f"to current instrument state?"
        )
        msgBox.setWindowTitle("Updating Configuration")
        msgBox.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        save_elsewhere = QPushButton("Change Directory")
        msgBox.addButton(save_elsewhere, QMessageBox.DestructiveRole)

        save_elsewhere.pressed.connect(lambda: self.select_directory(True, msgBox))

        return msgBox.exec()

    def select_directory(self, pressed, msgBox):
        """_summary_

        :param pressed: _description_
        :type pressed: _type_
        :param msgBox: _description_
        :type msgBox: _type_
        """
        fname = QFileDialog()
        folder = fname.getSaveFileName(directory=str(self.instrument.config_path))
        if folder[0] != "":  # user pressed cancel
            msgBox.setText(
                f"Do you want to update the instrument configuration file at {folder[0]} "
                f"to current instrument state?"
            )
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
