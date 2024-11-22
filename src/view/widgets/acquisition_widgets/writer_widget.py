from view.widgets.base_device_widget import BaseDeviceWidget, create_widget, scan_for_properties
from qtpy.QtWidgets import QFileDialog

class WriterWidget(BaseDeviceWidget):
    """Widget for handling metadata class"""
    def __init__(self, writer, advanced_user: bool = True) -> None:
        """
        :param writer: writer object
        :param advanced_user: future use argument to determine what should be shown
        """

        self.writer_properties = scan_for_properties(writer)
        # hide properties that are not needed
        del self.writer_properties['frame_count_px']
        del self.writer_properties['chunk_count_px']
        del self.writer_properties['column_count_px']
        del self.writer_properties['row_count_px']
        del self.writer_properties['acquisition_name']
        del self.writer_properties['filename']
        del self.writer_properties['channel']
        del self.writer_properties['color']
        del self.writer_properties['x_voxel_size_um']
        del self.writer_properties['y_voxel_size_um']
        del self.writer_properties['z_voxel_size_um']
        del self.writer_properties['x_position_mm']
        del self.writer_properties['y_position_mm']
        del self.writer_properties['z_position_mm']
        del self.writer_properties['theta_deg']

        super().__init__(type(writer), self.writer_properties)

        if not advanced_user:   # hide widgets
            for widget in self.property_widgets.values():
                widget.setVisible(False)

        combobox_data_type = self.property_widgets['data_type'].layout().itemAt(1).widget()
        combobox_compression = self.property_widgets['compression'].layout().itemAt(1).widget()
        widget_path = self.property_widgets['path'].layout().itemAt(1).widget()
        progress_bar = self.property_widgets['progress'].layout().itemAt(1).widget()

        new_widget_path = QFileDialog()
        widget_path.parentWidget().layout().replaceWidget(widget_path, new_widget_path)
        widget_path.deleteLater()

        # check if properties have setters and if not, disable widgets
        for i, prop in enumerate(['data_type']):
            attr = getattr(type(writer), prop, False)
            if getattr(attr, 'fset', None) is None:
                combobox_data_type.children()[i + 1].setEnabled(False)
        for i, prop in enumerate(['compression']):
            attr = getattr(type(writer), prop, False)
            if getattr(attr, 'fset', None) is None:
                combobox_compression.children()[i + 1].setEnabled(False)

        combined_widget = create_widget('VH',
                                        combobox_data_type,
                                        combobox_compression)

        central_widget = self.centralWidget()
        central_widget.layout().setSpacing(0)  # remove space between central widget and newly formatted widgets
        self.setCentralWidget(create_widget('V',
                                            new_widget_path,
                                            combined_widget,
                                            progress_bar))
