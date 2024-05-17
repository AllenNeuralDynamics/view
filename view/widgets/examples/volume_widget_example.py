from view.widgets.acquisition_widgets.volume_widget import VolumeWidget
from qtpy.QtWidgets import QApplication
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    channels = {
        '488': {
            'filters': ['BP488'],
            'lasers': ['488nm'],
            'cameras': ['vnp - 604mx', 'vp-151mx']},
        '561':
            {'filters': ['BP561'],
             'lasers': ['561nm'],
             'cameras': ['vnp - 604mx', 'vp-151mx']},
        '639': {
            'filters': ['LP638'],
            'lasers': ['639nm'],
            'cameras': ['vnp - 604mx', 'vp-151mx']}
    }

    settings = {
        'cameras': ['binning'],
        'lasers': ['power_mw']
    }
    volume_widget = VolumeWidget(channels, settings)

    sys.exit(app.exec_())