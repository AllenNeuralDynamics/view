from qtpy.QtWidgets import QApplication
import sys
from qtpy.QtCore import Slot
import threading
from time import sleep
from view.instrument_view import InstrumentView
from voxel.instruments.instrument import Instrument
from view.acquisition_view import AcquisitionView
from voxel.acquisition.acquisition import Acquisition
from pathlib import Path
import os
from time import sleep

RESOURCES_DIR = (Path(os.path.dirname(os.path.realpath(__file__))))

ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'
INSTRUMENT_YAML = RESOURCES_DIR / 'speakeasy_instrument.yaml'
GUI_YAML = RESOURCES_DIR / 'speakeasy_gui.yaml'

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # instrument
    instrument = Instrument(INSTRUMENT_YAML)
    # acquisition
    acquisition = Acquisition(instrument, ACQUISITION_YAML)

    instrument_view = InstrumentView(instrument, GUI_YAML)

    # instrument_view.grab_stage_positions_worker.pause()
    # while not instrument_view.grab_stage_positions_worker.is_paused:
    #     sleep(.1)

    acquisition_view = AcquisitionView(acquisition, instrument_view, GUI_YAML)
    sys.exit(app.exec_())
