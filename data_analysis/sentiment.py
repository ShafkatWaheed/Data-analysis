import re
import sys
import json
import time

from os import path
from threading import Thread
from queue import Queue

from PyQt5 import QtWidgets, QtCore
import numpy as np

import matplotlib
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvas

from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from mpl_toolkits.basemap import Basemap

from tweepy import Stream, API

from data_analysis.auth import auth
from data_analysis._strip_listener import StripListener
from data_analysis._util import get_text_cleaned as _get_text_cleaned
from data_analysis._util import WorkerThread as _WorkerThread

from nltk.sentiment.vader import SentimentIntensityAnalyzer


class Language(QtCore.QObject):
    # FIXME: bad naming
    analysis_signal = QtCore.pyqtSignal(str, float, int)
    def __init__(self, get_iso):
        super().__init__()
        self._cache = {}
        self.get_iso = get_iso
        self._analyzer = SentimentIntensityAnalyzer()

    def store_tweet(self, coordinates, tweet):
        polarity = self._analyzer.polarity_scores(tweet)
        score = polarity['compound']
        if score != 0:
            iso = self.get_iso(coordinates)
            print(iso, score)
            if iso:
                self._store_score(iso, score)

    def _store_score(self, iso, score):
        try:
            value = self._cache[iso]
            value.append(score)
        except KeyError:
            value = [score,]
            self._cache[iso] = value

        if len(value) > 9 or not iso in _POP:
            self.analysis_signal.emit(iso,
                                      np.mean(value),
                                      len(value))

            self._cache.pop(iso)

    def process_tweet(self, id_, tweet_string):
        tokens = self.tokenizer.tokenize(tweet_string)

    def process_geo_tweets(self, tweets, iso):
        scores = []
        for tweet in tweets:
            text = _get_text_cleaned(tweet)
            polarity = self._analyzer.polarity_scores(text)
            scores.append(polarity['compound'])

        self.analysis_signal.emit(iso, np.mean(scores), len(scores))


class Twitter(QtCore.QObject):
    MAX_API_REQUESTS = 450
    def __init__(self, get_iso, listener=None, parent=None):
        """
        we're going to pass in get_iso directly because it
        makes more sense to have this as a blocking call.
        AKA: I want the information NAO.
        """
        super().__init__(parent)
        self.stream = Stream(auth, listener)
        self.api = API(auth)
        # can only request so much in a 15 min window
        self._language = Language(get_iso)
        self._requests = 0
        self._requests_time = time.time()
        # Don't want to instantiate a new thread everytime
        # So we're going to use a "thread pool"
        self._task_thread = Queue()
        self._worker_thread = _WorkerThread(self._task_thread)

        self.running = True
        self.country_list = []

    def get_tweets_from_location(self, latitude, longitude, radius, iso):
        searched_tweets = []
        last_id = -1
        max_tweets = 50
        while len(searched_tweets) < max_tweets:
            tweets = self.api.search(lang='en',
                                     result_type='recent',
                                     geocode=(latitude, longitude, radius))

            searched_tweets.extend(tweets)

        self._language.process_geo_tweets(tweets, iso)

    def start_filter(self, **kwargs):
        defaults = {'locations': [-180,-90,180,90],
                    'languages': ('en',)}

        defaults.update(kwargs)
        self.stream.filter(async=True, **kwargs)

    def special_loop(self):
        while self.running:
            # FIXME: filter isn't blocking. Duh.
            self.stream.filter(locations=,
                               languages=('en',),
                               async=True)

            # we're going to break here
            if self.country_list:
                values = self.country_list.pop()
                self._task_thread.put((self.get_tweets_from_location,
                                       values, {}))


def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()
    widget = SentimentMapWidget()
    main_window.setCentralWidget(widget)

    get_iso = widget.get_iso3
    # FIXME: needs access to the `Language` instance
    listener = StripListener(get_iso)
    listener.analysis_signal.connect(widget.analysis_slot)

    main_window.show()

    app.exec_()
    listener.running = False

_POP = ('USA', 'IND', 'PAK', 'PHL', 'NGA', 'GBR', 'DEU', 'CAN', 'FRA', 'AUT', 'ITA', 'BGD', 'EGY', 'THA', 'NLD', 'NPL', 'ZAF', 'POL', 'TUR', 'IRQ', 'CHN', 'BRA', 'SWE', 'KEN', 'CMR')

class SentimentMapWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._analysis_cache = {}
        self._figure = plt.Figure()
        self._figure.set_tight_layout(True)
        self._last_updated = time.time()

        self.axis = self._figure.add_subplot(111)
        self.map_ = self._setup_map(self.axis)

        self._canvas = FigureCanvas(self._figure)
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._canvas)

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

        dir_filepath = path.dirname(path.abspath(__file__))
        map_.drawmapboundary(color='#d3d3d3')

        # this is weird
        shapefile = path.join(dir_filepath, 'data', 'ne_10m_admin_0_countries')
        map_.readshapefile(shapefile, 'countries', color='black', linewidth=.2)

        self._cache = []
        self._cache_polygons = []

        for info, shape in zip(map_.countries_info, map_.countries):
            iso3 = info['ADM0_A3']
            if iso3 == 'ATA':
                continue
            shape = np.array(shape)
            polygon = Polygon(shape, True)
            patches = [polygon]
            self._cache.append((iso3, matplotlib.path.Path(shape)))

            patch_collection = PatchCollection(patches)
            self._cache_polygons.append((iso3, patch_collection))
            patch_collection.set_facecolor('#d3d3d3')
            axis.add_collection(patch_collection)
        
        return map_

    def analysis_slot(self, iso, value, count):
        try:
            result = self._analysis_cache[iso]
            result.append((value, count))
        except KeyError:
            self._analysis_cache[iso] = [(value, count),]

        time_ = time.time()
        if time_ - self._last_updated > 10:
            for analysis_iso, values in self._analysis_cache.items():
                # FIXME: Right now just grab last value
                # NOTE: not using the count
                color = plt.cm.bwr_r(values[-1][0])
                for cache_iso, patch in self._cache_polygons:
                    if cache_iso == analysis_iso:
                        patch.set_facecolor(color)

            self.update_canvas()
            self._last_updated = time_

    def geo_slot(self, coords, tweets):
        isos = []
        for coord in coords:
            isos.append(self.get_iso3(coord))

        for iso, tweet in zip(isos, tweets):
            if iso is None:
                continue


    def get_iso3(self, coordinates):
        points = self.map_(*coordinates)
        # don't ask questions
        points = (points,)
        result = None
        for iso, path in self._cache:
            if path.contains_points(points):
                result = iso
                break

        return result

    def update_canvas(self):
        self._canvas.draw()


if __name__ == '__main__':
    main()
