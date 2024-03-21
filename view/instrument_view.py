from ruamel.yaml import YAML
from qtpy.QtCore import Slot
from pathlib import Path
import importlib
from device_widgets.base_device_widget import BaseDeviceWidget, create_widget, pathGet, label_maker, \
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
from napari._qt.widgets.qt_viewer_dock_widget import QtViewerDockWidget


class InstrumentView:

    def __init__(self, instrument, config_path: Path, log_level='INFO'):

        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)

        # instrument specific locks
        # TODO: Think about filter wheel and how that's connected to stage
        # should locks be object related too?
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
        self.grab_frames_worker = create_worker(lambda: None)  # dummy thread
        self.grab_stage_positions_worker = create_worker(lambda: None)

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

        # Set up instrument widgets #TODO: what to doe about ies plural devices?
        for device_type, device_specs in self.instrument.config['instrument']['devices'].items():
            self.create_device_widgets(device_specs, device_type[:-1])  # remove s for device type

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
        """Setup saveing to config if widget is from device-widget repo"""

        overlap_layout = QGridLayout()
        overlap_layout.addWidget(QWidget(), 1, 0)  # spacer widget
        for daq_name, daq_widget in self.daq_widgets.items():
            if str(daq_widget.__module__) == 'device_widgets.ni_widget':
                daq_widget.ValueChangedInside[str].connect(
                    lambda value, daq=self.instrument.daqs[daq_name], name=daq_name: self.write_waveforms(daq, name))

        stacked = self.stack_device_widgets('daq')
        self.viewer.window.add_dock_widget(stacked, area='right', name='DAQs')

    def stack_device_widgets(self, device_type):
        """Stack like device widgets in layout and hide/unhide with combo box"""

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
        """Hide device widget if not selected in combo box"""

        device_widgets = getattr(self, f'{device_type}_widgets')
        for name, widget in device_widgets.items():
            if name != text:
                widget.setVisible(False)
            else:
                widget.setVisible(True)

    def write_waveforms(self, daq, daq_name):
        """Write waveforms if livestreaming is on"""

        if self.grab_frames_worker.is_running:
            ao_task = self.instrument.config['instrument']['devices']['daqs'][daq_name]['tasks'].get('ao_task', None)
            do_task = self.instrument.config['instrument']['devices']['daqs'][daq_name]['tasks'].get('do_task', None)
            for task, task_type in zip([ao_task, do_task], ['ao', 'do']):
                with self.daq_locks[daq_name]:  # lock device
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
        stacked = self.stack_device_widgets('filter_wheel')
        self.viewer.window.add_dock_widget(stacked, area='bottom', name='Filter Wheels')

    def setup_camera_widgets(self):
        """Setup live view and snapshot button"""

        overlap_layout = QGridLayout()
        overlap_layout.addWidget(QWidget(), 1, 0)  # spacer widget
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


        with self.camera_locks[camera_name]:
            self.instrument.cameras[camera_name].prepare()
            self.instrument.cameras[camera_name].start(frames)

        laser_name = self.channels[self.livestream_channel]['laser']
        with self.laser_locks[laser_name]:
            self.instrument.lasers[self.livestream_channel].enable()

        filter_name, filter_slot = list(self.channels[self.livestream_channel]['filter_wheel'].items())[0]
        with self.filter_wheel_locks[filter_name]:
            self.instrument.filter_wheels[filter_name].filter = filter_slot
            self.filter_wheel_widgets[filter_name].filter = filter_slot

        for daq_name, daq in self.instrument.daqs.items():
            with self.daq_locks[daq_name]:
                ao_task = self.instrument.config['instrument']['devices']['daqs'][daq_name]['tasks'].get('ao_task', None)
                do_task = self.instrument.config['instrument']['devices']['daqs'][daq_name]['tasks'].get('do_task', None)
                co_task = self.instrument.config['instrument']['devices']['daqs'][daq_name]['tasks'].get('co_task', None)
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

        with self.camera_locks[camera_name]:
            self.instrument.cameras[camera_name].abort()
        for daq_name, daq in self.instrument.daqs.items():
            with self.daq_locks[daq_name]:
                daq.stop_all()

    @thread_worker
    def grab_frames(self, camera_name, frames=float("inf")):
        """Grab frames from camera"""
        i = 0
        while i < frames:  # while loop since frames can == inf
            with self.camera_locks[camera_name]:
                frame = self.instrument.cameras[camera_name].grab_frame(), camera_name
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
            # TODO: Add scale and what to do if yielded an invalid image

    # def save_image(self, layer, event):
    #     """Save image in viewer by right-clicking viewer"""
    #
    #     if event.button == 2:  # Left click
    #         image = Image.fromarray(layer.data)
    #         camera = layer.name.split(' ')[1]
    #         local_storage = self.acquisition.writers[camera].path
    #         fname = QFileDialog()
    #         folder = fname.getExistingDirectory(directory=local_storage)
    #         if folder != '':  # user pressed cancel
    #             # TODO: Allow users to add their own name
    #             image.save(folder + rf"\{layer.name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.tiff")

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
                with self.scanning_stage_locks.get(name, Lock()) and self.tiling_stage_locks.get(name, Lock()):
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

    def setup_channel_widget(self):
        """Create widget to select which laser to liverstream with"""

        widget = QWidget()
        widget_layout = QHBoxLayout()

        laser_button_group = QButtonGroup(widget)
        for channel, specs in self.channels.items():
            button = QRadioButton(str(channel))
            button.toggled.connect(lambda value, radio=button: self.change_channel(value, radio))
            laser_button_group.addButton(button)
            widget_layout.addWidget(create_widget('H', button, self.laser_widgets[specs['laser']]))
            button.setChecked(True)  # Arbitrarily set last button checked
        widget.setLayout(widget_layout)
        self.viewer.window.add_dock_widget(widget, area='bottom', name='Channels')

    def change_channel(self, checked, widget):

        if checked:
            self.livestream_channel = widget.text()
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

    def create_device_widgets(self, devices: dict, device_type: str, lock: Lock = None):
        """Create widgets based on device dictionary attributes from instrument or acquisition
         :param lock: lock to be used for device
         :param devices: dictionary of devices
         :param device_type: type of device of all devices in dictionary,
         """

        guis = {}
        for name, device_specs in devices.items():
            device = getattr(self.instrument, device_type + 's')[name]

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

            # set up lock for device in corresponding device task dictionary
            if not hasattr(self, f'{device_type}_locks'):
                setattr(self, f'{device_type}_locks', {})
            getattr(self, f'{device_type}_locks')[name] = Lock() if lock is None else lock

            # add ui to widget dictionary
            if not hasattr(self, f'{device_type}_widgets'):
                setattr(self, f'{device_type}_widgets', {})
            getattr(self, f'{device_type}_widgets')[name] = guis[name]


            for subdevice_type, subdevice_dictionary in device_specs.get('subdevices', {}).items():
                # if device has subdevice, create and pass on same Lock()
                self.create_device_widgets(subdevice_dictionary, subdevice_type[:-1],
                                           getattr(self, f'{device_type}_locks')[name])
                
            guis[name].setWindowTitle(f'{device_type} {name}')
            guis[name].show()

        return guis

    @Slot(str)
    def device_property_changed(self, name, device, widget, device_type):
        """Slot to signal when device widget has been changed
        :param name: name of attribute and widget"""

        with getattr(self, f'{device_type}_locks')[name]:  # lock device
            name_lst = name.split('.')
            self.log.debug(f'widget {name} changed to {getattr(widget, name_lst[0])}')
            value = getattr(widget, name_lst[0])
            if dictionary := getattr(device, name_lst[0], False):
                try:  # Make sure name is referring to same thing in UI and device
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
        :param device_type: type of device
        :param widget: widget changed
        :param device_name: key of device in instrument config
        :param name: name of attribute and widget"""

        path = name.split('.')
        self.log.debug(f'widget {name} changed to {getattr(widget, path[0])}')
        key = path[-1]
        value = getattr(widget, name)
        try:
            dictionary = pathGet(self.instrument.config['instrument']['devices'][device_type][device_name], path[:-1])
            if key not in dictionary.keys():
                raise KeyError
            dictionary[key] = value
            self.log.info(f"Config {'.'.join(path)} changed to "
                          f"{pathGet(self.instrument.config['instrument']['devices'][device_type][device_name], path[:-1])}")

        except KeyError:
            self.log.warning(f"Path {name} can't be mapped into instrument config")

    def add_undocked_widgets(self):
        """Add undocked widget so all windows close when closing napari viewer"""

        for device_type in self.instrument.config['instrument']['devices'].keys():
            for name in getattr(self.instrument, device_type).keys():
                widget = getattr(self, f'{device_type[:-1]}_widgets')[name]
                if widget not in self.viewer.window._qt_window.findChildren(type(widget)):
                    undocked_widget = self.viewer.window.add_dock_widget(widget, name=name)
                    undocked_widget.setFloating(True)

    def close(self):
        """Close instruments and end threads"""

        self.grab_stage_positions_worker.quit()
        self.grab_frames_worker.quit()
        for device_type in self.instrument.config['instrument']['devices'].keys():
            for device in getattr(self.instrument, device_type).values():
                device.close()
        # TODO: Save config and upload device states to config maybe. Pop up to ask if saving?
