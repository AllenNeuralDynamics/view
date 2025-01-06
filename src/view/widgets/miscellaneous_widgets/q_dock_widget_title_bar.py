from qtpy.QtCore import Property, QObject, Qt, QTimer, Signal, Slot
from qtpy.QtGui import QMouseEvent
from qtpy.QtWidgets import QDockWidget, QFrame, QHBoxLayout, QLabel, QPushButton, QStyle


class QDockWidgetTitleBar(QFrame):
    """
    Widget to act as a QDockWidget title bar. Will allow user to collapse, expand, pop out, and close widget.
    """

    resized = Signal()

    def __init__(self, dock: QDockWidget, *args, **kwargs):
        """_summary_

        :param dock: _description_
        :type dock: QDockWidget
        """
        super().__init__(*args, **kwargs)

        self._timeline = None
        self.current_height = None

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

    def close(self) -> None:
        """
        Close widget.
        """
        self.dock.close()

    def pop_out(self) -> None:
        """
        Pop out widget.
        """
        self.dock.setFloating(not self.dock.isFloating())

    def minimize(self) -> None:
        """
        Minimize widget.
        """
        self.dock.setMinimumHeight(25)
        self.current_height = self.dock.widget().height()
        self._timeline = TimeLine(loopCount=1, interval=1, step_size=-5)
        self._timeline.setFrameRange(self.current_height, 0)
        self._timeline.frameChanged.connect(self.set_widget_size)
        self._timeline.start()

    def maximize(self) -> None:
        """
        Minimize widget.
        """
        if self.current_height is not None:
            self._timeline = TimeLine(loopCount=1, interval=1, step_size=5)
            self._timeline.timerEnded.connect(lambda: self.dock.setMinimumHeight(25))
            self._timeline.timerEnded.connect(lambda: self.dock.setMaximumHeight(2500))
            self._timeline.setFrameRange(self.dock.widget().height(), self.current_height)
            self._timeline.frameChanged.connect(self.set_widget_size)
            self._timeline.start()

    def set_widget_size(self, i) -> None:
        """_summary_

        :param i: _description_
        :type i: _type_
        """
        self.dock.widget().resize(self.dock.widget().width(), int(i))
        self.dock.resize(self.dock.width(), int(i))
        if i > self.dock.minimumHeight():
            self.dock.setFixedHeight(int(i))  # prevent container widget from resizing back
        self.dock.setMinimumHeight(25)
        self.resized.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """_summary_

        :param event: _description_
        :type event: QMouseEvent
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.initial_pos = event.position().toPoint()
        super().mousePressEvent(event)
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """_summary_

        :param event: _description_
        :type event: QMouseEvent
        """
        if self.initial_pos is not None:
            delta = event.position().toPoint() - self.initial_pos
            self.window().move(
                self.window().x() + delta.x(),
                self.window().y() + delta.y(),
            )
        super().mouseMoveEvent(event)
        event.accept()


class TimeLine(QObject):
    """_summary_"""

    frameChanged = Signal(float)
    timerEnded = Signal()

    def __init__(self, interval=60, loopCount=1, step_size=1, parent=None):
        """_summary_

        :param interval: _description_, defaults to 60
        :type interval: int, optional
        :param loopCount: _description_, defaults to 1
        :type loopCount: int, optional
        :param step_size: _description_, defaults to 1
        :type step_size: int, optional
        :param parent: _description_, defaults to None
        :type parent: _type_, optional
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
        Function called by Qtimer that will trigger a step of current step_size and emit new counter value.
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
                self.timerEnded.emit()

    def setLoopCount(self, loopCount: int) -> None:
        """_summary_

        :param loopCount: _description_
        :type loopCount: int
        """
        self._loopCount = loopCount

    def loopCount(self) -> int:
        """_summary_

        :return: _description_
        :rtype: int
        """
        return self._loopCount

    interval = Property(int, fget=loopCount, fset=setLoopCount)

    def setInterval(self, interval: int) -> None:
        """_summary_

        :param interval: _description_
        :type interval: int
        """
        self._timer.setInterval(interval)

    def interval(self) -> int:
        """_summary_

        :return: _description_
        :rtype: int
        """
        return self._timer.interval()

    interval = Property(int, fget=interval, fset=setInterval)

    def setFrameRange(self, startFrame: float, endFrame: float) -> None:
        """_summary_

        :param startFrame: _description_
        :type startFrame: float
        :param endFrame: _description_
        :type endFrame: float
        """
        self._startFrame = startFrame
        self._endFrame = endFrame

    @Slot()
    def start(self) -> None:
        """_summary_"""
        self._counter = self._startFrame
        self._loop_counter = 0
        self._timer.start()

    def stop(self) -> None:
        """_summary_"""
        self._timer.stop()
        self.timerEnded.emit()
