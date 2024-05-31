from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, scan_for_properties
from qtpy.QtWidgets import QPushButton, QStyle, QLabel, QSizePolicy, QWidget
from qtpy.QtCore import Qt
import itertools

class CameraWidget(BaseDeviceWidget):

    def __init__(self, camera,
                 advanced_user: bool = True):
        """Modify BaseDeviceWidget to be specifically for camera. Main need are adding roi validator,
        live view button, and snapshot button.
        :param camera: camera object"""

        self.camera_properties = scan_for_properties(camera) if advanced_user else {}
        super().__init__(type(camera), self.camera_properties)

        # create and format livestream button and snapshot button
        self.live_button = self.create_live_button()
        self.snapshot_button = self.create_snapshot_button()
        picture_buttons = create_widget('H', self.live_button, self.snapshot_button)


        if advanced_user:  # Format widgets better in advaced user mode

            _ = QWidget()  # dummy widget
            direct = Qt.FindDirectChildrenOnly

            # reformat binning and pixel type
            pixel_widgets = create_widget('VH',
                               *self.property_widgets.get('binning', _).findChildren(QWidget, options=direct),
                               *self.property_widgets.get('pixel_type', _).findChildren(QWidget, options=direct))
            # check if properties have setters and if not, disable widgets. Have to do it inside pixel widget
            for i, prop in enumerate(['binning', 'pixel_type']):
                attr = getattr(type(camera), prop)
                if getattr(attr, 'fset', None) is None:
                    pixel_widgets.children()[i+1].setEnabled(False)

            # reformat timing widgets
            timing_widgets = create_widget('VH',
                               *self.property_widgets.get('exposure_time_ms', _).findChildren(QWidget, options=direct),
                               *self.property_widgets.get('frame_time_ms', _).findChildren(QWidget, options=direct),
                               *self.property_widgets.get('line_interval_us', _).findChildren(QWidget, options=direct))
            # check if properties have setters and if not, disable widgets
            for i, prop in enumerate(['exposure_time_ms', 'frame_time_ms', 'line_interval_us']):
                attr = getattr(type(camera), prop, False)
                if getattr(attr, 'fset', None) is None:
                    timing_widgets.children()[i+1].setEnabled(False)


            # reformat sensor height and width widget
            sensor_size_widget = create_widget('VH',
                               *self.property_widgets.get('sensor_width_px', _).findChildren(QWidget, options=direct),
                               *self.property_widgets.get('sensor_height_px', _).findChildren(QWidget, options=direct))
            # check if properties have setters and if not, disable widgets
            for i, prop in enumerate(['sensor_width_px', 'sensor_height_px']):
                attr = getattr(type(camera), prop, False)
                if getattr(attr, 'fset', None) is None:
                    sensor_size_widget.children()[i + 1].setEnabled(False)

            # reformat roi widget
            self.roi_widget = create_widget('VH',
                                *self.property_widgets.get('width_px', _).findChildren(QWidget, options=direct),
                                *self.property_widgets.get('width_offset_px', _).findChildren(QWidget, options=direct),
                                *self.property_widgets.get('height_px', _).findChildren(QWidget, options=direct),
                                *self.property_widgets.get('height_offset_px', _).findChildren(QWidget, options=direct))
            self.roi_widget.setContentsMargins(0, 0, 0, 0)
            # check if properties have setters and if not, disable widgets
            for i, prop in enumerate(['width_px', 'width_offset_px', 'height_px', 'height_offset_px']):
                attr = getattr(type(camera), prop, False)
                if getattr(attr, 'fset', None) is None:
                    self.roi_widget.children()[i + 1].setEnabled(False)


            central_widget = self.centralWidget()
            self.setCentralWidget(create_widget('V',
                                                picture_buttons,
                                                pixel_widgets,
                                                timing_widgets,
                                                sensor_size_widget,
                                                self.roi_widget,
                                                central_widget))

    def create_live_button(self):
        """Add live button"""

        button = QPushButton('Live')
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        button.setIcon(icon)

        return button

    def create_snapshot_button(self):
        """Add snapshot button"""

        button = QPushButton('Snapshot')
        # icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        # button.setIcon(icon)
        return button
