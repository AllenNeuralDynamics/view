from view.widgets.base_device_widget import BaseDeviceWidget
from view.widgets.miscellaneous_widgets.q_scrollable_line_edit import QScrollableLineEdit
from qtpy.QtWidgets import QLabel, QTextEdit
import importlib


def scan_for_properties(device):
    """Scan for properties with setters and getters in class and return dictionary
    :param device: object to scan through for properties
    """

    prop_dict = {}
    for attr_name in dir(device):
        attr = getattr(type(device), attr_name, None)
        if isinstance(attr, property) and getattr(device, attr_name) != None:
            prop_dict[attr_name] = getattr(device, attr_name)

    return prop_dict


class StageWidget(BaseDeviceWidget):

    def __init__(self, stage,
                 advanced_user: bool = True):
        """Modify BaseDeviceWidget to be specifically for Stage. Main need is advanced user.
        :param stage: stage object"""

        self.stage_properties = scan_for_properties(stage) if advanced_user else {'position_mm': stage.position_mm}

        self.stage_module = importlib.import_module(stage.__module__)
        super().__init__(type(stage), self.stage_properties)

        # alter position_mm widget to use instrument_axis as label
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