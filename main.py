import sys
import os
import csv
import subprocess
from PySide6.QtCore import QUrl, Qt, QTimer, QDateTime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QToolBar, QLineEdit,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
    QStatusBar, QDockWidget, QListWidget, QHBoxLayout,
    QLabel, QFrame
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage
from PySide6.QtNetwork import QNetworkProxy
from csv_viewer import CSVViewerTab

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
        self.resize(1200, 800)
        self.feed_page = 0

        # Persistent profile for cookie/session storage
        storage_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "profile")
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

        # RSS Reader Section
        rss_label = QLabel("<b>RSS Reader</b>")
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

        # Status Bar
        self.setStatusBar(QStatusBar())

        # Initial Tab
        self.add_new_tab(QUrl("http://www.google.com"), "Homepage")

        # Setup Scheduled Fetching
        self.fetch_timer = QTimer(self)
        self.fetch_timer.timeout.connect(self.check_schedule)
        self.fetch_timer.start(60000)  # Check every minute

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
            qurl = QUrl("http://www.google.com")

        tab = BrowserTab(self, self.profile)
        tab.browser.setUrl(qurl)
        
        i = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(i)

        # Update URL bar when URL changes
        tab.browser.urlChanged.connect(lambda qurl, tab=tab: self.update_urlbar(qurl, tab))
        # Update tab title when page title changes
        tab.browser.loadFinished.connect(lambda _, i=i, tab=tab: self.update_tab_title(i, tab))

        return tab.browser

    def add_csv_tab(self, file_path, label="CSV Viewer"):
        tab = CSVViewerTab(file_path, self)
        i = self.tabs.addTab(tab, label)
        self.tabs.setCurrentIndex(i)
        self.setWindowTitle(f"{label} - NeuroLit")

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
        elif isinstance(widget, CSVViewerTab):
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
        title = self.current_browser().page().title()
        self.setWindowTitle(f"{title} - NeuroLit")

    def current_browser(self):
        widget = self.tabs.currentWidget()
        if isinstance(widget, BrowserTab):
            return widget.browser
        return None

    def sidebar_item_clicked(self, item):
        if item.text() == "Feeds":
            self.feed_page = 0
            self.show_feeds()
        else:
            self.feeds_container.hide()

    def show_feeds(self):
        self.feeds_list.clear()
        file_path = "data/feeds.csv"
        if not os.path.isfile(file_path):
            return

        all_feeds = []
        with open(file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                all_feeds.append(row['url'])

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
        # Convert URL to filename as fetchrss.py likely does
        # e.g. http://habr.com/rss/all -> habr_com_rss_all.csv
        safe_name = feed_url.replace("http://", "").replace("https://", "").replace("/", "_").replace(".", "_").replace("?", "_").replace("&", "_").replace("=", "_")
        csv_path = f"data/feeds/{safe_name}.csv"
        
        if os.path.exists(csv_path):
            self.add_csv_tab(csv_path, os.path.basename(csv_path))
        else:
            # Try to find it by partial match if exact safe name fails
            found = False
            if os.path.exists("data/feeds"):
                for f in os.listdir("data/feeds"):
                    if f.endswith(".csv") and safe_name[:20] in f:
                        self.add_csv_tab(os.path.join("data/feeds", f), f)
                        found = True
                        break
            
            if not found:
                print(f"CSV not found for feed: {feed_url} (expected {csv_path})")
                # Fallback to opening the URL in a browser tab
                self.add_new_tab(QUrl(feed_url), "Feed URL")

    def navigate_home(self):
        self.current_browser().setUrl(QUrl("http://www.google.com"))

    def navigate_to_url(self):
        url_text = self.url_bar.text().strip()
        if not url_text.startswith(("http://", "https://")):
            url_text = "http://" + url_text
        
        q = QUrl(url_text)
        self.current_browser().setUrl(q)

    def set_proxy(self):
        proxy_url = self.proxy_input.text().strip()
        print(f"Setting proxy to: {proxy_url}")
        
        proxy = QNetworkProxy()
        if proxy_url:
            # Expected format: http://user:pass@host:port or http://host:port
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

        # Apply globally to the application network access
        QNetworkProxy.setApplicationProxy(proxy)

    def get_rss(self):
        rss_url = self.rss_input.text().strip()
        proxy_url = self.proxy_input.text().strip()
        print(f"Fetching RSS from: {rss_url}")
        
        if rss_url:
            if not rss_url.startswith(("http://", "https://")):
                rss_url = "http://" + rss_url
            
            # Save to CSV
            self.save_feed_to_csv(rss_url, "RSS Feed", proxy_url)
            
            self.add_new_tab(QUrl(rss_url), "RSS Feed")

    def run_fetch_rss(self):
        print("Running fetchrss.py...")
        try:
            # Run fetchrss.py as a separate process
            subprocess.Popen([sys.executable, "fetchrss.py"])
        except Exception as e:
            print(f"Error running fetchrss.py: {e}")
    
    def run_change_rss(self):
        print("Running change_rss.py...")
        try:
            # Run change_rss.py as a separate process
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("NeuroLit - Neuronet Literature")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
