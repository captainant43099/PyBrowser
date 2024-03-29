import sys
from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLineEdit, QPushButton, QHBoxLayout,
                             QVBoxLayout, QWidget, QTabWidget, QMessageBox, QFileDialog, QDialog,
                             QLabel, QProgressBar)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineDownloadItem

class DownloadDialog(QDialog):
    def __init__(self, filename, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Download Progress')
        self.setWindowModality(Qt.ApplicationModal)

        self.filename_label = QLabel(f'File: {filename}')
        self.path_label = QLabel(f'Save to: {path}')
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        layout = QVBoxLayout()
        layout.addWidget(self.filename_label)
        layout.addWidget(self.path_label)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

    def update_progress(self, received, total):
        if total > 0:
            percentage = int((received / total) * 100)
            self.progress_bar.setValue(percentage)

class BrowserWindow(QWebEngineView):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.page().profile().downloadRequested.connect(self.on_download_requested)

    def navigate_to(self, url):
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        self.setUrl(QUrl(url))

    def on_download_requested(self, download: QWebEngineDownloadItem):
        options = QFileDialog.Options()
        suggested_filename = download.suggestedFileName()
        path, _ = QFileDialog.getSaveFileName(self, "Save File", suggested_filename, "All Files (*)", options=options)
        
        if path:
            download.setPath(path)
            download.accept()
            download_dialog = DownloadDialog(suggested_filename, path, self)
            download_dialog.show()
            download.downloadProgress.connect(download_dialog.update_progress)

    def createWindow(self, _type):
        return self.main_window.add_tab()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PyBrowser 1.0')

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tab_widget)

        self.add_tab()

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Search the World Wide Web")
        self.url_bar.returnPressed.connect(self.navigate)

        self.back_button = QPushButton('<')
        self.forward_button = QPushButton('>')
        self.reload_button = QPushButton('R')
        self.add_tab_button = QPushButton('+')

        self.back_button.clicked.connect(lambda: self.tab_widget.currentWidget().back())
        self.forward_button.clicked.connect(lambda: self.tab_widget.currentWidget().forward())
        self.reload_button.clicked.connect(lambda: self.tab_widget.currentWidget().reload())
        self.add_tab_button.clicked.connect(self.add_tab)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.back_button)
        top_layout.addWidget(self.forward_button)
        top_layout.addWidget(self.reload_button)
        top_layout.addWidget(self.url_bar)
        top_layout.addWidget(self.add_tab_button)

        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_layout.addLayout(top_layout)
        container_layout.addWidget(self.tab_widget)
        self.setCentralWidget(container_widget)

    def add_tab(self, url=None):
        browser = BrowserWindow(self)
        browser.setUrl(QUrl(url) if url else QUrl('https://cse.google.com/cse?cx=36bf07a6061144d23#gsc.tab=0'))
        i = self.tab_widget.addTab(browser, 'New Tab')
        self.tab_widget.setCurrentIndex(i)
        browser.urlChanged.connect(lambda url, browser=browser: self.update_urlbar(url, browser))
        browser.loadFinished.connect(lambda _, i=i, browser=browser: 
                                     self.tab_widget.setTabText(i, browser.page().title()))
        return browser

    def close_tab(self, index):
        if self.tab_widget.count() < 2:
            return
        widget = self.tab_widget.widget(index)
        widget.deleteLater()
        self.tab_widget.removeTab(index)

    def update_urlbar(self, url, browser=None):
        if browser != self.tab_widget.currentWidget():
            return
        self.url_bar.setText(url.toString())

    def navigate(self):
        url = self.url_bar.text()
        if not url:
            return
        current_browser = self.tab_widget.currentWidget()
        if current_browser:
            current_browser.navigate_to(url)

    def closeEvent(self, event):
        if self.tab_widget.count() > 1:
            reply = QMessageBox.question(self, 'Close Browser', 
                                         f"You have {self.tab_widget.count()} tabs running. Are you sure you want to close the browser?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
