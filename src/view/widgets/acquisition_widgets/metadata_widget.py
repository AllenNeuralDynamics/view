from pathlib import Path
from typing import Callable

from qtpy.QtCore import Qt, QSize
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QButtonGroup,
)

from view.widgets.base_device_widget import BaseDeviceWidget, scan_for_properties


ICON_SIZE = 140

BRAIN_ORIENTATION_LOOKUP = {
    "option1": {
        "image": "dorsal_1.png",
        "x_anatomical_direction": "Anterior_to_posterior",
        "y_anatomical_direction": "Right_to_left",
        "z_anatomical_direction": "Superior_to_inferior",
    },
    "option2": {
        "image": "dorsal_2.png",
        "x_anatomical_direction": "Posterior_to_anterior",
        "y_anatomical_direction": "Left_to_right",
        "z_anatomical_direction": "Superior_to_inferior",
    },
    "option3": {
        "image": "ventral_1.png",
        "x_anatomical_direction": "Posterior_to_anterior",
        "y_anatomical_direction": "Left_to_right",
        "z_anatomical_direction": "Inferior_to_superior",
    },
    "option4": {
        "image": "ventral_2.png",
        "x_anatomical_direction": "Anterior_to_posterior",
        "y_anatomical_direction": "Right_to_left",
        "z_anatomical_direction": "Inferior_to_superior",
    },
}

BRAIN_ORIENTATIONS = {
    "option1": "option1",
    "option2": "option2",
    "option3": "option3",
    "option4": "option4",
}


class BrainOrientationWindow(QWidget):
    """Independent window for selecting brain orientation."""

    def __init__(self, parent_metadata_widget, image_dir: Path):
        super().__init__()

        self.parent_metadata_widget = parent_metadata_widget
        self.setWindowTitle("Brain orientation")

        layout = QVBoxLayout(self)

        label = QLabel("Select brain orientation")
        layout.addWidget(label)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        metadata = self.parent_metadata_widget.metadata_class
        current_orientation = getattr(metadata, "brain_orientation", None)

        for orientation_name, orientation_info in BRAIN_ORIENTATION_LOOKUP.items():
            button = QToolButton()
            button.setCheckable(True)
            # button.setText(orientation_name.replace("_", " "))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

            icon_path = image_dir / orientation_info["image"]
            button.setIcon(QIcon(str(icon_path)))
            button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))

            if orientation_name == current_orientation:
                button.setChecked(True)

            button.clicked.connect(
                lambda checked=False, name=orientation_name: self.set_orientation(name)
            )

            self.button_group.addButton(button)
            layout.addWidget(button)

        self.adjustSize()
        self.setFixedWidth(ICON_SIZE + 64)

    def set_orientation(self, orientation_name: str):
        orientation = BRAIN_ORIENTATION_LOOKUP[orientation_name]
        metadata = self.parent_metadata_widget.metadata_class

        metadata.brain_orientation = orientation_name
        metadata.x_anatomical_direction = orientation["x_anatomical_direction"]
        metadata.y_anatomical_direction = orientation["y_anatomical_direction"]
        metadata.z_anatomical_direction = orientation["z_anatomical_direction"]

        for name in [
            "brain_orientation",
            "x_anatomical_direction",
            "y_anatomical_direction",
            "z_anatomical_direction",
        ]:
            if name in self.parent_metadata_widget.property_widgets:
                self.parent_metadata_widget.update_property_widget(name)


class MetadataWidget(BaseDeviceWidget):
    """Widget for handling metadata class."""

    def __init__(self, metadata_class, advanced_user: bool = True) -> None:
        properties = scan_for_properties(metadata_class)
        self.metadata_class = metadata_class
        super().__init__(type(metadata_class), properties)

        self.metadata_class = metadata_class

        self.property_widgets.get(
            "acquisition_name_format",
            QWidget(),
        ).hide()

        for name in [
            "x_anatomical_direction",
            "y_anatomical_direction",
            "z_anatomical_direction",
        ]:
            self.property_widgets.get(name, QWidget()).hide()

        if "brain_orientation" in self.property_widgets:
            self.property_widgets["brain_orientation"].show()

        self.brain_orientation_window = None
        self.open_brain_orientation_window()

        for name in (
            getattr(self, "acquisition_name_format", [])
            + ["date_format" if hasattr(self, "date_format") else None]
            + ["delimiter" if hasattr(self, "delimiter") else None]
        ):
            if name is not None:
                prop = getattr(type(metadata_class), name)
                prop_setter = getattr(prop, "fset")
                filter_getter = getattr(prop, "fget")

                setattr(
                    type(metadata_class),
                    name,
                    property(
                        filter_getter,
                        self.name_property_change_wrapper(prop_setter),
                    ),
                )

    def open_brain_orientation_window(self):
        image_dir = Path(__file__).parent / "icons" / "brain_orientations"

        self.brain_orientation_window = BrainOrientationWindow(
            parent_metadata_widget=self,
            image_dir=image_dir,
        )
        self.brain_orientation_window.show()

    def name_property_change_wrapper(self, func: Callable) -> Callable:
        def wrapper(object, value):
            func(object, value)
            self.acquisition_name = self.metadata_class.acquisition_name
            self.update_property_widget("acquisition_name")

        return wrapper