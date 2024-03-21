from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot
import threading
from time import sleep
from view.instrument_view import InstrumentView
from voxel.instruments.instrument import Instrument
from voxel.acquisition.exaspim import ExASPIMAcquisition
from pathlib import Path
import os

RESOURCES_DIR = (Path(os.path.dirname(os.path.realpath(__file__))))

ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'
INSTRUMENT_YAML = RESOURCES_DIR / 'speakeasy_instrument.yaml'
GUI_YAML = RESOURCES_DIR / 'speakeasy_gui.yaml'

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # instrument
    instrument = Instrument(INSTRUMENT_YAML)

    view = InstrumentView(instrument, GUI_YAML)

    sys.exit(app.exec_())