import sys
from PyQt5 import QtWidgets, QtCore

from data_analysis.heat_map_widget import HeatMapWidget
from data_analysis.sentiment_widget import SentimentMapWidget
from data_analysis.realtime_graph_widget import RealTimeGraphWidget
from data_analysis._twitter_controller import TwitterController
from data_analysis._util import (add_progress_bar,
                                 remove_progress_bar,
                                 TabThread)


def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()

    tab_widget = StreamSwitchTab()
    main_window.setCentralWidget(tab_widget)

    _setup_progress_bar_helper(main_window, tab_widget)

    main_window.show()
    try:
        app.exec_()
    except KeyboardInterrupt:
        pass

    tab_widget.twitter_controller.__del__()


class StreamSwitchTab(QtWidgets.QTabWidget):
    remove_progress_bar = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self._realtime_graph = RealTimeGraphWidget()
        self._heat_map_widget = HeatMapWidget()
        self._influential_user_widget = HeatMapWidget()
        self._sentiment_map_widget = SentimentMapWidget(draw_map=False)

        self.heat_map_index = None
        self.influential_user_index = None
        self.sentiment_map_index = None
        self.realtime_graph_index = None
        self._sentiment_map_loaded = False

        self.twitter_controller = TwitterController(self._sentiment_map_widget)
        self.twitter_controller.start_realtime_widget()
        self._sentimet_thread = TabThread(self)

        self._add_tabs_helper()
        self._setup_signals_and_slots_helper()

    def _add_tabs_helper(self):
        self.realtime_graph_index = self.addTab(self._realtime_graph,
                                                'Velocity')

        self.heat_map_index = self.addTab(self._heat_map_widget,
                                          'Heat Map Widget')

        self.influential_user_index = self.addTab(self._influential_user_widget,
                                                  'Influential User Heat Map')

        self.sentiment_map_index = self.addTab(self._sentiment_map_widget,
                                               'Sentiment Map')


    def _setup_signals_and_slots_helper(self):
        realtime_slot = self._realtime_graph.count_data_slot
        self.twitter_controller.realtime_signal.connect(realtime_slot)

        geography_slot = self._heat_map_widget.geography_slot
        self.twitter_controller.geography_signal.connect(geography_slot)

        sentiment_slot = self._sentiment_map_widget.sentiment_slot
        self.twitter_controller.sentiment_signal.connect(sentiment_slot)

        influential_slot = self._influential_user_widget.influential_users_slot
        self.twitter_controller.important_user_signal.connect(influential_slot)

        self.progress_bar_signal = self._sentimet_thread.progress_bar_signal
        self.currentChanged.connect(self._tab_changed_slot)

        # NOTE: This is a bad way to signal. The `_tab_changed_slot` checks
        # to see if the map is loaded. If it's not, it triggers the map to start loading.
        # Once the map is loaded, the `remove_progress_bar` emits to the `start_sentiment_map`
        # signal, effectively starting everything from another thread. This is likely buggy
        # and undoubtly has a race condition.
        self.remove_progress_bar.connect(self.twitter_controller.start_sentiment_map)

    def _tab_changed_slot(self, index):
        if index == self.heat_map_index:
            self.twitter_controller.start_heat_map()
        elif index == self.realtime_graph_index:
            self.twitter_controller.start_realtime_widget()
        elif index == self.influential_user_index:
            self.twitter_controller.start_important_users_map()
        elif index == self.sentiment_map_index:
            # NOTE: see NOTE on line 63 of this file.
            if not self._sentiment_map_loaded:
                self._sentimet_thread.start()
                self._sentiment_map_loaded = True
                return

            self.twitter_controller.start_sentiment_map()

    def set_progress_bar_function(self, func):
        self._sentimet_thread.progress_bar_function = func


def _setup_progress_bar_helper(main_window, tab_widget):
    country_progress_signal = tab_widget._sentiment_map_widget.country_progress
    progress_bar, progress_bar_function = add_progress_bar(main_window,
                                                           country_progress_signal)

    tab_widget.progress_bar_signal.connect(progress_bar_function)
    tab_widget.set_progress_bar_function(progress_bar_function)

    progress_bar_closure = remove_progress_bar(main_window, progress_bar)
    tab_widget.remove_progress_bar.connect(progress_bar_closure)


if __name__ == '__main__':
    main()
