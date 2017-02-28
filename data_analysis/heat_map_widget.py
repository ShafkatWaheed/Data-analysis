import logging
from PyQt5 import QtWidgets, QtCore

import numpy as np
import scipy.spatial

from data_analysis.map_widget import MapWidget, plt


class HeatMapWidget(MapWidget):
    count_signal = QtCore.pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._draw_map()
        self._count = 0
        self._x_coords = []
        self._y_coords = []
        self._old_x = np.array([])
        self._old_y = np.array([])
        self._last_redraw = 0
        self._redraw_number = 100

        # users.log_followers, users.log_friends, users.log_listed
        self._centroids = [[4.07902064,  3.77380017, 1.95112355],
                           [ 2.92786075, 2.43917913, 0.48547647]]

        # NOTE: see `data_analysis.map_widget.CounterWidget` for source
        self.count_signal.connect(self.counter_widget.set_count)

    def _draw_map(self):
        self.map_.drawcoastlines(color='grey')

    def _get_distances_helper(self, user):
        point = np.log([user['followers_count'],
                        user['friends_count'],
                        user['listed_count']])

        # Get rid of all negative infities
        point = [x if x != -np.inf else 0 for x in point]
        # `cdist` expects an array of arrays
        point = (point,)

        # calculate and return distances
        return scipy.spatial.distance.cdist(self._centroids, point)

    def influential_users_slot(self, coords, users):
        """
        plots only the influntial users.
        """
        influential_coordinates = []

        for index, user in enumerate(users):
            # Get the distance from the influential and uninfluential centroid
            influential_dist, uninfluential_dit = self._get_distances_helper(user)
            # if closer to the influential centroid, add data to be plotted.
            if influential_dist > uninfluential_dit:
                influential_coordinates.append(coords[index])

        # Twitter API will not always have info if under load. Warn user.
        if len(influential_coordinates) == 0:
            logging.warn('Twitter API may be under stress and not reporting'
                         'Friend/Follower data!\nNo influential users will '
                         'show if this is the case!')

        # NOTE: Tweets ununsed in geography slot currently
        self.geography_slot(influential_coordinates, tweets=[])
        # NOTE: Much less influential users
        self._redraw_number = 10

    def geography_slot(self, coords, tweets):
        """
        Coords is a 20 member list of (lat, long)
        NOTE: `tweets` currently unused. If tweets become used,
        `user_geography_slot` is passing in an empty list
        """
        for index, (x, y) in enumerate(coords):
            coords[index] = self.map_(x, y)

        self._count += len(coords)
        self.count_signal.emit(self._count)
        # adds 20
        self._x_coords.extend([x[0] for x in coords])
        self._y_coords.extend([x[1] for x in coords])

        if self._count - self._last_redraw > self._redraw_number:
            self._last_redraw = self._count
            self._x_coords = np.append(self._x_coords, self._old_x)
            self._y_coords = np.append(self._y_coords, self._old_y)

            self.axis.cla()
            self._draw_map()

            self.map_.hexbin(self._x_coords,
                             self._y_coords,
                             cmap=plt.cm.rainbow,
                             mincnt=1)

            # keep 10,000 points
            if len(self._old_x) > 10000:
                self._old_x = self._x_coords[100:]
                self._old_y = self._y_coords[100:]
            else:
                self._old_x = self._x_coords
                self._old_y = self._y_coords

            self._x_coords = []
            self._y_coords = []

        self.update_canvas()
