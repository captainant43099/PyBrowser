import sys
import json
import subprocess
import platform
import os
from PyQt5.QtGui import QIcon, QKeySequence, QFont
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLineEdit, QPushButton, QHBoxLayout,
                             QVBoxLayout, QWidget, QTabWidget, QFileDialog, QDialog,
                             QLabel, QProgressBar, QMenu, QMessageBox, QStyleFactory, QComboBox, QSpinBox, QAction, QDialogButtonBox, QInputDialog)
from PyQt5.QtCore import QUrl, Qt, QSize, QProcess, QObject
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineDownloadItem, QWebEnginePage, QWebEngineProfile
from PyQt5.QtWebChannel import QWebChannel

# Define the current version of the application
CURRENT_VERSION = "v6.3 Dev Beta!!"

print(f"Application current version: {CURRENT_VERSION}")

def is_dark_mode_windows() -> bool:
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize')
        value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        return value == 0
    except Exception as e:
        print(f"Error detecting dark mode on Windows: {e}")
        return False

def is_dark_mode_macos() -> bool:
    try:
        result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'], capture_output=True, text=True)
        return 'Dark' in result.stdout
    except Exception as e:
        print(f"Error detecting dark mode on macOS: {e}")
        return False

def is_dark_mode() -> bool:
    os_name = platform.system()
    if os_name == 'Windows':
        return is_dark_mode_windows()
    elif os_name == 'Darwin':  # macOS
        return is_dark_mode_macos()
    return False

def apply_dark_theme(app: QApplication):
    dark_stylesheet = """
    QWidget {
        background-color: #2b2b2b;
        color: #dcdcdc;
    }
    QLineEdit {
        background-color: #333333;
        color: #dcdcdc;
    }
    QPushButton {
        background-color: #555555;
        color: #dcdcdc;
        border: 1px solid #6c6c6c;
    }
    QPushButton:hover {
        background-color: #6c6c6c;
    }
    QTabBar::tab {
        background-color: #555555;
        color: #dcdcdc;
    }
    QTabBar::tab:selected {
        background-color: #444444;
    }
    QTabWidget::pane {
        border: 1px solid #444444;
    }
    QMenuBar {
        background-color: #555555;
        color: #dcdcdc;
    }
    QMenu {
        background-color: #555555;
        color: #dcdcdc;
    }
    QMenu::item:selected {
        background-color: #6c6c6c;
    }
    """
    app.setStyleSheet(dark_stylesheet)

def apply_light_theme(app: QApplication):
    light_stylesheet = """
    QWidget {
        background-color: #ffffff;
        color: #000000;
    }
    QLineEdit {
        background-color: #ffffff;
        color: #000000;
    }
    QPushButton {
        background-color: #e6e6e6;
        color: #000000;
        border: 1px solid #adadad;
    }
    QPushButton:hover {
        background-color: #d4d4d4;
    }
    QTabBar::tab {
        background: #e6e6e6;
        color: #000000;
    }
    QTabBar::tab:selected {
        background: #ffffff;
    }
    QMenu {
        background-color: #ffffff;
        color: #000000;
    }
    QMenu::item:selected {
        background-color: #d4d4d4;
    }
    """
    app.setStyleSheet(light_stylesheet)

def reset_to_system_default(app: QApplication):
    app.setStyleSheet("")

class JavaScriptAPI(QObject):
    pass

class DownloadDialog(QDialog):
    def __init__(self, filename: str, path: str, parent=None):
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

    def update_progress(self, received: int, total: int):
        if total > 0:
            percentage = int((received / total) * 100)
            self.progress_bar.setValue(percentage)

    def download_complete(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('Download Complete')
        msg_box.setText('The download is complete.')
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.buttonClicked.connect(self.close)
        msg_box.exec_()

class WebEnginePage(QWebEnginePage):
    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser

    def createWindow(self, window_type):
        return self.browser.main_window.add_tab().page()

    def acceptFeaturePermission(self, securityOrigin, feature):
        if feature == QWebEnginePage.FullScreenVideoFeature:
            self.setFeaturePermission(securityOrigin, feature, QWebEnginePage.PermissionGrantedByUser)
        else:
            super().acceptFeaturePermission(securityOrigin, feature)

class BrowserWindow(QWebEngineView):
    def __init__(self, main_window):
        super().__init__()
        if main_window is None:
            raise ValueError("main_window is required")
        self.main_window = main_window
        self.setPage(WebEnginePage(self))
        self.page().profile().downloadRequested.connect(self.on_download_requested)
        self.loadFinished.connect(self.add_to_history)
        self.loadFinished.connect(self.on_load_finished)
        self.initial_load = True
        self.page().fullScreenRequested.connect(self.handle_fullscreen_requested)

        self.channel = QWebChannel(self.page())
        self.js_api = JavaScriptAPI()
        self.channel.registerObject('jsAPI', self.js_api)
        self.page().setWebChannel(self.channel)

        # Inject dark mode status on page load
        self.loadFinished.connect(self.inject_dark_mode_status)

    def on_load_finished(self, success: bool):
        try:
            if not success:
                print("Failed to load the page.")
            else:
                print("Page loaded successfully.")
        except Exception as e:
            print(f"Error in on_load_finished: {e}")

    def add_to_history(self, _):
        try:
            if self.initial_load:
                self.initial_load = False
                return
            url = self.url().toString()
            title = self.page().title()
            if url and not url.startswith("about:") and title:
                if self.main_window.history is None:
                    self.main_window.history = []
                self.main_window.history.append((title, url))
                self.main_window.save_history()
        except Exception as e:
            print(f"Error in add_to_history: {e}")

    def navigate_to(self, url: str):
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        self.setUrl(QUrl(url))

    def on_download_requested(self, download: QWebEngineDownloadItem):
        options = QFileDialog.Options()
        suggested_filename = download.suggestedFileName()
        default_dir = self.main_window.settings.get('download_dir', '')
        path, _ = QFileDialog.getSaveFileName(self, "Save File", f"{default_dir}/{suggested_filename}", "All Files (*)", options=options)
        if path:
            download.setPath(path)
            download.accept()
            download_dialog = DownloadDialog(suggested_filename, path, self)
            download_dialog.show()
            download.downloadProgress.connect(download_dialog.update_progress)
            download.finished.connect(lambda: self.download_complete(download_dialog))

    def download_complete(self, download_dialog):
        download_dialog.download_complete()

    def handle_fullscreen_requested(self, request):
        if request.toggleOn():
            self.window().showFullScreen()
        else:
            self.window().showNormal()
        request.accept()

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        context_menu.addAction("Back", self.main_window.navigate_back)
        context_menu.addAction("Forward", self.main_window.navigate_forward)
        context_menu.addAction("Reload", self.main_window.reload_page)
        context_menu.addAction("New Tab", self.main_window.add_tab)
        context_menu.addAction("Close Tab", lambda: self.main_window.close_tab(self.main_window.tab_widget.currentIndex()))
        context_menu.exec_(self.mapToGlobal(event.pos()))

    def inject_dark_mode_status(self):
        is_dark_mode = self.main_window.settings.get('theme', 'Light') == 'Dark'
        js_code = f"""
        (function() {{
            var isDarkMode = {str(is_dark_mode).lower()};
            document.documentElement.style.setProperty('--is-dark-mode', isDarkMode);
            var event = new CustomEvent('darkModeChanged', {{ detail: {{ isDarkMode: isDarkMode }} }});
            document.dispatchEvent(event);
        }})();
        """
        self.page().runJavaScript(js_code)

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle('PyBrowser Settings')  # Updated window title
        self.setMinimumSize(400, 400)  # Set minimum size for the window
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.theme_label = QLabel("Select Theme:")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])
        self.theme_combo.setCurrentText(self.main_window.settings.get('theme', 'Light'))
        self.theme_combo.currentIndexChanged.connect(self.change_theme)

        self.homepage_label = QLabel("Set Homepage URL:")
        self.homepage_edit = QLineEdit()
        self.homepage_edit.setText(self.main_window.settings.get('homepage_url', ''))
        self.homepage_edit.setPlaceholderText("Enter Homepage URL")

        self.download_dir_label = QLabel("Set Download Directory:")
        self.download_dir_edit = QLineEdit()
        self.download_dir_edit.setText(self.main_window.settings.get('download_dir', ''))
        self.download_dir_edit.setPlaceholderText("Enter Download Directory")
        self.download_dir_button = QPushButton("Browse...")
        self.download_dir_button.clicked.connect(self.browse_download_dir)

        self.font_size_label = QLabel("Set Font Size:")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 32)
        self.font_size_spin.setValue(self.main_window.settings.get('font_size', 12))

        self.default_zoom_label = QLabel("Set Default Zoom Level (%):")
        self.default_zoom_spin = QSpinBox()
        self.default_zoom_spin.setRange(25, 500)
        self.default_zoom_spin.setValue(self.main_window.settings.get('default_zoom', 100))

        self.privacy_button = QPushButton("Clear Browsing History")
        self.privacy_button.clicked.connect(self.clear_history)

        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)

        self.shutdown_button = QPushButton("Shutdown")
        self.shutdown_button.clicked.connect(self.confirm_shutdown)

        self.restart_button = QPushButton("Restart")
        self.restart_button.clicked.connect(self.confirm_restart)

        self.clear_settings_button = QPushButton("Clear Everything (Advanced)")
        self.clear_settings_button.clicked.connect(self.confirm_clear_everything)

        self.build_number_label = QLabel(f"Current Build: {CURRENT_VERSION}")  # Updated build number label
        self.build_number_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.theme_label)
        layout.addWidget(self.theme_combo)
        layout.addWidget(self.homepage_label)
        layout.addWidget(self.homepage_edit)
        layout.addWidget(self.download_dir_label)
        layout.addWidget(self.download_dir_edit)
        layout.addWidget(self.download_dir_button)
        layout.addWidget(self.font_size_label)
        layout.addWidget(self.font_size_spin)
        layout.addWidget(self.default_zoom_label)
        layout.addWidget(self.default_zoom_spin)
        layout.addWidget(self.privacy_button)
        layout.addWidget(self.save_button)
        layout.addWidget(self.shutdown_button)
        layout.addWidget(self.restart_button)
        layout.addWidget(self.clear_settings_button)
        layout.addWidget(self.build_number_label)

        self.setLayout(layout)

    def browse_download_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Download Directory")
        if directory:
            self.download_dir_edit.setText(directory)

    def change_theme(self, index: int):
        theme = self.theme_combo.currentText()
        self.main_window.change_theme(theme)

    def clear_history(self):
        self.main_window.history = []
        self.main_window.save_history()
        QMessageBox.information(self, "History Cleared", "Your browsing history has been cleared.")

    def save_settings(self):
        self.main_window.settings['theme'] = self.theme_combo.currentText()
        self.main_window.settings['homepage_url'] = self.homepage_edit.text()
        self.main_window.settings['download_dir'] = self.download_dir_edit.text()
        self.main_window.settings['font_size'] = self.font_size_spin.value()
        self.main_window.settings['default_zoom'] = self.default_zoom_spin.value()
        self.main_window.save_settings()
        self.main_window.apply_settings_immediately()  # Apply settings immediately
        self.main_window.update_startup_page()  # Update startup page
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")

    def confirm_shutdown(self):
        reply = QMessageBox.question(self, 'Confirm Shutdown',
                                     'This button is for debugging purposes. Are you sure you want to shutdown?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.shutdown()

    def confirm_restart(self):
        reply = QMessageBox.question(self, 'Confirm Restart',
                                     'This button is for debugging purposes. Are you sure you want to restart?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.restart()

    def confirm_clear_everything(self):
        reply = QMessageBox.question(self, 'Confirm Clear Everything',
                                     'This will reset PyBrowser! Are you sure you want to continue?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            QMessageBox.information(self, 'Clear Everything',
                                    'PyBrowser needs to close to fully clear your settings, history, cache, and cookies.')
            self.clear_everything()

    def clear_everything(self):
        self.main_window.settings = {}
        self.main_window.history = []
        self.main_window.profiles = []
        self.main_window.save_settings()
        self.main_window.save_history()
        self.main_window.save_profiles()

        # Delete all user-specific settings and history files
        for file in os.listdir():
            if file.endswith("_settings.json") or file.endswith("_history.json"):
                os.remove(file)
                
        profile = QWebEngineProfile.defaultProfile()
        profile.clearHttpCache()
        profile.clearAllVisitedLinks()
        profile.cookieStore().deleteAllCookies()
        QApplication.quit()

    def shutdown(self):
        QApplication.quit()

    def restart(self):
        QApplication.quit()
        QProcess.startDetached(sys.executable, sys.argv)

class ProfileDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Create User Profile')
        self.setModal(True)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.first_name_label = QLabel("First Name:")
        self.first_name_edit = QLineEdit()
        self.last_name_label = QLabel("Last Name:")
        self.last_name_edit = QLineEdit()

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(self.first_name_label)
        layout.addWidget(self.first_name_edit)
        layout.addWidget(self.last_name_label)
        layout.addWidget(self.last_name_edit)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def get_profile_data(self):
        return self.first_name_edit.text(), self.last_name_edit.text()

class ProfileSelectionDialog(QDialog):
    def __init__(self, profiles, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select User Profile')
        self.setModal(True)
        self.profiles = profiles
        self.selected_profile = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        self.profile_combo = QComboBox()
        for profile in self.profiles:
            self.profile_combo.addItem(f"{profile['first_name']} {profile['last_name']}", profile)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        new_user_button = QPushButton("Add New User")
        new_user_button.clicked.connect(self.add_new_user)

        layout.addWidget(QLabel("Select a user profile:"))
        layout.addWidget(self.profile_combo)
        layout.addWidget(new_user_button)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def accept(self):
        self.selected_profile = self.profile_combo.currentData()
        super().accept()

    def add_new_user(self):
        profile_dialog = ProfileDialog(self)
        if profile_dialog.exec_() == QDialog.Accepted:
            first_name, last_name = profile_dialog.get_profile_data()
            new_profile = {'first_name': first_name, 'last_name': last_name}
            self.profiles.append(new_profile)
            self.profile_combo.addItem(f"{first_name} {last_name}", new_profile)
            self.profile_combo.setCurrentIndex(self.profile_combo.count() - 1)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_path = "settings.json"
        self.history_path = "browser_history.json"
        self.profile_path = "user_profiles.json"
        self.settings = {}
        self.history = []
        self.profiles = self.load_profiles()
        self.profile = None
        if not self.profiles:
            if not self.prompt_for_profile():
                sys.exit()
        else:
            if not self.select_profile():
                sys.exit()
        if self.profile:
            self.load_user_data()
        self.setWindowTitle(f'PyBrowser {CURRENT_VERSION} - {self.profile["first_name"]} {self.profile["last_name"]}')  # Updated window title
        self.setWindowIcon(QIcon("icon.png"))  # Set the window icon
        self.setup_ui()
        self.restore_window_settings()
        self.apply_settings()

    def setup_ui(self):
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.setCentralWidget(self.tab_widget)
        self.add_tab()  # Open the new tab page by default

        self.url_bar = QLineEdit()
        self.url_bar.setPlaceholderText("Enter URL and press Enter")
        self.url_bar.returnPressed.connect(self.navigate)

        button_size = QSize(80, 32)  # Increased button size for better visibility
        font = QFont()
        font.setPointSize(10)  # Set font size for better visibility

        self.back_button = QPushButton('<')
        self.back_button.setMinimumSize(button_size)
        self.back_button.setFont(font)

        self.forward_button = QPushButton('>')
        self.forward_button.setMinimumSize(button_size)
        self.forward_button.setFont(font)

        self.reload_button = QPushButton('R')
        self.reload_button.setMinimumSize(button_size)
        self.reload_button.setFont(font)

        self.add_tab_button = QPushButton('+')
        self.add_tab_button.setMinimumSize(button_size)
        self.add_tab_button.setFont(font)

        self.menu_button = QPushButton('☰')
        self.menu_button.setMinimumSize(button_size)
        self.menu_button.setFont(font)

        self.tab_group_button = QPushButton('Group Tabs')
        self.tab_group_button.setMinimumSize(button_size)
        self.tab_group_button.setFont(font)

        self.tab_search_button = QPushButton('Search Tabs')
        self.tab_search_button.setMinimumSize(button_size)
        self.tab_search_button.setFont(font)

        self.back_button.clicked.connect(self.navigate_back)
        self.forward_button.clicked.connect(self.navigate_forward)
        self.reload_button.clicked.connect(self.reload_page)
        self.add_tab_button.clicked.connect(self.add_tab)
        self.tab_group_button.clicked.connect(self.group_tabs)
        self.tab_search_button.clicked.connect(self.search_tabs)

        self.menu = QMenu()
        self.menu.addAction('Settings', self.show_settings)
        self.menu.addAction('History', self.show_history)
        self.menu.addAction('Exit', self.close)
        self.menu_button.setMenu(self.menu)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.back_button)
        top_layout.addWidget(self.forward_button)
        top_layout.addWidget(self.reload_button)
        top_layout.addWidget(self.url_bar)
        top_layout.addWidget(self.add_tab_button)
        top_layout.addWidget(self.menu_button)
        top_layout.addWidget(self.tab_group_button)
        top_layout.addWidget(self.tab_search_button)

        container_widget = QWidget()
        container_layout = QVBoxLayout(container_widget)
        container_layout.addLayout(top_layout)
        container_layout.addWidget(self.tab_widget)
        self.setCentralWidget(container_widget)
        self.settings_window = None
        self.history_browser = None

        # Apply theme on startup
        self.apply_theme(self.settings.get('theme', 'Light'))

        # Add keyboard shortcuts
        self.add_shortcuts()

    def add_shortcuts(self):
        new_tab_action = QAction(self)
        new_tab_action.setShortcut(QKeySequence("Ctrl+T"))
        new_tab_action.triggered.connect(self.add_tab)
        self.addAction(new_tab_action)

        close_tab_action = QAction(self)
        close_tab_action.setShortcut(QKeySequence("Ctrl+W"))
        close_tab_action.triggered.connect(lambda: self.close_tab(self.tab_widget.currentIndex()))
        self.addAction(close_tab_action)

        reload_action = QAction(self)
        reload_action.setShortcut(QKeySequence("Ctrl+R"))
        reload_action.triggered.connect(self.reload_page)
        self.addAction(reload_action)

        back_action = QAction(self)
        back_action.setShortcut(QKeySequence("Alt+Left"))
        back_action.triggered.connect(self.navigate_back)
        self.addAction(back_action)

        forward_action = QAction(self)
        forward_action.setShortcut(QKeySequence("Alt+Right"))
        forward_action.triggered.connect(self.navigate_forward)
        self.addAction(forward_action)

        help_action = QAction(self)
        help_action.setShortcut(QKeySequence("F1"))
        help_action.triggered.connect(self.show_help)
        self.addAction(help_action)

        settings_action = QAction(self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self.show_settings)
        self.addAction(settings_action)

        history_action = QAction(self)
        history_action.setShortcut(QKeySequence("Ctrl+H"))
        history_action.triggered.connect(self.show_history)
        self.addAction(history_action)

        exit_action = QAction(self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        self.addAction(exit_action)

        group_tabs_action = QAction(self)
        group_tabs_action.setShortcut(QKeySequence("Ctrl+G"))
        group_tabs_action.triggered.connect(self.group_tabs)
        self.addAction(group_tabs_action)

        search_tabs_action = QAction(self)
        search_tabs_action.setShortcut(QKeySequence("Ctrl+F"))
        search_tabs_action.triggered.connect(self.search_tabs)
        self.addAction(search_tabs_action)

    def show_help(self):
        help_text = """
        <h1>PyBrowser Help</h1>
        <h2>Navigation</h2>
        <ul>
            <li><b>Back:</b> Alt + Left Arrow</li>
            <li><b>Forward:</b> Alt + Right Arrow</li>
            <li><b>Reload:</b> Ctrl + R</li>
            <li><b>New Tab:</b> Ctrl + T</li>
            <li><b>Close Tab:</b> Ctrl + W</li>
            <li><b>Toggle Full Screen:</b> F11</li>
            <li><b>Group Tabs:</b> Ctrl + G</li>
            <li><b>Search Tabs:</b> Ctrl + F</li>
        </ul>
        <h2>Other Shortcuts</h2>
        <ul>
            <li><b>Help:</b> F1</li>
            <li><b>Settings:</b> Ctrl + ,</li>
            <li><b>History:</b> Ctrl + H</li>
            <li><b>Exit:</b> Ctrl + Q</li>
        </ul>
        """
        QMessageBox.information(self, "Help", help_text)

    def apply_settings(self):
        # Apply homepage URL
        self.homepage_url = self.settings.get('homepage_url', '')

        # Apply download directory
        self.download_dir = self.settings.get('download_dir', '')

        # Apply font size
        font_size = self.settings.get('font_size', 12)
        self.setStyleSheet(f"* {{ font-size: {font_size}px; }}")

        # Apply default zoom level
        self.default_zoom = self.settings.get('default_zoom', 100)
        for i in range(self.tab_widget.count()):
            browser = self.tab_widget.widget(i)
            browser.setZoomFactor(self.default_zoom / 100)

    def apply_settings_immediately(self):
        # Apply font size immediately
        font_size = self.settings['font_size']
        self.setStyleSheet(f"* {{ font-size: {font_size}px; }}")

        # Apply zoom level immediately
        default_zoom = self.settings['default_zoom']
        for i in range(self.tab_widget.count()):
            browser = self.tab_widget.widget(i)
            browser.setZoomFactor(default_zoom / 100)

        # Apply theme immediately
        theme = self.settings.get('theme', 'Light')
        self.change_theme(theme)

    def change_theme(self, theme):
        if theme == "Dark":
            apply_dark_theme(QApplication.instance())
        elif theme == "Light":
            apply_light_theme(QApplication.instance())
        # Inject dark mode status for all open tabs
        for i in range(self.tab_widget.count()):
            browser = self.tab_widget.widget(i)
            browser.inject_dark_mode_status()

    def update_startup_page(self):
        search_engine = self.settings.get('search_engine', 'Google')
        search_url = {
            'Google': 'https://www.google.com/search',
            'Bing': 'https://www.bing.com/search',
            'DuckDuckGo': 'https://duckduckgo.com/'
        }.get(search_engine, 'https://www.google.com/search')

        new_tab_html = f"""
        <html>
            <head>
                <style>
                    body {{
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        margin: 0;
                        padding: 0;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        background-color: #f0f0f0;
                        color: #333;
                    }}
                    .container {{
                        text-align: center;
                    }}
                    h1 {{
                        font-size: 48px;
                        margin-bottom: 20px;
                    }}
                    input[type="text"] {{
                        font-size: 18px;
                        padding: 10px;
                        width: 300px;
                        border: 1px solid #ccc;
                        border-radius: 5px;
                    }}
                    input[type="submit"] {{
                        font-size: 18px;
                        padding: 10px 20px;
                        margin-left: 10px;
                        border: none;
                        border-radius: 5px;
                        background-color: #0078D7;
                        color: white;
                        cursor: pointer;
                    }}
                    input[type="submit"]:hover {{
                        background-color: #0056b3;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>Welcome to PyBrowser {CURRENT_VERSION}</h1>  <!-- Updated version -->
                    <p>Enter a search term below to start browsing:</p>
                    <form action="{search_url}" method="get">
                        <input type="text" name="q" placeholder="Search {search_engine}" />
                        <input type="submit" value="Search" />
                    </form>
                </div>
            </body>
        </html>
        """

        for i in range(self.tab_widget.count()):
            browser = self.tab_widget.widget(i)
            if browser.initial_load:
                browser.setHtml(new_tab_html)

    def show_settings(self):
        if (self.settings_window is None) or (not self.settings_window.isVisible()):
            self.settings_window = SettingsWindow(self)
            self.settings_window.show()

    def load_settings(self, profile_name) -> dict:
        try:
            with open(f"{profile_name}_settings.json", "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_settings(self):
        with open(f"{self.profile['first_name']}_{self.profile['last_name']}_settings.json", "w") as file:
            json.dump(self.settings, file)

    def apply_theme(self, theme: str):
        if theme == "Dark":
            apply_dark_theme(QApplication.instance())
        elif theme == "Light":
            apply_light_theme(QApplication.instance())

    def load_history(self, profile_name) -> list:
        try:
            with open(f"{profile_name}_history.json", "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_history(self):
        with open(f"{self.profile['first_name']}_{self.profile['last_name']}_history.json", "w") as file:
            json.dump(self.history, file)

    def load_profiles(self) -> list:
        try:
            with open(self.profile_path, "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_profiles(self):
        with open(self.profile_path, "w") as file:
            json.dump(self.profiles, file)

    def save_window_settings(self):
        self.settings['window_size'] = (self.size().width(), self.size().height())
        self.settings['window_position'] = (self.pos().x(), self.pos().y())
        self.save_settings()

    def restore_window_settings(self):
        size = self.settings.get('window_size', (800, 600))
        position = self.settings.get('window_position', (100, 100))
        self.resize(*size)
        self.move(*position)

    def prompt_for_profile(self):
        profile_dialog = ProfileDialog(self)
        if profile_dialog.exec_() == QDialog.Accepted:
            first_name, last_name = profile_dialog.get_profile_data()
            new_profile = {'first_name': first_name, 'last_name': last_name}
            self.profiles.append(new_profile)
            self.profile = new_profile
            self.save_profiles()
            return True
        return False

    def select_profile(self):
        profile_selection_dialog = ProfileSelectionDialog(self.profiles, self)
        if profile_selection_dialog.exec_() == QDialog.Accepted:
            self.profile = profile_selection_dialog.selected_profile
            self.save_profiles()
            return True
        return False

    def load_user_data(self):
        profile_name = f"{self.profile['first_name']}_{self.profile['last_name']}"
        self.settings = self.load_settings(profile_name)
        self.history = self.load_history(profile_name)

    def navigate_back(self):
        if self.tab_widget.currentWidget():
            self.tab_widget.currentWidget().back()

    def navigate_forward(self):
        if self.tab_widget.currentWidget():
            self.tab_widget.currentWidget().forward()

    def reload_page(self):
        if self.tab_widget.currentWidget():
            self.tab_widget.currentWidget().reload()

    def navigate(self):
        url = self.url_bar.text()
        if url:
            self.tab_widget.currentWidget().navigate_to(url)

    def add_tab(self, url=None) -> BrowserWindow:
        browser = BrowserWindow(self)
        homepage_url = self.settings.get('homepage_url', '')
        if url:
            browser.initial_load = False
            browser.setUrl(QUrl(url))
        elif homepage_url:
            browser.setUrl(QUrl(homepage_url))
        else:
            search_engine = self.settings.get('search_engine', 'Google')
            search_url = {
                'Google': 'https://www.google.com/search',
                'Bing': 'https://www.bing.com/search',
                'DuckDuckGo': 'https://duckduckgo.com/'
            }.get(search_engine, 'https://www.google.com/search')

            new_tab_html = f"""
            <html>
                <head>
                    <style>
                        body {{
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            margin: 0;
                            padding: 0;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            background-color: #f0f0f0;
                            color: #333;
                        }}
                        .container {{
                            text-align: center;
                        }}
                        h1 {{
                            font-size: 48px;
                            margin-bottom: 20px;
                        }}
                        input[type="text"] {{
                            font-size: 18px;
                            padding: 10px;
                            width: 300px;
                            border: 1px solid #ccc;
                            border-radius: 5px;
                        }}
                        input[type="submit"] {{
                            font-size: 18px;
                            padding: 10px 20px;
                            margin-left: 10px;
                            border: none;
                            border-radius: 5px;
                            background-color: #0078D7;
                            color: white;
                            cursor: pointer;
                        }}
                        input[type="submit"]:hover {{
                            background-color: #0056b3;
                        }}
                    </style>
                    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
                </head>
                <body>
                    <div class="container">
                        <h1>Welcome to PyBrowser {CURRENT_VERSION}</h1>  <!-- Updated version -->
                        <p>Enter a search term below to start browsing:</p>
                        <form action="{search_url}" method="get">
                            <input type="text" name="q" placeholder="Search {search_engine}" />
                            <input type="submit" value="Search" />
                        </form>
                    </div>
                </body>
            </html>
            """
            browser.setHtml(new_tab_html)
        i = self.tab_widget.addTab(browser, 'New Tab')
        self.tab_widget.setCurrentIndex(i)
        browser.urlChanged.connect(lambda url, browser=browser: self.update_urlbar(url, browser))
        browser.loadFinished.connect(lambda _, i=i, browser=browser:
                                     self.tab_widget.setTabText(i, browser.page().title() or 'New Tab'))
        return browser

    def close_tab(self, index: int):
        if self.tab_widget.count() < 2:
            return
        widget = self.tab_widget.widget(index)
        if widget == self.history_browser:
            self.history_browser = None
        widget.deleteLater()
        self.tab_widget.removeTab(index)

    def update_urlbar(self, url: QUrl, browser=None):
        if browser != self.tab_widget.currentWidget():
            return
        self.url_bar.setText(url.toString())

    def show_history(self):
        if not self.history:  # Check if history is empty
            QMessageBox.information(self, "No History", "There is no browsing history to show.")
            return

        history_html = """
        <html>
        <head>
            <style>
                body {
                    font-family: 'Arial', sans-serif;
                    margin: 20px;
                    background-color: #f4f4f9;
                    color: #333;
                }
                h1 {
                    color: #5d647b;
                    text-align: center;
                }
                ul {
                    list-style: none;
                    padding: 0;
                }
                li {
                    background: white;
                    border-bottom: 1px solid #ccc;
                    padding: 10px;
                    margin-top: 5px;
                }
                a {
                    color: #5d647b;
                    text-decoration: none;
                }
                a:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <h1>History</h1>
            <ul>"""

        for title, url in self.history:
            history_html += f"<li><a href='{url}'>{title}</a> - {url}</li>"

        history_html += "</ul></body></html>"

        # Ensure a new tab is opened for history or update an existing one
        if self.history_browser is None:
            self.history_browser = self.add_tab("about:history")
        self.history_browser.setHtml(history_html)

    def group_tabs(self):
        group_name, ok = QInputDialog.getText(self, 'Group Tabs', 'Enter a group name:')
        if ok and group_name:
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if self.tab_widget.tabText(i).startswith(group_name):
                    continue
                self.tab_widget.setTabText(i, f"{group_name}: {self.tab_widget.tabText(i)}")

    def search_tabs(self):
        search_text, ok = QInputDialog.getText(self, 'Search Tabs', 'Enter text to search in tabs:')
        if ok and search_text:
            for i in range(self.tab_widget.count()):
                widget = self.tab_widget.widget(i)
                if search_text.lower() in self.tab_widget.tabText(i).lower():
                    self.tab_widget.setCurrentIndex(i)
                    break

    def closeEvent(self, event):
        self.save_window_settings()
        tab_count = self.tab_widget.count()
        if tab_count > 1:
            reply = QMessageBox.question(self, 'Close Browser',
                                         f'You have {tab_count} tabs open. Are you sure you want to close the browser?',
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.save_history()
                event.accept()
            else:
                event.ignore()
        else:
            self.save_history()
            event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            if self.isFullScreen():
                self.showNormal()
            else:
                self.showFullScreen()
        super().keyPressEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))

    main_window = MainWindow()
    if main_window.profile:
        main_window.show()
    sys.exit(app.exec_())
