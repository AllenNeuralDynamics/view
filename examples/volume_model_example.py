from view.widgets.acquisition_widgets.volume_plan_widget import VolumePlanWidget
from view.widgets.acquisition_widgets.volume_model import VolumeModel
from view.widgets.acquisition_widgets.channel_plan_widget import ChannelPlanWidget
from qtpy.QtWidgets import QApplication
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)

    volume_model = VolumeModel()
    volume_model.show()

    sys.exit(app.exec_())