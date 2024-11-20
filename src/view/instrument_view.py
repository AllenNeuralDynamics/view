from ruamel.yaml import YAML
from qtpy.QtCore import Slot, Signal, Qt
from qtpy.QtGui import QMouseEvent
from pathlib import Path
import importlib
from view.widgets.base_device_widget import (
    BaseDeviceWidget,
    create_widget,
    pathGet,
    scan_for_properties,
    disable_button,
)
from qtpy.QtWidgets import (
    QStyle,
    QRadioButton,
    QWidget,
    QButtonGroup,
    QSlider,
    QGridLayout,
    QComboBox,
    QApplication,
    QVBoxLayout,
    QLabel,
    QFrame,
    QSizePolicy,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QScrollArea,
)
from PIL import Image
from napari.qt.threading import thread_worker, create_worker
from napari.utils.theme import get_theme
import napari
import datetime
from time import sleep
import logging
import inflection
import inspect
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit
from view.widgets.miscellaneous_widgets.q_scrollable_float_slider import QScrollableFloatSlider
from view.widgets.miscellaneous_widgets.q_dock_widget_title_bar import QDockWidgetTitleBar
import numpy as np
from typing import Literal, Union, Iterator


class InstrumentView(QWidget):
    """ "Class to act as a general instrument view model to voxel instrument"""

    snapshotTaken = Signal((np.ndarray, list))
    contrastChanged = Signal((np.ndarray, list))

    def __init__(
        self,
        instrument,
        config_path: Path,
        log_level: Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    ):
        """
        :param instrument: voxel like instrument object
        :param config_path: path to gui config yaml
        :param log_level: level to set logger
        """
        super().__init__()

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)
        # set all loggers to log_level
        loggers = [logging.getLogger(name) for name in logging.root.manager.loggerDict]
        for logger in loggers:
            logger.setLevel(log_level)

        # Eventual widget groups
        self.laser_widgets = {}
        self.daq_widgets = {}
        self.camera_widgets = {}
        self.scanning_stage_widgets = {}
        self.tiling_stage_widgets = {}
        self.focusing_stage_widgets = {}
        self.filter_wheel_widgets = {}
        self.joystick_widgets = {}

        # Eventual threads
        self.grab_frames_worker = create_worker(lambda: None)  # dummy thread
        self.property_workers = []  # list of property workers

        # Eventual attributes
        self.livestream_channel = None
        self.snapshot = False  # flag to signal snapshot has been taken

        self.instrument = instrument
        self.config_path = config_path
        self.config = YAML().load(config_path)

        # Convenient config maps
        self.channels = self.instrument.config["instrument"]["channels"]

        # Setup napari window
        self.viewer = napari.Viewer(title="View", ndisplay=2, axis_labels=("x", "y"))

        # setup daq with livestreaming tasks
        self.setup_daqs()

        # Set up instrument widgets
        for device_name, device_specs in self.instrument.config["instrument"]["devices"].items():
            self.create_device_widgets(device_name, device_specs)

        # setup widget additional functionalities
        self.setup_camera_widgets()
        self.setup_channel_widget()
        self.setup_laser_widgets()
        self.setup_daq_widgets()
        self.setup_filter_wheel_widgets()
        self.setup_stage_widgets()

        # add undocked widget so everything closes together
        self.add_undocked_widgets()

        # Set app events
        app = QApplication.instance()
        app.aboutToQuit.connect(self.update_config_on_quit)  # query if config should be saved and where
        self.config_save_to = self.instrument.config_path
        app.lastWindowClosed.connect(self.close)  # shut everything down when closing

    def setup_daqs(self) -> None:
        """
        Initialize daqs with livestreaming tasks if different from data acquisition tasks
        """

        for daq_name, daq in self.instrument.daqs.items():
            if daq_name in self.config["instrument_view"].get("livestream_tasks", {}).keys():
                daq.tasks = self.config["instrument_view"]["livestream_tasks"][daq_name]["tasks"]
                # Make sure if there is a livestreaming task, there is a corresponding data acquisition task:
                if not self.config["acquisition_view"].get("data_acquisition_tasks", {}).get(daq_name, False):
                    self.log.error(
                        f"Daq {daq_name} has a livestreaming task but no corresponding data acquisition "
                        f"task in instrument yaml."
                    )
                    raise ValueError

    def setup_stage_widgets(self) -> None:
        """
        Arrange stage position and joystick widget
        """

        stage_widgets = []
        for name, widget in {
            **self.tiling_stage_widgets,
            **self.scanning_stage_widgets,
            **self.focusing_stage_widgets,
        }.items():
            label = QLabel()
            frame = QFrame()
            layout = QVBoxLayout()
            layout.addWidget(create_widget("H", label, widget))
            frame.setLayout(layout)
            border_color = get_theme(self.viewer.theme, as_dict=False).foreground
            frame.setStyleSheet(f".QFrame {{ border:1px solid {border_color}; }} ")
            stage_widgets.append(frame)

        stage_axes_widget = create_widget("V", *stage_widgets)
        stage_axes_widget.setContentsMargins(0, 0, 0, 0)
        stage_axes_widget.layout().setSpacing(0)

        stage_scroll = QScrollArea()
        stage_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        stage_scroll.setWidget(stage_axes_widget)
        self.viewer.window.add_dock_widget(stage_scroll, area="left", name="Stages")

        joystick_scroll = QScrollArea()
        joystick_scroll.setWidget(self.stack_device_widgets("joystick"))
        self.viewer.window.add_dock_widget(joystick_scroll, area="left", name="Joystick")

    def setup_laser_widgets(self) -> None:
        """
        Arrange laser widgets
        """

        laser_widgets = []
        for name, widget in self.laser_widgets.items():
            label = QLabel(name)
            horizontal = QFrame()
            layout = QVBoxLayout()
            layout.addWidget(create_widget("H", label, widget))
            horizontal.setLayout(layout)
            border_color = get_theme(self.viewer.theme, as_dict=False).foreground
            horizontal.setStyleSheet(f".QFrame {{ border:1px solid {border_color}; }} ")
            laser_widgets.append(horizontal)
        laser_widget = create_widget("V", *laser_widgets)
        self.viewer.window.add_dock_widget(laser_widget, area="bottom", name="Lasers")

    def setup_daq_widgets(self) -> None:
        """
        Setup saving to config if widget is from device-widget repo
        """

        for daq_name, daq_widget in self.daq_widgets.items():
            # if daq_widget is BaseDeviceWidget or inherits from it, update waveforms when gui is changed
            if type(daq_widget) == BaseDeviceWidget or BaseDeviceWidget in type(daq_widget).__bases__:
                daq_widget.ValueChangedInside[str].connect(
                    lambda value, daq=self.instrument.daqs[daq_name]: self.write_waveforms(daq)
                )
                # update tasks if livestreaming task is different from data acquisition task
                if daq_name in self.config["instrument_view"].get("livestream_tasks", {}).keys():
                    daq_widget.ValueChangedInside[str].connect(
                        lambda attr, widget=daq_widget, name=daq_name: self.update_config_waveforms(
                            widget, daq_name, attr
                        )
                    )

        stacked = self.stack_device_widgets("daq")
        self.viewer.window.add_dock_widget(stacked, area="right", name="DAQs", add_vertical_stretch=False)

    def stack_device_widgets(self, device_type: str) -> QWidget:
        """
        Stack like device widgets in layout and hide/unhide with combo box
        :param device_type: type of device being stacked
        :return: widget containing all widgets pertaining to device type stacked ontop of each other
        """

        device_widgets = getattr(self, f"{device_type}_widgets")
        overlap_layout = QGridLayout()
        overlap_layout.addWidget(QWidget(), 1, 0)  # spacer widget
        for name, widget in device_widgets.items():
            widget.setVisible(False)
            overlap_layout.addWidget(widget, 2, 0)

        visible = QComboBox()
        visible.currentTextChanged.connect(lambda text: self.hide_devices(text, device_type))
        visible.addItems(device_widgets.keys())
        visible.setCurrentIndex(0)
        overlap_layout.addWidget(visible, 0, 0)

        overlap_widget = QWidget()
        overlap_widget.setLayout(overlap_layout)

        return overlap_widget

    def hide_devices(self, text: str, device_type: str) -> None:
        """
        Hide device widget if not selected in combo box
        :param text: selected text of combo box
        :param device_type: type of device related to combo box
        """

        device_widgets = getattr(self, f"{device_type}_widgets")
        for name, widget in device_widgets.items():
            if name != text:
                widget.setVisible(False)
            else:
                widget.setVisible(True)

    def write_waveforms(self, daq) -> None:
        """
        Write waveforms if livestreaming is on
        :param daq: daq object
        """

        if self.grab_frames_worker.is_running:  # if currently livestreaming
            if daq.ao_task is not None:
                daq.generate_waveforms("ao", self.livestream_channel)
                daq.write_ao_waveforms(rereserve_buffer=False)
            if daq.do_task is not None:
                daq.generate_waveforms("do", self.livestream_channel)
                daq.write_do_waveforms(rereserve_buffer=False)

    def update_config_waveforms(self, daq_widget, daq_name: str, attr_name: str) -> None:
        """
        If waveforms are changed in gui, apply changes to livestream_tasks and data_acquisition_tasks if
        applicable
        :param daq_widget: widget pertaining to daq object
        :param daq_name: name of daq
        :param attr_name: waveform attribute to update
        """

        path = attr_name.split(".")
        value = getattr(daq_widget, attr_name)
        self.log.debug(f"{daq_name} {attr_name} changed to {getattr(daq_widget, path[0])}")

        # update livestream_task
        self.config["instrument_view"]["livestream_tasks"][daq_name]["tasks"] = daq_widget.tasks

        # update data_acquisition_tasks if value correlates
        key = path[-1]
        try:
            dictionary = pathGet(self.config["acquisition_view"]["data_acquisition_tasks"][daq_name], path[:-1])
            if key not in dictionary.keys():
                raise KeyError
            dictionary[key] = value
            self.log.info(
                f"Data acquisition tasks parameters updated to "
                f"{self.config['acquisition_view']['data_acquisition_tasks'][daq_name]}"
            )

        except KeyError:
            self.log.warning(
                f"Path {attr_name} can't be mapped into data acquisition tasks so changes will not "
                f"be reflected in acquisition"
            )

    def setup_filter_wheel_widgets(self):
        """
        Stack filter wheels
        """

        stacked = self.stack_device_widgets("filter_wheel")
        self.viewer.window.add_dock_widget(stacked, area="bottom", name="Filter Wheels")

    def setup_camera_widgets(self):
        """
        Setup live view and snapshot button
        """

        for camera_name, camera_widget in self.camera_widgets.items():
            # Add functionality to snapshot button
            snapshot_button = getattr(camera_widget, "snapshot_button", QPushButton())
            snapshot_button.pressed.connect(
                lambda button=snapshot_button: disable_button(button)
            )  # disable to avoid spamming
            snapshot_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera, 1))

            # Add functionality to live button
            live_button = getattr(camera_widget, "live_button", QPushButton())
            live_button.pressed.connect(lambda button=live_button: disable_button(button))  # disable to avoid spamming
            live_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera))
            live_button.pressed.connect(lambda camera=camera_name: self.toggle_live_button(camera))

        stacked = self.stack_device_widgets("camera")
        self.viewer.window.add_dock_widget(stacked, area="right", name="Cameras", add_vertical_stretch=False)

    def toggle_live_button(self, camera_name: str) -> None:
        """
        Toggle text and functionality of live button when pressed
        :param camera_name: name of camera to set up
        """

        live_button = getattr(self.camera_widgets[camera_name], "live_button", QPushButton())
        live_button.disconnect()
        if live_button.text() == "Live":
            live_button.setText("Stop")
            stop_icon = live_button.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
            live_button.setIcon(stop_icon)
            live_button.pressed.connect(self.grab_frames_worker.quit)
        else:
            live_button.setText("Live")
            start_icon = live_button.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            live_button.setIcon(start_icon)
            live_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera_name))

        live_button.pressed.connect(lambda button=live_button: disable_button(button))
        live_button.pressed.connect(lambda camera=camera_name: self.toggle_live_button(camera_name))

    def setup_live(self, camera_name: str, frames=float("inf")) -> None:
        """
        Set up for either livestream or snapshot
        :param camera_name: name of camera to set up
        :param frames: how many frames to take
        """

        if self.grab_frames_worker.is_running:
            if frames == 1:  # create snapshot layer with the latest image
                # TODO: Maybe make this it's own function
                layer_name = f"{camera_name} {self.livestream_channel}"
                multiscale_image = self.viewer.layers[layer_name].data
                layer = self.viewer.add_image(multiscale_image, name=layer_name + " snapshot")
                layer.mouse_drag_callbacks.append(self.save_image)
                self.snapshotTaken.emit(np.rot90(multiscale_image[-3], k=3), layer.contrast_limits)
                layer.events.contrast_limits.connect(
                    lambda event: self.contrastChanged.emit(np.rot90(layer.data[-3], k=3), layer.contrast_limits)
                )
            return

        self.grab_frames_worker = self.grab_frames(camera_name, frames)

        if frames == 1:  # pass in optional argument that this image is a snapshot
            self.grab_frames_worker.yielded.connect(lambda args: self.update_layer(*args, snapshot=True))
        else:
            self.grab_frames_worker.yielded.connect(lambda args: self.update_layer(*args))

        self.grab_frames_worker.finished.connect(lambda: self.dismantle_live(camera_name))
        self.grab_frames_worker.start()

        self.instrument.cameras[camera_name].prepare()
        self.instrument.cameras[camera_name].start(frames)

        for laser in self.channels[self.livestream_channel].get("lasers", []):
            self.log.info(f"Enabling laser {laser}")
            self.instrument.lasers[laser].enable()

        for filter in self.channels[self.livestream_channel].get("filters", []):
            self.log.info(f"Enabling filter {filter}")
            self.instrument.filters[filter].enable()

        for daq_name, daq in self.instrument.daqs.items():
            if daq.tasks.get("ao_task", None) is not None:
                daq.add_task("ao")
                daq.generate_waveforms("ao", self.livestream_channel)
                daq.write_ao_waveforms()
            if daq.tasks.get("do_task", None) is not None:
                daq.add_task("do")
                daq.generate_waveforms("do", self.livestream_channel)
                daq.write_do_waveforms()
            if daq.tasks.get("co_task", None) is not None:
                pulse_count = daq.tasks["co_task"]["timing"].get("pulse_count", None)
                daq.add_task("co", pulse_count)

            daq.start()

    def dismantle_live(self, camera_name: str) -> None:
        """
        Safely shut down live
        :param camera_name: name of camera to shut down live
        """

        self.instrument.cameras[camera_name].abort()
        for daq_name, daq in self.instrument.daqs.items():
            daq.stop()
        for laser_name in self.channels[self.livestream_channel].get("lasers", []):
            self.instrument.lasers[laser_name].disable()

    @thread_worker
    def grab_frames(self, camera_name: str, frames=float("inf")) -> Iterator[tuple[np.ndarray, str]]:
        """
        Grab frames from camera
        :param frames: how many frames to take
        :param camera_name: name of camera
        """

        i = 0
        while i < frames:  # while loop since frames can == inf
            sleep(0.1)
            yield self.instrument.cameras[camera_name].grab_frame(), camera_name
            i += 1

    def update_layer(self, image: np.ndarray, camera_name: str, snapshot: bool = False) -> None:
        """
        Update viewer with new camera frame
        :param image: array like object to upload to viewer
        :param camera_name: name of camera image came off of
        :param snapshot: if image taken is a snapshot or not
        """

        if image is not None:
            layer_name = (
                f"{camera_name} {self.livestream_channel}"
                if not snapshot
                else f"{camera_name} {self.livestream_channel} snapshot"
            )
            if layer_name in self.viewer.layers and not snapshot:
                layer = self.viewer.layers[layer_name]
                layer.data = image
            else:
                # Add image to a new layer if layer doesn't exist yet or image is snapshot
                layer = self.viewer.add_image(image, name=layer_name)
                layer.mouse_drag_callbacks.append(self.save_image)
                if snapshot:  # emit signal if snapshot
                    image = image if not layer.multiscale else image[-3]
                    self.snapshotTaken.emit(image, layer.contrast_limits)
                    if layer.multiscale == True:  # emit most down sampled image if multiscale
                        layer.events.contrast_limits.connect(
                            lambda event: self.contrastChanged.emit(layer.data[-3], layer.contrast_limits)
                        )
                    else:
                        layer.events.contrast_limits.connect(
                            lambda event: self.contrastChanged.emit(layer.data, layer.contrast_limits)
                        )

    @staticmethod
    def save_image(
        layer: Union[napari.layers.image.image.Image, list[napari.layers.image.image.Image]], event: QMouseEvent
    ) -> None:
        """
        Save image in viewer by right-clicking viewer
        :param layer: layer that was pressed
        :param event: mouse event
        """

        if event.button == 2:  # Left click
            if layer.multiscale:
                image = Image.fromarray(layer.data[0])
            else:
                image = Image.fromarray(layer.data)
            fname = QFileDialog()
            folder = fname.getSaveFileName(
                directory=str(
                    Path(__file__).parent.resolve()
                    / Path(rf"\{layer.name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.tiff")
                )
            )
            if folder[0] != "":  # user pressed cancel
                image.save(folder[0])

    def setup_channel_widget(self) -> None:
        """
        Create widget to select which laser to livestream with
        """

        widget = QWidget()
        widget_layout = QVBoxLayout()

        laser_button_group = QButtonGroup(widget)
        for channel, specs in self.channels.items():
            button = QRadioButton(str(channel))
            button.toggled.connect(lambda value, ch=channel: self.change_channel(value, ch))
            laser_button_group.addButton(button)
            widget_layout.addWidget(button)
        button.setChecked(True)  # Arbitrarily set last button checked
        widget.setLayout(widget_layout)
        widget.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        self.viewer.window.add_dock_widget(widget, area="bottom", name="Channels")

    def change_channel(self, checked: bool, channel: str) -> None:
        """
        Update livestream_channel to newly selected channel
        :param channel: name of channel
        :param checked: if button is checked (True) or unchecked(False)
        """

        if checked:
            if self.grab_frames_worker.is_running:  # livestreaming is going
                for old_laser_name in self.channels[self.livestream_channel].get("lasers", []):
                    self.log.info(f"Disabling laser {old_laser_name}")
                    self.instrument.lasers[old_laser_name].disable()
                for daq_name, daq in self.instrument.daqs.items():
                    self.log.info(f"Writing new waveforms for {daq_name}")
                    self.write_waveforms(daq)
                for new_laser_name in self.channels[channel].get("lasers", []):
                    self.log.info(f"Enabling laser {new_laser_name}")
                    self.instrument.lasers[new_laser_name].enable()
            self.livestream_channel = channel
            # change filter
            for filter in self.channels[self.livestream_channel].get("filters", []):
                self.log.info(f"Enabling filter {filter}")
                self.instrument.filters[filter].enable()

    def create_device_widgets(self, device_name: str, device_specs: dict) -> None:
        """
        Create widgets based on device dictionary attributes from instrument or acquisition
         :param device_name: name of device
         :param device_specs: dictionary dictating how device should be set up
        """

        device_type = device_specs["type"]
        device = getattr(self.instrument, inflection.pluralize(device_type))[device_name]

        specs = self.config["instrument_view"]["device_widgets"].get(device_name, {})
        if specs != {} and specs.get("type", "") == device_type:
            gui_class = getattr(importlib.import_module(specs["driver"]), specs["module"])
            gui = gui_class(device, **specs.get("init", {}))  # device gets passed into widget
        else:
            properties = scan_for_properties(device)
            gui = BaseDeviceWidget(type(device), properties)

        # if gui is BaseDeviceWidget or inherits from it,
        # hook up widgets to device_property_changed when user changes value
        if type(gui) == BaseDeviceWidget or BaseDeviceWidget in type(gui).__bases__:
            gui.ValueChangedInside[str].connect(
                lambda value, dev=device, widget=gui: self.device_property_changed(value, dev, widget)
            )

            updating_props = specs.get("updating_properties", [])
            for prop_name in updating_props:
                worker = self.grab_property_value(device, prop_name, gui)
                worker.yielded.connect(lambda args: self.update_property_value(*args))
                worker.start()
                self.property_workers.append(worker)

        # add ui to widget dictionary
        if not hasattr(self, f"{device_type}_widgets"):
            setattr(self, f"{device_type}_widgets", {})
        getattr(self, f"{device_type}_widgets")[device_name] = gui

        for subdevice_name, subdevice_specs in device_specs.get("subdevices", {}).items():
            # if device has subdevice, create and pass on same Lock()
            self.create_device_widgets(subdevice_name, subdevice_specs)

        gui.setWindowTitle(f"{device_type} {device_name}")

    @thread_worker
    def grab_property_value(self, device: object, property_name: str, device_widget) -> Iterator:
        """
        Grab value of property and yield
        :param device: device to grab property from
        :param property_name: name of property to get
        :param device_widget: widget of entire device that is the parent of property widget
        :return: value of property and widget to update
        """

        while True:  # best way to do this or have some sort of break?
            sleep(0.5)
            try:
                value = getattr(device, property_name)
            except ValueError:  # Tigerbox sometime coughs up garbage. Locking issue?
                value = None
            yield value, device_widget, property_name

    def update_property_value(self, value, device_widget, property_name: str) -> None:
        """
        Update stage position in stage widget
        :param device_widget: widget of entire device that is the parent of property widget
        :param value: value to update with
        :param property_name: name of property to set
        """

        try:
            setattr(device_widget, property_name, value)  # setting attribute value will update widget
        except (RuntimeError, AttributeError):  # Pass when window's closed or widget doesn't have position_mm_widget
            pass

    @Slot(str)
    def device_property_changed(self, attr_name: str, device: object, widget) -> None:
        """
        Slot to signal when device widget has been changed
        :param widget: widget object relating to device
        :param device: device object
        :param attr_name: name of attribute
        """

        name_lst = attr_name.split(".")
        self.log.debug(f"widget {attr_name} changed to {getattr(widget, name_lst[0])}")
        value = getattr(widget, name_lst[0])
        try:  # Make sure name is referring to same thing in UI and device
            dictionary = getattr(device, name_lst[0])
            for k in name_lst[1:]:
                dictionary = dictionary[k]

            # attempt to pass in correct value of correct type
            descriptor = getattr(type(device), name_lst[0])
            fset = getattr(descriptor, "fset")
            input_type = list(inspect.signature(fset).parameters.values())[-1].annotation
            if input_type != inspect._empty:
                setattr(device, name_lst[0], input_type(value))
            else:
                setattr(device, name_lst[0], value)

            self.log.info(f"Device changed to {getattr(device, name_lst[0])}")
            # Update ui with new device values that might have changed
            # WARNING: Infinite recursion might occur if device property not set correctly
            for k, v in widget.property_widgets.items():
                if getattr(widget, k, False):
                    device_value = getattr(device, k)
                    setattr(widget, k, device_value)

        except (KeyError, TypeError):
            self.log.warning(f"{attr_name} can't be mapped into device properties")
            pass

    def add_undocked_widgets(self) -> None:
        """
        Add undocked widget so all windows close when closing napari viewer
        """

        widgets = []
        for key, dictionary in self.__dict__.items():
            if "_widgets" in key:
                widgets.extend(dictionary.values())
        for widget in widgets:
            if widget not in self.viewer.window._qt_window.findChildren(type(widget)):
                undocked_widget = self.viewer.window.add_dock_widget(widget, name=widget.windowTitle())
                undocked_widget.setFloating(True)
                # hide widget if empty property widgets
                if getattr(widget, "property_widgets", False) == {}:
                    undocked_widget.setVisible(False)

    def setDisabled(self, disable: bool) -> None:
        """
        Enable/disable viewer
        :param disable: boolean specifying whether to disable
        """

        widgets = []
        for key, dictionary in self.__dict__.items():
            if "_widgets" in key:
                widgets.extend(dictionary.values())
        for widget in widgets:
            try:
                widget.setDisabled(disable)
            except AttributeError:
                pass

    def update_config_on_quit(self) -> None:
        """
        Add functionality to close function to save device properties to instrument config
        """

        return_value = self.update_config_query()
        if return_value == QMessageBox.Ok:
            self.instrument.update_current_state_config()
            self.instrument.save_config(self.config_save_to)

    def update_config_query(self) -> Literal[0, 1]:
        """
        Pop up message asking if configuration would like to be saved
        :return: user reply to message box
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

    def select_directory(self, pressed: bool, msgBox: QMessageBox) -> None:
        """
        Select directory
        :param pressed: boolean for button press
        :param msgBox:
        """

        fname = QFileDialog()
        folder = fname.getSaveFileName(directory=str(self.instrument.config_path))
        if folder[0] != "":  # user pressed cancel
            msgBox.setText(
                f"Do you want to update the instrument configuration file at {folder[0]} "
                f"to current instrument state?"
            )
            self.config_save_to = Path(folder[0])

    def close(self) -> None:
        """
        Close instruments and end threads
        """

        for worker in self.property_workers:
            worker.quit()
        self.grab_frames_worker.quit()
        for device_name, device_specs in self.instrument.config["instrument"]["devices"].items():
            device_type = device_specs["type"]
            device = getattr(self.instrument, inflection.pluralize(device_type))[device_name]
            try:
                device.close()
            except AttributeError:
                self.log.debug(f"{device_name} does not have close function")
        self.instrument.close()
