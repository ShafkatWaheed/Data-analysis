import sys
import time

import numpy as np
from PyQt5 import QtWidgets, QtCore

from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavToolbar

import matplotlib.pyplot as plt

def main():
    app = QtWidgets.QApplication(sys.argv)
    main_window = QtWidgets.QMainWindow()
    main_window.setWindowTitle('Matplotlib Example')

    central_widget = TabWidget()

    main_window.setCentralWidget(central_widget)

    main_window.show()
    app.exec_()


class TabWidget(QtWidgets.QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        xy_scatter_widget = XYScatterGraphWidget()
        pie_widget = PieGraphWidget()
        bar_widget = BarGraphWidget()
        graph_widget = GraphWidget()

        self.addTab(graph_widget, 'Graph Widget')
        self.addTab(bar_widget, 'Bar Graph')
        self.addTab(xy_scatter_widget, 'Scatter Graph')
        self.addTab(pie_widget, 'Pie Graph')


class GraphWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._figure = plt.Figure()

        # Widget!
        self._canvas = FigureCanvas(self._figure)
        # widget!
        toolbar = NavToolbar(self._canvas, self)
        # Widget!
        plot_button = QtWidgets.QPushButton('Plot!')
        plot_button.clicked.connect(self.plot)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(self._canvas)
        layout.addWidget(plot_button)

        self.setLayout(layout)
        self.plot()

    """
        self.random_signal.connect(self.random_slot)
        self.random_signal.emit('hello', 5, False)

    random_signal = QtCore.pyqtSignal(str, int, bool)

    # you can add decorator in, but it's optional
    @QtCore.pyqtSlot(str, int, bool)
    def random_slot(self, string, integer, boolean, *args, **kwargs):
        print(string, integer, boolean)
    """

    def plot(self):
        data = np.random.rand(20)
        ax = self._figure.add_subplot(111)
        ax.set_yscale('log')
        ax.set_xlim(-1, 6)
        ax.set_ylim(-1, 3)
        ax.set_xlabel('This is an x label')
        ax.set_ylabel('Set a Y label')
        ax.legend()
        ax.set_title('A really cool default chart')

        ax.plot(data, '*-', label=time.time())
        self.update_canvas()

    def update_canvas(self):
        self._canvas.draw()


class XYScatterGraphWidget(GraphWidget):
    def plot(self):
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        n = 100
        x = np.random.rand(n)
        y = np.random.rand(n)
        colors = np.random.rand(n)
        area = np.pi * (15 * np.random.rand(n))**2
        ax.scatter(x, y, s=area, c=colors, alpha=0.5)
        self.update_canvas()

class PieGraphWidget(GraphWidget):
    def plot(self):
        labels = ['Eaten', 'Uneaten', 'Eat next']
        n = len(labels)
        data = np.random.rand(n) * 100
        # control how the percentages are displayed
        autopct = '%1.1f%%'
        # colors = ['r', 'g', 'b']
        explode = np.zeros(n)
        explode[-1] = 0.1

        self._figure.clear()

        ax = self._figure.add_subplot(111)
        ax.pie(data, explode=explode, labels=labels, 
               autopct=autopct, shadow=True, startangle=90)

        self.update_canvas()

class BarGraphWidget(GraphWidget):
    def plot(self):
        self._figure.clear()
        n = 10
        y = np.random.rand(n) * 100
        x = range(n)
        width = 1/1.5
        ax = self._figure.add_subplot(111)
        ax.bar(x, y, width, color='blue')
        self.update_canvas()

if __name__ == '__main__':
    main()
