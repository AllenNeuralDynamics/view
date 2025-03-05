from math import atan, cos, degrees, pi, radians, sin
from typing import Callable, Union

from pyqtgraph import PlotWidget, ScatterPlotItem, TextItem, mkBrush, mkPen, setConfigOptions
from qtpy.QtCore import Property, QObject, QTimer, Signal, Slot
from qtpy.QtGui import QColor, QFont
from qtpy.QtWidgets import QComboBox, QGraphicsEllipseItem

from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties

setConfigOptions(antialias=True)


class FilterWheelWidget(BaseDeviceWidget):
    """Widget for controlling a filter wheel device."""

    def __init__(self, filter_wheel: object, colors: dict = None, advanced_user: bool = True):
        """
        Initialize the FilterWheelWidget.

        :param filter_wheel: The filter wheel device.
        :type filter_wheel: object
        :param colors: Dictionary of colors for the filters, defaults to None.
        :type colors: dict, optional
        :param advanced_user: Flag to enable advanced user features, defaults to True.
        :type advanced_user: bool, optional
        """
        properties = scan_for_properties(filter_wheel)
        # wrap filterwheel filter property to emit signal when set
        filter_setter = getattr(type(filter_wheel).filter, "fset")
        filter_getter = getattr(type(filter_wheel).filter, "fget")
        setattr(type(filter_wheel), "filter", property(filter_getter, self.filter_change_wrapper(filter_setter)))

        super().__init__(type(filter_wheel), properties)

        # Remove filter widget
        self.centralWidget().layout().removeWidget(self.filter_widget)
        self.filter_widget.deleteLater()
        self.filters = filter_wheel.filters

        # recreate as combo box with filters as options
        self.filter_widget = QComboBox()
        self.filter_widget.addItems([f"{v}: {k}" for k, v in self.filters.items()])
        self.filter_widget.currentTextChanged.connect(lambda val: setattr(self, "filter", val[val.index(" ") + 1 :]))
        self.filter_widget.currentTextChanged.connect(lambda: self.ValueChangedInside.emit("filter"))
        self.filter_widget.setCurrentText(f"{self.filters[filter_wheel.filter]}: {filter_wheel.filter}")

        # Add back to property widget
        self.property_widgets["filter"].layout().addWidget(self.filter_widget)

        # Create wheel widget and connect to signals
        self.wheel_widget = FilterWheelGraph(self.filters, colors if colors else {})
        self.wheel_widget.ValueChangedInside[str].connect(
            lambda v: self.filter_widget.setCurrentText(f"{self.filters[v]}: {v}")
        )
        self.filter_widget.currentTextChanged.connect(
            lambda val: self.wheel_widget.move_wheel(val[val.index(" ") + 1 :])
        )
        self.ValueChangedOutside[str].connect(lambda name: self.wheel_widget.move_wheel(self.filter))
        self.centralWidget().layout().addWidget(self.wheel_widget)

        if not advanced_user:
            self.wheel_widget.setDisabled(True)
            self.filter_widget.setDisabled(True)

    def filter_change_wrapper(self, func: Callable) -> Callable:
        """
        Wrap the filter change function to emit a signal when the filter is changed.

        :param func: The original filter change function.
        :type func: Callable
        :return: The wrapped function.
        :rtype: Callable
        """

        def wrapper(object: object, value: str) -> None:
            """
            Wrapper function to emit signal on filter change.

            :param object: The filter wheel object.
            :type object: object
            :param value: The new filter value.
            :type value: str
            """
            func(object, value)
            self.filter = value
            self.ValueChangedOutside[str].emit("filter")

        return wrapper


class FilterItem(ScatterPlotItem):
    """
    ScatterPlotItem that will emit signal when pressed.
    """

    pressed = Signal(str)

    def __init__(self, filter_name: str, *args, **kwargs):
        """
        Initialize the FilterItem.

        :param filter_name: The name of the filter.
        :type filter_name: str
        """
        self.filter_name = filter_name
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, ev) -> None:
        """
        Emit signal containing filter_name when item is pressed.

        :param ev: QMousePressEvent triggered when item is clicked.
        :type ev: QMousePressEvent
        """
        super().mousePressEvent(ev)
        self.pressed.emit(self.filter_name)


class FilterWheelGraph(PlotWidget):
    """Graphical representation of the filter wheel."""

    ValueChangedInside = Signal((str,))

    def __init__(self, filters: dict, colors: dict, diameter: float = 10.0, **kwargs):
        """
        Initialize the FilterWheelGraph.

        :param filters: Dictionary of filters.
        :type filters: dict
        :param colors: Dictionary of colors for the filters.
        :type colors: dict
        :param diameter: Diameter of the filter wheel, defaults to 10.0.
        :type diameter: float, optional
        """
        super().__init__(**kwargs)

        self._timelines = []
        self.setMouseEnabled(x=False, y=False)
        self.showAxes(False, False)
        self.setBackground("#262930")

        self.filters = filters
        self.diameter = diameter

        # create wheel graphic
        wheel = QGraphicsEllipseItem(-self.diameter, -self.diameter, self.diameter * 2, self.diameter * 2)
        wheel.setPen(mkPen((0, 0, 0, 100)))  # outline of wheel
        wheel.setBrush(mkBrush((65, 75, 70)))  # color of wheel
        self.addItem(wheel)

        self.filter_path = self.diameter - 3
        # calculate diameter of filters based on quantity
        l = len(self.filters)
        max_diameter = (self.diameter - self.filter_path - 0.5) * 2
        del_filter = self.filter_path * cos((pi / 2) - (2 * pi / l)) - max_diameter  # dist between two filter points
        filter_diameter = max_diameter if del_filter > 0 or l == 2 else self.filter_path * cos((pi / 2) - (2 * pi / l))

        angles = [pi / 2 + (2 * pi / l * i) for i in range(l)]
        self.points = {}
        for angle, (filter, i) in zip(angles, self.filters.items()):
            color = colors.get(filter, "black")
            if type(color) is str:
                color = QColor(color).getRgb()
            else:
                color = QColor().fromRgb(*color).getRgb()
            color = list(color)
            pos = [self.filter_path * cos(angle), self.filter_path * sin(angle)]
            # create scatter point filter
            point = FilterItem(filter_name=filter, size=filter_diameter, pxMode=False, pos=[pos])
            # update opacity of filter outline color
            color[-1] = 255
            point.setBrush(mkBrush(tuple(color)))  # color of filter
            # update opacity of filter outline color
            color[-1] = 128
            point.setPen(mkPen(tuple(color), width=3))  # outline of filter
            point.setBrush(mkBrush(color))  # color of filter
            point.pressed.connect(self.move_wheel)
            self.addItem(point)
            self.points[filter] = point

            # create label
            index = TextItem(text=str(i), anchor=(0.5, 0.5), color="white")
            font = QFont()
            font.setPointSize(round(filter_diameter**2 - 6))
            index.setFont(font)
            index.setPos(*pos)
            self.addItem(index)
            self.points[i] = index

        # create active wheel graphic. Add after to display over filters
        active = ScatterPlotItem(
            size=2, pxMode=False, symbol="t1", pos=[[self.diameter * cos(pi / 2), self.diameter * sin(pi / 2)]]
        )
        black = QColor("black").getRgb()
        active.setPen(mkPen(black))  # outline
        active.setBrush(mkBrush(black))  # color
        self.addItem(active)

        self.setAspectLocked(1)

    def move_wheel(self, name: str) -> None:
        """
        Move the wheel to the specified filter.

        :param name: The name of the filter to move to.
        :type name: str
        """
        self.ValueChangedInside.emit(name)
        point = self.points[name]
        filter_pos = [point.getData()[0][0], point.getData()[1][0]]
        notch_pos = [self.diameter * cos(pi / 2), self.diameter * sin(pi / 2)]
        thetas = []
        for x, y in [filter_pos, notch_pos]:
            if y > 0 > x or (y < 0 and x < 0):
                thetas.append(180 + degrees(atan(y / x)))
            elif y < 0 < x:
                thetas.append(360 + degrees(atan(y / x)))
            else:
                thetas.append(degrees(atan(y / x)))

        filter_theta, notch_theta = thetas
        delta_theta = notch_theta - filter_theta
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
        filters = [
            filter_names[(filter_index + i) % len(filter_names)] for i in range(len(filter_names))
        ]  # reorder filters starting with filter selected
        del_theta = 2 * pi / len(filters)
        for i, filt in enumerate(filters):
            shift = degrees((del_theta * i))
            timeline = TimeLine(loopCount=1, interval=10, step_size=step_size)
            timeline.setFrameRange(filter_theta + shift, notch_theta + shift)
            timeline.frameChanged.connect(lambda i, slot=self.points[filt]: self.move_point(i, slot))
            timeline.frameChanged.connect(lambda i, slot=self.points[self.filters[filt]]: self.move_point(i, slot))
            self._timelines.append(timeline)

        # start all
        for timeline in self._timelines:
            timeline.start()

    @Slot(float)
    def move_point(self, angle: float, point: Union[FilterItem, TextItem]) -> None:
        """
        Move a point to a new angle.

        :param angle: The angle to move the point to.
        :type angle: float
        :param point: The point to move.
        :type point: Union[FilterItem, TextItem]
        """
        pos = [self.filter_path * cos(radians(angle)), self.filter_path * sin(radians(angle))]
        if type(point) is FilterItem:
            point.setData(pos=[pos])
        elif type(point) is TextItem:
            point.setPos(*pos)


class TimeLine(QObject):
    """
    QObject that steps through values over a period of time and emits values at set interval.
    """

    frameChanged = Signal(float)

    def __init__(self, interval: int = 60, loopCount: int = 1, step_size: float = 1, parent: QObject = None):
        """
        Initialize the TimeLine.

        :param interval: Interval between steps in milliseconds, defaults to 60.
        :type interval: int, optional
        :param loopCount: Number of times to loop, defaults to 1.
        :type loopCount: int, optional
        :param step_size: Size of each step, defaults to 1.
        :type step_size: float, optional
        :param parent: Parent QObject, defaults to None.
        :type parent: QObject, optional
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
        Function called by QTimer that will trigger a step of current step_size and emit new counter value.
        """
        if (self._startFrame <= self._counter <= self._endFrame and self._stepSize > 0) or (
            self._startFrame >= self._counter >= self._endFrame and self._stepSize < 0
        ):
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
        Set the number of times to loop.

        :param loopCount: Number of times to loop.
        :type loopCount: int
        """
        self._loopCount = loopCount

    def loopCount(self) -> int:
        """
        Get the number of times to loop.

        :return: Number of times to loop.
        :rtype: int
        """
        return self._loopCount

    def setInterval(self, interval: int) -> None:
        """
        Set the interval between steps.

        :param interval: Interval between steps in milliseconds.
        :type interval: int
        """
        self._timer.setInterval(interval)

    def interval(self) -> int:
        """
        Get the interval between steps.

        :return: Interval between steps in milliseconds.
        :rtype: int
        """
        return self._timer.interval()

    def setFrameRange(self, startFrame: float, endFrame: float) -> None:
        """
        Set the range of frames to step through.

        :param startFrame: The starting frame.
        :type startFrame: float
        :param endFrame: The ending frame.
        :type endFrame: float
        """
        self._startFrame = startFrame
        self._endFrame = endFrame

    @Slot()
    def start(self) -> None:
        """
        Start the QTimer and begin emitting and stepping through values.
        """
        self._counter = self._startFrame
        self._loop_counter = 0
        self._timer.start()

    def stop(self) -> None:
        """
        Stop the QTimer and stop stepping through values.
        """
        self._timer.stop()
