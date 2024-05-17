from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, scan_for_properties
from qtpy.QtWidgets import QPushButton, QStyle


class CameraWidget(BaseDeviceWidget):

    def __init__(self, camera,
                 advanced_user: bool = True):
        """Modify BaseDeviceWidget to be specifically for camera. Main need are adding roi validator,
        live view button, and snapshot button.
        :param camera: camera object"""

        self.camera_properties = scan_for_properties(camera) if advanced_user else {}
        super().__init__(type(camera), self.camera_properties)

        # TODO: Automatically set up validators for properties with min max values
        self.validator_attributes = {k: v for k, v in camera.__dict__.items() if 'min_' in k or
                                     'max_' in k or 'step_' in k}
        self.add_roi_validator()
        self.add_live_button()
        self.add_snapshot_button()

    def add_live_button(self):
        """Add live button"""

        button = QPushButton('Live')
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        button.setIcon(icon)
        widget = self.centralWidget()
        self.setCentralWidget(create_widget('V', button, widget))
        setattr(self, 'live_button', button)

    def add_snapshot_button(self):
        """Add snapshot button"""

        button = QPushButton('Snapshot')
        # icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        # button.setIcon(icon)
        widget = self.centralWidget()
        self.setCentralWidget(create_widget('V', button, widget))
        setattr(self, 'snapshot_button', button)

    def add_roi_validator(self):
        """Add checks on inputs to roi widgets"""
        if 'roi' in self.camera_properties.keys():
            for k in self.camera_properties['roi'].keys():
                getattr(self, f'roi.{k}_widget').disconnect()  # Disconnect all calls
                getattr(self, f'roi.{k}_widget').editingFinished.connect(lambda key=k: self.roi_validator(key))

    def roi_validator(self, k):
        """Check if input value adheres to max, min, divisor variables in module"""

        widget = getattr(self, f'roi.{k}_widget')
        value = int(widget.text())
        specs = {'min': self.validator_attributes.get(f'min_{k}', 0),
                 'max': self.validator_attributes.get(f'max_{k}', value),
                 'divisor': self.validator_attributes.get(f'step_{k}', 1)}
        widget.blockSignals(True)
        if value < specs['min']:
            value = specs['min']
        elif value > specs['max']:
            value = specs['max']
        elif value % specs['divisor'] != 0:
            value = round(value / specs['divisor']) * specs['divisor']
        getattr(self, 'roi').__setitem__(k, value)
        widget.setText(str(value))
        self.ValueChangedInside.emit(f'roi.{k}')
        widget.blockSignals(False)
