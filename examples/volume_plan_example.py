from view.widgets.acquisition_widgets.tile_plan_widget import TilePlanWidget
from qtpy.QtWidgets import QApplication
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)

    plan = TilePlanWidget()
    plan.show()

    sys.exit(app.exec_())