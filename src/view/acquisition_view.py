import logging
import importlib
from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties, create_widget, label_maker
from view.widgets.acquisition_widgets.metadata_widget import MetadataWidget
from view.widgets.acquisition_widgets.volume_plan_widget import (
    VolumePlanWidget,
    GridFromEdges,
    GridWidthHeight,
    GridRowsColumns,
)
from view.widgets.acquisition_widgets.volume_model import VolumeModel
from view.widgets.acquisition_widgets.channel_plan_widget import ChannelPlanWidget
from qtpy.QtCore import Slot, Qt
import inflection
from time import sleep
from qtpy.QtWidgets import (
    QGridLayout,
    QWidget,
    QComboBox,
    QSizePolicy,
    QScrollArea,
    QDockWidget,
    QLabel,
    QPushButton,
    QSplitter,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QProgressBar,
    QSlider,
    QApplication,
    QHBoxLayout,
    QFrame,
    QFileDialog,
    QMessageBox,
)
from qtpy.QtGui import QFont
from napari.qt.threading import thread_worker, create_worker
from view.widgets.miscellaneous_widgets.q_dock_widget_title_bar import QDockWidgetTitleBar
from view.widgets.miscellaneous_widgets.q_scrollable_float_slider import QScrollableFloatSlider
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit
from pathlib import Path
from typing import Literal, Union, Iterator
import numpy as np
import napari
from napari.qt import get_stylesheet
from napari.settings import get_settings


class AcquisitionView(QWidget):
    """ "Class to act as a general acquisition view model to voxel instrument"""

    def __init__(
        self,
        acquisition,
        instrument_view,
        log_level: Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
    ):
        """
        :param acquisition: voxel acquisition object
        :param instrument_view: view object relating to instrument. Needed to lock stage
        :param log_level: level to set logger at
        """

        super().__init__()
        self.log = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.log.setLevel(log_level)
        self.setStyleSheet(napari.qt.get_current_stylesheet())
        self.setStyleSheet(get_stylesheet(get_settings().appearance.theme))
        self.instrument_view = instrument_view
        self.acquisition = acquisition
        self.instrument = self.acquisition.instrument
        self.config = instrument_view.config
        self.coordinate_plane = self.config["acquisition_view"]["coordinate_plane"]
        self.unit = self.config["acquisition_view"]["unit"]

        # Eventual threads
        self.grab_fov_positions_worker = None
        self.property_workers = []

        # create workers for latest image taken by cameras
        for camera_name, camera in self.instrument.cameras.items():
            worker = self.grab_property_value(camera, "latest_frame", camera_name)
            worker.yielded.connect(lambda args: self.update_acquisition_layer(*args))
            worker.start()
            worker.pause()  # start and pause, so we can resume when acquisition starts and pause when over
            self.property_workers.append(worker)

        for device_name, operation_dictionary in self.acquisition.config["acquisition"]["operations"].items():
            for operation_name, operation_specs in operation_dictionary.items():
                self.create_operation_widgets(device_name, operation_name, operation_specs)

        # setup additional widgets
        self.metadata_widget = self.create_metadata_widget()
        self.acquisition_widget = self.create_acquisition_widget()
        self.start_button = self.create_start_button()
        self.stop_button = self.create_stop_button()

        # setup stage thread
        self.setup_fov_position()

        # Set up main window
        self.main_layout = QGridLayout()

        # Add start and stop button
        self.main_layout.addWidget(self.start_button, 0, 0, 1, 2)
        self.main_layout.addWidget(self.stop_button, 0, 2, 1, 2)

        # add volume widget
        self.main_layout.addWidget(self.acquisition_widget, 1, 0, 5, 3)

        # splitter for operation widgets
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # create scroll wheel for metadata widget
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self.metadata_widget)
        scroll.setWindowTitle("Metadata")
        scroll.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        dock = QDockWidget(scroll.windowTitle(), self)
        dock.setWidget(scroll)
        dock.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        dock.setTitleBarWidget(QDockWidgetTitleBar(dock))
        dock.setWidget(scroll)
        dock.setMinimumHeight(25)
        splitter.addWidget(dock)

        # create dock widget for operations
        for i, operation in enumerate(["writer", "file_transfer", "process", "routine"]):
            if hasattr(self, f"{operation}_widgets"):
                stack = self.stack_device_widgets(operation)
                stack.setFixedWidth(self.metadata_widget.size().width() - 20)
                scroll = QScrollArea()
                scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                scroll.setWidget(stack)
                scroll.setFixedWidth(self.metadata_widget.size().width())
                dock = QDockWidget(stack.windowTitle())
                dock.setTitleBarWidget(QDockWidgetTitleBar(dock))
                dock.setWidget(scroll)
                dock.setMinimumHeight(25)
                setattr(self, f"{operation}_dock", dock)
                splitter.addWidget(dock)
        self.main_layout.addWidget(splitter, 1, 3)
        self.setLayout(self.main_layout)
        self.setWindowTitle("Acquisition View")
        self.show()

        # Set app events
        app = QApplication.instance()
        app.aboutToQuit.connect(self.update_config_on_quit)  # query if config should be saved and where
        self.config_save_to = self.acquisition.config_path
        app.lastWindowClosed.connect(self.close)  # shut everything down when closing

    def create_start_button(self) -> QPushButton:
        """
        Create button to start acquisition
        :return: start button
        """

        start = QPushButton("Start")
        start.clicked.connect(self.start_acquisition)
        start.setStyleSheet("background-color: green")
        return start

    def create_stop_button(self) -> QPushButton:
        """
        Create button to stop acquisition
        :return: stop button
        """

        stop = QPushButton("Stop")
        stop.clicked.connect(self.acquisition.stop_acquisition)
        stop.setStyleSheet("background-color: red")
        stop.setDisabled(True)

        return stop

    def start_acquisition(self) -> None:
        """
        Start acquisition and disable widgets
        """

        # add tiles to acquisition config
        self.update_tiles()

        if self.instrument_view.grab_frames_worker.is_running:  # stop livestream if running
            self.instrument_view.grab_frames_worker.quit()

        # write correct daq values if different from livestream
        for daq_name, daq in self.instrument.daqs.items():
            if daq_name in self.config["acquisition_view"].get("data_acquisition_tasks", {}).keys():
                daq.tasks = self.config["acquisition_view"]["data_acquisition_tasks"][daq_name]["tasks"]

        # anchor grid in volume widget
        for anchor, widget in zip(self.volume_plan.anchor_widgets, self.volume_plan.grid_offset_widgets):
            anchor.setChecked(True)
            widget.setDisabled(True)
        self.volume_plan.tile_table.setDisabled(True)
        self.channel_plan.setDisabled(True)

        # disable acquisition view. Can't disable whole thing so stop button can be functional
        self.start_button.setEnabled(False)
        self.metadata_widget.setEnabled(False)
        for operation in ["writer", "transfer", "process", "routine"]:
            if hasattr(self, f"{operation}_dock"):
                getattr(self, f"{operation}_dock").setDisabled(True)
        self.stop_button.setEnabled(True)
        # disable instrument view
        self.instrument_view.setDisabled(True)

        # Start acquisition
        self.instrument_view.setDisabled(False)
        self.acquisition_thread = create_worker(self.acquisition.run)
        self.acquisition_thread.start()
        self.acquisition_thread.finished.connect(self.acquisition_ended)

        # start all workers
        for worker in self.property_workers:
            worker.resume()
            sleep(1)

    def acquisition_ended(self) -> None:
        """
        Re-enable UI's and threads after acquisition has ended
        """

        # enable acquisition view
        self.start_button.setEnabled(True)
        self.metadata_widget.setEnabled(True)
        for operation in ["writer", "transfer", "process", "routine"]:
            if hasattr(self, f"{operation}_dock"):
                getattr(self, f"{operation}_dock").setDisabled(False)
        self.stop_button.setEnabled(False)

        # write correct daq values if different from acquisition task
        for daq_name, daq in self.instrument.daqs.items():
            if daq_name in self.config["instrument_view"].get("livestream_tasks", {}).keys():
                daq.tasks = self.config["instrument_view"]["livestream_tasks"][daq_name]["tasks"]

        # unanchor grid in volume widget
        # anchor grid in volume widget
        for anchor, widget in zip(self.volume_plan.anchor_widgets, self.volume_plan.grid_offset_widgets):
            anchor.setChecked(False)
            widget.setDisabled(False)
        self.volume_plan.tile_table.setDisabled(False)
        self.channel_plan.setDisabled(False)

        # enable instrument view
        self.instrument_view.setDisabled(False)

        # restart stage threads
        self.setup_fov_position()

        for worker in self.property_workers:
            worker.pause()

    def stack_device_widgets(self, device_type: str) -> QWidget:
        """
        Stack like device widgets in layout and hide/unhide with combo box
        :param device_type: type of device being stacked
        :return: widget containing all widgets pertaining to device type stacked ontop of each other
        """

        device_widgets = {
            f"{inflection.pluralize(device_type)} {device_name}": create_widget("V", **widgets)
            for device_name, widgets in getattr(self, f"{device_type}_widgets").items()
        }

        overlap_layout = QGridLayout()
        overlap_layout.addWidget(QWidget(), 1, 0)  # spacer widget
        for name, widget in device_widgets.items():
            widget.setVisible(False)
            overlap_layout.addWidget(widget, 2, 0)

        visible = QComboBox()
        visible.currentTextChanged.connect(lambda text: self.hide_devices(text, device_widgets))
        visible.addItems(device_widgets.keys())
        visible.setCurrentIndex(0)
        overlap_layout.addWidget(visible, 0, 0)

        overlap_widget = QWidget()
        overlap_widget.setWindowTitle(inflection.pluralize(device_type))
        overlap_widget.setLayout(overlap_layout)

        return overlap_widget

    @staticmethod
    def hide_devices(text: str, device_widgets: dict) -> None:
        """
        Hide device widget if not selected in combo box
        :param text: selected text of combo box
        :param device_widgets: dictionary of widget groups
        """

        for name, widget in device_widgets.items():
            if name != text:
                widget.setVisible(False)
            else:
                widget.setVisible(True)

    def create_metadata_widget(self) -> MetadataWidget:
        """
        Create custom widget for metadata in config
        :return: widget for metadata
        """

        metadata_widget = MetadataWidget(self.acquisition.metadata)
        metadata_widget.ValueChangedInside[str].connect(
            lambda name: setattr(self.acquisition.metadata, name, getattr(metadata_widget, name))
        )
        for name, widget in metadata_widget.property_widgets.items():
            widget.setToolTip("")  # reset tooltips
        metadata_widget.setWindowTitle(f"Metadata")
        return metadata_widget

    def create_acquisition_widget(self) -> QSplitter:
        """
        Create widget to visualize acquisition grid
        :return: splitter widget containing the volume model, volume plan, and channel plan widget
        """

        # find limits of all axes
        lim_dict = {}
        # add tiling stages
        for name, stage in self.instrument.tiling_stages.items():
            lim_dict.update({f"{stage.instrument_axis}": stage.limits_mm})
        # last axis should be scanning axis
        ((scan_name, scan_stage),) = self.instrument.scanning_stages.items()
        lim_dict.update({f"{scan_stage.instrument_axis}": scan_stage.limits_mm})
        try:
            limits = [lim_dict[x.strip("-")] for x in self.coordinate_plane]
        except KeyError:
            raise KeyError("Coordinate plane must match instrument axes in tiling_stages")

        fov_dimensions = self.config["acquisition_view"]["fov_dimensions"]

        acquisition_widget = QSplitter(Qt.Vertical)
        acquisition_widget.setChildrenCollapsible(False)

        # create volume plan
        self.volume_plan = VolumePlanWidget(
            limits=limits, fov_dimensions=fov_dimensions, coordinate_plane=self.coordinate_plane, unit=self.unit
        )
        self.volume_plan.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)

        # create volume model
        self.volume_model = VolumeModel(
            limits=limits,
            fov_dimensions=fov_dimensions,
            coordinate_plane=self.coordinate_plane,
            unit=self.unit,
            **self.config["acquisition_view"]["acquisition_widgets"].get("volume_model", {}).get("init", {}),
        )
        # combine floating volume_model widget with glwindow
        combined_layout = QGridLayout()
        combined_layout.addWidget(self.volume_model, 0, 0, 3, 1)
        combined_layout.addWidget(self.volume_model.widgets, 3, 0, 1, 1)
        combined = QWidget()
        combined.setLayout(combined_layout)
        acquisition_widget.addWidget(create_widget("H", self.volume_plan, combined))

        # create channel plan
        self.channel_plan = ChannelPlanWidget(
            instrument_view=self.instrument_view,
            channels=self.instrument.config["instrument"]["channels"],
            unit=self.unit,
            **self.config["acquisition_view"]["acquisition_widgets"].get("channel_plan", {}).get("init", {}),
        )
        # place volume_plan.tile_table and channel plan table side by side
        table_splitter = QSplitter(Qt.Horizontal)
        table_splitter.setChildrenCollapsible(False)
        table_splitter.setHandleWidth(20)

        widget = QWidget()  # dummy widget to move tile_table down in layout
        widget.setMinimumHeight(25)
        table_splitter.addWidget(create_widget("V", widget, self.volume_plan.tile_table))
        table_splitter.addWidget(self.channel_plan)

        # format splitter handle. Must do after all widgets are added
        handle = table_splitter.handle(1)
        handle_layout = QHBoxLayout(handle)
        line = QFrame(handle)
        line.setStyleSheet("QFrame {border: 1px dotted grey;}")
        line.setFixedHeight(50)
        line.setFrameShape(QFrame.VLine)
        handle_layout.addWidget(line)

        # add tables to layout
        acquisition_widget.addWidget(table_splitter)

        # connect signals
        self.instrument_view.snapshotTaken.connect(self.volume_model.add_fov_image)  # connect snapshot signal
        self.instrument_view.contrastChanged.connect(
            self.volume_model.adjust_glimage_contrast
        )  # connect snapshot adjusted
        self.volume_model.fovHalt.connect(self.stop_stage)  # stop stage if halt button is pressed
        self.volume_model.fovMove.connect(self.move_stage)  # move stage to clicked coords
        self.volume_plan.valueChanged.connect(self.volume_plan_changed)
        self.channel_plan.channelAdded.connect(self.channel_plan_changed)
        self.channel_plan.channelChanged.connect(self.update_tiles)

        # TODO: This feels like a clunky connection. Works for now but could probably be improved
        self.volume_plan.header.startChanged.connect(lambda i: self.create_tile_list())
        self.volume_plan.header.stopChanged.connect(lambda i: self.create_tile_list())

        return acquisition_widget

    def channel_plan_changed(self, channel: str) -> None:
        """
        Handle channel being added to scan
        :param channel: channel added
        """

        tile_order = [[t.row, t.col] for t in self.volume_plan.value()]
        if len(tile_order) != 0:
            self.channel_plan.add_channel_rows(channel, tile_order)
        self.update_tiles()

    def volume_plan_changed(self, value: Union[GridRowsColumns, GridFromEdges, GridWidthHeight]) -> None:
        """
        Update channel plan and volume model when volume plan is changed
        :param value: new value from volume_plan
        """

        tile_volumes = self.volume_plan.scan_ends - self.volume_plan.scan_starts

        # update volume model
        self.volume_model.blockSignals(True)  # only trigger update once
        # self.volume_model.fov_dimensions = self.volume_plan.fov_dimensions
        self.volume_model.grid_coords = self.volume_plan.tile_positions
        self.volume_model.scan_volumes = tile_volumes
        self.volume_model.blockSignals(False)
        self.volume_model.tile_visibility = self.volume_plan.tile_visibility
        self.volume_model.set_path_pos([self.volume_model.grid_coords[t.row][t.col] for t in value])

        # update channel plan
        self.channel_plan.apply_all = self.volume_plan.apply_all
        self.channel_plan.tile_volumes = tile_volumes
        for ch in self.channel_plan.channels:
            self.channel_plan.add_channel_rows(ch, [[t.row, t.col] for t in value])
        self.update_tiles()

    def update_tiles(self) -> None:
        """
        Update config with the latest tiles
        """

        self.acquisition.config["acquisition"]["tiles"] = self.create_tile_list()

    def move_stage(self, fov_position: list[float, float, float]) -> None:
        """
        Slot for moving stage when fov_position is changed internally by grid_widget
        :param fov_position: new fov position to move to
        """
        scalar_coord_plane = [x.strip("-") for x in self.coordinate_plane]
        stage_names = {stage.instrument_axis: name for name, stage in self.instrument.tiling_stages.items()}
        # Move stages
        for axis, position in zip(scalar_coord_plane[:2], fov_position[:2]):
            self.instrument.tiling_stages[stage_names[axis]].move_absolute_mm(position, wait=False)
        ((scan_name, scan_stage),) = self.instrument.scanning_stages.items()
        scan_stage.move_absolute_mm(fov_position[2], wait=False)

    def stop_stage(self) -> None:
        """
        Slot for stop stage
        """

        for name, stage in {
            **getattr(self.instrument, "scanning_stages", {}),
            **getattr(self.instrument, "tiling_stages", {}),
        }.items():  # combine stage
            stage.halt()

    def setup_fov_position(self) -> None:
        """
        Set up live position thread
        """

        self.grab_fov_positions_worker = self.grab_fov_positions()
        self.grab_fov_positions_worker.yielded.connect(lambda pos: setattr(self.volume_plan, "fov_position", pos))
        self.grab_fov_positions_worker.yielded.connect(lambda pos: setattr(self.volume_model, "fov_position", pos))
        self.grab_fov_positions_worker.start()

    @thread_worker
    def grab_fov_positions(self) -> Iterator[list[float, float, float]]:
        """
        Grab stage position from all stage objects and yield positions
        """
        scalar_coord_plane = [x.strip("-") for x in self.coordinate_plane]
        while True:  # best way to do this or have some sort of break?
            fov_pos = [
                self.volume_plan.fov_position[0],
                self.volume_plan.fov_position[1],
                self.volume_plan.fov_position[2],
            ]
            for name, stage in {**self.instrument.tiling_stages, **self.instrument.scanning_stages}.items():
                if stage.instrument_axis in scalar_coord_plane:
                    index = scalar_coord_plane.index(stage.instrument_axis)
                    try:
                        pos = stage.position_mm
                        fov_pos[index] = pos if pos is not None else self.volume_plan.fov_position[index]
                    except ValueError as e:  # Tigerbox sometime coughs up garbage. Locking issue?
                        pass
                    sleep(0.1)
            yield fov_pos

    def create_operation_widgets(self, device_name: str, operation_name: str, operation_specs: dict) -> None:
        """
        Create widgets based on operation dictionary attributes from instrument or acquisition
         :param operation_name: name of operation
         :param device_name: name of device correlating to operation
         :param operation_specs: dictionary describing set up of operation
        """

        operation_type = operation_specs["type"]
        operation = getattr(self.acquisition, inflection.pluralize(operation_type))[device_name][operation_name]

        specs = self.config["acquisition_view"]["operation_widgets"].get(device_name, {}).get(operation_name, {})
        if specs.get("type", "") == operation_type and "driver" in specs.keys() and "module" in specs.keys():
            gui_class = getattr(importlib.import_module(specs["driver"]), specs["module"])
            gui = gui_class(operation, **specs.get("init", {}))  # device gets passed into widget
        else:
            properties = scan_for_properties(operation)
            gui = BaseDeviceWidget(type(operation), properties)  # create label

        # if gui is BaseDeviceWidget or inherits from it
        if type(gui) == BaseDeviceWidget or BaseDeviceWidget in type(gui).__bases__:
            # Hook up widgets to device_property_changed
            gui.ValueChangedInside[str].connect(
                lambda value, op=operation, widget=gui: self.operation_property_changed(value, op, widget)
            )

            updating_props = specs.get("updating_properties", [])
            for prop_name in updating_props:
                descriptor = getattr(type(operation), prop_name)
                unit = getattr(descriptor, "unit", None)
                # if operation is percentage, change property widget to QProgressbar
                if unit in ["%", "percent", "percentage"]:
                    widget = getattr(gui, f"{prop_name}_widget")
                    progress_bar = QProgressBar()
                    progress_bar.setMaximum(100)
                    progress_bar.setMinimum(0)
                    widget.parentWidget().layout().replaceWidget(getattr(gui, f"{prop_name}_widget"), progress_bar)
                    widget.deleteLater()
                    setattr(gui, f"{prop_name}_widget", progress_bar)
                worker = self.grab_property_value(operation, prop_name, getattr(gui, f"{prop_name}_widget"))
                worker.yielded.connect(lambda args: self.update_property_value(*args))
                worker.start()
                worker.pause()  # start and pause, so we can resume when acquisition starts and pause when over
                self.property_workers.append(worker)

        # Add label to gui
        font = QFont()
        font.setBold(True)
        label = QLabel(operation_name)
        label.setFont(font)
        labeled = create_widget("V", label, gui)

        # add ui to widget dictionary
        if not hasattr(self, f"{operation_type}_widgets"):
            setattr(self, f"{operation_type}_widgets", {device_name: {}})
        elif not getattr(self, f"{operation_type}_widgets").get(device_name, False):
            getattr(self, f"{operation_type}_widgets")[device_name] = {}
        getattr(self, f"{operation_type}_widgets")[device_name][operation_name] = labeled

        # TODO: Do we need this?
        for subdevice_name, suboperation_dictionary in operation_specs.get("subdevices", {}).items():
            for suboperation_name, suboperation_specs in suboperation_dictionary.items():
                self.create_operation_widgets(subdevice_name, suboperation_name, suboperation_specs)

        labeled.setWindowTitle(f"{device_name} {operation_type} {operation_name}")
        labeled.show()

    def update_acquisition_layer(self, image: np.ndarray, camera_name: str) -> None:
        """
        Update viewer with latest frame taken during acquisition
        :param image: numpy array to add to viewer
        :param camera_name: name of camera that image came off
        """

        if image is not None:
            # TODO: How to get current channel
            layer_name = f"{camera_name}"
            if layer_name in self.instrument_view.viewer.layers:
                layer = self.instrument_view.viewer.layers[layer_name]
                layer.data = image
            else:
                layer = self.instrument_view.viewer.add_image(image, name=layer_name)

    @thread_worker
    def grab_property_value(self, device: object, property_name: str, widget) -> Iterator:
        """
        Grab value of property and yield
        :param device: device to grab property from
        :param property_name: name of property to get
        :param widget: corresponding device widget
        :return: value of property and widget to update
        """

        while True:  # best way to do this or have some sort of break?
            sleep(1)
            value = getattr(device, property_name)
            yield value, widget

    def update_property_value(self, value, widget) -> None:
        """
        Update stage position in stage widget
        :param widget: widget to update
        :param value: value to update with
        """

        try:
            if type(widget) in [QLineEdit, QScrollableLineEdit]:
                widget.setText(str(value))
            elif type(widget) in [QSpinBox, QDoubleSpinBox, QSlider, QScrollableFloatSlider]:
                widget.setValue(value)
            elif type(widget) == QComboBox:
                index = widget.findText(value)
                widget.setCurrentIndex(index)
            elif type(widget) == QProgressBar:
                widget.setValue(round(value))
        except (RuntimeError, AttributeError):  # Pass when window's closed or widget doesn't have position_mm_widget
            pass

    @Slot(str)
    def operation_property_changed(self, attr_name: str, operation: object, widget) -> None:
        """
        Slot to signal when operation widget has been changed
        :param widget: widget object relating to operation
        :param operation: operation object
        :param attr_name: name of attribute
        """

        name_lst = attr_name.split(".")
        self.log.debug(f"widget {attr_name} changed to {getattr(widget, name_lst[0])}")
        value = getattr(widget, name_lst[0])
        try:  # Make sure name is referring to same thing in UI and operation
            dictionary = getattr(operation, name_lst[0])
            for k in name_lst[1:]:
                dictionary = dictionary[k]
            setattr(operation, name_lst[0], value)
            self.log.info(f"Device changed to {getattr(operation, name_lst[0])}")
            # Update ui with new operation values that might have changed
            # WARNING: Infinite recursion might occur if operation property not set correctly
            for k, v in widget.property_widgets.items():
                if getattr(widget, k, False):
                    operation_value = getattr(operation, k)
                    setattr(widget, k, operation_value)

        except (KeyError, TypeError) as e:
            self.log.warning(f"{attr_name} can't be mapped into operation properties due to {e}")
            pass

    def create_tile_list(self) -> list:
        """
        Return a list of tiles for a scan
        :return: list of tiles
        """

        tiles = []
        tile_slice = slice(self.volume_plan.start, self.volume_plan.stop)
        value = self.volume_plan.value()
        sliced_value = [tile for tile in value][tile_slice]
        if self.channel_plan.channel_order.currentText() == "per Tile":
            for tile in sliced_value:
                for ch in self.channel_plan.channels:
                    tiles.append(self.write_tile(ch, tile))
        elif self.channel_plan.channel_order.currentText() == "per Volume":
            for ch in self.channel_plan.channels:
                for tile in sliced_value:
                    tiles.append(self.write_tile(ch, tile))
        return tiles

    def write_tile(self, channel: str, tile) -> dict:
        """
        Write dictionary describing tile parameters
        :param channel: channel the tile is in
        :param tile: tile object
        :return
        """

        row, column = tile.row, tile.col
        table_row = self.volume_plan.tile_table.findItems(str([row, column]), Qt.MatchExactly)[0].row()

        tile_dict = {
            "channel": channel,
            f"position_{self.unit}": {
                k[0]: self.volume_plan.tile_table.item(table_row, j + 1).data(Qt.EditRole)
                for j, k in enumerate(self.volume_plan.table_columns[1:-2])
            },
            "tile_number": table_row,
        }
        # load channel plan values
        for device_type, properties in self.channel_plan.properties.items():
            if device_type in self.channel_plan.possible_channels[channel].keys():
                for device_name in self.channel_plan.possible_channels[channel][device_type]:
                    tile_dict[device_name] = {}
                    for prop in properties:
                        column_name = label_maker(f"{device_name}_{prop}")
                        if getattr(self.channel_plan, column_name, None) is not None:
                            array = getattr(self.channel_plan, column_name)[channel]
                            input_type = self.channel_plan.column_data_types[column_name]
                            if input_type is not None:
                                tile_dict[device_name][prop] = input_type(array[row, column])
                            else:
                                tile_dict[device_name][prop] = array[row, column]
            else:
                column_name = label_maker(f"{device_type}")
                if getattr(self.channel_plan, column_name, None) is not None:
                    array = getattr(self.channel_plan, column_name)[channel]
                    input_type = self.channel_plan.column_data_types[column_name]
                    if input_type is not None:
                        tile_dict[device_type] = input_type(array[row, column])
                    else:
                        tile_dict[device_type] = array[row, column]

        for name in ["steps", "step_size", "prefix"]:
            array = getattr(self.channel_plan, name)[channel]
            tile_dict[name] = array[row, column]
        return tile_dict

    def update_config_on_quit(self) -> None:
        """
        Add functionality to close function to save device properties to instrument config
        """

        return_value = self.update_config_query()
        if return_value == QMessageBox.Ok:
            self.acquisition.update_current_state_config()
            self.acquisition.save_config(self.config_save_to)

    def update_config_query(self) -> None:
        """
        Pop up message asking if configuration would like to be saved
        """
        msgBox = QMessageBox()
        msgBox.setIcon(QMessageBox.Question)
        msgBox.setText(
            f"Do you want to update the acquisition configuration file at {self.config_save_to} "
            f"to current acquisition state?"
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
        folder = fname.getSaveFileName(directory=str(self.acquisition.config_path))
        if folder[0] != "":  # user pressed cancel
            msgBox.setText(
                f"Do you want to update the instrument configuration file at {folder[0]} "
                f"to current instrument state?"
            )
            self.config_save_to = Path(folder[0])

    def close(self) -> None:
        """
        Close operations and end threads
        """

        for worker in self.property_workers:
            worker.quit()
        self.grab_fov_positions_worker.quit()
        for device_name, operation_dictionary in self.acquisition.config["acquisition"]["operations"].items():
            for operation_name, operation_specs in operation_dictionary.items():
                operation_type = operation_specs["type"]
                operation = getattr(self.acquisition, inflection.pluralize(operation_type))[device_name][operation_name]
                try:
                    operation.close()
                except AttributeError:
                    self.log.debug(f"{device_name} {operation_name} does not have close function")
        self.acquisition.close()
