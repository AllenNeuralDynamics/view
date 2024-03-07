from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot
import threading
from time import sleep
from exa_spim_view.exa_spim_view import ExaSpimView
from voxel.instrument import Instrument
from voxel.acquisition import Acquisition
from pathlib import Path
import os

RESOURCES_DIR = (
        Path(os.path.dirname(os.path.realpath(__file__))) / "resources"
)
ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'
INSTRUMENT_YAML = RESOURCES_DIR / 'simulated_instrument.yaml'
GUI_YAML = RESOURCES_DIR / 'gui_config.yaml'

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # instrument
    instrument = Instrument(INSTRUMENT_YAML)
    # acquisition
    #acquisition = Acquisition(instrument, ACQUISITION_YAML)

    view = ExaSpimView(instrument, 'acquisition', GUI_YAML)

    sys.exit(app.exec_())