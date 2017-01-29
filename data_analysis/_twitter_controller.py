import json
from os import path
from queue import Queue

from PyQt5 import QtCore

import pandas as pd

from tweepy import Stream, StreamListener, API

from data_analysis.sentiment_widget import SentimentController
from data_analysis._util import WorkerThread
from data_analysis.auth import auth
from data_analysis._util import get_text_cleaned as _get_text_cleaned


class TwitterController(QtCore.QObject):
    def __init__(self, get_iso, parent=None):
        """
        we're going to pass in get_iso directly because it
        makes more sense to have it as a blocking call rather than passing it
        around
        """
        super().__init__(parent)
        self._sentiment_controller = SentimentController(get_iso)
        self._sentiment_listener = SentimentListener(self._sentiment_controller)
        self._geography_listener = GeographyListener()
        # Duck type our two signals on this class for easy access
        self.geography_signal = self._geography_listener.geography_signal
        self.sentiment_signal = self._sentiment_listener.sentiment_signal

        # Store our base filter kwargs
        self._base_filter_kwargs = {'locations': [-180, -90, 180, 90],
                                    'async': True}

        # Set the stream listeners manually
        self.stream = Stream(auth, None)
        self.api = API(auth)

        # Don't want to instantiate a new thread everytime
        # So we're going to use a "thread pool"
        self._task_thread = Queue()
        self._worker_thread = WorkerThread(self._task_thread,
                                           self._rate_errored_callback)

        directory = path.abspath(path.dirname(__file__))
        country_file = path.join(directory, 'data', 'country_radius_info.csv')
        self._country_info = pd.read_csv(country_file)

        self.running = True
        self.country_list = []

    def _rate_errored_callback(self):
        self.running = False
        kwargs = dict(**self._base_filter_kwargs, langauges=('en',))
        self._task_thread.put((self.stream.filter,
                               [],
                               kwargs))

    @property
    def running(self):
        return self.stream.running

    @running.setter
    def running(self, running):
        self.stream.running = running

    def get_tweets_from_location(self, latitude, longitude, radius, iso):
        geocode = '{},{},{}mi'.format(latitude, longitude, radius)
        tweets = self.api.search(lang='en',
                                 result_type='recent',
                                 geocode=geocode)

        if tweets:
            self._sentiment_controller.process_geo_tweets(tweets, iso)

    def start_twitter_loop(self):
        for index, data in self._country_info.iterrows():
            # lat, long, radius, iso
            values = (data.lat,
                      data.long,
                      data.radius,
                      data.ISO3166)

            self._task_thread.put((self.get_tweets_from_location,
                                   values, {}))

            # FIXME: hack
            if index > 100:
                self._rate_errored_callback()
                break

    def start_heat_map(self):
        self.running = False
        self.stream.listener = self._geography_listener
        self.stream.filter(**self._base_filter_kwargs)

    def start_sentiment_map(self):
        self.running = False
        self.stream.listener = self._sentiment_listener
        kwargs = dict(**self._base_filter_kwargs, languages=('en',))
        self.stream.filter(**kwargs)


class SentimentListener(StreamListener):
    """
    Just grabs coordinates and the text of the tweet
    """
    def __init__(self,
                 sentiment_controller: SentimentController):

        self._sentiment_controller = sentiment_controller 
        self.sentiment_signal = self._sentiment_controller.sentiment_signal
        self.running = True

    def on_data(self, data):
        data = json.loads(data)
        if 'in_reply_to_status_id' in data:
            if data['coordinates'] is not None:
                text = _get_text_cleaned(data)
                # Don't ask questions
                coords = data['coordinates']['coordinates']

                self._sentiment_controller.store_tweet(coords, text)

        if not self.running:
            return False

class _Signaler(QtCore.QObject):
    geography_signal = QtCore.pyqtSignal(list, list)

    def __init__(self, parent=None):
        super().__init__(parent)


class GeographyListener(StreamListener):
    def __init__(self, parent=None):
        super().__init__()
        self.signaler = _Signaler()
        self.geography_signal = self.signaler.geography_signal
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
