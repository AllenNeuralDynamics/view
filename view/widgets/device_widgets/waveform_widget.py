import numpy as np
from pyqtgraph import PlotWidget, GraphItem, mkPen
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget, QVBoxLayout
from view.widgets.miscellaneous_widgets.q_clickable_label import QClickableLabel
from typing import Literal, TypedDict


# TODO: Use this else where to. Consider moving it so we don't have to copy paste?
class SignalChangeVar:
    """Class that emits signal containing name when set function is used"""

    def __set_name__(self, owner, name) -> None:
        """
        Set name of class. Called in the init of class
        :param owner: instance of class
        :param name: set name of class. Will be variable name
        """
        self.name = f"_{name}"

    def __set__(self, instance, value) -> None:
        """
        Setting function of class
        :param instance: instance of class
        :param value: value to set to
        """

        setattr(instance, self.name, value)  # initially setting attr
        instance.valueChanged.emit(self.name[1:], value)

    def __get__(self, instance, value):
        """
        Getting function of class
        :param instance: instance of class
        :param value: object calling function
        :return: value of class
        """
        return getattr(instance, self.name)


class PointyWaveParameters(TypedDict):
    start_time_ms: float
    end_time_ms: float
    amplitude_volts: float
    offset_volts: float
    cutoff_frequency_hz: float
    device_min_volts: float
    device_max_volts: float


class SquareWaveParameters(TypedDict):
    start_time_ms: float
    end_time_ms: float
    max_volts: float
    min_volts: float
    device_min_volts: float
    device_max_volts: float


class DraggableGraphItem(GraphItem):
    """Graph item representing triangle, sawtooth, and square wave that can be dragged by user to modify wave"""
    # initialize waveform parameters
    start_time_ms = SignalChangeVar()
    end_time_ms = SignalChangeVar()
    amplitude_volts = SignalChangeVar()
    offset_volts = SignalChangeVar()
    cutoff_frequency_hz = SignalChangeVar()
    max_volts = SignalChangeVar()
    min_volts = SignalChangeVar()
    valueChanged = Signal((str, float))

    def __init__(self, pos: np.ndarray,
             waveform: Literal['square wave', 'sawtooth', 'triangle wave'],
             parameters: PointyWaveParameters or SquareWaveParameters, **kwargs):
        """
        :param pos: 2d numpy array of concatenated lists of [[x],[y]] values
        :param waveform: type of waveform positions represent
        :param parameters: dictionary of parameters like amplitude_volts, end_time_ms, ect. and the corresponding values
        :param kwargs: kwargs relating to PlotWidget plot function
        """

        self.pos = pos
        self.waveform = waveform
        self.dragPoint = None
        self.dragOffset = None
        self.parameters = parameters
        self.name = kwargs.get('name', None)
        self.color = kwargs.get('color', 'black')
        super().__init__(pos=pos, **kwargs)

    def setData(self, **kwargs) -> None:
        """
        Set data for waveform graph item
        :param kwargs: data to set
        """

        self.pos = kwargs.get('pos', self.pos)
        self.waveform = kwargs.get('waveform', self.waveform)
        self.parameters = kwargs.get('parameters', self.parameters)
        self.define_waves(self.waveform)

        npts = self.pos.shape[0]
        kwargs['adj'] = np.column_stack((np.arange(0, npts - 1), np.arange(1, npts)))
        kwargs['data'] = np.empty(npts, dtype=[('index', int)])
        kwargs['data']['index'] = np.arange(npts)
        super().setData(**kwargs)

    def define_waves(self, waveform: Literal['square wave', 'sawtooth', 'triangle wave']) -> None:
        """
        Validate and define key indices in waveform
        :param waveform: specification of what waveform graph item represents
        """

        if 'sawtooth' in waveform or 'triangle' in waveform:
            if self.pos.shape[0] != 5:
                raise Exception(f"Waveform {waveform} must have 5 points in data set. "
                                f"Waveform has {self.pos.shape[0]}")

        elif 'square' in waveform:
            if self.pos.shape[0] != 6:
                raise Exception(f"Waveform {waveform} must have 6 points in data set. "
                                f"Waveform has {self.pos.shape[0]}")

        for k, v in self.parameters.items():
            setattr(self, k, v)

    def mouseDragEvent(self, ev) -> None:
        """
        Register if user clicks and drags point of waveform
        :param ev: mouse drag event
        """

        if ev.isStart():
            pos = ev.buttonDownPos()
            pts = self.scatter.pointsAt(pos)
            if len(pts) == 0:
                ev.ignore()
                return
            self.dragPoint = pts[0]
            ind = pts[0].data()[0]
            self.dragOffsetY = self.pos[ind][1] - pos[1]
            self.dragOffsetX = self.pos[ind][0] - pos[0]

        elif ev.isFinish():
            self.dragPoint = None
            return
        else:
            if self.dragPoint is None:
                ev.ignore()
                return
        ind = self.dragPoint.data()[0]
        if self.waveform == 'square wave':
            self.move_square_wave(ind, ev)
        elif self.waveform == 'sawtooth':
            self.move_sawtooth(ind, ev)
        elif self.waveform == 'triangle wave':
            self.move_triangle_wave(ind, ev)

        self.setData(pos=self.pos)
        ev.accept()

    def move_square_wave(self, ind: int, ev) -> None:
        """
        Move square wave type waveform. Square wave will have 6 indices
        :param ind: index being dragged
        :param ev: mouse event
        """

        min_v = self.device_min_volts
        max_v = self.device_max_volts

        y_pos = ev.pos()[1] + self.dragOffsetY  # new y pos is old plus drag offset
        if ind in [1, 4] and min_v <= y_pos <= max_v:       # either side of square is moved
            for i in [0, 1, 4, 5]:
                self.pos[i][1] = y_pos
        elif ind in [2, 3] and min_v <= y_pos <= max_v:    # square is moved
            for i in [2, 3]:
                self.pos[i][1] = y_pos
        self.min_volts = self.pos[1][1]
        self.max_volts = self.pos[2][1]

        x_pos = ev.pos()[0] + self.dragOffsetX # new x pos is old plus drag offset
        lower_limit_x = self.pos[ind - 1][0] if ind in [1, 3] else self.pos[ind - 2][0]
        upper_limit_x = self.pos[ind + 2][0] if ind in [1, 3] else self.pos[ind + 1][0]
        if lower_limit_x <= x_pos <= upper_limit_x and ind in [1, 2, 3, 4]:
            x_list = [ind + 1, ind] if ind in [1, 3] else [ind - 1, ind]
            for i in x_list:
                self.pos[i][0] = ev.pos()[0] + self.dragOffsetX

        self.start_time_ms = self.pos[1][0] / 10
        self.end_time_ms = self.pos[4][0] / 10

    def move_sawtooth(self, ind: int, ev) -> None:
        """
        Move sawtooth type waveform. Sawtooth will have 5 indices
        :param ind: index being dragged
        :param ev: mouse event
        """

        min_v = self.device_min_volts
        max_v = self.device_max_volts

        y_pos = ev.pos()[1] + self.dragOffsetY  # new y pos is old plus drag offset
        if ind in [1, 3] and min_v <= y_pos <= max_v:   # either side of peak is moved
            for i in [0, 1, 3, 4]:  # update points to include drag value
                self.pos[i][1] = ev.pos()[1] + self.dragOffsetY
            self.offset_volts = (self.pos[2][1] + y_pos) / 2    # update offset volts
            self.pos[2][1] = y_pos + (self.pos[2][1] - self.pos[3][1])  # update peak to account for new offset volts

        elif ind == 2 and min_v <= y_pos <= max_v and min_v <= 2 * self.offset_volts - y_pos <= max_v:   # peak is moved
            self.pos[2][1] = ev.pos()[1] + self.dragOffsetY     # update peak with drag value
            self.amplitude_volts = y_pos - self.offset_volts    # update amplitude
            for i in [0, 1, 3, 4]:      # update points to account for new amplitude
                self.pos[i][1] = self.offset_volts - self.amplitude_volts

        x_pos = ev.pos()[0] + self.dragOffsetX      # new x pos is old plus drag offset
        if ind in [1] and self.pos[ind - 1][0] <= x_pos <= self.pos[ind + 1][0]:    # start time dragged
            self.pos[ind][0] = x_pos
            self.start_time_ms = x_pos / 10
            self.pos[2][0] = x_pos + (self.end_time_ms / self.period_time_ms) * (self.pos[3][0] - x_pos)

        elif ind == 2 and self.pos[1][0] <= x_pos <= self.pos[3][0]:      # peak is dragged
            self.pos[ind][0] = x_pos
            self.end_time_ms = ((x_pos - self.pos[1][0]) / (self.pos[3][0] - self.pos[1][0])) * \
                               self.period_time_ms

    def move_triangle_wave(self, ind: int, ev) -> None:
        """
        Move triangle type waveform. Triangle will have 5 indices
        :param ind: index being dragged
        :param ev: mouse event
        """

        min_v = self.device_min_volts
        max_v = self.device_max_volts

        y_pos = ev.pos()[1] + self.dragOffsetY  # new y pos is old plus drag offset
        if ind in [1, 3] and min_v <= y_pos <= max_v:   # either side of peak is moved
            for i in [0, 1, 3, 4]:  # update points to include drag value
                self.pos[i][1] = ev.pos()[1] + self.dragOffsetY
            self.offset_volts = (self.pos[2][1] + y_pos) / 2    # update offset volts
            self.pos[2][1] = y_pos + (self.pos[2][1] - self.pos[3][1])  # update peak to account for new offset volts

        elif ind == 2 and min_v <= y_pos <= max_v and min_v <= 2 * self.offset_volts - y_pos <= max_v:   # peak is moved
            self.pos[2][1] = ev.pos()[1] + self.dragOffsetY     # update peak with drag value
            self.amplitude_volts = y_pos - self.offset_volts    # update amplitude
            for i in [0, 1, 3, 4]:      # update points to account for new amplitude
                self.pos[i][1] = self.offset_volts - self.amplitude_volts

        x_pos = ev.pos()[0] + self.dragOffsetX      # new x pos is old plus drag offset
        if ind == 1 and self.pos[0][0] <= x_pos <= self.pos[2][0]:    # point before peak
            self.pos[1][0] = x_pos
            self.start_time_ms = x_pos / 10     # update start time
            self.pos[2][0] = x_pos + (.5 * (self.pos[3][0] - x_pos))    # shift peak

class WaveformWidget(PlotWidget):

    def __init__(self, **kwargs):
        """
        Plot widget to show daq waveforms
        """
        # initialize legend widget
        self.legend = QWidget()
        self.legend.setLayout(QVBoxLayout())
        self.legend_labels = {}

        super().__init__(**kwargs)

        self.setBackground('#262930')

    def plot(self, pos: np.ndarray,
             waveform: Literal['square wave', 'sawtooth', 'triangle wave'],
             parameters: PointyWaveParameters or SquareWaveParameters, **kwargs) -> DraggableGraphItem:
        """
        Plot waveforms on graph
        :param pos: 2d numpy array of concatenated lists of [[x],[y]] values
        :param waveform: type of waveform positions represent
        :param parameters: dictionary of parameters like amplitude_volts, end_time_ms, ect. and the corresponding values
        :param kwargs: kwargs relating to PlotWidget plot function
        :return: item plotted in graph
        """
        kwargs['pen'] = mkPen(color=kwargs.get('color', 'grey'), width=3)
        item = DraggableGraphItem(pos=pos, waveform=waveform, parameters=parameters, **kwargs)
        item.setData(pos=pos, waveform=waveform, parameters=parameters, **kwargs)
        self.addItem(item)
        if 'name' in kwargs.keys():
            self.add_legend_item(item)
        item.valueChanged.connect(lambda value: self.update())
        return item

    def add_legend_item(self, item: DraggableGraphItem) -> None:
        """
        Add item to legend widget
        :param item: item to add to legend
        """

        self.legend_labels[item.name] = QClickableLabel(f'<font color="white">{item.name}</font>'
                                                        f'<s><font size="50" color="{item.color}">&nbsp;&nbsp;&nbsp;'
                                                        f'</font></s>')
        self.legend_labels[item.name].clicked.connect(lambda: self.hide_show_line(item))
        self.legend.layout().addWidget(self.legend_labels[item.name])

    def removeDraggableGraphItem(self, item: DraggableGraphItem) -> None:
        """
        Remove DraggableGraphItem and remove from legend
        :param item: item to remove"""

        self.removeItem(item)
        if item.name is not None:
            label = self.legend_labels[item.name]
            self.legend.layout().removeWidget(label)

    def hide_show_line(self, item) -> None:
        """
        Hide or reveal line if legend is clicked
        :param item: item to hide
        """
        if item.isVisible():
            item.setVisible(False)
            self.legend_labels[item.name].setText(f'<font color="grey">{item.name}</font>'
                                                  f'<s><font size="50" color="{item.color}">&nbsp;&nbsp;&nbsp;'
                                                  f'</font></s>')
        else:
            item.setVisible(True)
            self.legend_labels[item.name].setText(f'<font color="white">{item.name}</font>'
                                                  f'<s><font size="50" color="{item.color}">&nbsp;&nbsp;&nbsp;'
                                                  f'</font></s>')

    def wheelEvent(self, ev):
        """Overwriting to disable zoom"""
        pass
