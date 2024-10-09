from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties
from qtpy.QtWidgets import QLabel
import importlib

class StageWidget(BaseDeviceWidget):

    def __init__(self, stage,
                 advanced_user: bool = True):
        """
        Modify BaseDeviceWidget to be specifically for Stage. Main need is advanced user.
        :param stage: stage object
        :param advanced_user: boolean specifying complexity of widget. If False, only position is shown
        """

        self.stage_properties = scan_for_properties(stage) if advanced_user else {'position_mm': stage.position_mm}

        self.stage_module = importlib.import_module(stage.__module__)
        super().__init__(type(stage), self.stage_properties)

        # alter position_mm widget to use instrument_axis as label
        self.property_widgets['position_mm'].setEnabled(False)
        position_label = self.property_widgets['position_mm'].findChild(QLabel)
        unit = getattr(type(stage).position_mm, 'unit', 'mm')  # TODO: Change when deliminated property is updated
        position_label.setText(f'{stage.instrument_axis} [{unit}]')

        # update property_widgets['position_mm'] text to be white
        style = """
        QScrollableLineEdit {
            color: white;
        } 

        QLabel {
            color : white;     
        }    
        """
        self.property_widgets['position_mm'].setStyleSheet(style)
