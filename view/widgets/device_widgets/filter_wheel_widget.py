from pyqtgraph import PlotWidget, TextItem, mkPen, mkBrush, ScatterPlotItem, setConfigOptions
from qtpy.QtWidgets import QGraphicsEllipseItem
from qtpy.QtCore import Signal, QTimer, Property, QObject, Slot
from math import sin, cos, pi, atan, degrees, radians
from qtpy.QtGui import QFont
from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties

setConfigOptions(antialias=True)

class FilterWheelWidget(BaseDeviceWidget):
    def __init__(self, filter_wheel,
                 advanced_user: bool = True):
        """Simple scroll widget for filter wheel
        :param filter_wheel: filter wheel device"""

        properties = scan_for_properties(filter_wheel)
        super().__init__(type(filter_wheel), properties)

        # Remove filter widget
        self.centralWidget().layout().removeWidget(self.filter_widget)
        self.filter_widget.deleteLater()
        # recreate as combo box with filters as options
        self.filter_widget = self.create_combo_box('filter', filter_wheel.filters)
        self.filter_widget.setCurrentText(str(filter_wheel.filter))
        # Add back to property widget
        self.property_widgets['filter'].layout().addWidget(self.filter_widget)

        # Create wheel widget and connect to signals
        wheel_widget = FilterWheelGraph(list(filter_wheel.filters.keys()))
        wheel_widget.ValueChangedInside[str].connect(lambda value: self.filter_widget.setCurrentText(str(value)))
        self.filter_widget.currentTextChanged.connect(lambda value: wheel_widget.set_index(value))
        self.ValueChangedOutside[str].connect(lambda name: wheel_widget.set_index(getattr(self, name)))
        self.centralWidget().layout().addWidget(wheel_widget)

        if not advanced_user:
            wheel_widget.setDisabled(True)
            self.filter_widget.setDisabled(True)

class FilterWheelGraph(PlotWidget):
    ValueChangedInside = Signal((str,))

    def __init__(self, filters, radius=10, **kwargs):
        """Simple scroll widget for filter wheel
        :param filters: list possible filters"""

        super().__init__(**kwargs)

        self._timeline = TimeLine(loopCount=1, interval=50)
        self.setMouseEnabled(x=False, y=False)
        self.showAxes(False, False)
        self.setBackground('#262930')

        self.filters = filters
        self.radius = radius

        wheel = QGraphicsEllipseItem(-self.radius, -self.radius, self.radius * 2, self.radius * 2)
        wheel.setPen(mkPen((0, 0, 0, 100)))
        wheel.setBrush(mkBrush((128, 128, 128)))
        self.addItem(wheel)

        angles = [2 * pi / len(self.filters) * i for i in range(len(self.filters))]
        points = {}
        for angle, slot in zip(angles, self.filters):
            point = FilterItem(text=str(slot), anchor=(.5, .5), color='white')
            font = QFont()
            font.setPixelSize(9)
            point.setFont(font)
            point.setPos((self.radius + 1) * cos(angle),
                         (self.radius + 1) * sin(angle))
            point.pressed.connect(self.move_wheel)
            self.addItem(point)
            points[slot] = point

        self.notch = ScatterPlotItem(pos=[[(self.radius - 3) * cos(0),
                                           (self.radius - 3) * sin(0)]], size=5, pxMode=False)
        self.addItem(self.notch)

        self.setAspectLocked(1)
    def set_index(self, slot_name):
        filter_index = self.filters.index(slot_name)
        angle = [2 * pi / len(self.filters) * i for i in range(len(self.filters))][filter_index]
        self.move_wheel(slot_name, ((self.radius + 1) * cos(angle),(self.radius + 1) * sin(angle)))

    def move_wheel(self, name, slot_pos):

        self.ValueChangedInside.emit(name)
        notch_pos = [self.notch.getData()[0][0],self.notch.getData()[1][0]]
        thetas = []
        for x,y in [notch_pos, slot_pos]:
            if y > 0 > x or (y < 0 and x < 0):
                thetas.append(180+degrees(atan(y/x)))
            elif y < 0 < x:
                thetas.append(360+degrees(atan(y/x)))
            else:
                thetas.append(degrees(atan(y/x)))

        notch_theta, slot_theta = thetas
        delta_theta = slot_theta-notch_theta
        if slot_theta > notch_theta and delta_theta <= 180:
            step_size = 1
        elif slot_theta > notch_theta and delta_theta > 180:
            step_size = -1
            slot_theta = (slot_theta - notch_theta) - 360
        else:
            step_size = -1
        self._timeline.stop()
        self._timeline = TimeLine(loopCount=1, interval=10, step_size=step_size)
        self._timeline.setFrameRange(notch_theta, slot_theta)
        self._timeline.frameChanged.connect(self.generate_data)
        self._timeline.start()

    @Slot(float)
    def generate_data(self, i):
        self.notch.setData(pos=[[(self.radius - 3) * cos(radians(i)),
                                 (self.radius - 3) * sin(radians(i))]])

class FilterItem(TextItem):
    pressed = Signal((str, list))

    def mousePressEvent(self, ev):
        super().mousePressEvent(ev)
        self.pressed.emit(self.textItem.toPlainText(), self.pos())


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
