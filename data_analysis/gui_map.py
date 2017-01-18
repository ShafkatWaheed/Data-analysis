import re
import sys # NOTE: TEMPORARY
from os import path

from PyQt5 import QtWidgets, QtCore
import numpy as np

from tweepy import Stream
from tweepy.streaming import StreamListener

import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib import cm


from mpl_toolkits.basemap import Basemap

from data_analysis.auth import auth


# NOTE: TEMPORARY
def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()
    # widget = MapWidget()
    widget = HeatMapWidget()
    main_window.setCentralWidget(widget)

    listener = PrintListener()
    listener.geography_signal.connect(widget.geography_slot)
    stream = Stream(auth, listener, timeout=60, retry_count=20)
    # languages = ('en',)
    # stream.filter(locations=[-180,-90,180,90], async=True, languages=('en',))
    stream.filter(locations=[-180,-90,180,90], async=True)
    main_window.show()
    try:
        app.exec_()
    except KeyboardInterrupt:
        pass

    stream.running = False
    listener.finished = True

class _Signaler(QtCore.QObject):
    geography_signal = QtCore.pyqtSignal(list, list)
    def __init__(self, parent=None):
        super().__init__(parent)

class PrintListener(StreamListener):
    def __init__(self, parent=None):
        super().__init__()
        self.signaler = _Signaler()
        self.geography_signal = self.signaler.geography_signal
        self.finished = False
        self._coord_cache = []
        self._tweet_cache = []

    def on_status(self, status):
        if status.coordinates is not None:
            self._coord_cache.append(status.coordinates['coordinates'])
            self._tweet_cache.append(status.text)
            if len(self._coord_cache) > 19:
                self.geography_signal.emit(self._coord_cache,
                                           self._tweet_cache)
                self._coord_cache = []
                self._tweet_cache = []

        if self.finished:
            return False

    def on_error(self, error):
        print(error)



class CounterWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._count_string = 'Collected Data Points: {}'
        self._time_string = 'Elasped Time: {}'

        self.count_label = QtWidgets.QLabel()
        self.count_label.setText(self._count_string.format(0))

        self._timer = QtCore.QTime()
        self._timer.start()
        self.time_label = QtWidgets.QLabel()
        self.time_label.setText(self._time_string.format(self._timer.elapsed()))

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.count_label)
        layout.addWidget(self.time_label)
        self.setLayout(layout)

    def get_elapsed_time(self):
        millis = self._timer.elapsed()
        seconds = int((millis/1000) % 60)
        minutes = int((millis/(1000*60)) % 60)
        hours = int((millis/(1000*3600)) % 24)

        return '{}:{}:{}'.format(hours, minutes, seconds)

    def count(self, integer):
        self.count_label.setText(self._count_string.format(str(integer)))
        time = self.get_elapsed_time()
        self.time_label.setText(self._time_string.format(time))

class HeatMapWidget(QtWidgets.QWidget):
    count_signal = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        self._x_coords = []
        self._y_coords = []
        self._old_x = np.array([])
        self._old_y = np.array([]) 

        self._figure = plt.Figure()
        self._figure.set_tight_layout(True)
        counter = CounterWidget()
        self.count_signal.connect(counter.count)
        # plt.ion()

        self.axis = self._figure.add_subplot(111)
        self.map_ = self._setup_map(self.axis)

        self._canvas = FigureCanvas(self._figure)
        # self._canvas.draw()
        # self._ax_background = self._canvas.copy_from_bbox(self.ax.bbox)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._canvas)
        layout.addWidget(counter)
        self.setLayout(layout)

    def _setup_map(self, axis):
        """
        helper method to setup the basemap
        """
        map_ = Basemap(projection='merc',
                       llcrnrlat=-60,
                       urcrnrlat=80,
                       llcrnrlon=-180,
                       urcrnrlon=180,
                       lat_ts=20,
                       ax=axis,
                       resolution='c')
 
        # map_.bluemarble(scale=0.3)
        # map_.shadedrelief(scale=0.1)
        # map_.drawcoastlines()
        self._draw_map(map_)
        return map_

    def _draw_map(self, map_=None):
        if map_ is None:
            map_ = self.map_

        map_.drawcoastlines(color='grey')

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

            r = self.map_.hexbin(self._x_coords,
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
        plt.pause(0.1)

    def update_canvas(self):
        self._canvas.draw()


class MapWidget(QtWidgets.QWidget):
    process_tweet_signal = QtCore.pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        self._x_coords = []
        self._y_coords = []

        self._figure = plt.Figure()
        self._figure.set_tight_layout(True)
        plt.ion()

        # get the default axis from figure
        axis = self._figure.add_subplot(111)
        self.map_ = self._setup_map(axis)

        self._canvas = FigureCanvas(self._figure)
        # self._canvas.draw()
        # self._ax_background = self._canvas.copy_from_bbox(self.ax.bbox)
       # widget!
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._canvas)

        self._worker_thread = QtCore.QThread(parent=self)
        self._worker = Language()
        self._worker.moveToThread(self._worker_thread)
        self._worker_thread.start()

        self.process_tweet_signal.connect(self._worker.process_tweet)
        self.setLayout(layout)

    def geography_slot(self, x_coord, y_coord, tweet):
        x_coord, y_coord = self.map_(x_coord, y_coord)
        self._x_coords.append(x_coord)
        self._y_coords.append(y_coord)

        if self._count % 20 == 0:
            colleciton = self.map_.scatter(self._x_coords,
                                           self._y_coords,
                                           s=10,
                                           color='orange')

            self._x_coords = []
            self._y_coords = []

        # TODO: map result to tweet
        self.process_tweet_signal.emit(self._count, tweet)
        self._count += 1
        self.update_canvas()
        plt.pause(0.1)


    def _setup_map(self, axis):
        """
        helper method to setup the basemap
        """
        map_ = Basemap(projection='merc',
                       llcrnrlat=-80,
                       urcrnrlat=80,
                       llcrnrlon=-160,
                       urcrnrlon=180,
                       lat_ts=20,
                       ax=axis,
                       resolution='c')
 
        # map_.bluemarble(scale=0.3)
        map_.shadedrelief()
        # map_.drawcoastlines()
        return map_

    def update_canvas(self):
        # self._canvas.restore_region(self._ax_background)
        # self.ax.draw_artist(self.circle)
        # self.canvas.blit(self.ax.bbox)
        # self.canvas.flush_events()
        self._canvas.draw()


if __name__ == '__main__':
    main()
    """
    map_widget = MapWidget()
    map_widget.show()
    """
