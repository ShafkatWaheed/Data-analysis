from PyQt5 import QtWidgets, QtCore
import numpy as np

from tweepy.streaming import StreamListener, Stream

from data_analysis.map_widget import MapWidget, plt


class HeatMapWidget(MapWidget):
    count_signal = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._draw_map()
        self._count = 0
        self._x_coords = []
        self._y_coords = []
        self._old_x = np.array([])
        self._old_y = np.array([])

        # NOTE: see `data_analysis.map_widget.CounterWidget` for source
        self.count_signal.connect(self.counter_widget.set_count)

    def _draw_map(self):
        self.map_.drawcoastlines(color='grey')

    def geography_slot(self, coords, tweets):
        for index, (x, y) in enumerate(coords):
            coords[index] = self.map_(x, y)

        self._count += len(coords)
        self.count_signal.emit(self._count)
        # adds 20
        self._x_coords.extend([x[0] for x in coords])
        self._y_coords.extend([x[1] for x in coords])

        if self._count % 100 == 0:
            self._x_coords = np.append(self._x_coords, self._old_x)
            self._y_coords = np.append(self._y_coords, self._old_y)

            self.axis.cla()
            self._draw_map()

            self.map_.hexbin(self._x_coords,
                             self._y_coords,
                             cmap=plt.cm.rainbow,
                             mincnt=1)

            # plt.colorbar(shrink=0.625, aspect=20, fraction=0.2,pad=0.02)

            # keep 10,000 points
            if len(self._old_x) > 10000:
                self._old_x = self._x_coords[100:]
                self._old_y = self._y_coords[100:]
            else:
                self._old_x = self._x_coords
                self._old_y = self._y_coords

            self._x_coords = []
            self._y_coords = []

        self.update_canvas()
