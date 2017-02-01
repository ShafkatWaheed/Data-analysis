import sys
from os import path
from queue import Queue

from PyQt5 import QtWidgets, QtCore

import pandas as pd

from data_analysis.heat_map_widget import HeatMapWidget
from data_analysis.sentiment_widget import SentimentMapWidget
from data_analysis._twitter_controller import TwitterController


def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()

    tab_widget = StreamSwitchTab()
    country_progress_signal = tab_widget._sentiment_map_widget.country_progress
    progress_bar, progress_bar_function = _add_progress_bar(main_window,
                                                            country_progress_signal)

    tab_widget.progress_bar_signal.connect(progress_bar_function)
    tab_widget.set_progress_bar_function(progress_bar_function)

    progress_bar_closure = remove_progress_bar(main_window, progress_bar)
    tab_widget.remove_progress_bar.connect(progress_bar_closure)

    main_window.setCentralWidget(tab_widget)
    main_window.show()
    try:
        app.exec_()
    except KeyboardInterrupt:
        pass

    tab_widget.twitter_controller.running = False


class StreamSwitchTab(QtWidgets.QTabWidget):
    remove_progress_bar = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Create our two widgets
        self._heat_map_widget = HeatMapWidget()
        self._sentiment_map_widget = SentimentMapWidget()
        # Add the two widgets and store the index for later comparison
        self.heat_map = self.addTab(self._heat_map_widget, 'Heat Map')
        self.sentiment_map = self.addTab(self._sentiment_map_widget, 'Sentiment Map')

        # Create twitter controller
        self.twitter_controller = TwitterController(self._sentiment_map_widget)

        geography_slot = self._heat_map_widget.geography_slot
        self.twitter_controller.geography_signal.connect(geography_slot)

        sentiment_slot = self._sentiment_map_widget.sentiment_slot
        self.twitter_controller.sentiment_signal.connect(sentiment_slot)

        self.twitter_controller.start_heat_map()
        self._sentiment_map_loaded = False
        self._sentimet_thread = TabThread(self)
        # Duck type "Quack Quack"
        self.progress_bar_signal = self._sentimet_thread.progress_bar_signal
        self.currentChanged.connect(self._current_changed_slot)
        # TODO: Either this or put a check if for the path cache
        # Can't start the sentminent map until we have all of the map
        self.remove_progress_bar.connect(self.twitter_controller.start_sentiment_map)

    def set_progress_bar_function(self, func):
        self._sentimet_thread.progress_bar_function = func

    def _current_changed_slot(self, index):
        if not self._sentiment_map_loaded:
            self._sentimet_thread.start()
            self._sentiment_map_loaded = True
            return

        if index == self.heat_map:
            self.twitter_controller.start_heat_map()
        elif index == self.sentiment_map:
            self.twitter_controller.start_sentiment_map()



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


def _add_progress_bar(qmainwindow, progress_signal):
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


if __name__ == '__main__':
    main()
