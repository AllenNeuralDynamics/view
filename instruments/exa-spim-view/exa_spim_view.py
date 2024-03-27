from qtpy.QtWidgets import QApplication, QMessageBox, QPushButton, QFileDialog
import sys
from view.instrument_view import InstrumentView
from voxel.instruments.microscopes.exaspim import ExASPIM
from voxel.acquisition.exaspim import ExASPIMAcquisition
from pathlib import Path
import os
import yaml
from napari.qt.threading import thread_worker
import pyclesperanto as cle

RESOURCES_DIR = (Path(os.path.dirname(os.path.realpath(__file__))))
ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'
INSTRUMENT_YAML = RESOURCES_DIR / 'simulated_instrument.yaml'
GUI_YAML = RESOURCES_DIR / 'gui_config.yaml'

# ACQUISITION_YAML = RESOURCES_DIR / 'test_acquisition.yaml'
# INSTRUMENT_YAML = RESOURCES_DIR / 'speakeasy_instrument.yaml'
# GUI_YAML = RESOURCES_DIR / 'speakeasy_gui.yaml'

class ExASPIMView(InstrumentView):
    """View for ExASPIM Instrument"""

    def __init__(self, instrument, config_path: Path, log_level='INFO'):
        super().__init__(instrument, config_path, log_level)
        app.aboutToQuit.connect(self.update_config_on_quit)
        app.focusChanged.connect(self.toggle_grab_stage_positions)

        self.config_save_to = self.instrument.config_path

    @thread_worker
    def grab_frames(self, camera_name, frames=float("inf")):
        """Grab frames from camera and create multiscale array
        :param frames: how many frames to take
        :param camera_name: name of camera"""

        i = 0
        while i < frames:  # while loop since frames can == inf
            with self.camera_locks[camera_name]:
                frame = self.instrument.cameras[camera_name].grab_frame()

            # TODO: Do we want to import from exaspim what to use?
            multiscale = [frame]
            input_frame = cle.push(frame)
            for binning in range(2,6): # TODO: variable or get from somewhere?
                downsampled_frame = cle.scale(input_frame,
                                              factor_x=1 / binning,
                                              factor_y=1 / binning,
                                              device=cle.select_device(),
                                              resize=True)
                multiscale.append(cle.pull(downsampled_frame))
            yield multiscale, camera_name  # wait until unlocking camera to be able to quit napari thread
            i += 1

    def update_config_on_quit(self):
        """Add functionality to close function to save device properties to instrument config"""

        return_value = self.update_config_query()
        if return_value == QMessageBox.Ok:
            for device_types, device_dictionaries in self.instrument.config['instrument']['devices'].items():
                self.update_config(device_types, device_dictionaries)
            with open(self.config_save_to, 'w') as outfile:
                yaml.dump(self.instrument.config, outfile)

    def update_config(self, device_type, device_dictionaries):
        """Update setting in instrument config if already there"""

        for device_name, device_specs in device_dictionaries.items():
            for key in device_specs.get('settings', {}).keys():
                device_object = getattr(self.instrument, device_type)[device_name]
                device_specs.get('settings')[key] = getattr(device_object, key)
                for subdevice_type, subdevice_dictionary in device_specs.get('subdevices', {}).items():
                    self.update_config(subdevice_type, subdevice_dictionary)

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
        if folder[0] != '': # user pressed cancel
            msgBox.setText(f"Do you want to update the instrument configuration file at {folder[0]} "
                           f"to current instrument state?")
            self.config_save_to = folder[0]


    def toggle_grab_stage_positions(self):
        """When focus on view has changed, resume or pause grabbing stage positions"""
        try:
            if self.viewer.window._qt_window.isActiveWindow() and self.grab_stage_positions_worker.is_paused:
                self.grab_stage_positions_worker.resume()
            elif not self.viewer.window._qt_window.isActiveWindow() and self.grab_stage_positions_worker.is_running:
                self.grab_stage_positions_worker.pause()
        except RuntimeError:    # Pass error when window has been closed
            pass

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # instrument
    instrument = ExASPIM(INSTRUMENT_YAML)
    # acquisition
    #acquisition = ExASPIMAcquisition(instrument, ACQUISITION_YAML)

    view = ExASPIMView(instrument, GUI_YAML)

    sys.exit(app.exec_())