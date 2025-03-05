#
# Copyright 2018 Michal Mach
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

__version__ = '1.0'
__author__ = 'Michal Mach'

import sys
import os
import math
import glob
import fnmatch

from functools import partial
from distutils.util import strtobool
import numbers
import random

try:
    from PySide6 import QtWidgets, QtUiTools, QtCore
    from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QFileDialog, QGraphicsPixmapItem
    from PySide6.QtUiTools import QUiLoader
    from PySide6.QtCore import QFile
    from PySide6.QtGui import QImage, QPixmap
except ImportError:
    from PySide2 import QtWidgets, QtUiTools, QtCore
    from PySide2.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QFileDialog, QGraphicsPixmapItem
    from PySide2.QtUiTools import QUiLoader
    from PySide2.QtCore import QFile
    from PySide2.QtGui import QImage, QPixmap, QPainter
try:
    import shiboken6 as shiboken
except ImportError:
    import shiboken2 as shiboken


def ms_to_time_string(ms):
    mins = ms // 60000
    mod_result = ms % 60000
    secs = mod_result // 1000
    # mod_result = mod_result % 1000
    return "{}:{}".format(mins, secs)

def old_div(a, b):
   if isinstance(a, numbers.Integral) and isinstance(b, numbers.Integral):
       return a // b
   else:
       return a / b


def filter_files(file_list, ext_list):
    for file in file_list:
        for ext in ext_list:
            if fnmatch.fnmatch(file, ext):
                yield file
                break

IMG_EXTENSIONS= "*.jpg", "*.jpeg", "*.png", "*.bmp", "*.tga"

class ImageViewer(QtWidgets.QLabel):
    gotoNext = QtCore.Signal()
    gotoPrev = QtCore.Signal()
    def __init__(self, parent=None):
        super(ImageViewer, self).__init__(parent)

        policy =  QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

        self.setMinimumSize(150, 150)
        self.base_pixmap = QPixmap()
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def setBasePixmap(self, pixmap):
        self.base_pixmap = pixmap
        self.update()
        self.updateGeometry()

    def heightForWidth(self, width):
        if self.base_pixmap.isNull():
            return width
        height = round(width * (self.base_pixmap.height() / self.base_pixmap.width()))
        return max(height, 512)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Up:
            self.gotoPrev.emit()
        elif event.key() == QtCore.Qt.Key_Down:
            self.gotoNext.emit()
        event.accept()

    def keyReleaseEvent(self, event):
        event.accept()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QtCore.Qt.black)
        pixmap = self.base_pixmap.scaled(self.width(), self.height(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

        wo = old_div((self.width()-pixmap.width()),2)
        ho = old_div((self.height()-pixmap.height()),2)

        painter.drawPixmap(wo, ho, pixmap.width(), pixmap.height(), pixmap)
        painter.end()


class PoseLibraryViewerUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        file = QFile("pose_library_viewer.ui")
        file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.ui = loader.load(file, self) # Load the UI, set self as parent
        file.close()
        self.setCentralWidget(self.ui.mainWidget) # Set loaded UI as central widget

        self.session_running = False
        self.current_image_time = 120000
        self.update_interval = 1000
        self.update_timer = QtCore.QTimer()
        self.image_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_image_viewer)
        self.image_timer.timeout.connect(self.start_next_image)

        self.ui.pauseButton.clicked.connect(self.start_session)
        self.ui.stopButton.clicked.connect(self.stop_session)

        self._image_paths = []
        self._image_index = 0
        self.imageViewer = ImageViewer()
        # self.imageViewer.setScaledContents(True)
        self.ui.imageViewerLayout.insertWidget(0, self.imageViewer)

        self.ui.pushButton.clicked.connect(self.load)
        self.ui.nextButton.clicked.connect(partial(self.next_image, 1))
        self.ui.prevButton.clicked.connect(partial(self.next_image, -1))

        # init settings
        script_name = os.path.basename(__file__)
        script_base, ext = os.path.splitext(script_name)  # extract basename and ext from filename
        self.settings = QtCore.QSettings("PoseLibraryViewer", script_base)
        # self.restoreSettings()


    def update_image_viewer(self):
        label_text = "time: {}".format(ms_to_time_string(self.image_timer.remainingTime()))
        self.ui.timerLabel.setText(label_text)
        self.update_timer.start(self.update_interval)

    def start_next_image(self):
        self.next_image(1)
        self.image_timer.start(self.current_image_time)

    def start_session(self):
        self.start_next_image()
        self.update_image_viewer()

    def stop_session(self):
        self.update_timer.stop()
        self.image_timer.stop()

    def next_image(self, increment):
        if not self._image_paths:
            return

        self._image_index += increment
        if self._image_index > len(self._image_indexes) - 1:
            self._image_index = 0
        elif self._image_index < 0:
            self._image_index = len(self._image_indexes) - 1

        self.image_qt = QImage(self._image_paths[self._image_indexes[self._image_index]])
        self.imageViewer.setBasePixmap(QPixmap.fromImage(self.image_qt))



    def load(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select directory with images"
        )
        if not path:
            return

        self.ui.imageFolderEdit.setText(path)

        for dirname, dirnames, filenames in os.walk(path):
            matches = list(filter_files(filenames, IMG_EXTENSIONS))
            self._image_paths = sorted(list(os.path.join(dirname, f) for f in matches))
        self._image_indexes = list(range(0, len(self._image_paths)))
        self.next_image(0)
        return

if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    main_window = PoseLibraryViewerUI()
    main_window.show()
    app.exec_()
