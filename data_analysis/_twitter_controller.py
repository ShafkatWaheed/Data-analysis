import time
import json

from os import path
from queue import Queue
from collections import Counter

import numpy as np
import scipy.stats.distributions

from PyQt5 import QtCore
import pandas as pd

from tweepy import Stream, StreamListener, API

from data_analysis.auth import auth
from data_analysis._util import WorkerThread
from data_analysis.topic_tokenizer import TopicTokenizer, LDAModel
from data_analysis.sentiment_widget import SentimentController
from data_analysis._util import get_text_cleaned as _get_text_cleaned


class TwitterController(QtCore.QObject):
    def __init__(self, sentiment_map_widget, parent=None):
        super().__init__(parent)

        self._sentiment_controller = None
        self._setup_sentiment_controller(sentiment_map_widget)

        # Set the stream listeners manually
        self.stream = Stream(auth, None)
        self.api = API(auth)

        self._geography_listener = GeographyListener()
        self._sentiment_listener = SentimentListener(self._sentiment_controller)
        self._important_user_listener = GeographyListener(send_tweet_data=False)
        self._realtime_listener = TopicListener()

        self.geography_signal = None
        self.sentiment_signal = None
        self.important_user_signal = None
        self.realtime_signal = None

        # NOTE: helps reduce clutter/busy-ness of intializer
        self._setup_signal_helper()

        # Don't want to instantiate a new thread everytime
        # So we're going to use a "thread pool"
        self._task_thread = Queue()
        self._worker_thread = WorkerThread(self._task_thread,
                                           self._rate_errored_callback)

        # Store our base filter kwargs
        self._base_filter_kwargs = {'locations': _WORLDWIDE_COORDS,
                                    'async': True}

        self._country_info = None
        self._setup_country_info()

    def _setup_country_info(self):
        """
        Loads the country information from `country_radius_info.csv` into file
        """
        directory = path.abspath(path.dirname(__file__))
        country_file = path.join(directory, 'data', 'country_radius_info.csv')
        self._country_info = pd.read_csv(country_file)

    def _setup_sentiment_controller(self, sentiment_map_widget):
        map_ = sentiment_map_widget.map_
        iso_paths_list = sentiment_map_widget._cache_path
        self._sentiment_controller = SentimentController(map_, iso_paths_list)

    def _setup_signal_helper(self):
        """
        Duck types all of our signals onto our class
        """
        self.important_user_signal = self._important_user_listener.geography_signal
        self.geography_signal = self._geography_listener.geography_signal
        self.sentiment_signal = self._sentiment_listener.sentiment_signal
        self.realtime_signal = self._realtime_listener.count_signal
        self.topic_signal = self._realtime_listener.topic_signal

    def _rate_errored_callback(self):
        self.running = False
        kwargs = dict(**self._base_filter_kwargs, langauges=('en',))
        self._task_thread.put((self.stream.filter,
                               [],
                               kwargs))

    def __del__(self):
        self._geography_listener.running = False
        self._important_user_listener.running = False
        self._sentiment_listener.running = False
        self._realtime_listener.running = False

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

    def start_important_users_map(self):
        self.running = False
        self.stream.listener = self._important_user_listener
        self.stream.filter(**self._base_filter_kwargs)

    def start_realtime_widget(self):
        self.running = False
        self.stream.listener = self._realtime_listener
        self.stream.sample(async=True, languages=('en',))


class GeographyConvienceWrapper:
    """
    Convience class for recording/demonstration Geography purposes.
    """
    def __init__(self):
        self._geography_listener = GeographyListener()
        # Duck type our signal onto this class for easy access
        self.geography_signal = self._geography_listener.geography_signal
        self.geo_tweet_signal = self._geography_listener.geography_signal
        self.stream = Stream(auth, self._geography_listener)

    def start(self):
        self.stream.filter(locations=_WORLDWIDE_COORDS,
                           async=True)


class SentimentListener(StreamListener):
    """
    Just grabs coordinates and the text of the tweet
    """
    def __init__(self,
                 sentiment_controller: SentimentController):

        self._sentiment_controller = sentiment_controller
        self.sentiment_signal = self._sentiment_controller.sentiment_signal
        self.running = True

    def on_error(self, error):
        print('Error in Sentiment listener!', 'Twitter HTTP Error:', error)

    def on_data(self, data):
        data = json.loads(data)
        if 'in_reply_to_status_id' in data:
            if data['coordinates'] is not None:
                text = _get_text_cleaned(data)
                # coordinates are nested
                coords = data['coordinates']['coordinates']

                self._sentiment_controller.analyze_tweet_sentiment(coords, text)

        if not self.running:
            return False

class _Signaler(QtCore.QObject):
    geography_signal = QtCore.pyqtSignal(list, list)

    def __init__(self, parent=None):
        super().__init__(parent)


class GeographyListener(StreamListener):
    def __init__(self, send_tweet_data=True):
        """
        if `send_tweet_data` is False, will send user data instead.
        """
        super().__init__()
        self.signaler = _Signaler()
        self.geography_signal = self.signaler.geography_signal
        self._coord_cache = []
        self._tweet_cache = []
        self._user_cache = []
        self._send_tweet_data = send_tweet_data
        self.running = True

    def on_error(self, error):
        print('Error in Geography listener!', 'Twitter HTTP Error:', error)

    def on_data(self, data):
        if self._send_tweet_data:
            return super().on_data(data)

        data = json.loads(data)
        if 'in_reply_to_status_id' in data:
            return self._send_user_data_helper(data)

    def on_status(self, status):
        if status.coordinates is not None:
            self._coord_cache.append(status.coordinates['coordinates'])
            self._tweet_cache.append(status.text)
            if len(self._coord_cache) > 19:
                self.geography_signal.emit(self._coord_cache,
                                           self._tweet_cache)

                self._coord_cache = []
                self._tweet_cache = []

        if not self.running:
            return False

    def _send_user_data_helper(self, data):
        if data.get('coordinates', None):
            self._coord_cache.append(data['coordinates']['coordinates'])
            self._user_cache.append(data['user'])
            # Much, much less influential users
            if len(self._coord_cache) > 39:
                self.geography_signal.emit(self._coord_cache,
                                           self._user_cache)

                self._coord_cache = []
                self._user_cache = []

        if not self.running:
            return False

class SimplePoisson:
    def __init__(self, alpha=0):
        self.mean = None
        self.alpha = alpha
        self._last_count = None

    def get_effect_size(self, count):
        # First, calculate our relative confidence
        interval = scipy.stats.distributions.poisson.interval(self.alpha,
                                                              self.mean)

        delta_r = interval[1] - interval[0]
        relative_confidence = delta_r/self.mean

        # Second, our senstivity
        sensitivity = abs(count - self.mean)/self.mean
        # lastly, using those two measures, calculate our figure-of-merit
        eta = sensitivity/relative_confidence

        return eta


class _TopicListenerHelper(QtCore.QObject):
    """
    Translates between the Stream Listener and the Qt layer
    """
    count_signal = QtCore.pyqtSignal(int)
    topic_signal = QtCore.pyqtSignal(object, object)

    def __init__(self, listner):
        super().__init__(None)
        self._listener = listner
        self._count_timer = QtCore.QTimer()
        self._count_timer.setInterval(1000)
        self._count_timer.timeout.connect(self.counter_timeout)

        self._lda_timer = QtCore.QTimer()
        self._lda_timer.setInterval(60000)
        self._lda_timer.timeout.connect(self._lda_timeout)

        self._poisson = SimplePoisson()
        self._queue = Queue()
        self._worker = WorkerThread(self._queue)

    def _helper(self):
        token_list = [t for t in self._listener.lda_model.token_list if t]
        topic_numbers = self._listener.lda_model.train_model(token_list)
        counter = np.array(Counter(topic_numbers).most_common())
        keys = counter[:, 0]
        values = counter[:, 1]
        num_topics = 10
        topic_key_words = self._listener.lda_model.get_vocabulary_helper(keys[:num_topics])
        topic_key_words = [' '.join(word) for word in topic_key_words]
        values = values[:num_topics]
        self.topic_signal.emit(topic_key_words, values)

    def _lda_timeout(self):
        # Get rid of empty lists

        if self._lda_timer.timeout == 60000:
            self._lda_timer.setInterval(180000)
            self._listener.lda_model.set_number_topics(100)
        else:
            # self._listener.lda_model.token_list = []
            pass

        self._queue.put((self._helper, (), {}))


    def start_timer(self):
        self._count_timer.start()
        self._lda_timer.start()

    def counter_timeout(self):
        count = self._listener.count
        self._listener.count = 0
        # print(self._listener._token_counter.most_common(100))
        self.count_signal.emit(count)

    def emit_topics(self, topics):
        pass


class TopicListener(StreamListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = 0
        self.running = True


        self._helper = _TopicListenerHelper(self)
        # Get our two signals
        self.count_signal = self._helper.count_signal
        self.topic_signal = self._helper.topic_signal

        self._helper.start_timer()

        self.lda_model = LDAModel(n_topics=100)
        self._tokenizer = TopicTokenizer()

    def on_error(self, error):
        print('Error in topic listener!', 'Twitter HTTP Error:', error)

    def on_data(self, data):
        data = json.loads(data)
        if 'in_reply_to_status_id' in data:
            # store count
            self.count += 1
            # Get text
            text = data['text']
            # get tokens from text
            tokens = self._tokenizer.tokenize(text)
            # store tokens
            self.lda_model.token_list.append(tokens)

            """
            hashtags = data['entities']['hashtags']
            for hashtag in hashtags:
                hashtag = hashtag['text']
                self._hashtag_counter.update((hashtag,))
            """

        return self.running


_WORLDWIDE_COORDS = (-180, -90, 180, 90)
# NOTE: classes are identical
SentimentConvienceWrapper = GeographyConvienceWrapper
