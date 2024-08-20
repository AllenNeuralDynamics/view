from view.widgets.acquisition_widgets.volume_plan_widget import VolumePlanWidget
from qtpy.QtWidgets import QApplication
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)

    plan = VolumePlanWidget()
    plan.show()

    plan.valueChanged.connect(lambda val: print(val))

    sys.exit(app.exec_())