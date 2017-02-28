import time

from PyQt5 import QtCore, QtChart, QtGui, QtWidgets
import matplotlib
matplotlib.use('Qt5Agg')

from matplotlib.backends.backend_qt5agg import FigureCanvas
import matplotlib.pyplot as plt


class RealTimeGraphWidget(QtChart.QChartView):
    EPOCH = QtCore.QDateTime(1969, 12, 31, 17, 0)

    def __init__(self, color='blue', parent=None):
        super().__init__(parent)
        self.x_axis = None
        self.y_axis = None
        self._old_time = None
        self._max_count = 50

        self.chart = QtChart.QChart()
        self.setChart(self.chart)
        self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.tweet_count_series = QtChart.QSplineSeries()
        self.tweet_count_series.setName('Tweet count')
        self._series = [self.tweet_count_series,]

        self._setup_axi()
        self.chart.addSeries(self.tweet_count_series)

        self.chart.addAxis(self.x_axis, QtCore.Qt.AlignBottom)
        self.chart.addAxis(self.y_axis, QtCore.Qt.AlignLeft)

        self._setup_series()
        self._setup_pen(color)

        self._scroll = self.chart.plotArea().width() / self.x_axis.tickCount()

    def append_data(self, xdata, ydata):
        self.tweet_count_series.append(xdata, ydata)

    def count_data_slot(self, count):
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
            self.chart.scroll(self._scroll, 0)
            self._old_time = self.x_axis.max().toMSecsSinceEpoch()
        self.tweet_count_series.append(time_, count)

    def _setup_pen(self, color=None):
        pen = self.tweet_count_series.pen()
        if color is not None:
            pen.setColor(QtGui.QColor(color))
        pen.setWidth(3)
        self.tweet_count_series.setPen(pen)

    def _setup_series(self, series=None):
        """
        Use OpenGl and attach the axi
        """
        if series is None:
            series = self._series

        for s in series:
            s.setUseOpenGL(True)
            s.attachAxis(self.x_axis)
            s.attachAxis(self.y_axis)

    def _setup_axi(self):
        """
        Creates and formats the x and y axis
        """
        self.x_axis = QtChart.QDateTimeAxis()
        self.x_axis.setFormat('mm:ss')
        self.x_axis.setTitleText('Time')
        self.x_axis.setTickCount(5)

        self.y_axis = QtChart.QValueAxis()
        self.y_axis.setTitleText('Count')
        self.y_axis.setRange(0, self._max_count)
        self.y_axis.setTickCount(6)


class TopicWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._figure = plt.Figure()
        self._figure.set_tight_layout(True)

        self.axis = self._figure.add_subplot(111)
        self._canvas = FigureCanvas(self._figure)

        self._realtime_widget = RealTimeGraphWidget()

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._canvas)
        layout.addWidget(self._realtime_widget)

    def _setup_axis(self):
        pass

    def graph_topics(self, topics, probabilities):
        pass

    def update_canvas(self):
        self._canvas.draw()
