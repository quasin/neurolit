import sys
import os
import csv
import subprocess
import ctypes  # Для исправления иконки в панели задач

from PySide6.QtCore import QUrl, Qt, QTimer, QDateTime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QLineEdit,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
    QStatusBar, QDockWidget, QListWidget, QHBoxLayout,
    QLabel, QFrame, QSystemTrayIcon, QMenu  # Добавлены классы трея
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
        
        self.sidebar_list = QListWidget()
        self.sidebar_list.addItems(["Feeds", "History", "Bookmarks", "Settings"])
        self.sidebar_list.itemClicked.connect(self.sidebar_item_clicked)
        sidebar_layout.addWidget(self.sidebar_list)
        
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

        # Bookmarks Section (Hidden by default)
        self.bookmarks_container = QWidget()
        self.bookmarks_layout = QVBoxLayout(self.bookmarks_container)
        self.bookmarks_list = QListWidget()
        self.bookmarks_list.itemClicked.connect(self.bookmark_item_clicked)
        self.bookmarks_layout.addWidget(self.bookmarks_list)
        
        bookmarks_btn_layout = QHBoxLayout()
        add_bookmark_btn = QPushButton("+ Add Current Page")
        add_bookmark_btn.clicked.connect(self.add_current_page_bookmark)
        bookmarks_btn_layout.addWidget(add_bookmark_btn)
        
        self.bookmarks_layout.addLayout(bookmarks_btn_layout)
        self.bookmarks_container.hide()
        sidebar_layout.addWidget(self.bookmarks_container)

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
        
        return tab.browser.window()

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

    def sidebar_item_clicked(self, item):
        if item.text() == "Feeds":
            self.feed_page = 0
            self.bookmarks_container.hide()
            self.show_feeds()
        elif item.text() == "Bookmarks":
            self.feeds_container.hide()
            self.show_bookmarks()
        else:
            self.feeds_container.hide()
            self.bookmarks_container.hide()

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

    def load_bookmarks(self):
        file_path = "data/bookmarks.csv"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if not os.path.isfile(file_path):
            with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["title", "url"], delimiter='\t')
                writer.writeheader()
                writer.writerow({"title": "OpenSpeedTest.Ru", "url": "https://openspeedtest.ru"})
        
        bookmarks = []
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                bookmarks.append(row)
        return bookmarks

    def save_bookmarks(self, bookmarks):
        file_path = "data/bookmarks.csv"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["title", "url"], delimiter='\t')
            writer.writeheader()
            writer.writerows(bookmarks)

    def show_bookmarks(self):
        self.bookmarks_list.clear()
        bookmarks = self.load_bookmarks()
        for bm in bookmarks:
            self.bookmarks_list.addItem(f"{bm['title']} — {bm['url']}")
        self.bookmarks_container.show()

    def bookmark_item_clicked(self, item):
        text = item.text()
        if " — " in text:
            url = text.split(" — ", 1)[1]
        else:
            url = text
        self.add_new_tab(QUrl(url), text.split(" — ")[0] if " — " in text else "Bookmark")

    def add_current_page_bookmark(self):
        browser = self.current_browser()
        if not browser:
            return
        
        url = browser.url().toString()
        title = browser.page().title() or url
        bookmarks = self.load_bookmarks()
        
        for bm in bookmarks:
            if bm['url'] == url:
                return
        
        bookmarks.append({"title": title, "url": url})
        self.save_bookmarks(bookmarks)
        self.show_bookmarks()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("NeuroLit - Neuronet Literature")
    
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.png")
    app.setWindowIcon(QIcon(icon_path))
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())
