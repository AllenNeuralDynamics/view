from random import randint
from typing import Union

import numpy as np
import qtpy.QtGui as QtGui
from qtpy.QtCore import Qt, Slot
from qtpy.QtWidgets import QComboBox, QSizePolicy, QTreeWidgetItem
from scipy import signal

from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, label_maker, pathGet
from view.widgets.device_widgets.waveform_widget import WaveformWidget
from view.widgets.miscellaneous_widgets.q_non_scrollable_tree_widget import QNonScrollableTreeWidget
from view.widgets.miscellaneous_widgets.q_scrollable_float_slider import QScrollableFloatSlider
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit


class NIWidget(BaseDeviceWidget):
    """_summary_"""

    def __init__(self, daq, exposed_branches: dict = None, advanced_user: bool = True):
        """_summary_

        :param daq: _description_
        :type daq: _type_
        :param exposed_branches: _description_, defaults to None
        :type exposed_branches: dict, optional
        :param advanced_user: _description_, defaults to True
        :type advanced_user: bool, optional
        """
        self.advanced_user = advanced_user
        self.exposed_branches = {"tasks": daq.tasks} if exposed_branches is None else exposed_branches

        # initialize base widget to create convenient widgets and signals
        super().__init__(daq, {"tasks": daq.tasks})
        del self.property_widgets["tasks"]  # delete so view won't confuse and try and update. Hacky?
        # available channels    #TODO: this seems pretty hard coded?  A way to avoid this?
        self.ao_physical_chans = [x.replace(f"{daq.id}/", "") for x in daq.ao_physical_chans]
        self.co_physical_chans = [x.replace(f"{daq.id}/", "") for x in daq.co_physical_chans]
        self.do_physical_chans = [x.replace(f"{daq.id}/", "") for x in daq.do_physical_chans]
        self.dio_ports = [x.replace(f"{daq.id}/", "") for x in daq.dio_ports]

        # create waveform widget
        if advanced_user:
            self.waveform_widget = WaveformWidget()
            self.waveform_widget.setYRange(daq.min_ao_volts, daq.max_ao_volts)

        # create tree widget and format configured widgets into tree
        self.tree = QNonScrollableTreeWidget()
        for tasks, widgets in self.exposed_branches.items():
            header = QTreeWidgetItem(
                self.tree, [label_maker(tasks.split(".")[-1])]
            )  # take last of list incase key is a map
            self.create_tree_widget(tasks, header)

        self.tree.setHeaderLabels(["Tasks", "Values"])
        self.tree.setColumnCount(2)

        # Set up waveform widget
        if advanced_user:
            graph_parent = QTreeWidgetItem(self.tree, ["Graph"])
            graph_child = QTreeWidgetItem(graph_parent)
            self.tree.setItemWidget(
                graph_child, 1, create_widget("H", self.waveform_widget.legend, self.waveform_widget)
            )
            graph_parent.addChild(graph_child)

        self.setCentralWidget(self.tree)
        self.tree.expandAll()

        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

    def update_waveform(self, channel_name: str) -> None:
        """_summary_

        :param channel_name: _description_
        :type channel_name: str
        """
        if not self.advanced_user:
            return

        name_lst = channel_name.split(".")
        task = ".".join(name_lst[: name_lst.index("ports")])
        port_name = ".".join(name_lst[: name_lst.index("ports") + 2])
        wl = name_lst[-1]

        waveform = getattr(self, f"{port_name}.waveform")
        kwargs = {
            "sampling_frequency_hz": getattr(self, f"{task}.timing.sampling_frequency_hz"),
            "period_time_ms": getattr(self, f"{task}.timing.period_time_ms"),
            "start_time_ms": getattr(self, f"{port_name}.parameters.start_time_ms.channels.{wl}"),
            "end_time_ms": getattr(self, f"{port_name}.parameters.end_time_ms.channels.{wl}"),
            "rest_time_ms": getattr(self, f"{task}.timing.rest_time_ms"),
        }

        scale = kwargs["sampling_frequency_hz"] / 1000  # account for scaling that occurs in waveform functions

        if waveform == "square wave":
            kwargs["max_volts"] = getattr(self, f"{port_name}.parameters.max_volts.channels.{wl}", 5)
            kwargs["min_volts"] = getattr(self, f"{port_name}.parameters.min_volts.channels.{wl}", 0)
            voltages = square_wave(**kwargs)
            start = int(kwargs["start_time_ms"] * scale)
            end = int(kwargs["period_time_ms"] * scale)
            y = [
                kwargs["min_volts"],
                kwargs["min_volts"],
                kwargs["max_volts"],
                kwargs["max_volts"],
                kwargs["min_volts"],
                kwargs["min_volts"],
            ]
            x = [0, start - 1, start, end, end + 1, len(voltages)]
        else:
            kwargs["amplitude_volts"] = getattr(self, f"{port_name}.parameters.amplitude_volts.channels.{wl}")
            kwargs["offset_volts"] = getattr(self, f"{port_name}.parameters.offset_volts.channels.{wl}")
            kwargs["cutoff_frequency_hz"] = getattr(self, f"{port_name}.parameters.cutoff_frequency_hz.channels.{wl}")
            if waveform == "sawtooth":
                voltages = sawtooth(**kwargs)
                max_point = (
                    int(kwargs["end_time_ms"] * scale) if kwargs["end_time_ms"] != kwargs["period_time_ms"] else -1
                )
            else:
                voltages = triangle_wave(**kwargs)
                max_point = round(
                    (kwargs["start_time_ms"] + ((kwargs["period_time_ms"] - kwargs["start_time_ms"]) / 2)) * scale
                )

            pre_rise_point = int(kwargs["start_time_ms"] * scale)
            post_rise_point = int(kwargs["period_time_ms"] * scale) if kwargs["rest_time_ms"] != 0 else -1

            y = [voltages[0], voltages[pre_rise_point], voltages[max_point], voltages[post_rise_point], voltages[-1]]
            x = [0, pre_rise_point, max_point, post_rise_point, len(voltages)]

        if "do_task" not in channel_name:
            # Add min and max for graph
            kwargs["device_max_volts"] = getattr(self, f"{port_name}.device_max_volts")
            kwargs["device_min_volts"] = getattr(self, f"{port_name}.device_min_volts")

        if item := getattr(self, f"{port_name}.{wl}_plot_item", False):
            color = item.color
            self.waveform_widget.removeDraggableGraphItem(item)
        else:
            colors = QtGui.QColor.colorNames()
            colors.remove("black")
            color = colors[randint(0, len(colors) - 1)]
        item = self.waveform_widget.plot(
            pos=np.column_stack((x, y)),
            waveform=waveform,
            name=name_lst[name_lst.index("ports") + 1] + " " + wl,
            color=color,
            parameters={
                **{k: v["channels"][wl] for k, v in getattr(self, f"{port_name}.parameters").items()},
                **kwargs,
            },
        )
        item.valueChanged[str, float].connect(
            lambda var, val: self.waveform_value_changed(val, f"{port_name}.parameters.{var}.channels.{wl}")
        )
        setattr(self, f"{port_name}.{wl}_plot_item", item)

    @Slot(str, float)
    def waveform_value_changed(self, value: float, name: str) -> None:
        """_summary_

        :param value: _description_
        :type value: float
        :param name: _description_
        :type name: str
        """
        name_lst = name.split(".")
        if hasattr(self, f"{name}_slider"):  # value is included in exposed branches
            textbox = getattr(self, f"{name}_widget")
            slider = getattr(self, f"{name}_slider")
            value = round(value, 0) if "time" in name else round(value, 3)
            textbox.setText(str(value))
            slider.setValue(value)
        dictionary = pathGet(self.__dict__, name_lst[0:-1])
        dictionary.__setitem__(name_lst[-1], value)
        setattr(self, name, value)
        self.ValueChangedInside.emit(name)

    def remodel_timing_widgets(
        self, name: str, widget: Union[QComboBox, QScrollableLineEdit]
    ) -> Union[QComboBox, QScrollableLineEdit]:
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        path = name.split(".")
        if options := self.check_driver_variables(path[-1]):
            widget = self.create_attribute_widget(name, "combo", options)

        elif path[-1] in ["trigger_port", "output_port"]:
            widget = self.create_attribute_widget(name, "combo", self.dio_ports)

        return widget

    def remodel_port_widgets(
        self, name: str, widget: Union[QComboBox, QScrollableLineEdit]
    ) -> Union[QComboBox, QScrollableLineEdit]:
        """_summary_

        :return: _description_
        :rtype: _type_
        """
        path = name.split(".")
        task = "ao" if "ao_task" in path else "do"

        if path[-1] == "port":
            options = getattr(self, f"{task}_physical_chans")
            widget = self.create_attribute_widget(name, "combo", options)

        elif path[-1] == "waveform":
            options = self.check_driver_variables(f"{task}_waveforms")
            widget = self.create_attribute_widget(name, "combo", options)
            widget.setDisabled(True)  # can't change waveform for now. Maybe implemented later on if useful

        return widget

    def create_sliders(self, name: str) -> None:
        """_summary_

        :param name: _description_
        :type name: str
        """
        textbox = getattr(self, f"{name}_widget")
        slider = QScrollableFloatSlider(orientation=Qt.Horizontal)
        path = name.split(".")
        if "time" in name:
            task = ".".join(path[: path.index("ports")])
            maximum = getattr(self, f"{task}.timing.period_time_ms")
            slider.setMaximum(maximum)
            textbox.validator().setRange(0.0, maximum, decimals=0)
        elif "volt" in name:
            slider.divisor = 1000
            port = ".".join(path[: path.index("ports") + 2]) if "ports" in path else 0
            # Triangle and sawtooths max amplitude can be less than max volts due to offset so force fixup check
            maximum = getattr(self, f"{port}.device_max_volts", 5)
            minimum = (
                getattr(self, f"{port}.device_min_volts", 0) if "amplitude" not in name else -maximum
            )  # allow for negative amplitude
            slider.setMaximum(maximum)
            slider.setMinimum(minimum)
            textbox.validator().setRange(minimum, maximum, decimals=4)

        slider.setValue(getattr(self, f"{name}"))

        if "amplitude_volts" in name or "offset_volts" in name:
            textbox.editingFinished.connect(lambda: self.check_amplitude(float(textbox.text()), name))
            slider.sliderMoved.connect(lambda value: self.check_amplitude(value, name))
        else:
            textbox.editingFinished.connect(lambda: slider.setValue(float(textbox.text())))
            textbox.validator().fixup = lambda value=None: self.textbox_fixup(value, name)
            textbox.editingFinished.connect(lambda: self.update_waveform(name))

            slider.sliderMoved.connect(lambda value: textbox.setText(str(value)))
            slider.sliderMoved.connect(lambda value: setattr(self, name, float(value)))
            slider.sliderMoved.connect(lambda value: pathGet(self.__dict__, path[0:-1]).__setitem__(path[-1], value))
            slider.sliderMoved.connect(lambda: self.ValueChangedInside.emit(name))
            slider.sliderMoved.connect(lambda: self.update_waveform(name))
        setattr(self, f"{name}_slider", slider)

    def create_tree_widget(self, name: str, parent=None) -> QTreeWidgetItem:
        """_summary_

        :param name: _description_
        :type name: str
        :param parent: _description_, defaults to None
        :type parent: _type_, optional
        :return: _description_
        :rtype: QTreeWidgetItem
        """
        parent = self.tree if parent is None else parent
        # TODO: This is haaaaaacky. but might be good for now
        iterable = self.mappedpathGet(self.exposed_branches.copy(), name.split("."))
        items = []
        for i, item in enumerate(iterable):
            key = item if hasattr(iterable, "keys") else str(i)  # account for yaml typed
            id = f"{name}.{key}"
            if widget := getattr(self, f"{id}_widget", False):
                item = QTreeWidgetItem(parent, [key])
                if "channel" in name:
                    self.update_waveform(id)
                    self.create_sliders(id)
                    widget = create_widget("H", getattr(self, f"{id}_widget"), getattr(self, f"{id}_slider"))
                elif "timing" in name:
                    widget = self.remodel_timing_widgets(id, widget)
                elif key in ["port", "waveform"]:
                    widget = self.remodel_port_widgets(id, widget)
                self.tree.setItemWidget(item, 1, widget)
            else:
                item = QTreeWidgetItem(parent, [key])
                children = self.create_tree_widget(f"{name}.{key}", item)
                item.addChildren(children)
            items.append(item)
            self.check_to_hide(id, item)
        return items

    def mappedpathGet(self, dictionary: dict, path: list[str]) -> dict:
        """_summary_

        :param dictionary: _description_
        :type dictionary: dict
        :param path: _description_
        :type path: list[str]
        :return: _description_
        :rtype: dict
        """
        # TODO: This is haaaaaacky. but might be good for now
        try:
            dictionary = pathGet(dictionary, path)
        except KeyError:
            if ".".join(path[0:2]) in dictionary.keys():
                dictionary = self.mappedpathGet(dictionary[".".join(path[0:2])], path[2:])
            else:
                dictionary = self.mappedpathGet(dictionary, [".".join(path[0:2]), *path[2:]])
        finally:
            return dictionary

    def check_to_hide(self, name: str, item: QTreeWidgetItem, dictionary: dict = None) -> None:
        """_summary_

        :param name: _description_
        :type name: str
        :param item: _description_
        :type item: QTreeWidgetItem
        :param dictionary: _description_, defaults to None
        :type dictionary: dict, optional
        """
        # TODO: This is haaaaaacky. but might be good for now
        dictionary = self.exposed_branches.copy() if dictionary is None else dictionary
        try:
            self.mappedpathGet(dictionary, name.split("."))
        except KeyError:
            item.setHidden(True)

    def check_amplitude(self, value: float, name: str) -> None:
        """_summary_

        :param value: _description_
        :type value: float
        :param name: _description_
        :type name: str
        """
        textbox = getattr(self, f"{name}_widget")
        slider = getattr(self, f"{name}_slider")
        maximum = slider.maximum()

        name_lst = name.split(".")
        parameters = ".".join(name_lst[: name_lst.index("parameters") + 1])
        wl = name_lst[-1]

        # sawtooth or triangle
        offset = value if "offset_volts" in name else getattr(self, f"{parameters}.offset_volts.channels.{wl}")
        amplitude = value if "amplitude_volts" in name else getattr(self, f"{parameters}.amplitude_volts.channels.{wl}")
        other_voltage = amplitude if "offset_volts" in name else offset

        total_amplitude = offset + amplitude
        if total_amplitude > maximum:
            value = value - (total_amplitude - maximum)
        elif ("amplitude_volts" in name and amplitude > offset) or ("offset_volts" in name and offset < amplitude):
            value = other_voltage
        textbox.setText(str(value))
        slider.setValue(float(value))
        self.ValueChangedInside.emit(name)
        setattr(self, name, value)
        pathGet(self.__dict__, name_lst[0:-1]).__setitem__(name_lst[-1], value)
        self.update_waveform(name)

    def textbox_fixup(self, value: float | str, name: str) -> None:
        """_summary_

        :param value: _description_
        :type value: floatorstr
        :param name: _description_
        :type name: str
        """
        textbox = getattr(self, f"{name}_widget")
        slider = getattr(self, f"{name}_slider")
        maximum = slider.maximum()
        textbox.setText(str(maximum))
        textbox.editingFinished.emit()


def sawtooth(
    sampling_frequency_hz: float,
    period_time_ms: float,
    start_time_ms: float,
    end_time_ms: float,
    rest_time_ms: float,
    amplitude_volts: float,
    offset_volts: float,
    cutoff_frequency_hz: float,
) -> np.ndarray:
    """_summary_

    :param sampling_frequency_hz: _description_
    :type sampling_frequency_hz: float
    :param period_time_ms: _description_
    :type period_time_ms: float
    :param start_time_ms: _description_
    :type start_time_ms: float
    :param end_time_ms: _description_
    :type end_time_ms: float
    :param rest_time_ms: _description_
    :type rest_time_ms: float
    :param amplitude_volts: _description_
    :type amplitude_volts: float
    :param offset_volts: _description_
    :type offset_volts: float
    :param cutoff_frequency_hz: _description_
    :type cutoff_frequency_hz: float
    :return: _description_
    :rtype: np.ndarray
    """
    time_samples_ms = np.linspace(0, 2 * np.pi, int(((period_time_ms - start_time_ms) / 1000) * sampling_frequency_hz))
    waveform = offset_volts + amplitude_volts * signal.sawtooth(t=time_samples_ms, width=end_time_ms / period_time_ms)
    # add in delay
    delay_samples = int((start_time_ms / 1000) * sampling_frequency_hz)
    waveform = np.pad(
        array=waveform, pad_width=(delay_samples, 0), mode="constant", constant_values=(offset_volts - amplitude_volts)
    )

    # add in rest
    rest_samples = int((rest_time_ms / 1000) * sampling_frequency_hz)
    waveform = np.pad(
        array=waveform, pad_width=(0, rest_samples), mode="constant", constant_values=(offset_volts - amplitude_volts)
    )
    return waveform


def square_wave(
    sampling_frequency_hz: float,
    period_time_ms: float,
    start_time_ms: float,
    end_time_ms: float,
    rest_time_ms: float,
    max_volts: float,
    min_volts: float,
) -> np.ndarray:
    """_summary_

    :param sampling_frequency_hz: _description_
    :type sampling_frequency_hz: float
    :param period_time_ms: _description_
    :type period_time_ms: float
    :param start_time_ms: _description_
    :type start_time_ms: float
    :param end_time_ms: _description_
    :type end_time_ms: float
    :param rest_time_ms: _description_
    :type rest_time_ms: float
    :param max_volts: _description_
    :type max_volts: float
    :param min_volts: _description_
    :type min_volts: float
    :return: _description_
    :rtype: np.ndarray
    """
    time_samples = int(((period_time_ms + rest_time_ms) / 1000) * sampling_frequency_hz)
    start_sample = int((start_time_ms / 1000) * sampling_frequency_hz)
    end_sample = int((end_time_ms / 1000) * sampling_frequency_hz)

    waveform = np.zeros(time_samples) + min_volts
    waveform[start_sample:end_sample] = max_volts

    return waveform


def triangle_wave(
    sampling_frequency_hz: float,
    period_time_ms: float,
    start_time_ms: float,
    end_time_ms: float,
    rest_time_ms: float,
    amplitude_volts: float,
    offset_volts: float,
    cutoff_frequency_hz: float,
) -> np.ndarray:
    """_summary_

    :return: _description_
    :rtype: _type_
    """
    # sawtooth with end time in center of waveform
    waveform = sawtooth(
        sampling_frequency_hz,
        period_time_ms,
        start_time_ms,
        (period_time_ms - start_time_ms) / 2,
        rest_time_ms,
        amplitude_volts,
        offset_volts,
        cutoff_frequency_hz,
    )

    return waveform
