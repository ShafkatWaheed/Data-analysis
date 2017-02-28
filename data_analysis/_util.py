import array
from threading import Thread
from collections import defaultdict
import numpy as np
import scipy.sparse

from tweepy.error import RateLimitError
from PyQt5 import QtWidgets, QtCore


def get_text_cleaned(tweet):
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


def make_document_term_matrix(token_list):
    """Function for creating a document term matrix. Taken from SciKit-Learn"""
    vocabulary = defaultdict()
    vocabulary.default_factory = vocabulary.__len__
    j_indices = []
    """Construct an array.array of a type suitable for scipy.sparse indices."""
    indptr = array.array(str("i"))
    values = array.array(str("i"))
    indptr.append(0)

    for tokens in token_list:
        feature_counter = {}
        for token in tokens:
            feature_idx = vocabulary[token]
            if feature_idx not in feature_counter:
                feature_counter[feature_idx] = 1
            else:
                feature_counter[feature_idx] += 1
        j_indices.extend(feature_counter.keys())
        values.extend(feature_counter.values())
        indptr.append(len(j_indices))

    vocabulary = dict(vocabulary)
    j_indices = np.asarray(j_indices, dtype=np.intc)
    indptr = np.frombuffer(indptr, dtype=np.intc)
    values = np.frombuffer(values, dtype=np.intc)

    X = scipy.sparse.csr_matrix((values, j_indices, indptr),
                       shape=(len(indptr) - 1, len(vocabulary)),
                       dtype=np.int64)
    X.sort_indices()
    return vocabulary, X


class WorkerThread(Thread):
    """
    A simple thread to be used in a thread pool
    """
    def __init__(self,
                 task: 'queue.Queue',
                 fallback_call=None):
        super().__init__()
        self.task = task
        self.daemon = True
        self.fallback_call = fallback_call
        self.start()

    def run(self):
        while True:
            func, args, kwargs = self.task.get()
            try:
                func(*args, **kwargs)
            except RateLimitError:
                with self.task.mutex:
                    self.task.queue.clear()
                print('Twitter Rate limit reached!')
                if self.fallback_call:
                    self.fallback_call()

            except Exception as e:
                print(e)
            finally:
                self.task.task_done()


def add_progress_bar(qmainwindow, progress_signal):
    status = qmainwindow.statusBar()
    progress_bar = QtWidgets.QProgressBar()
    def inner():
        progress_bar.setMinimum(0)
        # 4268 iterations
        progress_bar.setMaximum(4268)
        progress_signal.connect(progress_bar.setValue)

        status.addWidget(progress_bar, 0)
    return progress_bar, inner


def remove_progress_bar(qmainwindow, progress_bar):
    def inner():
        status = qmainwindow.statusBar()
        status.removeWidget(progress_bar)
    return inner


class TabThread(QtCore.QThread):
    """
    Responsible for uploading the map data and keeping track of progress
    """
    progress_bar_signal = QtCore.pyqtSignal()
    def __init__(self, tab_widget, parent=None):
        super().__init__(parent)
        self._tab_widget = tab_widget

    def run(self):
        self.progress_bar_signal.emit()
        sentiment_widget = self._tab_widget._sentiment_map_widget
        sentiment_widget._detailed_map_setup()
        sentiment_widget.update_canvas()
        self._tab_widget.remove_progress_bar.emit()
