from qtpy.QtWidgets import QApplication, QMessageBox, QPushButton, QFileDialog
import sys
from view.instrument_view import InstrumentView
from view.acquisition_view import AcquisitionView
from voxel.instruments.instrument import Instrument
from voxel.acquisition.acquisition import Acquisition
from pathlib import Path
import os
import yaml
import inflection
from qtpy.QtCore import Qt

RESOURCES_DIR = (Path(os.path.dirname(os.path.realpath(__file__))))
ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'
INSTRUMENT_YAML = RESOURCES_DIR / 'simulated_instrument.yaml'
GUI_YAML = RESOURCES_DIR / 'gui_config.yaml'


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # instrument
    instrument = Instrument(INSTRUMENT_YAML)
    # acquisition
    acquisition = Acquisition(instrument, ACQUISITION_YAML)

    instrument_view = InstrumentView(instrument, GUI_YAML)
    acquisition_view = AcquisitionView(acquisition, instrument_view)
    sys.exit(app.exec_())