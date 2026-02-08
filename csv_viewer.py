import sys
import csv
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QHBoxLayout, QPushButton, QMenu
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

class CSVViewerTab(QWidget):
    def __init__(self, file_path, main_window):
        super().__init__()
        self.file_path = file_path
        self.main_window = main_window
        self.layout = QVBoxLayout(self)
        
        # Header info
        header_layout = QHBoxLayout()
        self.title_label = QLabel(f"<b>Viewing:</b> {os.path.basename(file_path)}")
        header_layout.addWidget(self.title_label)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self.load_csv)
        header_layout.addStretch()
        header_layout.addWidget(refresh_btn)
        
        self.layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d3d3d3;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d3d3d3;
                font-weight: bold;
                color: #008000;
            }
        """)
        self.table.verticalHeader().setVisible(True)
        self.layout.addWidget(self.table)
        
        # Context menu for links
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        self.load_csv()

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item and item.text().startswith("http"):
            menu = QMenu(self)
            open_action = menu.addAction("Open Link")
            action = menu.exec(self.table.viewport().mapToGlobal(pos))
            if action == open_action:
                # Open in a new tab within the application
                self.main_window.add_new_tab(QUrl(item.text()), "Loading...")

    def load_csv(self):
        if not os.path.exists(self.file_path):
            self.title_label.setText(f"<font color='red'>File not found: {self.file_path}</font>")
            return

        try:
            with open(self.file_path, mode='r', newline='', encoding='utf-8') as f:
                # Use tab as the explicit delimiter
                reader = csv.reader(f, delimiter='\t')
                data = list(reader)

            if not data:
                self.table.setRowCount(0)
                self.table.setColumnCount(0)
                return

            headers = data[0]
            rows = data[1:]

            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)
            self.table.setRowCount(len(rows))

            for row_idx, row_data in enumerate(rows):
                for col_idx, cell_data in enumerate(row_data):
                    # Simple "beautify": strip quotes and handle long text
                    clean_data = cell_data.strip('"')
                    item = QTableWidgetItem(clean_data)
                    
                    # If it looks like a link, make it blue
                    if clean_data.startswith("http"):
                        item.setForeground(Qt.blue)
                    
                    self.table.setItem(row_idx, col_idx, item)

            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
            self.table.horizontalHeader().setStretchLastSection(True)
            self.table.resizeColumnsToContents()
            
            # Limit column width for very long descriptions
            for i in range(self.table.columnCount()):
                header_text = self.table.horizontalHeaderItem(i).text().lower()
                if "title" in header_text:
                    if self.table.columnWidth(i) > 700:
                        self.table.setColumnWidth(i, 700)
                elif self.table.columnWidth(i) > 400:
                    self.table.setColumnWidth(i, 400)
                if "link" in header_text:
                    if self.table.columnWidth(i) > 40:
                        self.table.setColumnWidth(i, 40)
        except Exception as e:
            self.title_label.setText(f"<font color='red'>Error loading CSV: {str(e)}</font>")
