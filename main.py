import sys
import os
import csv
import subprocess
import shutil
import ctypes  # Для исправления иконки в панели задач

from PySide6.QtCore import QUrl, Qt, QTimer, QDateTime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QLineEdit,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
    QStatusBar, QDockWidget, QListWidget, QHBoxLayout,
    QLabel, QFrame, QSystemTrayIcon, QMenu,  # Добавлены классы трея
    QTextEdit,  # Для History
    QTreeWidget, QTreeWidgetItem,  # For collapsible sidebar folders
    QInputDialog, QMessageBox  # For subfolder dialogs
)

from PySide6.QtGui import QIcon, QAction  # Добавлен QAction
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtNetwork import QNetworkProxy

# Если у вас есть этот файл рядом, оставляем импорт
try:
    from csv_viewer import CSVViewerTab
except ImportError:
    # Заглушка, если файла нет при запуске
    CSVViewerTab = None 
    print("Warning: csv_viewer module not found.")

# [FIX] Исправление группировки иконки в панели задач Windows 11
if sys.platform == 'win32':
    myappid = 'neurolit.browser.client.1.0'  # Уникальный ID приложения
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

class BrowserTab(QWidget):
    def __init__(self, main_window, profile=None):
        super().__init__()
        self.main_window = main_window
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.browser = QWebEngineView()
        
        if profile is not None:
            page = QWebEnginePage(profile, self.browser)
            self.browser.setPage(page)
            
        self.browser.createWindow = self.create_window
        self.layout.addWidget(self.browser)

    def create_window(self, _type):
        return self.main_window.add_new_tab()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NeuroLit - Neuronet Literature")
        
        # Настройка путей
        base_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(base_dir, "favicon.png")
        
        # Установка иконки окна
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        self.resize(1200, 800)
        self.feed_page = 0

        # Persistent profile for cookie/session storage
        storage_path = os.path.join(base_dir, "data", "profile")
        self.profile = QWebEngineProfile("neurolit", self)
        self.profile.setPersistentStoragePath(storage_path)
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBarDoubleClicked.connect(self.tab_open_doubleclick)
        self.tabs.currentChanged.connect(self.current_tab_changed)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_current_tab)
        self.setCentralWidget(self.tabs)

        # Navigation Bar
        nav_bar = QToolBar("Navigation")
        self.addToolBar(nav_bar)

        # Back Button
        back_btn = QPushButton("<")
        back_btn.clicked.connect(lambda: self.current_browser().back() if self.current_browser() else None)
        back_btn.setFixedWidth(32)
        nav_bar.addWidget(back_btn)

        # Forward Button
        next_btn = QPushButton(">")
        next_btn.clicked.connect(lambda: self.current_browser().forward() if self.current_browser() else None)
        next_btn.setFixedWidth(32)
        nav_bar.addWidget(next_btn)

        # Reload Button
        reload_btn = QPushButton("@")
        reload_btn.clicked.connect(lambda: self.current_browser().reload() if self.current_browser() else None)
        reload_btn.setFixedWidth(32)
        nav_bar.addWidget(reload_btn)

        # Home Button
        home_btn = QPushButton("H")
        home_btn.clicked.connect(self.navigate_home)
        home_btn.setFixedWidth(32)
        nav_bar.addWidget(home_btn)

        # URL Bar
        self.url_bar = QLineEdit()
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        nav_bar.addWidget(self.url_bar)

        # Go Button
        go_btn = QPushButton("Go")
        go_btn.setFixedWidth(32)
        go_btn.clicked.connect(self.navigate_to_url)
        nav_bar.addWidget(go_btn)

        # New Tab Button
        new_tab_btn = QPushButton("+")
        new_tab_btn.setFixedWidth(32)
        new_tab_btn.clicked.connect(lambda: self.add_new_tab())
        nav_bar.addWidget(new_tab_btn)

        # Sidebar
        self.sidebar = QDockWidget("Sidebar", self)
        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setAlignment(Qt.AlignTop)

        # Ensure data directory exists
        self.data_dir = os.path.join(base_dir, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "history"), exist_ok=True)

        # Tree Widget for collapsible sidebar sections
        self.sidebar_tree = QTreeWidget()
        self.sidebar_tree.setHeaderHidden(True)
        self.sidebar_tree.setAnimated(True)
        self.sidebar_tree.setIndentation(16)
        self.sidebar_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sidebar_tree.customContextMenuRequested.connect(self.sidebar_context_menu)

        # Feeds top-level item
        self.feeds_tree_item = QTreeWidgetItem(self.sidebar_tree, ["Feeds"])
        self.feeds_tree_item.setFlags(self.feeds_tree_item.flags() | Qt.ItemIsEnabled)

        # Bookmarks folder (collapsible)
        self.bookmarks_tree_item = QTreeWidgetItem(self.sidebar_tree, ["Bookmarks"])
        self.bookmarks_tree_item.setFlags(self.bookmarks_tree_item.flags() | Qt.ItemIsEnabled)
        self.populate_bookmarks_tree()

        # History folder (collapsible)
        self.history_tree_item = QTreeWidgetItem(self.sidebar_tree, ["History"])
        self.history_tree_item.setFlags(self.history_tree_item.flags() | Qt.ItemIsEnabled)
        self.history_page = 0
        self.populate_history_tree()

        # Settings top-level item
        self.settings_tree_item = QTreeWidgetItem(self.sidebar_tree, ["Settings"])
        self.settings_tree_item.setFlags(self.settings_tree_item.flags() | Qt.ItemIsEnabled)

        self.sidebar_tree.itemClicked.connect(self.sidebar_tree_item_clicked)
        self.sidebar_tree.itemExpanded.connect(self.sidebar_tree_item_expanded)
        sidebar_layout.addWidget(self.sidebar_tree)

        # Feeds List Section (Hidden by default)
        self.feeds_container = QWidget()
        self.feeds_layout = QVBoxLayout(self.feeds_container)
        self.feeds_list = QListWidget()
        self.feeds_list.itemClicked.connect(self.feed_item_clicked)
        self.feeds_layout.addWidget(self.feeds_list)
        
        feeds_nav_layout = QHBoxLayout()
        self.feeds_back_btn = QPushButton("<")
        self.feeds_back_btn.clicked.connect(self.prev_feeds_page)
        self.feeds_next_btn = QPushButton(">")
        self.feeds_next_btn.clicked.connect(self.next_feeds_page)
        
        feeds_nav_layout.addWidget(self.feeds_back_btn)
        feeds_nav_layout.addWidget(self.feeds_next_btn)
        self.feeds_layout.addLayout(feeds_nav_layout)
        self.feeds_container.hide()
        sidebar_layout.addWidget(self.feeds_container)

        # Bookmarks buttons section (Hidden by default)
        self.bookmarks_btn_container = QWidget()
        bookmarks_btn_layout = QHBoxLayout(self.bookmarks_btn_container)
        bookmarks_btn_layout.setContentsMargins(0, 0, 0, 0)
        add_bookmark_btn = QPushButton("+ Add Current Page")
        add_bookmark_btn.clicked.connect(self.add_current_page_bookmark)
        bookmarks_btn_layout.addWidget(add_bookmark_btn)
        remove_bookmark_btn = QPushButton("- Remove")
        remove_bookmark_btn.clicked.connect(self.remove_selected_bookmark)
        bookmarks_btn_layout.addWidget(remove_bookmark_btn)
        self.bookmarks_btn_container.hide()
        sidebar_layout.addWidget(self.bookmarks_btn_container)

        # History editor section (Hidden by default)
        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_title_input = QLineEdit()
        self.history_title_input.setPlaceholderText("Title")
        self.history_layout.addWidget(self.history_title_input)
        self.history_text = QTextEdit()
        self.history_text.setPlaceholderText("Page text will appear here...")
        self.history_layout.addWidget(self.history_text)
        history_btn_layout = QHBoxLayout()
        history_save_btn = QPushButton("Save")
        history_save_btn.clicked.connect(self.save_history)
        history_btn_layout.addWidget(history_save_btn)
        history_refresh_btn = QPushButton("Refresh")
        history_refresh_btn.clicked.connect(self.refresh_history_tree)
        history_btn_layout.addWidget(history_refresh_btn)
        self.history_layout.addLayout(history_btn_layout)

        self.history_container.hide()
        sidebar_layout.addWidget(self.history_container)

        # RSS Reader Section
        rss_label = QLabel("RSS Reader")
        sidebar_layout.addWidget(rss_label)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        sidebar_layout.addWidget(line)
        
        # Proxy Input
        proxy_layout = QHBoxLayout()
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("Proxy URL")
        self.proxy_input.setStyleSheet("color: green;")
        proxy_layout.addWidget(self.proxy_input)
        
        proxy_ok_btn = QPushButton("Ok")
        proxy_ok_btn.setFixedWidth(40)
        proxy_ok_btn.clicked.connect(self.set_proxy)
        proxy_layout.addWidget(proxy_ok_btn)
        sidebar_layout.addLayout(proxy_layout)
        
        # RSS Input
        rss_input_layout = QHBoxLayout()
        self.rss_input = QLineEdit()
        self.rss_input.setPlaceholderText("RSS URL")
        self.rss_input.setStyleSheet("color: green;")
        rss_input_layout.addWidget(self.rss_input)
        
        get_rss_btn = QPushButton("Ok")
        get_rss_btn.setFixedWidth(40)
        get_rss_btn.clicked.connect(self.get_rss)
        rss_input_layout.addWidget(get_rss_btn)
        sidebar_layout.addLayout(rss_input_layout)
        
        # Fetch RSS Button
        fetch_rss_btn = QPushButton("FetchRSS")
        fetch_rss_btn.setFixedWidth(60)
        fetch_rss_btn.clicked.connect(self.run_fetch_rss)
        sidebar_layout.addWidget(fetch_rss_btn)

        self.sidebar.setWidget(sidebar_container)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.sidebar)

        # [FIX] Статус бар (делаем его видимым сразу)
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # [FIX] Настройка системного трея
        self.setup_tray_icon(icon_path)

        # Initial Tab
        self.add_new_tab(QUrl("https://www.google.com/search?q=&udm=50&hl=ru"), "Homepage")

        # Setup Scheduled Fetching
        self.fetch_timer = QTimer(self)
        self.fetch_timer.timeout.connect(self.check_schedule)
        self.fetch_timer.start(60000) # Check every minute

    # --- МЕТОДЫ ДЛЯ ТРЕЯ ---
    def setup_tray_icon(self, icon_path):
        self.tray_icon = QSystemTrayIcon(self)
        
        if os.path.exists(icon_path):
            self.tray_icon.setIcon(QIcon(icon_path))
        else:
            # Если иконки нет, используем стандартную
            self.tray_icon.setIcon(self.style().standardIcon(Qt.Style.SP_ComputerIcon))
        
        # Контекстное меню
        tray_menu = QMenu()
        
        show_action = QAction("Открыть", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        # Левый клик по иконке трея
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def show_window(self):
        self.show()
        self.setWindowState(Qt.WindowActive)
        self.activateWindow()

    def closeEvent(self, event):
        # Перехватываем закрытие окна -> сворачиваем в трей
        if self.tray_icon.isVisible():
            event.ignore()
            self.hide()
            self.tray_icon.showMessage("NeuroLit", "Приложение свернуто в трей", QSystemTrayIcon.Information, 2000)
        else:
            super().closeEvent(event)
    # -----------------------

    def check_schedule(self):
        now = QDateTime.currentDateTime().time()
        hour = now.hour()
        minute = now.minute()
        if minute == 0 or minute == 30:
            self.run_fetch_rss()
        if hour == 0 and minute == 0:
            self.run_change_rss()

    def add_new_tab(self, qurl=None, label="New Tab"):
        if qurl is None:
            qurl = QUrl("https://www.google.com/search?q=&udm=50&hl=ru")
        
        tab = BrowserTab(self, self.profile)
        tab.browser.setUrl(qurl)
        i = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(i)
        
        # Connect signals
        tab.browser.urlChanged.connect(lambda qurl, tab=tab: self.update_urlbar(qurl, tab))
        tab.browser.loadFinished.connect(lambda _, i=i, tab=tab: self.update_tab_title(i, tab))
        
        return tab.browser

    def add_csv_tab(self, file_path, label="CSV Viewer"):
        if CSVViewerTab:
            tab = CSVViewerTab(file_path, self)
            i = self.tabs.addTab(tab, label)
            self.tabs.setCurrentIndex(i)
            self.setWindowTitle(f"{label} - NeuroLit")
        else:
            print("CSVViewerTab not available")

    def update_tab_title(self, i, tab):
        title = tab.browser.page().title()
        if len(title) > 32:
            display_title = title[:29] + "..."
        else:
            display_title = title
        self.tabs.setTabText(i, display_title)
        self.update_title(tab)

    def tab_open_doubleclick(self, i):
        if i == -1:
            self.add_new_tab()

    def current_tab_changed(self, i):
        widget = self.tabs.currentWidget()
        if isinstance(widget, BrowserTab):
            qurl = widget.browser.url()
            self.update_urlbar(qurl, widget)
            self.update_title(widget)
        elif CSVViewerTab and isinstance(widget, CSVViewerTab):
            self.url_bar.setText(widget.file_path)
            self.setWindowTitle(f"{os.path.basename(widget.file_path)} - NeuroLit")

    def close_current_tab(self, i):
        if self.tabs.count() < 2:
            return
        self.tabs.removeTab(i)

    def update_urlbar(self, q, browser=None):
        if browser != self.tabs.currentWidget():
            return
        self.url_bar.setText(q.toString())
        self.url_bar.setCursorPosition(0)

    def update_title(self, browser):
        if browser != self.tabs.currentWidget():
            return
        current = self.current_browser()
        if current:
            title = current.page().title()
            self.setWindowTitle(f"{title} - NeuroLit")

    def current_browser(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, BrowserTab):
            return widget.browser
        return None

    def _is_descendant_of(self, item, ancestor):
        """Check if item is a descendant of ancestor in the tree."""
        current = item.parent()
        while current is not None:
            if current == ancestor:
                return True
            current = current.parent()
        return False

    def sidebar_tree_item_clicked(self, item, column):
        """Handle clicks on tree items."""
        parent = item.parent()

        if parent is None:
            # Top-level item clicked
            text = item.text(0)
            if text == "Feeds":
                self.feed_page = 0
                self.bookmarks_btn_container.hide()
                self.history_container.hide()
                self.show_feeds()
            elif text == "Bookmarks":
                self.feeds_container.hide()
                self.history_container.hide()
                self.bookmarks_btn_container.show()
                # Toggle expand/collapse
                if item.isExpanded():
                    self.sidebar_tree.collapseItem(item)
                else:
                    self.sidebar_tree.expandItem(item)
            elif text == "History":
                self.feeds_container.hide()
                self.bookmarks_btn_container.hide()
                self.history_container.show()
                # Load selected text from browser
                browser = self.current_browser()
                if browser:
                    browser.page().runJavaScript(
                        "window.getSelection().toString();",
                        self._on_history_text_ready
                    )
                # Toggle expand/collapse
                if item.isExpanded():
                    self.sidebar_tree.collapseItem(item)
                else:
                    self.sidebar_tree.expandItem(item)
            else:
                self.feeds_container.hide()
                self.bookmarks_btn_container.hide()
                self.history_container.hide()
        elif self._is_descendant_of(item, self.bookmarks_tree_item):
            # Bookmark item or subfolder clicked
            role = item.data(0, Qt.UserRole)
            if role == "__folder__":
                # Subfolder - toggle expand/collapse
                if item.isExpanded():
                    self.sidebar_tree.collapseItem(item)
                else:
                    self.sidebar_tree.expandItem(item)
            elif role:
                # Bookmark child clicked - navigate to URL
                title = item.text(0)
                self.add_new_tab(QUrl(role), title)
        elif self._is_descendant_of(item, self.history_tree_item):
            # History item or subfolder clicked
            role = item.data(0, Qt.UserRole)
            if role == "__folder__":
                # Subfolder - toggle expand/collapse
                if item.isExpanded():
                    self.sidebar_tree.collapseItem(item)
                else:
                    self.sidebar_tree.expandItem(item)
            elif role:
                # History child clicked - load file content
                self.history_file_clicked_by_name(role)

    def sidebar_tree_item_expanded(self, item):
        """Handle tree item expansion."""
        text = item.text(0)
        if text == "Bookmarks":
            self.bookmarks_btn_container.show()
        elif text == "History":
            self.history_container.show()

    def populate_bookmarks_tree(self):
        """Populate the Bookmarks tree folder with items from data/bookmarks.txt.
        
        File format supports subfolders:
            [FolderName]        - defines a subfolder
            Title|URL           - bookmark item (under current folder or root)
        """
        # Remove existing children
        self.bookmarks_tree_item.takeChildren()

        bookmarks_file = os.path.join(self.data_dir, "bookmarks.txt")
        if not os.path.isfile(bookmarks_file):
            # Create default bookmarks file
            os.makedirs(self.data_dir, exist_ok=True)
            with open(bookmarks_file, 'w', encoding='utf-8') as f:
                f.write("OpenSpeedTest.Ru|https://openspeedtest.ru\n")

        try:
            current_folder = None
            with open(bookmarks_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # Subfolder header
                    if line.startswith('[') and line.endswith(']'):
                        folder_name = line[1:-1].strip()
                        if folder_name:
                            current_folder = QTreeWidgetItem(self.bookmarks_tree_item, [folder_name])
                            current_folder.setData(0, Qt.UserRole, "__folder__")
                            current_folder.setFlags(current_folder.flags() | Qt.ItemIsEnabled)
                        continue
                    # End of folder block
                    if line == '[]':
                        current_folder = None
                        continue
                    # Bookmark entry
                    if '|' in line:
                        title, url = line.split('|', 1)
                    else:
                        title = line
                        url = line
                    parent = current_folder if current_folder else self.bookmarks_tree_item
                    child = QTreeWidgetItem(parent, [title.strip()])
                    child.setData(0, Qt.UserRole, url.strip())
                    child.setToolTip(0, url.strip())
        except Exception as e:
            print(f"Error loading bookmarks: {e}")

    def populate_history_tree(self):
        """Populate the History tree folder with .txt files from data/history/ and its subdirectories."""
        self.history_tree_item.takeChildren()

        history_dir = os.path.join(self.data_dir, "history")
        if not os.path.isdir(history_dir):
            return

        # Add subdirectories as subfolders
        entries = sorted(os.listdir(history_dir))
        subdirs = [d for d in entries if os.path.isdir(os.path.join(history_dir, d))]
        for subdir in subdirs:
            folder_item = QTreeWidgetItem(self.history_tree_item, [subdir])
            folder_item.setData(0, Qt.UserRole, "__folder__")
            folder_item.setFlags(folder_item.flags() | Qt.ItemIsEnabled)
            subdir_path = os.path.join(history_dir, subdir)
            sub_files = sorted(
                [f for f in os.listdir(subdir_path) if f.endswith(".txt")],
                reverse=True
            )
            for fname in sub_files:
                display_name = os.path.splitext(fname)[0]
                child = QTreeWidgetItem(folder_item, [display_name])
                child.setData(0, Qt.UserRole, os.path.join(subdir, fname))
                child.setToolTip(0, fname)

        # Add root-level files
        all_files = sorted(
            [f for f in entries if f.endswith(".txt") and os.path.isfile(os.path.join(history_dir, f))],
            reverse=True
        )

        for fname in all_files:
            display_name = os.path.splitext(fname)[0]
            child = QTreeWidgetItem(self.history_tree_item, [display_name])
            child.setData(0, Qt.UserRole, fname)
            child.setToolTip(0, fname)

    def refresh_history_tree(self):
        """Refresh the history tree items."""
        self.populate_history_tree()
        self.status_bar.showMessage("History list refreshed.")

    def remove_selected_bookmark(self):
        """Remove the currently selected bookmark from the tree and file."""
        selected = self.sidebar_tree.currentItem()
        if not selected:
            return
        # Check if it's a direct child of bookmarks or a child of a bookmark subfolder
        if self._is_descendant_of(selected, self.bookmarks_tree_item):
            role = selected.data(0, Qt.UserRole)
            if role == "__folder__":
                # Remove entire subfolder
                parent = selected.parent()
                idx = parent.indexOfChild(selected)
                if idx >= 0:
                    parent.takeChild(idx)
                    self.save_bookmarks_from_tree()
                    self.status_bar.showMessage(f"Bookmark folder '{selected.text(0)}' removed.")
            else:
                # Remove individual bookmark
                parent = selected.parent()
                idx = parent.indexOfChild(selected)
                if idx >= 0:
                    parent.takeChild(idx)
                    self.save_bookmarks_from_tree()
                    self.status_bar.showMessage("Bookmark removed.")

    def history_file_clicked_by_name(self, fname):
        """Load the content of a history file into the text area."""
        file_path = os.path.join(self.data_dir, "history", fname)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.history_text.setPlainText(content)
            self.history_title_input.setText(os.path.splitext(fname)[0])
            self.history_container.show()
            self.status_bar.showMessage(f"Loaded {fname}")
        except Exception as e:
            self.status_bar.showMessage(f"Error reading {fname}: {e}")

    def show_feeds(self):
        self.feeds_list.clear()
        file_path = "data/feeds.csv"
        if not os.path.isfile(file_path):
            return
        
        all_feeds = []
        try:
            with open(file_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    all_feeds.append(row['url'])
        except Exception as e:
            print(f"Error reading feeds: {e}")
            return

        start = self.feed_page * 10
        end = start + 10
        page_feeds = all_feeds[start:end]
        
        for feed in page_feeds:
            self.feeds_list.addItem(feed)
            
        self.feeds_back_btn.setEnabled(self.feed_page > 0)
        self.feeds_next_btn.setEnabled(end < len(all_feeds))
        self.feeds_container.show()

    def next_feeds_page(self):
        self.feed_page += 1
        self.show_feeds()

    def prev_feeds_page(self):
        self.feed_page -= 1
        self.show_feeds()

    def feed_item_clicked(self, item):
        feed_url = item.text()
        # Convert URL to filename logic
        safe_name = feed_url.replace("http://", "").replace("https://", "").replace("/", "_").replace(".", "_").replace("?", "_").replace("&", "_").replace("=", "_")
        csv_path = f"data/feeds/{safe_name}.csv"
        
        if os.path.exists(csv_path):
            self.add_csv_tab(csv_path, os.path.basename(csv_path))
        else:
            found = False
            if os.path.exists("data/feeds"):
                for f in os.listdir("data/feeds"):
                    if f.endswith(".csv") and safe_name[:20] in f:
                        self.add_csv_tab(os.path.join("data/feeds", f), f)
                        found = True
                        break
            if not found:
                print(f"CSV not found for feed: {feed_url} (expected {csv_path})")
                self.add_new_tab(QUrl(feed_url), "Feed URL")

    def navigate_home(self):
        browser = self.current_browser()
        if browser:
            browser.setUrl(QUrl("https://www.google.com/search?q=&udm=50&hl=ru"))
        else:
            self.add_new_tab(QUrl("https://www.google.com/search?q=&udm=50&hl=ru"), "Homepage")

    def navigate_to_url(self):
        url_text = self.url_bar.text().strip()
        if not url_text.startswith(("http://", "https://")):
            url_text = "http://" + url_text
        
        q = QUrl(url_text)
        browser = self.current_browser()
        if browser:
            browser.setUrl(q)
        else:
            self.add_new_tab(q, "New Tab")

    def set_proxy(self):
        proxy_url = self.proxy_input.text().strip()
        print(f"Setting proxy to: {proxy_url}")
        proxy = QNetworkProxy()
        
        if proxy_url:
            if "://" not in proxy_url:
                proxy_url = "http://" + proxy_url
            url = QUrl(proxy_url)
            proxy.setType(QNetworkProxy.HttpProxy)
            proxy.setHostName(url.host())
            proxy.setPort(url.port() if url.port() != -1 else 8080)
            proxy.setUser(url.userName())
            proxy.setPassword(url.password())
        else:
            proxy.setType(QNetworkProxy.NoProxy)
            
        QNetworkProxy.setApplicationProxy(proxy)

    def get_rss(self):
        rss_url = self.rss_input.text().strip()
        proxy_url = self.proxy_input.text().strip()
        print(f"Fetching RSS from: {rss_url}")
        
        if rss_url:
            if not rss_url.startswith(("http://", "https://")):
                rss_url = "http://" + rss_url
            
            self.save_feed_to_csv(rss_url, "RSS Feed", proxy_url)
            self.add_new_tab(QUrl(rss_url), "RSS Feed")

    def run_fetch_rss(self):
        print("Running fetchrss.py...")
        try:
            subprocess.Popen([sys.executable, "fetchrss.py"])
        except Exception as e:
            print(f"Error running fetchrss.py: {e}")

    def run_change_rss(self):
        print("Running change_rss.py...")
        try:
            subprocess.Popen([sys.executable, "change_rss.py"])
        except Exception as e:
            print(f"Error running change_rss.py: {e}")

    def save_feed_to_csv(self, url, description, proxy):
        file_path = "data/feeds.csv"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        rows = []
        updated = False
        header = ["url", "description", "proxy"]
        
        if os.path.isfile(file_path):
            with open(file_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    if row['url'] == url:
                        row['description'] = description
                        row['proxy'] = proxy
                        updated = True
                    rows.append(row)
        
        if not updated:
            rows.append({"url": url, "description": description, "proxy": proxy})
            
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header, delimiter='\t')
            writer.writeheader()
            writer.writerows(rows)

    def save_bookmarks_from_tree(self):
        """Save all bookmarks from the tree widget to data/bookmarks.txt.
        
        Supports subfolders using [FolderName] / [] block format.
        """
        bookmarks_file = os.path.join(self.data_dir, "bookmarks.txt")
        os.makedirs(self.data_dir, exist_ok=True)
        try:
            with open(bookmarks_file, 'w', encoding='utf-8') as f:
                for i in range(self.bookmarks_tree_item.childCount()):
                    child = self.bookmarks_tree_item.child(i)
                    role = child.data(0, Qt.UserRole)
                    if role == "__folder__":
                        # Write subfolder header
                        f.write(f"[{child.text(0)}]\n")
                        # Write children of this subfolder
                        for j in range(child.childCount()):
                            sub_child = child.child(j)
                            title = sub_child.text(0)
                            url = sub_child.data(0, Qt.UserRole) or ""
                            f.write(f"{title}|{url}\n")
                        f.write("[]\n")
                    else:
                        title = child.text(0)
                        url = role or ""
                        f.write(f"{title}|{url}\n")
        except Exception as e:
            print(f"Error saving bookmarks: {e}")

    def _check_bookmark_duplicate(self, parent_item, url):
        """Recursively check for duplicate bookmark URL under parent_item."""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            role = child.data(0, Qt.UserRole)
            if role == "__folder__":
                if self._check_bookmark_duplicate(child, url):
                    return True
            elif role == url:
                return True
        return False

    def add_current_page_bookmark(self):
        """Add the current page as a bookmark to the tree and file.
        
        If a bookmark subfolder is currently selected, the bookmark is added there.
        """
        browser = self.current_browser()
        if not browser:
            return

        url = browser.url().toString()
        title = browser.page().title() or url

        # Check for duplicates across all bookmarks (including subfolders)
        if self._check_bookmark_duplicate(self.bookmarks_tree_item, url):
            self.status_bar.showMessage("Bookmark already exists.")
            return

        # Determine target parent: selected subfolder or root bookmarks
        target = self.bookmarks_tree_item
        selected = self.sidebar_tree.currentItem()
        if selected and self._is_descendant_of(selected, self.bookmarks_tree_item):
            if selected.data(0, Qt.UserRole) == "__folder__":
                target = selected
            elif selected.parent() and selected.parent().data(0, Qt.UserRole) == "__folder__":
                target = selected.parent()

        # Add to tree
        child = QTreeWidgetItem(target, [title])
        child.setData(0, Qt.UserRole, url)
        child.setToolTip(0, url)

        # Save to file
        self.save_bookmarks_from_tree()
        self.sidebar_tree.expandItem(self.bookmarks_tree_item)
        if target != self.bookmarks_tree_item:
            self.sidebar_tree.expandItem(target)
        self.status_bar.showMessage(f"Bookmarked: {title}")

    def _on_history_text_ready(self, text):
        """Callback when selected text is extracted from the browser."""
        if text:
            self.history_text.setPlainText(text)

    def save_history(self):
        """Save the history text to data/history/{title}.txt.
        
        If a history subfolder is selected, saves into that subfolder.
        """
        title = self.history_title_input.text().strip()
        if not title:
            self.status_bar.showMessage("Please enter a title for the history entry.")
            return

        # Sanitize filename
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_title:
            self.status_bar.showMessage("Invalid title. Use alphanumeric characters.")
            return

        # Determine target directory: selected subfolder or root history
        history_dir = os.path.join(self.data_dir, "history")
        target_dir = history_dir
        selected = self.sidebar_tree.currentItem()
        if selected and self._is_descendant_of(selected, self.history_tree_item):
            role = selected.data(0, Qt.UserRole)
            if role == "__folder__":
                target_dir = os.path.join(history_dir, selected.text(0))
            elif selected.parent() and selected.parent().data(0, Qt.UserRole) == "__folder__":
                target_dir = os.path.join(history_dir, selected.parent().text(0))

        os.makedirs(target_dir, exist_ok=True)

        file_path = os.path.join(target_dir, f"{safe_title}.txt")
        content = self.history_text.toPlainText()

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.status_bar.showMessage(f"Saved to {file_path}")
            self.populate_history_tree()
        except Exception as e:
            self.status_bar.showMessage(f"Error saving history: {e}")

    # ---- Context Menu for Sidebar Tree ----

    def sidebar_context_menu(self, position):
        """Show context menu for sidebar tree items (right-click)."""
        item = self.sidebar_tree.itemAt(position)
        if not item:
            return

        menu = QMenu(self)

        # Context menu for Bookmarks top-level
        if item == self.bookmarks_tree_item:
            add_folder_action = menu.addAction("Add Subfolder")
            add_folder_action.triggered.connect(lambda: self._add_bookmark_subfolder(self.bookmarks_tree_item))
            menu.exec(self.sidebar_tree.viewport().mapToGlobal(position))
            return

        # Context menu for History top-level
        if item == self.history_tree_item:
            add_folder_action = menu.addAction("Add Subfolder")
            add_folder_action.triggered.connect(self._add_history_subfolder)
            menu.exec(self.sidebar_tree.viewport().mapToGlobal(position))
            return

        # Context menu for bookmark subfolders
        if self._is_descendant_of(item, self.bookmarks_tree_item) and item.data(0, Qt.UserRole) == "__folder__":
            rename_action = menu.addAction("Rename Subfolder")
            rename_action.triggered.connect(lambda: self._rename_bookmark_subfolder(item))
            remove_action = menu.addAction("Remove Subfolder")
            remove_action.triggered.connect(lambda: self._remove_bookmark_subfolder(item))
            menu.exec(self.sidebar_tree.viewport().mapToGlobal(position))
            return

        # Context menu for history subfolders
        if self._is_descendant_of(item, self.history_tree_item) and item.data(0, Qt.UserRole) == "__folder__":
            rename_action = menu.addAction("Rename Subfolder")
            rename_action.triggered.connect(lambda: self._rename_history_subfolder(item))
            remove_action = menu.addAction("Remove Subfolder")
            remove_action.triggered.connect(lambda: self._remove_history_subfolder(item))
            menu.exec(self.sidebar_tree.viewport().mapToGlobal(position))
            return

    # ---- Bookmark Subfolder Management ----

    def _add_bookmark_subfolder(self, parent_item):
        """Add a new subfolder under the given bookmark parent item."""
        name, ok = QInputDialog.getText(self, "New Bookmark Subfolder", "Subfolder name:")
        if ok and name.strip():
            name = name.strip()
            folder = QTreeWidgetItem(parent_item, [name])
            folder.setData(0, Qt.UserRole, "__folder__")
            folder.setFlags(folder.flags() | Qt.ItemIsEnabled)
            self.sidebar_tree.expandItem(parent_item)
            self.save_bookmarks_from_tree()
            self.status_bar.showMessage(f"Bookmark subfolder '{name}' added.")

    def _rename_bookmark_subfolder(self, item):
        """Rename a bookmark subfolder."""
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "Rename Bookmark Subfolder", "New name:", text=old_name)
        if ok and new_name.strip():
            item.setText(0, new_name.strip())
            self.save_bookmarks_from_tree()
            self.status_bar.showMessage(f"Bookmark subfolder renamed to '{new_name.strip()}'.")

    def _remove_bookmark_subfolder(self, item):
        """Remove a bookmark subfolder and all its contents."""
        name = item.text(0)
        reply = QMessageBox.question(
            self, "Remove Bookmark Subfolder",
            f"Remove subfolder '{name}' and all its bookmarks?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            parent = item.parent()
            idx = parent.indexOfChild(item)
            if idx >= 0:
                parent.takeChild(idx)
                self.save_bookmarks_from_tree()
                self.status_bar.showMessage(f"Bookmark subfolder '{name}' removed.")

    # ---- History Subfolder Management ----

    def _add_history_subfolder(self):
        """Add a new subfolder (subdirectory) under data/history/."""
        name, ok = QInputDialog.getText(self, "New History Subfolder", "Subfolder name:")
        if ok and name.strip():
            safe_name = "".join(c for c in name.strip() if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_name:
                self.status_bar.showMessage("Invalid folder name.")
                return
            folder_path = os.path.join(self.data_dir, "history", safe_name)
            try:
                os.makedirs(folder_path, exist_ok=True)
                self.populate_history_tree()
                self.sidebar_tree.expandItem(self.history_tree_item)
                self.status_bar.showMessage(f"History subfolder '{safe_name}' created.")
            except Exception as e:
                self.status_bar.showMessage(f"Error creating folder: {e}")

    def _rename_history_subfolder(self, item):
        """Rename a history subfolder (subdirectory)."""
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "Rename History Subfolder", "New name:", text=old_name)
        if ok and new_name.strip():
            safe_name = "".join(c for c in new_name.strip() if c.isalnum() or c in (' ', '-', '_')).strip()
            if not safe_name:
                self.status_bar.showMessage("Invalid folder name.")
                return
            old_path = os.path.join(self.data_dir, "history", old_name)
            new_path = os.path.join(self.data_dir, "history", safe_name)
            if os.path.exists(new_path):
                self.status_bar.showMessage(f"Folder '{safe_name}' already exists.")
                return
            try:
                os.rename(old_path, new_path)
                self.populate_history_tree()
                self.status_bar.showMessage(f"History subfolder renamed to '{safe_name}'.")
            except Exception as e:
                self.status_bar.showMessage(f"Error renaming folder: {e}")

    def _remove_history_subfolder(self, item):
        """Remove a history subfolder (subdirectory) and all its files."""
        name = item.text(0)
        reply = QMessageBox.question(
            self, "Remove History Subfolder",
            f"Remove subfolder '{name}' and all its files?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            folder_path = os.path.join(self.data_dir, "history", name)
            try:
                shutil.rmtree(folder_path)
                self.populate_history_tree()
                self.status_bar.showMessage(f"History subfolder '{name}' removed.")
            except Exception as e:
                self.status_bar.showMessage(f"Error removing folder: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("NeuroLit - Neuronet Literature")
    
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.png")
    app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
