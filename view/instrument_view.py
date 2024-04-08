from ruamel.yaml import YAML
from qtpy.QtCore import Slot
from pathlib import Path
import importlib
from instrument_widgets.base_device_widget import BaseDeviceWidget, create_widget, pathGet, label_maker, \
    scan_for_properties, disable_button
from threading import Lock
from qtpy.QtWidgets import QPushButton, QStyle, QFileDialog, QRadioButton, QWidget, QButtonGroup, QHBoxLayout, \
    QGridLayout, QComboBox
from PIL import Image
from napari.qt.threading import thread_worker, create_worker
import napari
import datetime
from time import sleep
import logging
import inflection

class InstrumentView:
    """"Class to act as a general instrument view model to voxel instrument"""

    def __init__(self, instrument, config_path: Path, log_level='INFO'):

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)

        # Eventual locks
        self.daq_locks = {}
        self.camera_locks = {}
        self.scanning_stage_locks = {}
        self.tiling_stage_locks = {}
        self.laser_locks = {}
        self.filter_wheel_locks = {}

        # Eventual widget groups
        self.laser_widgets = {}
        self.daq_widgets = {}
        self.camera_widgets = {}
        self.scanning_stage_widgets = {}
        self.tiling_stage_widgets = {}
        self.filter_wheel_widgets = {}
        self.joystick_widgets = {}

        # Eventual threads
        self.grab_frames_worker = create_worker(lambda: None) # dummy thread
        self.grab_stage_positions_worker = None

        # Eventual attributes
        self.livestream_channel = None

        self.instrument = instrument
        self.config = YAML(typ='safe', pure=True).load(config_path)  # TODO: maybe bulldozing comments but easier

        # Convenient config maps
        self.channels = self.instrument.config['instrument']['channels']

        # Setup napari window
        self.viewer = napari.Viewer(title='View', ndisplay=2, axis_labels=('x', 'y'))
        app = napari._qt.qt_event_loop.get_app()
        app.lastWindowClosed.connect(self.close)  # shut everything down when closing

        # Set up instrument widgets
        for device_name, device_specs in self.instrument.config['instrument']['devices'].items():
            self.create_device_widgets(device_name, device_specs)

        # setup widget additional functionalities
        self.setup_camera_widgets()
        self.setup_daq_widgets()
        self.setup_channel_widget()
        self.setup_filter_wheel_widgets()
        self.setup_stage_widgets()
        self.setup_live_position()

        # add undocked widget so everything closes together
        self.add_undocked_widgets()

    def setup_stage_widgets(self):
        """Arrange stage position and joystick widget"""

        stage_layout = QGridLayout()
        stage_layout.addWidget(create_widget('H', **self.scanning_stage_widgets, **self.tiling_stage_widgets))
        stacked = self.stack_device_widgets('joystick')
        stage_layout.addWidget(stacked)

        stage_widget = QWidget()
        stage_widget.setLayout(stage_layout)
        self.viewer.window.add_dock_widget(stage_widget, area='left', name='Stages')

    def setup_daq_widgets(self):
        """Setup saving to config if widget is from device-widget repo"""

        for daq_name, daq_widget in self.daq_widgets.items():
            # if daq_widget is BaseDeviceWidget or inherits from it
            if type(daq_widget) == BaseDeviceWidget or BaseDeviceWidget in type(daq_widget).__bases__:
                daq_widget.ValueChangedInside[str].connect(
                    lambda value, daq=self.instrument.daqs[daq_name], name=daq_name: self.write_waveforms(daq, name))

        stacked = self.stack_device_widgets('daq')
        self.viewer.window.add_dock_widget(stacked, area='right', name='DAQs')

    def stack_device_widgets(self, device_type):
        """Stack like device widgets in layout and hide/unhide with combo box
        :param device_type: type of device being stacked"""

        device_widgets = getattr(self, f'{device_type}_widgets')
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

    def hide_devices(self, text, device_type):
        """Hide device widget if not selected in combo box
        :param text: selected text of combo box
        :param device_type: type of device related to combo box"""

        device_widgets = getattr(self, f'{device_type}_widgets')
        for name, widget in device_widgets.items():
            if name != text:
                widget.setVisible(False)
            else:
                widget.setVisible(True)

    def write_waveforms(self, daq, daq_name):
        """Write waveforms if livestreaming is on
        :param daq: daq object
        :param daq_name: name of daq"""

        if self.grab_frames_worker.is_running:  # if currently livestreaming
            with self.daq_locks[daq_name]:  # lock device
                if daq.ao_task is not None:
                    daq.generate_waveforms('ao', self.livestream_channel)
                    daq.write_ao_waveforms(rereserve_buffer=False)
                if daq.do_task is not None:
                    daq.generate_waveforms('do', self.livestream_channel)
                    daq.write_do_waveforms(rereserve_buffer=False)


    def setup_filter_wheel_widgets(self):
        """Setup changing filter wheel changes channel of self.livestream_channel """

        for wheel_name, wheel_widget in self.filter_wheel_widgets.items():
            self.channels[self.livestream_channel]['filter_wheel'][wheel_name] = wheel_widget.filter
            if type(wheel_widget) == BaseDeviceWidget or BaseDeviceWidget in type(wheel_widget).__bases__:
                wheel_widget.ValueChangedInside[str].connect(lambda val,
                                                              ch=self.livestream_channel,
                                                              wh=wheel_name,
                                                              slot=wheel_widget.filter:
                                                       pathGet(self.channels, [ch, 'filter_wheel']).__setitem__(wh, slot))
        stacked = self.stack_device_widgets('filter_wheel')
        self.viewer.window.add_dock_widget(stacked, area='bottom', name='Filter Wheels')

    def setup_camera_widgets(self):
        """Setup live view and snapshot button"""

        for camera_name, camera_widget in self.camera_widgets.items():
            # Add functionality to snapshot button
            snapshot_button = getattr(camera_widget, 'snapshot_button', QPushButton())
            snapshot_button.pressed.connect(
                lambda button=snapshot_button: disable_button(button))  # disable to avoid spamming
            snapshot_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera, 1))

            # Add functionality to live button
            live_button = getattr(camera_widget, 'live_button', QPushButton())
            live_button.pressed.connect(lambda button=live_button: disable_button(button))  # disable to avoid spamming
            live_button.pressed.connect(lambda camera=camera_name: self.setup_live(camera))
            live_button.pressed.connect(lambda camera=camera_name: self.toggle_live_button(camera))

        stacked = self.stack_device_widgets('camera')
        self.viewer.window.add_dock_widget(stacked, area='right', name='Cameras')

    def toggle_live_button(self, camera_name):
        """Toggle text and functionality of live button when pressed
        :param camera_name: name of camera to set up"""

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
        """Set up for either livestream or snapshot
        :param camera_name: name of camera to set up
        :param frames: how many frames to take"""

        self.grab_frames_worker = self.grab_frames(camera_name, frames)
        self.grab_frames_worker.yielded.connect(self.update_layer)
        self.grab_frames_worker.finished.connect(lambda: self.dismantle_live(camera_name))
        self.grab_frames_worker.start()


        with self.camera_locks[camera_name]:
            self.instrument.cameras[camera_name].prepare()
            self.instrument.cameras[camera_name].start(frames)

        laser_name = self.channels[self.livestream_channel]['laser']
        with self.laser_locks[laser_name]:
            self.instrument.lasers[laser_name].enable()

        filter_name, filter_slot = list(self.channels[self.livestream_channel]['filter_wheel'].items())[0]
        with self.filter_wheel_locks[filter_name]:
            self.instrument.filter_wheels[filter_name].filter = filter_slot
            self.filter_wheel_widgets[filter_name].filter = filter_slot

        for daq_name, daq in self.instrument.daqs.items():
            with self.daq_locks[daq_name]:
                if daq.tasks.get('ao_task', None) is not None:
                    daq.add_task('ao')
                    daq.generate_waveforms('ao', self.livestream_channel)
                    daq.write_ao_waveforms()
                if daq.tasks.get('do_task', None) is not None:
                    daq.add_task('do')
                    daq.generate_waveforms('do', self.livestream_channel)
                    daq.write_do_waveforms()
                if daq.tasks.get('co_task', None) is not None:
                    pulse_count = daq.tasks['co_task']['timing'].get('pulse_count', None)
                    daq.add_task('co', pulse_count)

                daq.start()

    def dismantle_live(self, camera_name):
        """Safely shut down live
        :param camera_name: name of camera to shut down live"""

        with self.camera_locks[camera_name]:
            self.instrument.cameras[camera_name].abort()
        for daq_name, daq in self.instrument.daqs.items():
            with self.daq_locks[daq_name]:
                daq.stop()
        laser_name = self.channels[self.livestream_channel]['laser']
        with self.laser_locks[laser_name]:
            self.instrument.lasers[laser_name].disable()

    @thread_worker
    def grab_frames(self, camera_name, frames=float("inf")):
        """Grab frames from camera
        :param frames: how many frames to take
        :param camera_name: name of camera"""

        i = 0
        while i < frames:  # while loop since frames can == inf
            with self.camera_locks[camera_name]:
                frame_info = self.instrument.cameras[camera_name].grab_frame(), camera_name
            yield frame_info  # wait until unlocking camera to be able to quit napari thread
            i += 1

    def update_layer(self, args):
        """Update viewer with new camera frame
        :param args: tuple containing image and camera name"""

        (image, camera_name) = args
        if image is not None:
            try:
                layer = self.viewer.layers[f"Video {camera_name} {self.livestream_channel}"]
                layer.data = image
            except KeyError:
                # Add image to a new layer if layer doesn't exist yet
                layer = self.viewer.add_image(image, name=f"Video {camera_name} {self.livestream_channel}")
                layer.mouse_drag_callbacks.append(self.save_image)
                # TODO: Add scale?

    def save_image(self, layer, event):
        """Save image in viewer by right-clicking viewer
        :param layer: layer that was pressed
        :param event: event type"""

        if event.button == 2:  # Left click
            image = Image.fromarray(layer.data)
            fname = QFileDialog()
            folder = fname.getSaveFileName(directory=str(Path(__file__).parent.resolve()/
                                  Path(rf"\{layer.name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.tiff")))
            if folder[0] != '':  # user pressed cancel
                image.save(folder[0])

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
            for name, stage in self.instrument.tiling_stages.items():  # combine stage
                with self.scanning_stage_locks.get(name, Lock()) and self.tiling_stage_locks.get(name, Lock()):
                    position = stage.position  # don't yield while locked
                yield name, position

    def update_stage_position(self, args):
        """Update stage position in stage widget
        :param args: tuple containing the name of stage and position of stage"""

        (name, position) = args
        stages = {**self.tiling_stage_widgets, **self.scanning_stage_widgets}   # group stage widgets dicts to find name
        if type(position) == dict:
            for k, v in position.items():
                try:
                    getattr(stages[name], f"position.{k}_widget").setText(str(v))
                except RuntimeError:    # Pass error when window has been closed
                    pass
        else:
            stages[name].position_widget.setText(str(position))

    def setup_channel_widget(self):
        """Create widget to select which laser to livestream with"""

        widget = QWidget()
        widget_layout = QHBoxLayout()

        laser_button_group = QButtonGroup(widget)
        for channel, specs in self.channels.items():
            button = QRadioButton(str(channel))
            button.toggled.connect(lambda value, ch=channel: self.change_channel(value, ch))
            laser_button_group.addButton(button)
            widget_layout.addWidget(create_widget('H', button, self.laser_widgets[specs['laser']]))
            button.setChecked(True)  # Arbitrarily set last button checked
        widget.setLayout(widget_layout)
        self.viewer.window.add_dock_widget(widget, area='bottom', name='Channels')

    def change_channel(self, checked, channel):
        """Update livestream_channel to newly selected channel
        :param channel: name of channel
        :param checked: if button is checked (True) or unchecked(False)"""

        if checked:
            self.livestream_channel = channel
            filter_name, filter_slot = list(self.channels[self.livestream_channel]['filter_wheel'].items())[0]
            with self.filter_wheel_locks[filter_name]:
                self.instrument.filter_wheels[filter_name].filter = filter_slot
                self.filter_wheel_widgets[filter_name].filter = filter_slot
            if self.grab_frames_worker.is_running:
                laser_name = self.channels[self.livestream_channel]['laser']
                with self.laser_locks[laser_name]:
                    self.instrument.lasers[laser_name].disable()
                for daq_name, daq in self.instrument.daqs.items():
                    self.write_waveforms(daq, daq_name)
                with self.laser_locks[laser_name]:
                    self.instrument.lasers[laser_name].enable()

    def create_device_widgets(self,  device_name: str, device_specs: dict, lock: Lock = None):
        """Create widgets based on device dictionary attributes from instrument or acquisition
         :param lock: lock to be used for device
         :param device_name: name of device
         :param device_specs: dictionary dictating how device should be set up
         """
        lock = Lock() if lock is None else lock

        device_type = device_specs['type']
        device = getattr(self.instrument, inflection.pluralize(device_type))[device_name]

        specs = self.config['device_widgets'].get(device_name, {})
        if specs != {} and specs.get('type', '') == device_type:
            gui_class = getattr(importlib.import_module(specs['driver']), specs['module'])
            gui = gui_class(device, **specs.get('init', {}))  # device gets passed into widget
        else:
            properties = scan_for_properties(device)
            gui = BaseDeviceWidget(type(device), properties)

        # if gui is BaseDeviceWidget or inherits from it
        if type(gui) == BaseDeviceWidget or BaseDeviceWidget in type(gui).__bases__:
            # Hook up widgets to device_property_changed
            gui.ValueChangedInside[str].connect(
                lambda value, dev=device, widget=gui, dev_lock=lock:
                self.device_property_changed(value, dev, widget, dev_lock))

        # set up lock for device in corresponding device task dictionary
        if not hasattr(self, f'{device_type}_locks'):
            setattr(self, f'{device_type}_locks', {})
        getattr(self, f'{device_type}_locks')[device_name] = lock

        # add ui to widget dictionary
        if not hasattr(self, f'{device_type}_widgets'):
            setattr(self, f'{device_type}_widgets', {})
        getattr(self, f'{device_type}_widgets')[device_name] = gui


        for subdevice_name, subdevice_specs in device_specs.get('subdevices', {}).items():
            # if device has subdevice, create and pass on same Lock()
            self.create_device_widgets(subdevice_name, subdevice_specs,
                                       getattr(self, f'{device_type}_locks')[device_name])

        gui.setWindowTitle(f'{device_type} {device_name}')
        gui.show()

    @Slot(str)
    def device_property_changed(self, attr_name: str, device, widget, device_lock: Lock):
        """Slot to signal when device widget has been changed
        :param device_lock: lock corresponding to device
        :param widget: widget object relating to device
        :param device: device object
        :param attr_name: name of attribute"""

        with device_lock:  # lock device
            name_lst = attr_name.split('.')
            self.log.debug(f'widget {attr_name} changed to {getattr(widget, name_lst[0])}')
            value = getattr(widget, name_lst[0])
            try:  # Make sure name is referring to same thing in UI and device
                dictionary = getattr(device, name_lst[0])
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
                self.log.warning(f"{attr_name} can't be mapped into device properties")
                pass

    def add_undocked_widgets(self):
        """Add undocked widget so all windows close when closing napari viewer"""

        widgets = []
        for key, dictionary in self.__dict__.items():
            if '_widgets' in key:
                widgets.extend(dictionary.values())
        for widget in widgets:
            if widget not in self.viewer.window._qt_window.findChildren(type(widget)):
                undocked_widget = self.viewer.window.add_dock_widget(widget, name=widget.windowTitle())
                undocked_widget.setFloating(True)

    def close(self):
        """Close instruments and end threads"""

        self.grab_stage_positions_worker.quit()
        self.grab_frames_worker.quit()
        for device_name, device_specs in self.instrument.config['instrument']['devices'].items():
            device_type = device_specs['type']
            device = getattr(self.instrument, inflection.pluralize(device_type))[device_name]
            with getattr(self, f'{device_type}_locks')[device_name]:
                try:
                    device.close()
                except AttributeError:
                    self.log.debug(f'{device_name} does not have close function')
