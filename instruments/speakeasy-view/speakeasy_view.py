import os
import sys
from pathlib import Path

from qtpy.QtWidgets import QApplication

from view.acquisition_view import AcquisitionView
from view.instrument_view import InstrumentView
from voxel.acquisition.acquisition import Acquisition
from voxel.instruments.instrument import Instrument

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

    acquisition_view = AcquisitionView(acquisition, instrument_view)
    sys.exit(app.exec_())
