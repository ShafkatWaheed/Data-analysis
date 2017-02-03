import sys
from os import path

from PyQt5 import QtWidgets, QtCore
import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.pyplot as plt

import numpy as np

from mpl_toolkits.basemap import Basemap

from data_analysis._twitter_controller import GeographyConvienceWrapper
from data_analysis.sentiment_widget import SentimentMapWidget
from data_analysis._twitter_controller import SentimentConvienceWrapper
from data_analysis.sentiment_model import SentimentClassifier

from nltk.sentiment.vader import SentimentIntensityAnalyzer


def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()

    tab_widget = StreamSwitch()
    main_window.setCentralWidget(tab_widget)
    main_window.show()
    try:
        app.exec_()
    except KeyboardInterrupt:
        pass

class SentimentController(QtCore.QObject):
    # country code (3 digit str), aggregate sentiment, count of values
    sentiment_signal = QtCore.pyqtSignal(str, float, int)

    def __init__(self, sentiment_widget, parent=None):
        super().__init__(parent)
        self._widget = sentiment_widget
        self._twitter_access = SentimentConvienceWrapper()
        self._twitter_access.geo_tweet_signal.connect(self.analyze_tweets)
        # self._classifier = SentimentClassifier()
        self._classifier = SentimentIntensityAnalyzer()
        self._twitter_access.start()

    def analyze_tweets(self, coordinates: list, tweets: list):
        country_codes = []
        for coordinate in coordinates:
            country_code = self._widget.get_country_code(coordinate)
            country_codes.append(country_code)

        sentiments = {}
        for country, tweet in zip(country_codes, tweets):
            # sentiment = self._classifier.classify(tweet)
            polarity = self._classifier.polarity_scores()
            sentiment = ploarity['compound']
            try:
                sentiments[country].append(sentiment)
            except KeyError:
                sentiments[country] = [sentiment,]

        for country, values in sentiments.items():
            self.sentiment_signal.emit(country,
                                       np.mean(values),
                                       len(values))


class StreamSwitch(QtWidgets.QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        heat_map_widget = HeatMapWidget()
        """
        self._twitter_geography_access = GeographyConvienceWrapper()
        self._twitter_geography_access.geography_signal.connect(
                heat_map_widget.geography_slot)
        self._twitter_geography_access.start()
        """
        self.sentiment_widget = SentimentMapWidget()
        self.sentiment_controller = SentimentController(self.sentiment_widget)

        self.sentiment_controller.sentiment_signal.connect(
                self.sentiment_widget.sentiment_slot)

        self.addTab(self.sentiment_widget, 'Sentiment Map')
        self.addTab(heat_map_widget, 'Heat Map')


class MapWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._figure = plt.Figure()
        self._figure.set_tight_layout(True)
        self.axis = self._figure.add_subplot(111)
        self.map_ = self._setup_map(self.axis)
        self.map_.drawcoastlines(color='grey')
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

        # NOTE: see `data_analysis.map_widget.CounterWidget` for `counter_widget` source
        self.count_signal.connect(self.counter_widget.set_count)

    def _draw_map(self):
        self.map_.drawcoastlines(color='grey')

    def geography_slot(self, coords, tweets):
        """
        Coords is typically a 20 member list of (lats, longs)

        `tweets` currently unused.
        """
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


if __name__ == '__main__':
	main()
