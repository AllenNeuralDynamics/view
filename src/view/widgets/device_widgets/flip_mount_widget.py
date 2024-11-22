from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, scan_for_properties
from qtpy.QtWidgets import QSizePolicy


class FlipMountWidget(BaseDeviceWidget):

    def __init__(self, flip_mount):
        """
        Modify BaseDeviceWidget to be specifically for laser. Main need is adding slider .
        :param flip_mount: flip mount object
        """

        self.flip_mount_properties = scan_for_properties(flip_mount)
        super().__init__(type(flip_mount), self.flip_mount_properties)

        positions = self.property_widgets['position'].layout().itemAt(1).widget()
        positions.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        flip_time = self.property_widgets['flip_time_ms'].layout().itemAt(1).widget()
        flip_time.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Maximum)

        central_widget = self.centralWidget()
        central_widget.layout().setSpacing(0)  # remove space between central widget and newly formatted widgets
        self.setCentralWidget(create_widget('H',
                                            positions,
                                            self.property_widgets['flip_time_ms']))
