import sys
from PyQt5 import QtWidgets

from data_analysis.realtime_graph_widget import GraphWidget

def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()

    tab_widget = StreamSwitchTab()
    main_window.setCentralWidget(tab_widget)
    main_window.show()
    try:
        app.exec_()
    except KeyboardInterrupt:
        pass

class StreamSwitchTab(QtWidgets.QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        graph = GraphWidget()
        self.addTab(graph, 'Velocity')
        graph.start_recording()

if __name__ == '__main__':
    main()
