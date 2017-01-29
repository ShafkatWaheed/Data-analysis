from PyQt5 import QtWidgets, QtCore

import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.pyplot as plt

from mpl_toolkits.basemap import Basemap

class MapWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._figure = plt.Figure()
        self._figure.set_tight_layout(True)
        self.axis = self._figure.add_subplot(111)
        self.map_ = self._setup_map(self.axis)
        self._canvas = FigureCanvas(self._figure)

        self.counter_widget = CounterWidget()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._canvas)
        layout.addWidget(self.counter_widget)
        self.setLayout(layout)


    def _setup_map(self, axis):
        map_ = Basemap(projection='merc',
                       llcrnrlat=-60,
                       urcrnrlat=80,
                       llcrnrlon=-180,
                       urcrnrlon=180,
                       lat_ts=20,
                       ax=axis,
                       resolution='c')

        return map_

    def update_canvas(self):
        self._canvas.draw()


class CounterWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._count_string = 'Collected Data Points: {}'
        self._time_string = 'Elasped Time: {}'
        self._internal_count = 0

        self.count_label = QtWidgets.QLabel()
        self.count_label.setText(self._count_string.format(0))

        self._timer = QtCore.QTime()
        self._timer.start()
        self.time_label = QtWidgets.QLabel()
        elasped = self._timer.elapsed()
        self.time_label.setText(self._time_string.format(elasped))

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.count_label)
        layout.addWidget(self.time_label)
        self.setLayout(layout)

    def get_elapsed_time(self):
        millis = self._timer.elapsed()
        seconds = int((millis/1000) % 60)
        minutes = int((millis/(1000*60)) % 60)
        hours = int((millis/(1000*3600)) % 24)

        return '{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)

    def set_count(self, integer):
        self.count_label.setText(self._count_string.format(str(integer)))
        self._internal_count = integer
        self._set_time_helper()

    def add_to_count(self, integer):
        self._internal_count += integer
        s = self._count_string.format(str(self._internal_count))
        self.count_label.setText(s)
        self._set_time_helper()

    def _set_time_helper(self):
        time = self.get_elapsed_time()
        self.time_label.setText(self._time_string.format(time))
