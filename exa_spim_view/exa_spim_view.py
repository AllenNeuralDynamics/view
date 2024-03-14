from ruamel.yaml import YAML
from qtpy.QtCore import Slot
from pathlib import Path
import importlib
from device_widgets.base_device_widget import BaseDeviceWidget
from threading import Lock
# from aind_data_schema.core import acquisition
from qtpy.QtWidgets import QPushButton, QStyle, QFileDialog, QRadioButton, QWidget, QButtonGroup, QHBoxLayout, \
    QVBoxLayout, QApplication
import qtpy.QtCore as QtCore
from PIL import Image
from napari.qt.threading import thread_worker, create_worker
import napari
import datetime
from time import sleep
import logging
import sys

class ExaSpimView:

    def __init__(self, instrument, acquisition, config_path: Path, log_level='INFO'):

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)

        # instrument specific locks
        # TODO: Think about filter wheel and how that's connected to stage
        # should locks be object related too?
        self.daq_lock = None
        self.camera_lock = None
        self.scanning_stage_lock = None
        self.tiling_stage_lock = None
        self.laser_lock = None
        self.filter_wheel_lock = None

        # Eventual widget groups
        self.laser_widgets = None
        self.daq_widgets = None
        self.camera_widgets = None
        self.scanning_stage_widgets = None
        self.tiling_stage_widgets = None
        self.filter_wheel_widgets = None

        # Eventual threads
        self.grab_frames_worker = create_worker(lambda: None)  # dummy thread
        self.grab_stage_positions_worker = create_worker(lambda: None)

        # Eventual attributes
        self.livestream_channel = None  # TODO: Dummy wl value for livestream

        self.instrument = instrument
        self.acquisition = acquisition
        self.config = YAML(typ='safe', pure=True).load(config_path)  # TODO: maybe bulldozing comments but easier

        # Convenient config maps
        self.channels = self.instrument.config['instrument']['channels']

        # Setup napari window
        self.viewer = napari.Viewer(title='exa-SPIM-view', ndisplay=2, axis_labels=('x', 'y'))
        app = napari._qt.qt_event_loop.get_app()
        app.lastWindowClosed.connect(self.close)    # shut everything down when closing

        # Set up instrument widgets
        for device in self.instrument.config['instrument']['devices'].keys():
            self.create_device_widgets(getattr(instrument, device), device[:-1])  # remove s for device type

        acquisition_devices = ['writers', 'transfers']
        # Set up acquisition widgets
        for device in acquisition_devices:
            self.create_device_widgets(getattr(acquisition, device), device[:-1])  # remove s for device type

        # setup additional widgets
        self.create_metadata_widget()
        self.create_joystick_widget()
        self.create_laser_widget()

        # setup widget additional functionalities
        self.setup_camera_widgets()
        self.setup_daq_widgets()
        self.setup_filter_wheel_widgets()
        self.setup_live_position()

        # TODO: setup downsampler and downsampler lock

    def setup_daq_widgets(self):
        """Setup saveing to config if widget is from device-widget repo"""

        for daq_name, widget in self.daq_widgets.items():
            if str(widget.__module__) == 'device_widgets.ni_widget':
                widget.ValueChangedInside[str].connect(
                    lambda value, daq=self.instrument.daqs[daq_name], name=daq_name: self.write_waveforms(daq, name))

    def write_waveforms(self, daq, daq_name):
        """Write waveforms if livestreaming is on"""

        if self.grab_frames_worker.is_running:
            ao_task = self.instrument.config['instrument']['devices']['daqs'][daq_name]['tasks'].get('ao_task', None)
            do_task = self.instrument.config['instrument']['devices']['daqs'][daq_name]['tasks'].get('do_task', None)
            for task, task_type in zip([ao_task, do_task], ['ao', 'do']):
                with self.daq_lock:  # lock device
                    daq.generate_waveforms(task, task_type, self.livestream_channel)
                    getattr(daq, f'write_{task_type}_waveforms')()

    def setup_filter_wheel_widgets(self):
        """Setup changing filter wheel changes channel of self.livestream_channel """

        for wheel_name, widget in self.filter_wheel_widgets.items():
            self.channels[self.livestream_channel]['filter_wheel'][wheel_name] = widget.filter
            widget.ValueChangedInside[str].connect(lambda val,
                                                          ch=self.livestream_channel,
                                                          wh=wheel_name,
                                                          slot=widget.filter:
                                                   pathGet(self.channels, [ch, 'filter_wheel']).__setitem__(wh, slot))

    def setup_camera_widgets(self):
        """Setup live view and snapshot button"""

        for camera_name, widget in self.camera_widgets.items():
            # Add functionality to snapshot button
            snapshot_button = getattr(widget, 'snapshot_button', QPushButton())
            snapshot_button.pressed.connect(
                lambda button=snapshot_button: disable_button(button))  # disable to avoid spamming
            snapshot_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera, 1))

            # Add functionality to live button
            live_button = getattr(widget, 'live_button', QPushButton())
            live_button.pressed.connect(lambda button=live_button: disable_button(button))  # disable to avoid spamming
            live_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera))
            live_button.pressed.connect(lambda camera=camera_name: self.toggle_live_button(camera))

    def toggle_live_button(self, camera_name):
        """Toggle text and functionality of live button when pressed"""
        live_button = getattr(self.camera_widgets[camera_name], 'live_button', QPushButton())
        live_button.disconnect()
        if live_button.text() == 'Live':
            live_button.setText('Stop')
            stop_icon = live_button.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
            live_button.setIcon(stop_icon)
            live_button.pressed.connect(self.grab_frames_worker.quit)
        else:
            live_button.setText('Live')
            start_icon = live_button.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            live_button.setIcon(start_icon)
            live_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera_name))

        live_button.pressed.connect(lambda button=live_button: disable_button(button))
        live_button.pressed.connect(lambda camera=camera_name: self.toggle_live_button(camera_name))

    def setup_live(self, camera_name, frames=float('inf')):
        """Set up for either livestream or snapshot"""

        self.grab_frames_worker = self.grab_frames(camera_name, frames)
        self.grab_frames_worker.yielded.connect(self.update_layer)
        self.grab_frames_worker.finished.connect(lambda: self.dismantle_live(camera_name))
        self.grab_frames_worker.start()

        with self.camera_lock:
            self.instrument.cameras[camera_name].prepare()
            self.instrument.cameras[camera_name].start(frames)

        with self.laser_lock:
            self.instrument.lasers[self.livestream_channel].enable()

        with self.filter_wheel_lock:
            name, filter = zip(*self.channels[self.livestream_channel]['filter_wheel'].items())
            self.instrument.filter_wheels[name[0]].filter = filter[0]
            self.filter_wheel_widgets[name[0]].filter = filter[0]

        with self.daq_lock:
            for name, daq in self.instrument.daqs.items():
                ao_task = self.instrument.config['instrument']['devices']['daqs'][name]['tasks'].get('ao_task', None)
                do_task = self.instrument.config['instrument']['devices']['daqs'][name]['tasks'].get('do_task', None)
                co_task = self.instrument.config['instrument']['devices']['daqs'][name]['tasks'].get('co_task', None)
                if ao_task is not None:
                    daq.add_task(ao_task, 'ao')
                    daq.generate_waveforms(ao_task, 'ao', self.livestream_channel)
                    daq.write_ao_waveforms()
                if do_task is not None:
                    daq.add_task(do_task, 'do')
                    daq.generate_waveforms(do_task, 'do', self.livestream_channel)
                    daq.write_do_waveforms()
                if co_task is not None:
                    pulse_count = co_task['timing'].get('pulse_count', None)
                    daq.add_task(co_task, 'co', pulse_count)

                daq.start_all()

    def dismantle_live(self, camera_name):
        """Safely shut down live"""

        with self.camera_lock:
            self.instrument.cameras[camera_name].abort()
        with self.daq_lock:
            for daq in self.instrument.daqs.values():
                daq.stop_all()

    @thread_worker
    def grab_frames(self, camera_name, frames=float("inf")):
        """Grab frames from camera"""
        i = 0
        while i < frames:  # while loop since frames can == inf
            with self.camera_lock:
                frame = self.instrument.cameras[camera_name].grab_frame(), camera_name  # TODO: downsample
            yield frame  # wait until unlocking camera to be able to quit napari thread
            i += 1

    def update_layer(self, args):
        """Update viewer with new multiscaled camera frame"""
        try:
            (image, camera_name) = args
            layer = self.viewer.layers[f"Video {camera_name} {self.livestream_channel}"]
            layer.data = image
        except KeyError:
            # Add image to a new layer if layer doesn't exist yet
            layer = self.viewer.add_image(image, name=f"Video {camera_name} {self.livestream_channel}", )
            layer.mouse_drag_callbacks.append(self.save_image)
            # multiscale=True)
            # TODO: Add scale and what to do if yielded an invalid image

    def save_image(self, layer, event):
        """Save image in viewer by right-clicking viewer"""

        if event.button == 2:  # Left click
            image = Image.fromarray(layer.data)
            camera = layer.name.split(' ')[1]
            local_storage = self.acquisition.writers[camera].path
            fname = QFileDialog()
            folder = fname.getExistingDirectory(directory=local_storage)
            if folder != '':  # user pressed cancel
                # TODO: Allow users to add their own name
                image.save(folder + rf"\{layer.name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.tiff")

    def setup_live_position(self):
        """Set up live position thread"""

        self.grab_stage_positions_worker = self.grab_stage_positions()
        self.grab_stage_positions_worker.yielded.connect(self.update_stage_position)
        self.grab_stage_positions_worker.start()

    @thread_worker
    def grab_stage_positions(self):
        """Grab stage position from all stage objects and yeild positions"""

        while True:  # best way to do this or have some sort of break?
            sleep(.1)
            for name, stage in {**self.instrument.scanning_stages,
                                **self.instrument.tiling_stages}.items():  # combine stage
                with self.scanning_stage_lock and self.tiling_stage_lock:
                    position = stage.position  # don't yield while locked
                yield name, position

    def update_stage_position(self, args):
        """Update stage position in stage widget"""

        (name, position) = args
        stages = {**self.tiling_stage_widgets, **self.scanning_stage_widgets}
        if type(position) == dict:
            for k, v in position.items():
                getattr(stages[name], f"position.{k}_widget").setText(str(v))
        else:
            stages[name].position_widget.setText(str(position))

    def create_metadata_widget(self):
        """Create custom widget for metadata in config"""

        acquisition_properties = dict(self.acquisition.config['acquisition']['metadata'])
        self.metadata_widget = BaseDeviceWidget(acquisition_properties, acquisition_properties)
        self.metadata_widget.ValueChangedInside[str].connect(lambda name:
                                                             self.acquisition.config['acquisition'][
                                                                 'metadata'].__setitem__(name,
                                                                                         getattr(self.metadata_widget,
                                                                                                 name)))
        for name, widget in self.metadata_widget.property_widgets.items():
            widget.setToolTip('')  # reset tooltips
        self.metadata_widget.show()

    def create_joystick_widget(self):
        """Create widget to remap joystick"""

    def create_laser_widget(self):
        """Create widget to select which laser to liverstream with"""

        widget = QWidget()
        widget_layout = QVBoxLayout()

        laser_button_group = QButtonGroup(widget)
        for channel, specs in self.channels.items():
            button = QRadioButton(str(channel))
            button.toggled.connect(lambda value, radio=button: self.change_laser(value, radio))
            laser_button_group.addButton(button)

            laser = self.laser_widgets[specs['laser']]
            widget_layout.addWidget(create_widget('H', button, laser.property_widgets['power_setpoint_mw']))
        button.setChecked(True)  # Arbitrarily set last button checked
        widget.setLayout(widget_layout)
        self.viewer.window.add_dock_widget(widget, area='right', name='Channels')

    def change_laser(self, checked, widget):

        if checked:
            self.livestream_channel = widget.text()
            with self.filter_wheel_lock:
                wheel, filter_slot = zip(*self.channels[self.livestream_channel]['filter_wheel'].items())
                self.instrument.filter_wheels[wheel[0]].filter = filter_slot[0]
                self.filter_wheel_widgets[wheel[0]].filter = filter_slot[0]
            if self.grab_frames_worker.is_running:
                laser = self.channels[self.livestream_channel]['laser']
                with self.laser_lock:
                    self.instrument.lasers[laser].disable()
                for name, daq in self.instrument.daqs.items():
                    self.write_waveforms(daq, name)
                with self.laser_lock:
                    self.instrument.lasers[laser].enable()

    def create_device_widgets(self, devices: dict, device_type: str):
        """Create widgets based on device dictionary attributes from instrument or acquisition
         :param devices: dictionary of devices
         :param device_type: type of device of all devices in dictionary"""
        guis = {}
        for name, device in devices.items():

            specs = self.config['device_widgets'].get(name, {})
            if specs != {} and specs.get('type', '') == device_type:
                gui_class = getattr(importlib.import_module(specs['driver']), specs['module'])
                guis[name] = gui_class(device, **specs.get('init', {}))  # device gets passed into widget
            else:
                properties = scan_for_properties(device)
                guis[name] = BaseDeviceWidget(type(device), properties)

            # if gui is BaseDeviceWidget or inherits from it
            if type(guis[name]) == BaseDeviceWidget or BaseDeviceWidget in type(guis[name]).__bases__:
                # Hook up all widgets to device_property_changed and change_instrument_config which has checks.
                guis[name].ValueChangedInside[str].connect(
                    lambda value, dev=device, gui=guis[name], dev_type=device_type:
                    self.device_property_changed(value, dev, gui, dev_type))
                guis[name].ValueChangedInside[str].connect(
                    lambda value, dev_name=name, gui=guis[name], dev_type=device_type + 's':
                    self.change_instrument_config(value, dev_name, gui, dev_type))

            guis[name].setWindowTitle(f'{device_type} {name}')
            guis[name].show()

        setattr(self, f'{device_type}_widgets', guis)  # set up attribute
        setattr(self, f'{device_type}_lock', Lock())  # set up lock specific to device

        return guis

    @Slot(str)
    def metadata_property_changed(self, name):

        value = getattr(self.metadata_widget, name)
        self.acquisition.config['acquisition']['metadata'][name] = value

    @Slot(str)
    def device_property_changed(self, name, device, widget, device_type):
        """Slot to signal when device widget has been changed
        :param name: name of attribute and widget"""

        with getattr(self, f'{device_type}_lock'):  # lock device
            name_lst = name.split('.')
            self.log.debug(f'widget {name} changed to {getattr(widget, name_lst[0])}')
            value = getattr(widget, name_lst[0])
            if dictionary := getattr(device, name_lst[0], False):
                try:  # Make sure name are referring to same thing in UI and device
                    for k in name_lst[1:]:
                        dictionary = dictionary[k]
                    setattr(device, name_lst[0], value)
                    self.log.info(f'Device changed to {getattr(device, name_lst[0])}')
                    # Update ui with new device values that might have changed
                    # WARNING: Infinite recursion might occur if device property not set correctly
                    for k, v in widget.property_widgets.items():
                        if getattr(widget, k, False):
                            device_value = getattr(device, k)
                            setattr(widget, k, device_value)

                except (KeyError, TypeError):
                    self.log.warning(f"{name} can't be mapped into device properties")
                    pass

    @Slot(str)
    def change_instrument_config(self, name, device_name, widget, device_type):
        """Slot to signal when device widget has been changed
        :param name: name of attribute and widget"""

        name_lst = name.split('.')
        self.log.debug(f'widget {name} changed to {getattr(widget, name_lst[0])}')
        value = getattr(widget, name_lst[0])
        dictionary = self.instrument.config['instrument']['devices'][device_type][device_name]
        try:
            for k in name_lst:
                dictionary = dictionary[k]
            self.instrument.config['instrument']['devices'][device_type][device_name] = value
            self.log.info(f"cfg changed to {self.instrument.config['instrument']['devices'][device_type][device_name]}")

        except KeyError:
            self.log.warning(f"Path {name} can't be mapped into instrument config")
            pass

    def close(self):
        """Close instruments and end threads"""

        self.grab_stage_positions_worker.quit()
        self.grab_frames_worker.quit()
        for device_type in self.instrument.config['instrument']['devices'].keys():
            for device in getattr(self.instrument, device_type).values():
                device.close()


# Convenience Functions. Reused in BaseDeviceWidget. Put somewhere else?
def create_widget(struct: str, *args, **kwargs):
    """Creates either a horizontal or vertical layout populated with widgets
    :param struct: specifies whether the layout will be horizontal, vertical, or combo
    :param kwargs: all widgets contained in layout"""

    layouts = {'H': QHBoxLayout(), 'V': QVBoxLayout()}
    widget = QWidget()
    if struct == 'V' or struct == 'H':
        layout = layouts[struct]
        for arg in [*kwargs.values(), *args]:
            layout.addWidget(arg)

    elif struct == 'VH' or 'HV':
        bin0 = {}
        bin1 = {}
        j = 0
        for v in [*kwargs.values(), *args]:
            bin0[str(v)] = v
            j += 1
            if j == 2:
                j = 0
                bin1[str(v)] = create_widget(struct=struct[0], **bin0)
                bin0 = {}
        return create_widget(struct=struct[1], **bin1)

    layout.setContentsMargins(0, 0, 0, 0)
    widget.setLayout(layout)
    return widget


def scan_for_properties(device):
    """Scan for properties with setters and getters in class and return dictionary
    :param device: object to scan through for properties
    """

    prop_dict = {}
    for attr_name in dir(device):
        attr = getattr(type(device), attr_name, None)
        if isinstance(attr, property):  # and attr.fset is not None:
            prop_dict[attr_name] = getattr(device, attr_name, None)

    return prop_dict


def disable_button(button, pause=1000):
    """Function to disable button clicks for a period of time to avoid crashing gui"""

    button.setEnabled(False)
    QtCore.QTimer.singleShot(pause, lambda: button.setDisabled(False))


def pathGet(dictionary: dict, path: list):
    """Based on list of nested dictionary keys, return inner dictionary"""

    for k in path:
        dictionary = dictionary[k]
    return dictionary
