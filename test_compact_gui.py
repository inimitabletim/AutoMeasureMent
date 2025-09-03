#!/usr/bin/env python3
"""
測試簡潔版Keithley GUI界面
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon

from widgets.keithley_widget_compact import CompactKeithleyWidget
from src.keithley_2461 import Keithley2461
from src.unified_logger import get_logger


class CompactTestWindow(QMainWindow):
    """簡潔版測試主窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger("CompactTest")
        self.init_ui()
        
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("Keithley 2461 - 簡潔專業版")
        self.setMinimumSize(1000, 700)
        
        # 創建儀器實例
        keithley = Keithley2461()
        
        # 創建簡潔版Widget
        self.keithley_widget = CompactKeithleyWidget(keithley, self)
        
        # 設置為中央Widget
        self.setCentralWidget(self.keithley_widget)
        
        # 設置窗口圖標和樣式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2C3E50;
            }
        """)
        

def main():
    """主程序"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 使用Fusion風格獲得更好的外觀
    
    # 設置應用程式圖標
    app.setApplicationName("Keithley 2461 Compact")
    app.setApplicationVersion("2.0")
    
    # 創建主窗口
    window = CompactTestWindow()
    window.show()
    
    # 運行應用程式
    try:
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\n應用程式被用戶中斷")
        sys.exit(0)


if __name__ == "__main__":
    main()