from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, label_maker, scan_for_properties
from qtpy.QtWidgets import QLabel, QFrame, QVBoxLayout

class JoystickWidget(BaseDeviceWidget):

    def __init__(self, joystick,
                 advanced_user: bool = True):
        """
        Modify BaseDeviceWidget to be specifically for Joystick.
        :param joystick: joystick object
        :param advanced_user: boolean specifying complexity of widget. If False, returns blank widget
        """

        properties = scan_for_properties(joystick) if advanced_user else {}
        super().__init__(type(joystick), properties)
        self.advanced_user = advanced_user

        if self.advanced_user:
            self.create_axis_combo_box()

    def create_axis_combo_box(self) -> None:
        """
        Transform Instrument Axis text box into combo box and allow selection of only available axes
        """

        joystick_widgets = [QLabel('Joystick Mapping'), QLabel()]
        for joystick_axis, specs in self.joystick_mapping.items():
            unused = list(
                set(self.stage_axes) - set(axis['instrument_axis'] for axis in self.joystick_mapping.values()))
            unused.append(specs['instrument_axis'])
            old_widget = getattr(self, f'joystick_mapping.{joystick_axis}.instrument_axis_widget')
            new_widget = self.create_combo_box(f'joystick_mapping.{joystick_axis}.instrument_axis', unused)
            old_widget.parentWidget().layout().removeItem(old_widget.parentWidget().layout().itemAt(0))
            old_widget.parentWidget().layout().replaceWidget(old_widget, new_widget)
            setattr(self, f'joystick_mapping.{joystick_axis}.instrument_axis_widget', new_widget)
            new_widget.currentTextChanged.connect(self.update_axes_selection)
            widget_dict = {'label': QLabel(label_maker(joystick_axis)),
                           **getattr(self, f'joystick_mapping.{joystick_axis}_widgets')}
            # add frame
            frame = QFrame()
            layout = QVBoxLayout()
            layout.addWidget(create_widget('V', **widget_dict))
            frame.setLayout(layout)
            frame.setStyleSheet(f".QFrame {{ border:1px solid grey ; }} ")
            if not self.advanced_user:
                frame.setEnabled(False)
            joystick_widgets.append(frame)

        self.centralWidget().layout().replaceWidget(self.property_widgets['joystick_mapping'],
                                                    create_widget('HV', *joystick_widgets))

    def update_axes_selection(self) -> None:
        """
        When joystick axis mapped to new stage axis, update available stage axis
        """

        for joystick_axis, specs in self.joystick_mapping.items():
            unused = list(set(self.stage_axes) - set(ax['instrument_axis'] for ax in self.joystick_mapping.values()))
            unused.append(specs['instrument_axis'])
            widget = getattr(self, f'joystick_mapping.{joystick_axis}.instrument_axis_widget')
            # block signals to not trigger currentTextChanged
            widget.blockSignals(True)
            widget.clear()
            widget.addItems(unused)
            widget.setCurrentText(specs['instrument_axis'])
            widget.blockSignals(False)
