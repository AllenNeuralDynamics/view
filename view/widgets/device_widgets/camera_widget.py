from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, scan_for_properties
from qtpy.QtWidgets import QPushButton, QStyle, QLabel


class CameraWidget(BaseDeviceWidget):

    def __init__(self, camera,
                 advanced_user: bool = True):
        """Modify BaseDeviceWidget to be specifically for camera. Main need are adding roi validator,
        live view button, and snapshot button.
        :param camera: camera object"""

        self.camera_properties = scan_for_properties(camera) if advanced_user else {}
        super().__init__(type(camera), self.camera_properties)

        self.organize_roi()
        self.add_live_button()
        self.add_snapshot_button()

        self.roi_widget = create_widget('H', QLabel('ROI: '),
                                        self.property_widgets['width_px'],
                                        self.property_widgets['width_offset_px'],
                                        self.property_widgets['height_px'],
                                        self.property_widgets['height_offset_px'])

        self.centralWidget().layout().addWidget(self.roi_widget)

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

    def organize_roi(self):
        """Organize width, height, and offsets widgets"""


        self.property_widgets['width_px'] = create_widget('V', *self.property_widgets['width_px'].children())
        self.property_widgets['width_offset_px'] = create_widget('V',
                                                                 *self.property_widgets['width_offset_px'].children())
        self.property_widgets['height_px'] = create_widget('V', *self.property_widgets['height_px'].children())
        self.property_widgets['height_offset_px'] = create_widget('V',
                                                                 *self.property_widgets['height_offset_px'].children())

