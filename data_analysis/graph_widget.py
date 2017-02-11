import time
import json


from PyQt5 import QtCore, QtChart, QtGui
import nltk
from tweepy import StreamListener, Stream

from data_analysis.auth import auth
from data_analysis.sentiment_model import CustomTokenizer

class _Helper(QtCore.QObject):
    count_signal = QtCore.pyqtSignal(int)
    def __init__(self, listner):
        super().__init__(None)
        self._listener = listner
        self._timer = QtCore.QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self.handle_timeout)

    def start_timer(self):
        self._timer.start()

    def handle_timeout(self):
        count = self._listener._count
        self._listener._count = 0
        self.count_signal.emit(count)


class TimerListener(StreamListener):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._count = 0
        self._helper = _Helper(self)
        self.count_signal = self._helper.count_signal
        self._helper.start_timer()
        self.running = True
        self._tokenizer = CustomTokenizer()

    def on_data(self, data):
        data = json.loads(data)
        if 'in_reply_to_status_id' in data:
            self._count += 1
            text = data['text']
            print(tuple(nltk.bigrams(self._tokenizer.tokenize(text))))

        return self.running

class GraphWidget(QtChart.QChartView):
    def __init__(self, color='blue', parent=None):
        super().__init__(parent)
        self.chart = QtChart.QChart()
        self.setChart(self.chart)
        self.setRenderHint(QtGui.QPainter.Antialiasing)

        self.x_axis = QtChart.QDateTimeAxis()
        self.x_axis.setFormat('hh mm ss')
        # self.x_axis = QtChart.QValueAxis()
        self.x_axis.setTitleText('Time')
        self.x_axis.setTickCount(6)
        self.y_axis = QtChart.QValueAxis()
        self.y_axis.setTitleText('Count')
        self.y_axis.setRange(0, 75)

        self.series = QtChart.QSplineSeries()
        # self.series = QtChart.QScatterSeries()
        self.chart.addSeries(self.series)

        self.chart.addAxis(self.x_axis, QtCore.Qt.AlignBottom)
        self.chart.addAxis(self.y_axis, QtCore.Qt.AlignLeft)

        self.series.setUseOpenGL(True)
        self.series.attachAxis(self.x_axis)
        self.series.attachAxis(self.y_axis)
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
    EPOCH = QtCore.QDateTime(1969, 12, 31, 17, 0)
    def handle_timeout(self, count):
        if count == 0:
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
            print(time_, self._old_time, self._scroll)
            self.chart.scroll(self._scroll, 0)
            self._old_time = self.x_axis.max().toMSecsSinceEpoch()
        print(time_, count)
        self.series.append(time_, count)

    def _setup_pen(self, color=None):
        pen = self.series.pen()
        if color is not None:
            pen.setColor(QtGui.QColor(color))
        pen.setWidth(3)
        self.series.setPen(pen)

    def append_data(self, xdata, ydata):
        self.series.append(xdata, ydata)
