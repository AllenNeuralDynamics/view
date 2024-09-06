Instrument and Acquisition View
This repository contains modules for managing and interacting with various instruments and acquisition processes in a voxel-based system. It leverages the napari viewer for visualization and integrates multiple device widgets for controlling different components of the instrument and acquisition.

Features
Instrument View
Logging: Configurable logging setup to monitor and debug the instrument’s operations.
Device Widgets: Dynamic creation and management of widgets for various devices such as lasers, DAQs, cameras, stages, and more.
Live Streaming: Setup and control of live streaming from cameras, including snapshot functionality.
DAQ Management: Initialization and configuration of DAQs with tasks for both live streaming and data acquisition.
Stage Control: Arrangement and control of stage positions and joystick widgets.
Laser Control: Management of laser widgets and their configurations.
Filter Wheel Control: Stacking and management of filter wheel widgets.
Channel Selection: Widget for selecting which laser to use for live streaming.
Configuration Management: Saving and updating the instrument configuration on application quit.
Acquisition View
Metadata Management: Custom widget for managing metadata related to the acquisition.
Volume Planning: Visualization and planning of acquisition grids, including volume and channel plans.
Operation Widgets: Dynamic creation and management of widgets for various acquisition operations such as writing, transferring, processing, and routines.
Stage Positioning: Live tracking and updating of field-of-view (FOV) positions.
Acquisition Control: Start and stop buttons for controlling the acquisition process.
Configuration Management: Saving and updating the acquisition configuration on application quit.
Installation
Ensure you have the following dependencies installed:

ruamel.yaml
qtpy
pathlib
importlib
PIL
napari
numpy
logging
inflection
inspect
You can install these dependencies using pip:

pip install ruamel.yaml qtpy pathlib importlib PIL napari numpy logging inflection inspect

Usage
Instrument View
To use the InstrumentView class, initialize it with the instrument configuration and desired log level:

Python

from pathlib import Path
from instrument_view import InstrumentView

instrument = ...  # Your instrument object
config_path = Path('path/to/config.yaml')
view = InstrumentView(instrument, config_path, log_level='INFO')
AI-generated code. Review and use carefully. More info on FAQ.
Acquisition View
To use the AcquisitionView class, initialize it with the acquisition configuration and the instrument view:

Python

from acquisition_view import AcquisitionView

acquisition = ...  # Your acquisition object
instrument_view = ...  # Your instrument view object
acquisition_view = AcquisitionView(acquisition, instrument_view, log_level='INFO')
AI-generated code. Review and use carefully. More info on FAQ.
Key Methods
Instrument View
setup_daqs(): Initializes DAQs with live streaming tasks.
setup_stage_widgets(): Arranges stage position and joystick widgets.
setup_laser_widgets(): Arranges laser widgets.
setup_daq_widgets(): Sets up DAQ widgets and their configurations.
setup_camera_widgets(): Sets up live view and snapshot buttons for cameras.
setup_channel_widget(): Creates a widget to select which laser to live stream with.
create_device_widgets(device_name, device_specs): Creates widgets based on device specifications.
update_config_on_quit(): Saves device properties to the instrument configuration on application quit.
Acquisition View
create_start_button(): Creates a button to start the acquisition.
create_stop_button(): Creates a button to stop the acquisition.
start_acquisition(): Starts the acquisition process.
acquisition_ended(): Re-enables UI and threads after the acquisition has ended.
stack_device_widgets(device_type): Stacks device widgets in a layout and hides/unhides them with a combo box.
create_metadata_widget(): Creates a custom widget for metadata.
create_acquisition_widget(): Creates a widget to visualize the acquisition grid.
update_config_on_quit(): Saves device properties to the acquisition configuration on application quit.
Signals
Instrument View
snapshotTaken: Emitted when a snapshot is taken.
contrastChanged: Emitted when the contrast of an image changes.
Acquisition View
fovHalt: Emitted to stop the stage.
fovMove: Emitted to move the stage to clicked coordinates.
Example
Instrument View
Python

# Example of setting up the InstrumentView
from pathlib import Path
from instrument_view import InstrumentView

instrument = ...  # Initialize your instrument object
config_path = Path('path/to/config.yaml')
view = InstrumentView(instrument, config_path, log_level='DEBUG')

# Start the application
app = QApplication.instance()
app.exec_()
AI-generated code. Review and use carefully. More info on FAQ.
Acquisition View
Python

# Example of setting up the AcquisitionView
from acquisition_view import AcquisitionView

acquisition = ...  # Initialize your acquisition object
instrument_view = ...  # Initialize your instrument view object
acquisition_view = AcquisitionView(acquisition, instrument_view, log_level='DEBUG')

# Start the application
app = QApplication.instance()
app.exec_()
AI-generated code. Review and use carefully. More info on FAQ.
Contributing
Contributions are welcome! Please submit a pull request or open an issue to discuss any changes.

License
This project is licensed under the MIT License.

Feel free to customize this README further based on your specific needs! If you have any other questions or need additional details, let me know.