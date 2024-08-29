from pyqtgraph import PlotWidget, TextItem, mkPen, mkBrush, ScatterPlotItem, setConfigOptions, Point
from qtpy.QtWidgets import QGraphicsEllipseItem, QComboBox
from qtpy.QtCore import Signal, QTimer, Property, QObject, Slot
from math import sin, cos, pi, atan, degrees, radians
from qtpy.QtGui import QFont, QColor
from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties

setConfigOptions(antialias=True)


class FilterWheelWidget(BaseDeviceWidget):

    def __init__(self, filter_wheel,
                 colors: dict = {},
                 advanced_user: bool = True):
        """Simple scroll widget for filter wheel
        :param colors: colors for filters
        :param filter_wheel: filter wheel device"""

        properties = scan_for_properties(filter_wheel)

        # wrap filterwheel filter property to emit signal when set
        filter_setter = getattr(type(filter_wheel).filter, 'fset')
        filter_getter = getattr(type(filter_wheel).filter, 'fget')
        setattr(type(filter_wheel), 'filter', property(filter_getter, self.filter_change_wrapper(filter_setter)))

        super().__init__(type(filter_wheel), properties)

        # Remove filter widget
        self.centralWidget().layout().removeWidget(self.filter_widget)
        self.filter_widget.deleteLater()
        self.filters = filter_wheel.filters

        # recreate as combo box with filters as options
        self.filter_widget = QComboBox()
        self.filter_widget.addItems([f'{v}: {k}' for k, v in self.filters.items()])
        self.filter_widget.currentTextChanged.connect(lambda val: setattr(self, 'filter', val[val.index(' ')+1:]))
        self.filter_widget.currentTextChanged.connect(lambda: self.ValueChangedInside.emit('filter'))
        self.filter_widget.setCurrentText(f'{self.filters[filter_wheel.filter]}: {filter_wheel.filter}')

        # Add back to property widget
        self.property_widgets['filter'].layout().addWidget(self.filter_widget)

        # Create wheel widget and connect to signals
        self.wheel_widget = FilterWheelGraph(self.filters, colors)
        self.wheel_widget.ValueChangedInside[str].connect(lambda v: self.filter_widget.setCurrentText(f'{self.filters[v]}: {v}'))
        self.filter_widget.currentTextChanged.connect(lambda val: self.wheel_widget.move_wheel(val[val.index(' ')+1:]))
        self.ValueChangedOutside[str].connect(lambda name: self.wheel_widget.move_wheel(self.filter))
        self.centralWidget().layout().addWidget(self.wheel_widget)

        if not advanced_user:
            self.wheel_widget.setDisabled(True)
            self.filter_widget.setDisabled(True)

    def filter_change_wrapper(self, func):
        """Wrapper function that emits a signal when filterwheel filter setter has been called"""

        def wrapper(object, value):
            func(object, value)
            self.filter = value
            self.ValueChangedOutside[str].emit('filter')

        return wrapper


class FilterWheelGraph(PlotWidget):
    ValueChangedInside = Signal((str,))

    def __init__(self, filters: dict, colors: dict, diameter=10, **kwargs):
        """Simple scroll widget for filter wheel
        :param filters: list possible filters"""

        super().__init__(**kwargs)

        self._timelines = []
        self.setMouseEnabled(x=False, y=False)
        self.showAxes(False, False)
        self.setBackground('#262930')

        self.filters = filters
        self.diameter = diameter

        # create wheel graphic
        wheel = QGraphicsEllipseItem(-self.diameter, -self.diameter, self.diameter * 2, self.diameter * 2)
        wheel.setPen(mkPen((0, 0, 0, 100)))  # outline of wheel
        wheel.setBrush(mkBrush((128, 128, 128)))  # color of wheel
        self.addItem(wheel)

        self.filter_path = self.diameter - 3
        # calculate diameter of filters based on quantity
        l = len(self.filters)
        max_diameter = (self.diameter - self.filter_path - .5) * 2
        del_filter = self.filter_path * cos((pi / 2) - (2 * pi / l)) - max_diameter  # dist between two filter points
        filter_diameter = max_diameter if del_filter > 0 or l == 2 else self.filter_path * cos((pi / 2) - (2 * pi / l))

        angles = [pi / 2+(2 * pi / l * i) for i in range(l)]
        self.points = {}
        for angle, (filter, i) in zip(angles, self.filters.items()):
            color = QColor(colors.get(filter, 'black')).getRgb()
            pos = [self.filter_path * cos(angle), self.filter_path * sin(angle)]
            # create scatter point filter
            point = FilterItem(filter_name=filter, size=filter_diameter, pxMode=False, pos=[pos])
            point.setPen(mkPen((0, 0, 0, 100), width=2))  # outline of filter
            point.setBrush(mkBrush(color))  # color of filter
            point.pressed.connect(self.move_wheel)
            self.addItem(point)
            self.points[filter] = point

            # create label
            index = TextItem(text=str(i), anchor=(.5, .5), color='white')
            font = QFont()
            font.setPointSize(round(filter_diameter**2))
            index.setFont(font)
            index.setPos(*pos)
            self.addItem(index)
            self.points[i] = index

        # create active wheel graphic. Add after to display over filters
        active = ScatterPlotItem(size=2, pxMode=False, symbol='t1', pos=[[self.diameter * cos(pi / 2),
                                                                          self.diameter * sin(pi / 2)]])
        black = QColor('black').getRgb()
        active.setPen(mkPen(black))  # outline
        active.setBrush(mkBrush(black))  # color
        self.addItem(active)

        self.setAspectLocked(1)

    def move_wheel(self, name):

        self.ValueChangedInside.emit(name)
        point = self.points[name]
        filter_pos = [point.getData()[0][0],point.getData()[1][0]]
        notch_pos = [self.diameter * cos(pi / 2), self.diameter * sin(pi / 2)]
        thetas = []
        for x,y in [filter_pos, notch_pos]:
            if y > 0 > x or (y < 0 and x < 0):
                thetas.append(180+degrees(atan(y/x)))
            elif y < 0 < x:
                thetas.append(360+degrees(atan(y/x)))
            else:
                thetas.append(degrees(atan(y/x)))

        filter_theta, notch_theta = thetas
        delta_theta = notch_theta-filter_theta
        if notch_theta > filter_theta and delta_theta <= 180:
            step_size = 1
        elif notch_theta > filter_theta and delta_theta > 180:
            step_size = -1
            notch_theta = (notch_theta - filter_theta) - 360
        else:
            step_size = -1

        # stop all previous
        for timeline in self._timelines:
            timeline.stop()

        self._timelines = []
        # create timelines for all filters and labels
        filter_names = list(self.filters.keys())
        filter_index = filter_names.index(name)
        filters = [filter_names[(filter_index+i) % len(filter_names)] for i in range(len(filter_names))]  # reorder filters starting with filter selected
        del_theta = 2 * pi / len(filters)
        for i, filt in enumerate(filters):
            shift = degrees((del_theta*i))
            timeline = TimeLine(loopCount=1, interval=10, step_size=step_size)
            timeline.setFrameRange(filter_theta+shift, notch_theta+shift)
            timeline.frameChanged.connect(lambda i, slot=self.points[filt]: self.generate_data(i, slot))
            timeline.frameChanged.connect(lambda i, slot=self.points[self.filters[filt]]: self.generate_data(i, slot))
            self._timelines.append(timeline)

        # start all
        for timeline in self._timelines:
            timeline.start()

    @Slot(float)
    def generate_data(self, i, point):
        pos = [self.filter_path * cos(radians(i)),
               self.filter_path * sin(radians(i))]
        if type(point) == FilterItem:
            point.setData(pos=[pos])
        elif type(point) == TextItem:
            point.setPos(*pos)

class FilterItem(ScatterPlotItem):
    pressed = Signal(str)

    def __init__(self, filter_name: str, *args, **kwargs):
        self.filter_name = filter_name
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        self.pressed.emit(self.filter_name)

class TimeLine(QObject):
    frameChanged = Signal(float)

    def __init__(self, interval=60, loopCount=1, step_size=1, parent=None):
        super(TimeLine, self).__init__(parent)
        self._stepSize = step_size
        self._startFrame = 0
        self._endFrame = 0
        self._loopCount = loopCount
        self._timer = QTimer(self, timeout=self.on_timeout)
        self._counter = 0
        self._loop_counter = 0
        self.setInterval(interval)

    def on_timeout(self):

        if (self._startFrame <= self._counter <= self._endFrame and self._stepSize > 0) or \
                (self._startFrame >= self._counter >= self._endFrame and self._stepSize < 0):
            self.frameChanged.emit(self._counter)
            self._counter += self._stepSize
        else:
            self._counter = 0
            self._loop_counter += 1
        if self._loopCount > 0:
            if self._loop_counter >= self.loopCount():
                self._timer.stop()

    def setLoopCount(self, loopCount):
        self._loopCount = loopCount

    def loopCount(self):
        return self._loopCount

    interval = Property(int, fget=loopCount, fset=setLoopCount)

    def setInterval(self, interval):
        self._timer.setInterval(interval)

    def interval(self):
        return self._timer.interval()

    interval = Property(int, fget=interval, fset=setInterval)

    def setFrameRange(self, startFrame, endFrame):
        self._startFrame = startFrame
        self._endFrame = endFrame

    @Slot()
    def start(self):
        self._counter = self._startFrame
        self._loop_counter = 0
        self._timer.start()

    def stop(self):
        self._timer.stop()
