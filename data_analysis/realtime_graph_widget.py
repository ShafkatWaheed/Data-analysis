import time
import json
from collections import Counter


from PyQt5 import QtCore, QtChart, QtGui
import nltk
from tweepy import StreamListener, Stream

from data_analysis.auth import auth
from data_analysis.topic_tokenizer import TopicTokenizer

class _Helper(QtCore.QObject):
    """
    Translates between the Stream Listener and the Qt layer
    """
    # FIXME
    count_signal = QtCore.pyqtSignal(int, int, int)
    def __init__(self, listner):
        super().__init__(None)
        self._listener = listner
        self._timer = QtCore.QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.handle_timeout)
        # FIXME
        self._total_count = 0

    def start_timer(self):
        self._timer.start()

    def handle_timeout(self):
        count = self._listener.count
        self._total_count += count
        self._listener.count = 0
        love_count = self._listener._token_counter.get('love', 0)
        like_count = self._listener._token_counter.get('like', 0)
        print(self._listener._hashtag_counter.most_common(20))
        self.count_signal.emit(count, love_count, like_count)
        self._listener._token_counter['love'] = 0
        self._listener._token_counter['like'] = 0
        # self._listener._token_counter.clear()


class TimerListener(StreamListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.count = 0
        self._helper = _Helper(self)
        self.count_signal = self._helper.count_signal
        self._helper.start_timer()
        self.running = True
        self._tokenizer = TopicTokenizer()
        self._token_counter = Counter()
        self._hashtag_counter = Counter()

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
            self._token_counter.update(tokens)
            hashtags = data['entities']['hashtags']
            for hashtag in hashtags:
                hashtag = hashtag['text']
                self._hashtag_counter.update((hashtag,))

        return self.running

class GraphWidget(QtChart.QChartView):
    EPOCH = QtCore.QDateTime(1969, 12, 31, 17, 0)

    def __init__(self, color='blue', parent=None):
        super().__init__(parent)
        self.chart = QtChart.QChart()
        self.setChart(self.chart)
        self.setRenderHint(QtGui.QPainter.Antialiasing)

        self.x_axis = QtChart.QDateTimeAxis()
        # self.x_axis.setFormat('hh mm ss')
        self.x_axis.setFormat('mm:ss')
        # self.x_axis = QtChart.QValueAxis()
        self.x_axis.setTitleText('Time')
        self.x_axis.setTickCount(5)
        self.y_axis = QtChart.QValueAxis()
        self.y_axis.setTitleText('Count')
        self.y_axis.setRange(0, 75)
        self.y_axis.setTickCount(6)

        self.series = QtChart.QSplineSeries()
        self.series.setName('Count')

        self.love_series = QtChart.QSplineSeries()
        self.love_series.setName('Love Count')

        self.like_series = QtChart.QSplineSeries()
        self.like_series.setName('Like Count')

        self._series = [self.series, self.love_series, self.like_series]

        for series in self._series:
            self.chart.addSeries(series)

        # self.series = QtChart.QScatterSeries()

        self.chart.addAxis(self.x_axis, QtCore.Qt.AlignBottom)
        self.chart.addAxis(self.y_axis, QtCore.Qt.AlignLeft)
        for series in self._series:
            series.setUseOpenGL(True)
            series.attachAxis(self.x_axis)
            series.attachAxis(self.y_axis)

        self._max_count = 75

        self._setup_pen(color)

        self._timer_listener = TimerListener()
        self.twitter_access = Stream(auth, self._timer_listener)
        self._timer_listener.count_signal.connect(self.handle_timeout)
        self._old_time = None
        self._scroll = self.chart.plotArea().width() / self.x_axis.tickCount()

    def __del__(self):
        self._timer_listener.running = False

    def start_recording(self):
        self.twitter_access.sample(async=True, languages=('en',))

    def handle_timeout(self, count, love_count, like_count):
        if count == 0 and love_count == 0:
            return

        if count > self._max_count:
            self._max_count = count
            self.y_axis.setRange(0, self._max_count)
        time_ = QtCore.QDateTime.currentDateTime().toMSecsSinceEpoch()
        if self.x_axis.min() == self.EPOCH:
            current_time = QtCore.QDateTime.currentDateTime()
            self.x_axis.setRange(current_time, current_time.addSecs(60))
            self._old_time = self.x_axis.max().toMSecsSinceEpoch()
        if time_ > self._old_time:
            self.chart.scroll(self._scroll, 0)
            self._old_time = self.x_axis.max().toMSecsSinceEpoch()
        self.series.append(time_, count)
        self.love_series.append(time_, love_count)
        self.like_series.append(time_, like_count)

    def _setup_pen(self, color=None):
        pen = self.series.pen()
        if color is not None:
            pen.setColor(QtGui.QColor(color))
        pen.setWidth(3)
        self.series.setPen(pen)

    def append_data(self, xdata, ydata):
        self.series.append(xdata, ydata)
