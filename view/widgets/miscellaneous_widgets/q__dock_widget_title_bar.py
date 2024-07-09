from qtpy.QtWidgets import QFrame, QPushButton, QStyle, QDockWidget, QLabel, QHBoxLayout
from qtpy.QtCore import Qt
from qtpy.QtCore import Signal, QTimer, Property, QObject, Slot


class QDockWidgetTitleBar(QFrame):
    """Widget to act as a QDockWidget title bar. Will allow user to collapse, expand, pop out, and close widget"""

    resized = Signal()

    def __init__(self, dock:QDockWidget):

        super().__init__()

        self._timeline = None
        self.current_height = 25

        self.setAutoFillBackground(True)
        self.initial_pos = None

        self.dock = dock
        self.dock.setMinimumHeight(0)

        self.setStyleSheet("QFrame {background-color: rgb(215, 214, 213);} QPushButton {border: 0px;}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(30)

        label = QLabel(dock.windowTitle())
        layout.addWidget(label)

        button_width = 20

        min_button = QPushButton()
        min_button.setMaximumWidth(button_width)
        icon = QDockWidget().style().standardIcon(QStyle.SP_TitleBarMinButton)
        min_button.setIcon(icon)
        min_button.clicked.connect(self.minimize)
        layout.addWidget(min_button)

        max_button = QPushButton()
        max_button.setMaximumWidth(button_width)
        icon = QDockWidget().style().standardIcon(QStyle.SP_TitleBarMaxButton)
        max_button.setIcon(icon)
        max_button.clicked.connect(self.maximize)
        layout.addWidget(max_button)

        pop_button = QPushButton()
        pop_button.setMaximumWidth(button_width)
        icon = QDockWidget().style().standardIcon(QStyle.SP_TitleBarNormalButton)
        pop_button.setIcon(icon)
        pop_button.clicked.connect(self.pop_out)
        layout.addWidget(pop_button)

        close_button = QPushButton()
        close_button.setMaximumWidth(button_width)
        icon = QDockWidget().style().standardIcon(QStyle.SP_TitleBarCloseButton)
        close_button.setIcon(icon)
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        self.setLayout(layout)

    def close(self):
        """Close widget"""

        self.dock.close()

    def pop_out(self):
        """Pop out widget"""

        self.dock.setFloating(not self.dock.isFloating())

    def minimize(self):
        """Minimize widget"""

        self.dock.setMinimumHeight(25)
        self.current_height = self.dock.widget().height()   # save to expand to later
        self._timeline = TimeLine(loopCount=1, interval=1, step_size=-5)
        self._timeline.setFrameRange(self.current_height, 0)
        self._timeline.frameChanged.connect(self.set_widget_size)
        self._timeline.start()

    def maximize(self):
        """Minimize widget"""

        if self.dock.height() == 25: # already maximized
            self._timeline = TimeLine(loopCount=1, interval=1, step_size=5)
            self._timeline.timerEnded.connect(lambda: self.dock.setMaximumHeight(2500))
            self._timeline.setFrameRange(self.dock.widget().height(), self.current_height)
            self._timeline.frameChanged.connect(self.set_widget_size)
            self._timeline.start()

    def set_widget_size(self, i):
        """Change size of widget based on qtimer"""


        self.dock.widget().resize(self.dock.widget().width(), int(i))
        self.dock.resize(self.dock.width(), int(i))
        if i > self.dock.minimumHeight():
            self.dock.setFixedHeight(int(i))  # prevent container widget from resizing back
        self.dock.setMinimumHeight(25)
        self.resized.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.initial_pos = event.position().toPoint()
        super().mousePressEvent(event)
        event.accept()

    def mouseMoveEvent(self, event):
        if self.initial_pos is not None:
            delta = event.position().toPoint() - self.initial_pos
            self.window().move(
                self.window().x() + delta.x(),
                self.window().y() + delta.y(),
            )
        super().mouseMoveEvent(event)
        event.accept()

class TimeLine(QObject):
    frameChanged = Signal(float)
    timerEnded = Signal()

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
                self.timerEnded.emit()

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
        self.timerEnded.emit()