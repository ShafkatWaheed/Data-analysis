import re
import sys
import json
import time

from os import path

from PyQt5 import QtWidgets, QtCore
import numpy as np

import matplotlib
matplotlib.use('Qt5Agg')

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvas

from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
from mpl_toolkits.basemap import Basemap

from tweepy import Stream
from tweepy.streaming import StreamListener

from data_analysis.auth import auth

from nltk.sentiment.vader import SentimentIntensityAnalyzer


class Language(QtCore.QObject):
    # FIXME
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

    def get_cache_slot(self):
        pass

def _get_text_cleaned(tweet):
    text = tweet['text']
    
    slices = []
    #Strip out the urls.
    if 'urls' in tweet['entities']:
        for url in tweet['entities']['urls']:
            slices += [{'start': url['indices'][0], 'stop': url['indices'][1]}]
    
    #Strip out the hashtags.
    if 'hashtags' in tweet['entities']:
        for tag in tweet['entities']['hashtags']:
            slices += [{'start': tag['indices'][0], 'stop': tag['indices'][1]}]
    
    #Strip out the user mentions.
    if 'user_mentions' in tweet['entities']:
        for men in tweet['entities']['user_mentions']:
            slices += [{'start': men['indices'][0], 'stop': men['indices'][1]}]
    
    #Strip out the media.
    if 'media' in tweet['entities']:
        for med in tweet['entities']['media']:
            slices += [{'start': med['indices'][0], 'stop': med['indices'][1]}]
    
    #Strip out the symbols.
    if 'symbols' in tweet['entities']:
        for sym in tweet['entities']['symbols']:
            slices += [{'start': sym['indices'][0], 'stop': sym['indices'][1]}]
    
    # Sort the slices from highest start to lowest.
    slices = sorted(slices, key=lambda x: -x['start'])
    
    #No offsets, since we're sorted from highest to lowest.
    for s in slices:
        text = text[:s['start']] + text[s['stop']:]
        
    return text


class StripListener(StreamListener):
    def __init__(self, get_iso):
        self._language = Language(get_iso)
        self.analysis_signal = self._language.analysis_signal
        self.running = True

    def on_data(self, data):
        data = json.loads(data)
        if 'in_reply_to_status_id' in data:
            if data['coordinates'] is not None:
                text = _get_text_cleaned(data)
                # Don't ask questions
                coords = data['coordinates']['coordinates']

                self._language.store_tweet(coords, text)

        if not self.running:
            return False


def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()
    widget = SentimentMapWidget()
    get_iso = widget.get_iso3
    main_window.setCentralWidget(widget)

    listener = StripListener(get_iso)
    listener.analysis_signal.connect(widget.analysis_slot)
    stream = Stream(auth, listener)
    stream.filter(locations=[-180,-90,180,90], languages=('en',), async=True)

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
