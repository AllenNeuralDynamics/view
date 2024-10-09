from pyqtgraph import PlotWidget, TextItem, mkPen, mkBrush, ScatterPlotItem, setConfigOptions
from qtpy.QtWidgets import QGraphicsEllipseItem, QComboBox
from qtpy.QtCore import Signal, QTimer, Property, QObject, Slot
from math import sin, cos, pi, atan, degrees, radians
from qtpy.QtGui import QFont, QColor
from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties
from typing import Callable, Union

setConfigOptions(antialias=True)


class FilterWheelWidget(BaseDeviceWidget):

    def __init__(self, filter_wheel,
                 colors: dict = None,
                 advanced_user: bool = True):
        """
        Simple scroll widget for filter wheel
        :param filter_wheel: filter wheel object
        :param colors: colors for filters. Defaults to empty dictionary if not specified
        :param advanced_user: boolean specifying complexity of widget. If False, user won't be able to manually change
        filter wheel but graphics will still work.
        """

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
        self.wheel_widget = FilterWheelGraph(self.filters, colors if colors else {})
        self.wheel_widget.ValueChangedInside[str].connect(lambda v: self.filter_widget.setCurrentText(f'{self.filters[v]}: {v}'))
        self.filter_widget.currentTextChanged.connect(lambda val: self.wheel_widget.move_wheel(val[val.index(' ')+1:]))
        self.ValueChangedOutside[str].connect(lambda name: self.wheel_widget.move_wheel(self.filter))
        self.centralWidget().layout().addWidget(self.wheel_widget)

        if not advanced_user:
            self.wheel_widget.setDisabled(True)
            self.filter_widget.setDisabled(True)

    def filter_change_wrapper(self, func: Callable) -> Callable:
        """
        Wrapper function that emits a signal when filterwheel filter setter has been called
        :param func: setter of filter wheel object
        """

        def wrapper(object, value):
            func(object, value)
            self.filter = value
            self.ValueChangedOutside[str].emit('filter')

        return wrapper

class FilterItem(ScatterPlotItem):
    """ScatterPlotItem that will emit signal when pressed"""
    pressed = Signal(str)

    def __init__(self, filter_name: str, *args, **kwargs):
        """
        :param filter_name: name of filter that will be emitted when pressed
        """
        self.filter_name = filter_name
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, ev) -> None:
        """
        Emit signal containing filter_name when item is pressed
        :param ev: QMousePressEvent triggered when item is clicked
        """
        super().mousePressEvent(ev)
        self.pressed.emit(self.filter_name)

class FilterWheelGraph(PlotWidget):
    ValueChangedInside = Signal((str,))

    def __init__(self, filters: dict, colors: dict, diameter: float = 10.0 , **kwargs):
        """
        Plot widget that creates a visual of filter wheel using points on graph
        :param filters: list possible filters
        :param colors: desired colors of filters where key is filter name and value is string of color. If empty dict,
        default is grey.
        :param diameter: desired diameter of wheel graphic
        """

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

    def move_wheel(self, name: str) -> None:
        """
        Create visual of wheel moving to new filer by changing position of filter points
        :param name: name of active filter
        """
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
            timeline.frameChanged.connect(lambda i, slot=self.points[filt]: self.move_point(i, slot))
            timeline.frameChanged.connect(lambda i, slot=self.points[self.filters[filt]]: self.move_point(i, slot))
            self._timelines.append(timeline)

        # start all
        for timeline in self._timelines:
            timeline.start()

    @Slot(float)
    def move_point(self, angle: float, point: Union[FilterItem, TextItem]) -> None:
        """
        Calculate new position of point based on the angle given
        :param angle: angle in degrees
        :param point: point needing to be moved
        """
        pos = [self.filter_path * cos(radians(angle)),
               self.filter_path * sin(radians(angle))]
        if type(point) == FilterItem:
            point.setData(pos=[pos])
        elif type(point) == TextItem:
            point.setPos(*pos)

class TimeLine(QObject):
    """QObject that steps through values over a period of time and emits values at set interval"""

    frameChanged = Signal(float)

    def __init__(self, interval: int = 60, loopCount: int = 1, step_size: float =1, parent=None):
        """
        :param interval: interval at which to step up and emit value in milliseconds
        :param loopCount: how many times to repeat timeline
        :param step_size: step size to take between emitted values
        :param parent: parent of widget
        """
        super(TimeLine, self).__init__(parent)
        self._stepSize = step_size
        self._startFrame = 0
        self._endFrame = 0
        self._loopCount = loopCount
        self._timer = QTimer(self, timeout=self.on_timeout)
        self._counter = 0
        self._loop_counter = 0
        self.setInterval(interval)

    def on_timeout(self) -> None:
        """
        Function called by Qtimer that will trigger a step of current step_size and emit new counter value
        """
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

    def setLoopCount(self, loopCount: int) -> None:
        """
        Function set loop count variable
        :param loopCount: integer specifying how many times to repeat timeline
        """
        self._loopCount = loopCount

    def loopCount(self) -> int:
        """
        Current loop count
        :return: Current loop count
        """
        return self._loopCount

    interval = Property(int, fget=loopCount, fset=setLoopCount)

    def setInterval(self, interval: int) -> None:
        """
        Function to set interval variable in seconds
        :param interval: integer specifying the length of timeline in milliseconds
        """
        self._timer.setInterval(interval)

    def interval(self) -> int:
        """
        Current interval time in milliseconds
        :return: integer value of current interval time in milliseconds
        """
        return self._timer.interval()

    interval = Property(int, fget=interval, fset=setInterval)

    def setFrameRange(self, startFrame: float, endFrame: float) -> None:
        """
        Setting function for starting and end value that timeline will step through
        :param startFrame: starting value
        :param endFrame: ending value
        """
        self._startFrame = startFrame
        self._endFrame = endFrame

    @Slot()
    def start(self) -> None:
        """
        Function to start QTimer and begin emitting and stepping through value
        """
        self._counter = self._startFrame
        self._loop_counter = 0
        self._timer.start()

    def stop(self) -> None:
        """Function to stop QTimer and stop stepping through values"""
        self._timer.stop()
