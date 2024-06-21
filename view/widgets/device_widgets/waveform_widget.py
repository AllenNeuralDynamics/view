import numpy as np
from pyqtgraph import PlotWidget, GraphItem, mkPen
from qtpy.QtCore import Signal
from qtpy.QtWidgets import QWidget, QVBoxLayout
from view.widgets.miscellaneous_widgets.q_clickable_label import QClickableLabel

# TODO: Use this else where to. Consider moving it so we don't have to copy paste?
class SignalChangeVar:

    def __set_name__(self, owner, name):
        self.name = f"_{name}"

    def __set__(self, instance, value):
        setattr(instance, self.name, value)  # initially setting attr
        instance.valueChanged.emit(self.name[1:], value)

    def __get__(self, instance, value):
        return getattr(instance, self.name)


class WaveformWidget(PlotWidget):

    def __init__(self, **kwargs):

        # initialize legend widget
        self.legend = QWidget()
        self.legend.setLayout(QVBoxLayout())
        self.legend_labels = {}

        super().__init__(**kwargs)

        self.setBackground('#262930')

    def plot(self, pos, waveform: str, parameters: list, *args, **kwargs):
        """Plot waveforms on graph"""

        kwargs['pen']=mkPen(color=kwargs.get('color', 'grey'), width=3)
        item = DraggableGraphItem(**{'pos': pos, 'waveform': waveform, 'parameters': parameters, **kwargs})
        item.setData(**{'pos': pos, 'waveform': waveform, 'parameters': parameters, **kwargs})
        self.addItem(item)
        if 'name' in kwargs.keys():
            self.add_legend_item(item)

        return item

    def add_legend_item(self, item):
        """Add item to legend widget"""

        self.legend_labels[item.name] = QClickableLabel(f'<font color="white">{item.name}</font>'
                                                        f'<s><font size="50" color="{item.color}">&nbsp;&nbsp;&nbsp;'
                                                        f'</font></s>')
        self.legend_labels[item.name].clicked.connect(lambda: self.hide_show_line(item))
        self.legend.layout().addWidget(self.legend_labels[item.name])

    def removeDraggableGraphItem(self, item):
        """Remove DraggableGraphItem and remove from legend"""

        self.removeItem(item)
        if item.name is not None:
            label = self.legend_labels[item.name]
            self.legend.layout().removeWidget(label)

    def hide_show_line(self, item):
        """Hide or reveal line if legend is clicked"""
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


class DraggableGraphItem(GraphItem):
    # initialize waveform parameters
    start_time_ms = SignalChangeVar()
    end_time_ms = SignalChangeVar()
    amplitude_volts = SignalChangeVar()
    offset_volts = SignalChangeVar()
    cutoff_frequency_hz = SignalChangeVar()
    max_volts = SignalChangeVar()
    min_volts = SignalChangeVar()
    valueChanged = Signal((str, float))

    def __init__(self, **kwargs):
        self.waveform = None
        self.dragPoint = None
        self.dragOffset = None
        self.parameters = None
        self.name = kwargs.get('name', None)
        self.color = kwargs.get('color', 'black')
        super().__init__(**kwargs)

    def setData(self, **kwds):
        self.data = kwds
        self.pos = self.data['pos']
        self.waveform = self.data['waveform']
        self.parameters = self.data['parameters']
        self.define_waves(self.waveform)

        npts = self.pos.shape[0]
        self.data['adj'] = np.column_stack((np.arange(0, npts - 1), np.arange(1, npts)))
        self.data['data'] = np.empty(npts, dtype=[('index', int)])
        self.data['data']['index'] = np.arange(npts)

        super().setData(**self.data)

    def define_waves(self, waveform: str):
        """Validate and define key indices in waveform"""

        if 'sawtooth' in waveform or 'triangle' in waveform:
            if self.pos.shape[0] != 5:
                raise Exception(f"Waveform {waveform} must have 5 points in data set. "
                                f"Waveform has {self.data['pos'].shape[0]}")

        elif 'square' in waveform:
            if self.pos.shape[0] != 6:
                raise Exception(f"Waveform {waveform} must have 6 points in data set. "
                                f"Waveform has {self.data['pos'].shape[0]}")

        for k, v in self.data['parameters'].items():
            setattr(self, k, v)

    def mouseDragEvent(self, ev):

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

        super().setData(**self.data)
        ev.accept()

    def move_square_wave(self, ind, ev, y_list=[], x_list=[]):
        """Move square wave type waveform"""
        # square wave will have 6 indices
        y_pos = ev.pos()[1] + self.dragOffsetY
        if getattr(self, 'device_min_volts', None) is not None:
            if ind in [1, 4] and getattr(self, 'device_min_volts') <= y_pos <= self.pos[2][1]:
                y_list = [0, 1, 4, 5]
            elif ind in [2, 3] and getattr(self, 'device_max_volts') >= y_pos >= self.pos[1][1]:
                y_list = [2, 3]
            for i in y_list:
                self.pos[i][1] = y_pos
            self.min_volts = self.pos[1][1]
            self.max_volts = self.pos[2][1]

        x_pos = ev.pos()[0] + self.dragOffsetX
        lower_limit_x = self.pos[ind - 1][0] if ind in [1, 3] else self.pos[ind - 2][0]
        upper_limit_x = self.pos[ind + 2][0] if ind in [1, 3] else self.pos[ind + 1][0]
        if lower_limit_x <= x_pos <= upper_limit_x and ind in [1, 2, 3, 4]:
            x_list = [ind + 1, ind] if ind in [1, 3] else [ind - 1, ind]
        for i in x_list:
            self.pos[i][0] = ev.pos()[0] + self.dragOffsetX

        self.start_time_ms = self.pos[1][0] / 10
        self.end_time_ms = self.pos[4][0] / 10

    def move_sawtooth(self, ind, ev, y_list=[], x_list=[]):
        """Move sawtooth type waveform"""
        # sawtooth will have 5 indices
        y_pos = ev.pos()[1] + self.dragOffsetY

        if ind in [1, 3] and getattr(self, 'device_min_volts') <= y_pos <= self.pos[2][1] and \
                y_pos + (self.pos[2][1] - self.pos[3][1]) <= getattr(self, 'device_max_volts'):
            y_list = [0, 1, 3, 4]
            self.offset_volts = (self.pos[2][1] + y_pos) / 2
            self.pos[2][1] = y_pos + (self.pos[2][1] - self.pos[3][1])

        # elif ind == 2 and getattr(self, 'device_max_volts') >= y_pos >= self.pos[3][1] >= getattr(self,
        #                                                                                           'device_min_volts'):
        elif ind == 2 and getattr(self, 'device_max_volts') >= y_pos >=  getattr(self, 'device_min_volts'):
            y_list = [2]
            self.amplitude_volts = y_pos - self.offset_volts
            self.pos[3][1] = self.offset_volts - self.amplitude_volts
            self.pos[1][1] = self.offset_volts - self.amplitude_volts
            self.pos[0][1] = self.offset_volts - self.amplitude_volts
            self.pos[4][1] = self.offset_volts - self.amplitude_volts
        for i in y_list:
            self.pos[i][1] = ev.pos()[1] + self.dragOffsetY

        x_pos = ev.pos()[0] + self.dragOffsetX
        if ind in [1] and self.pos[ind - 1][0] <= x_pos <= self.pos[ind + 1][0]:
            x_list = [ind]
            self.start_time_ms = x_pos / 10
            self.pos[2][0] = x_pos + (self.end_time_ms / self.period_time_ms) * (self.pos[3][0] - x_pos)

        elif ind == 2 and self.pos[1][0] <= x_pos <= self.pos[3][0]:
            x_list = [2]
            self.end_time_ms = ((x_pos - self.pos[1][0]) / (self.pos[3][0] - self.pos[1][0])) * \
                               self.period_time_ms

        for i in x_list:
            self.pos[i][0] = x_pos

    def move_triangle_wave(self, ind, ev, y_list=[], x_list=[]):
        """Move triangle type waveform"""
        # triangle will have 5 indices
        y_pos = ev.pos()[1] + self.dragOffsetY

        # if ind in [1, 3] and getattr(self, 'device_min_volts') <= y_pos <= self.pos[2][1] and \
        #         y_pos + (self.pos[2][1] - self.pos[3][1]) <= getattr(self, 'device_max_volts'):
        if ind in [1, 3] and getattr(self, 'device_min_volts') <= y_pos <= getattr(self, 'device_max_volts'):
            y_list = [0, 1, 3, 4]
            self.offset_volts = (self.pos[2][1] + y_pos) / 2
            self.pos[2][1] = y_pos + (self.pos[2][1] - self.pos[3][1])

        elif ind == 2 and getattr(self, 'device_max_volts') >= y_pos >= self.pos[3][1] >= getattr(self,
                                                                                                  'device_min_volts'):
            y_list = [2]
            self.amplitude_volts = y_pos - self.offset_volts
            self.pos[3][1] = self.offset_volts - self.amplitude_volts
            self.pos[1][1] = self.offset_volts - self.amplitude_volts
            self.pos[0][1] = self.offset_volts - self.amplitude_volts
            self.pos[4][1] = self.offset_volts - self.amplitude_volts
        for i in y_list:
            self.pos[i][1] = ev.pos()[1] + self.dragOffsetY

        x_pos = ev.pos()[0] + self.dragOffsetX
        if ind in [1] and self.pos[ind - 1][0] <= x_pos <= self.pos[ind + 1][0]:
            x_list = [ind]
            self.start_time_ms = x_pos / 10
            self.pos[2][0] = x_pos + (.5 * (self.pos[3][0] - x_pos))

        for i in x_list:
            self.pos[i][0] = x_pos
