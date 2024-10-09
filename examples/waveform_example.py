from view.widgets.device_widgets.ni_widget import sawtooth, triangle_wave, square_wave
from view.widgets.device_widgets.waveform_widget import WaveformWidget
from qtpy.QtWidgets import QApplication
import sys
import numpy as np
from qtpy.QtGui import QColor
from random import randint

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # list of colors
    colors = QColor.colorNames()
    colors.remove('black')

    # create widget
    waveform = WaveformWidget()
    waveform.setYRange(-10, 10)
    waveform.show()

    start_time_ms = 10
    end_time_ms = 400
    cutoff_frequency_hz = 200
    period_time_ms = 500
    rest_time_ms = 50
    sampling_frequency_hz = 10000

    scale = sampling_frequency_hz/1000

    square_parameters = {'sampling_frequency_hz': sampling_frequency_hz,
                         'period_time_ms': period_time_ms,
                         'start_time_ms': start_time_ms,
                         'end_time_ms': end_time_ms,
                         'rest_time_ms': rest_time_ms,
                         'max_volts': 5,
                         'min_volts': -5,
                         'device_min_volts': -10,
                         'device_max_volts': 10}
    square_x = [0, (start_time_ms * scale) - 1, start_time_ms*10, end_time_ms*10, (end_time_ms * scale) - 1,
                (period_time_ms + rest_time_ms) * scale]
    square_y = [0, 0, 5, 5, 0, 0]
    square_item = waveform.plot(pos=np.column_stack((square_x, square_y)),
                  waveform='square wave',
                  color=colors[randint(0, len(colors) - 1)],
                  parameters=square_parameters)
    # hook up item event to update parameters when values have changed
    square_item.valueChanged.connect(lambda value: square_parameters.__setitem__(value, getattr(square_item, value)))
    square_item.valueChanged.connect(lambda value: print(square_parameters))

    sawtooth_parameters = {'sampling_frequency_hz': sampling_frequency_hz,
                           'period_time_ms': period_time_ms,
                           'start_time_ms': start_time_ms,
                           'end_time_ms': end_time_ms,
                           'rest_time_ms': rest_time_ms,
                           'amplitude_volts': 1,
                           'offset_volts': 2.5,
                           'cutoff_frequency_hz': cutoff_frequency_hz,
                           }
    saw_voltages = sawtooth(**sawtooth_parameters)
    saw_x = [0, start_time_ms * scale, end_time_ms * scale, period_time_ms * scale,
             (period_time_ms + rest_time_ms) *scale]
    saw_y = [saw_voltages[0], saw_voltages[start_time_ms], saw_voltages[end_time_ms], saw_voltages[period_time_ms],
             saw_voltages[-1]]
    sawtooth_parameters['device_min_volts'] = -10
    sawtooth_parameters['device_max_volts'] = 10
    saw_item = waveform.plot(pos=np.column_stack((saw_x, saw_y)),
                  waveform='sawtooth',
                  color=colors[randint(0, len(colors) - 1)],
                  parameters=sawtooth_parameters)
    # hook up item event to update parameters when values have changed
    saw_item.valueChanged.connect(lambda value: sawtooth_parameters.__setitem__(value, getattr(saw_item, value)))
    saw_item.valueChanged.connect(lambda value: print(sawtooth_parameters))

    triangle_parameters = {'sampling_frequency_hz': sampling_frequency_hz,
                           'period_time_ms': period_time_ms,
                           'start_time_ms': start_time_ms,
                           'end_time_ms': end_time_ms,
                           'rest_time_ms': rest_time_ms,
                           'amplitude_volts': 1,
                           'offset_volts': 2.5,
                           'cutoff_frequency_hz': cutoff_frequency_hz,
                           }
    tri_voltages = triangle_wave(**triangle_parameters)
    tri_x = [0, start_time_ms * scale, end_time_ms * scale, period_time_ms * scale,
             (period_time_ms + rest_time_ms) * scale]
    tri_y = [tri_voltages[0], tri_voltages[start_time_ms], tri_voltages[end_time_ms], tri_voltages[period_time_ms],
             tri_voltages[-1]]
    triangle_parameters['device_min_volts'] = -10
    triangle_parameters['device_max_volts'] = 10
    tri_item = waveform.plot(pos=np.column_stack((tri_x, tri_y)),
                  waveform='triangle wave',
                  color=colors[randint(0, len(colors) - 1)],
                  parameters=triangle_parameters)
    # hook up item event to update parameters when values have changed
    tri_item.valueChanged.connect(lambda value: triangle_parameters.__setitem__(value, getattr(tri_item, value)))
    tri_item.valueChanged.connect(lambda value: print(triangle_parameters))

    sys.exit(app.exec_())
