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
    from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QFileDialog, QGraphicsPixmapItem, QButtonGroup
    from PySide6.QtUiTools import QUiLoader
    from PySide6.QtCore import QFile
    from PySide6.QtGui import QImage, QPixmap
except ImportError:
    from PySide2 import QtWidgets, QtUiTools, QtCore
    from PySide2.QtWidgets import QApplication, QMainWindow, QGraphicsScene, QFileDialog, QGraphicsPixmapItem, QButtonGroup
    from PySide2.QtUiTools import QUiLoader
    from PySide2.QtCore import QFile
    from PySide2.QtGui import QImage, QPixmap, QPainter
try:
    import shiboken6 as shiboken
except ImportError:
    import shiboken2 as shiboken

CLASSES = {}
CLASSES['10min'] = [60, 60, 60, 60, 60, 60, 120, 120]
CLASSES['20min'] = [60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 120, 120, 120, 120, 120]
CLASSES['30min'] = [60, 60, 60, 60, 60, 60, 60, 60, 120, 120, 120, 120, 120, 120, 300, 300]
CLASSES['45min'] = [60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 120, 120, 120, 120, 120, 120, 120, 120, 120, 300, 300, 300]
CLASSES['60min'] = [60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 60, 120, 120, 120, 120, 120, 120, 120, 120, 120, 300, 300, 300, 300, 600]

def generate_class_description(sequence):
    times = sorted([*{*sequence}])
    class_str = ""

    for t in times:
        c = sequence.count(t)
        minutes = int(t / 60)
        minutes_str = "minutes" if minutes > 1 else "minute"
        class_str += '{} poses in {} {}\n'.format(c, minutes, minutes_str)
    return class_str

def ms_to_time_string(ms):
    mins = ms // 60000
    mod_result = ms % 60000
    secs = mod_result // 1000
    # mod_result = mod_result % 1000
    return "{:02}:{:02}".format(mins, secs)

def get_timer_value(timer_str):
    if timer_str == "30s":
        return 30
    else:
        return int(timer_str[:-1]) * 60

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

        self._image_indexes = None
        self.session_type = None
        self.current_class = None
        self.session_running = False
        self.current_image_time = 120000
        self.update_interval = 1000
        self.class_img_index = 0
        self.update_timer = QtCore.QTimer()
        self.image_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_image_viewer)
        self.image_timer.timeout.connect(partial(self.start_next_image, 1))

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
        self.sessionTypeButtonGroup = QButtonGroup()
        self.sessionTypeButtonGroup.buttonClicked.connect(self.update_session)
        self.sessionTypeButtonGroup.addButton(self.ui.radioButtonStatic)
        self.sessionTypeButtonGroup.addButton(self.ui.radioButtonClass)
        self.sessionDurationButtonGroup = QButtonGroup()
        self.sessionDurationButtonGroup.addButton(self.ui.radioButtonClass10min)
        self.sessionDurationButtonGroup.addButton(self.ui.radioButtonClass20min)
        self.sessionDurationButtonGroup.addButton(self.ui.radioButtonClass30min)
        self.sessionDurationButtonGroup.addButton(self.ui.radioButtonClass45min)
        self.sessionDurationButtonGroup.addButton(self.ui.radioButtonClass60min)
        self.sessionDurationButtonGroup.buttonClicked.connect(self.update_session)
        self.timerDurationButtonGroup = QButtonGroup()
        self.timerDurationButtonGroup.addButton(self.ui.radioButton30s)
        self.timerDurationButtonGroup.addButton(self.ui.radioButton1min)
        self.timerDurationButtonGroup.addButton(self.ui.radioButton2min)
        self.timerDurationButtonGroup.addButton(self.ui.radioButton5min)
        self.timerDurationButtonGroup.addButton(self.ui.radioButton15min)
        self.timerDurationButtonGroup.buttonClicked.connect(self.update_session)
        self.imgOrderButtonGroup = QButtonGroup()
        self.imgOrderButtonGroup.addButton(self.ui.radioButtonRandom)
        self.imgOrderButtonGroup.addButton(self.ui.radioButtonSequential)
        self.imgOrderButtonGroup.buttonClicked.connect(self.update_img_sequence)
        self.update_session(None)

        # init settings
        script_name = os.path.basename(__file__)
        script_base, ext = os.path.splitext(script_name)  # extract basename and ext from filename
        self.settings = QtCore.QSettings("PoseLibraryViewer", script_base)
        # self.restoreSettings()


    def update_img_sequence(self, button):
        if self._image_indexes:
            if button.text() == 'Random':
                random.shuffle(self._image_indexes)
            else:
                self._image_indexes = sorted(self._image_indexes)
            self.next_image(0)


    def update_session(self, button):
        if self.ui.radioButtonStatic.isChecked():
            self.ui.groupBoxClassDuration.setVisible(False)
            self.ui.groupBoxStaticTimer.setVisible(True)
            timer_button = self.timerDurationButtonGroup.checkedButton()
            if timer_button:
                self.ui.textBrowser.setText("All images at {} interval".format(timer_button.text()))
                self.session_type = "timer"
                self.current_image_time = get_timer_value(timer_button.text()) * 1000
                print(self.current_image_time)
        else:
            self.ui.groupBoxClassDuration.setVisible(True)
            self.ui.groupBoxStaticTimer.setVisible(False)
            class_button = self.sessionDurationButtonGroup.checkedButton()
            if class_button:
                self.ui.textBrowser.setText(generate_class_description(CLASSES[class_button.text()]))
                self.session_type = "class"
                self.class_list = CLASSES[class_button.text()]

    def update_image_viewer(self):
        label_text = "time: {}".format(ms_to_time_string(self.image_timer.remainingTime()))
        self.ui.timerLabel.setText(label_text)
        self.update_timer.start(self.update_interval)

    def start_next_image(self, increment):
        if self.session_type == 'class' and self.class_list:
            if self.class_img_index < len(self.class_list) - 1:
                self.current_image_time = self.class_list[self.class_img_index] * 1000
                self.class_img_index += 1
                self.next_image(increment)
                self.image_timer.start(self.current_image_time)
            else:
                self.stop_session()
        elif self.session_type == 'timer':
                self.next_image(increment)
                self.image_timer.start(self.current_image_time)


    def start_session(self):
        self.class_img_index = 0
        self.start_next_image(0)
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
        if self.image_timer.isActive():
            self.image_timer.start()
            self.update_image_viewer()



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
