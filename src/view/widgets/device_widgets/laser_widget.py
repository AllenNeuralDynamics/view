from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, scan_for_properties
from qtpy.QtCore import Qt
import importlib
from view.widgets.miscellaneous_widgets.q_scrollable_float_slider import QScrollableFloatSlider
from qtpy.QtGui import QIntValidator, QDoubleValidator
from qtpy.QtWidgets import QSizePolicy
class LaserWidget(BaseDeviceWidget):

    def __init__(self, laser,
                 color: str = 'blue',
                 advanced_user: bool = True):
        """
        Modify BaseDeviceWidget to be specifically for laser. Main need is adding slider .
        :param laser: laser object
        :param color: color of laser slider
        :param advanced_user: boolean specifying complexity of widget. If False, only power widget will be visible
        """

        self.laser_properties = scan_for_properties(laser) if advanced_user else \
            {'power_setpoint_mw': laser.power_setpoint_mw,
             'power_mw': laser.power_mw}
        self.laser_module = importlib.import_module(laser.__module__)
        self.slider_color = color
        super().__init__(type(laser), self.laser_properties)
        self.max_power_mw = getattr(type(laser).power_setpoint_mw, 'maximum', 110)
        self.add_power_slider()

    def add_power_slider(self) -> None:
        """
        Modify power widget to be slider
        """

        setpoint = self.power_setpoint_mw_widget
        power = self.power_mw_widget

        if type(setpoint.validator()) == QDoubleValidator:
            setpoint.validator().setRange(0.0, self.max_power_mw, decimals=2)
            power.validator().setRange(0.0, self.max_power_mw, decimals=2)
        elif type(setpoint.validator()) == QIntValidator:
            setpoint.validator().setRange(0, self.max_power_mw)
            power.validator().setRange(0.0, self.max_power_mw)

        power.setEnabled(False)
        power.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)
        setpoint.validator().fixup = self.power_slider_fixup
        setpoint.editingFinished.connect(lambda: slider.setValue(round(float(setpoint.text()))))
        setpoint.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        textbox_power_mw_label = self.property_widgets['power_mw'].layout().itemAt(0).widget()
        textbox_power_mw_label.setVisible(False)  # hide power_mw label

        slider = QScrollableFloatSlider(orientation=Qt.Horizontal)
        slider.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        slider.setStyleSheet("QSlider::groove:horizontal {border: 1px solid #777;height: 10px;border-radius: 4px;}"
                             "QSlider::handle:horizontal {background-color: grey; width: 16px; height: 20px; "
                             "line-height: 20px; margin-top: -5px; margin-bottom: -5px; border-radius: 10px; }"
                             f"QSlider::sub-page:horizontal {{background: {self.slider_color};border: 1px solid #777;"
                             f"height: 10px;border-radius: 4px;}}")

        slider.setMinimum(0)  # Todo: is it always zero?
        slider.setMaximum(int(self.max_power_mw))
        slider.setValue(int(self.power_setpoint_mw))
        slider.sliderMoved.connect(lambda: setpoint.setText(str(slider.value())))
        slider.sliderReleased.connect(lambda: setattr(self, 'power_setpoint_mw', float(slider.value())))
        slider.sliderReleased.connect(lambda: self.ValueChangedInside.emit('power_setpoint_mw'))

        self.power_setpoint_mw_widget_slider = slider
        self.property_widgets['power_setpoint_mw'].layout().addWidget(self.power_mw_widget)
        self.property_widgets['power_setpoint_mw'].layout().addWidget(slider)


    def power_slider_fixup(self, value) -> None:
        """
        Fix entered values that are larger than max power
        :param value: value entered that is above maximum of slider
        """

        self.power_setpoint_mw_widget.setText(str(self.max_power_mw))
        self.power_setpoint_mw_widget.editingFinished.emit()