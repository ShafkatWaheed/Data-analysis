import time

from os import path

from PyQt5 import QtWidgets, QtCore
import numpy as np
import pandas as pd

import matplotlib

from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

from data_analysis.map_widget import MapWidget, plt
from data_analysis._util import get_text_cleaned as _get_text_cleaned
from data_analysis._util import WorkerThread as _WorkerThread

from nltk.sentiment.vader import SentimentIntensityAnalyzer


class SentimentController(QtCore.QObject):
    sentiment_signal = QtCore.pyqtSignal(str, float, int)

    def __init__(self, map_, iso_path_list):
        super().__init__()
        self._cache = {}
        self._analyzer = SentimentIntensityAnalyzer()
        self._map_ = map_
        self._paths = iso_path_list

    def store_tweet(self, coordinates, tweet):
        polarity = self._analyzer.polarity_scores(tweet)
        score = polarity['compound']
        if score != 0:
            iso = self.get_iso(coordinates)
            # print(iso, score)
            if iso:
                self._store_score(iso, score)

    def _store_score(self, iso, score):
        try:
            value = self._cache[iso]
            value.append(score)
        except KeyError:
            value = [score, ]
            self._cache[iso] = value

        if len(value) > 9 or iso not in _POP:
            self.sentiment_signal.emit(iso,
                                       np.mean(value),
                                       len(value))
           
            # NOTE: Fixes race condition
            try:
                self._cache.pop(iso)
            except KeyError:
                pass

    def get_iso3(self, coordinates):
        points = self._map_(*coordinates)
        # don't ask questions
        points = (points,)
        result = None
        for iso, path in self._paths:
            if path.contains_points(points):
                result = iso
                break

        return result

    def process_geo_tweets(self, tweets, iso):
        scores = []
        for tweet in tweets:
            text = _get_text_cleaned(tweet._json)
            polarity = self._analyzer.polarity_scores(text)
            scores.append(polarity['compound'])

        self.sentiment_signal.emit(iso, np.mean(scores), len(scores))


# NOTE: Largest english population. Used to decide if keep incoming values in
# small cache or not
_POP = ('USA', 'IND', 'PAK', 'PHL', 'NGA', 'GBR', 'DEU', 'CAN', 'FRA', 'AUT',
        'ITA', 'BGD', 'EGY', 'THA', 'NLD', 'NPL', 'ZAF', 'POL', 'TUR', 'IRQ',
        'CHN', 'BRA', 'SWE', 'KEN', 'CMR')


class SentimentMapWidget(MapWidget):
    """
    Colors countries red or blue according to their average sentiment score
    """
    # NOTE: `country_progress` used to update the progress bar while loading
    country_progress = QtCore.pyqtSignal(int)
    # NOTE: `add_count_signal` used to keep track of tweets analyzed
    add_count_signal = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        # base class contains a lot of the map logic!
        super().__init__(parent)
        # stores the ISO name and the aggregate sentiment logic
        self._sentiment_cache = {}
        # matplotlib wasn't made to do real time analytics, so we'll limit
        # updates to hack around this
        self._last_updated = time.time()
        # connect the count to the counter
        self.add_count_signal.connect(self.counter_widget.add_to_count)

    def _detailed_map_setup(self):
        """
        Loads the shapefile from the files, stores country information and
        geometery for determing which country a tweet falls in and coloring
        that country according to the analyzed sentiment.

        Also ticks the progress bar as the countries are loaded.
        """
        # Get the shapefile path name
        dir_filepath = path.dirname(path.abspath(__file__))
        shapefile = path.join(dir_filepath, 'data', 'ne_10m_admin_0_countries')

        # Draw the outer map
        self.map_.drawmapboundary(color='#d3d3d3')
        # read in the shapefile
        self.map_.readshapefile(shapefile, 'countries', color='black', linewidth=.2)

        # store the (iso_name, path) for determining which country tweet is in
        # using the `contains_points` method
        self._cache_path = []
        # store the (iso_name, patch) for coloring using `set_facecolor` method
        self._cache_patches = []

        # iterate over the country info and shape info. Use `index` to record
        # loading progress
        for index, (info, shape) in enumerate(zip(self.map_.countries_info,
                                                  self.map_.countries)):

            # `iso3` is a 3 letter country code
            iso3 = info['ADM0_A3']
            # don't map the antartic
            if iso3 == 'ATA':
                continue
            # convert shape to numpy array for use with basemap
            shape = np.array(shape)
            # basemap/matplotlib specific data wrangling
            polygon = Polygon(shape, True)
            patches = [polygon]
            # store the (iso_name, path) in cache. Will use `contains_points`
            # method to later determine in which country tweets fall
            self._cache_path.append((iso3, matplotlib.path.Path(shape)))

            # basemap/matplotlib specific data wrangling
            patch_collection = PatchCollection(patches)
            # store the (iso_name, patch_collection) to change the country
            # color
            self._cache_patches.append((iso3, patch_collection))
            # Set default country facecolor to be gray.
            patch_collection.set_facecolor('#d3d3d3')
            # basemap/matplotlib specific data wrangling
            self.axis.add_collection(patch_collection)

            # There's ~4268 items. 1/100 or one tick mark is every 42 paces
            if index % 42 == 0:
                self.country_progress.emit(index)

    def sentiment_slot(self, iso: str, average_sentiment: float, count: int):
        """
        `iso` is a 3 digit country code.
        `average_sentiment` is the average sentiment value, value between (-1, +1)
        `count` is the count of observations that make up the average_sentiment
        """
        try:
            # get the old value
            result = self._sentiment_cache[iso]
            # get the old count
            old_count = result[1]
            # add the total count
            total_count = old_count + count
            old_total_value = result[0] * old_count
            new_average = (old_total_value + average_sentiment*count)/total_count
            self._sentiment_cache[iso] = (new_average, total_count)
        except KeyError:
            self._sentiment_cache[iso] = (average_sentiment, count)

        self.add_count_signal.emit(count)

        time_ = time.time()
        # If it's been more than 10 seconds...
        if time_ - self._last_updated > 10:
            # for each item in the sentiment cache...
            for analysis_iso, values in self._sentiment_cache.items():
                # get the corresponding color for the sentiment value...
                color = plt.cm.bwr(values[0])
                # countries are made up of many patches, and we want to color them all...
                for cache_iso, patch in self._cache_patches:
                    # If the countries match...
                    if cache_iso == analysis_iso:
                        # color the patch
                        patch.set_facecolor(color)

            self.update_canvas()
            self._last_updated = time_

