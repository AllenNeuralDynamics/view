import importlib

from qtpy.QtWidgets import QLabel

from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties


class StageWidget(BaseDeviceWidget):
    """_summary_"""

    def __init__(self, stage, advanced_user: bool = True):
        """_summary_

        :param stage: _description_
        :type stage: _type_
        :param advanced_user: _description_, defaults to True
        :type advanced_user: bool, optional
        """
        self.stage_properties = scan_for_properties(stage) if advanced_user else {"position_mm": stage.position_mm}

        self.stage_module = importlib.import_module(stage.__module__)
        super().__init__(type(stage), self.stage_properties)

        # alter position_mm widget to use instrument_axis as label
        self.property_widgets["position_mm"].setEnabled(False)
        position_label = self.property_widgets["position_mm"].findChild(QLabel)
        unit = getattr(type(stage).position_mm, "unit", "mm")  # TODO: Change when deliminated property is updated
        position_label.setText(f"{stage.instrument_axis} [{unit}]")

        # update property_widgets['position_mm'] text to be white
        style = """
        QScrollableLineEdit {
            color: white;
        } 

        QLabel {
            color : white;     
        }    
        """
        self.property_widgets["position_mm"].setStyleSheet(style)
