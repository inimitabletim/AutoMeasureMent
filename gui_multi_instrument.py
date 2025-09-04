#!/usr/bin/env python3
"""
多儀器控制系統 GUI 主程式
支援 Keithley 2461 和 Rigol DP711 的統一控制介面
"""

import sys
import logging
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTabWidget, QLabel, QPushButton,
                            QLineEdit, QMessageBox, QStatusBar, QFrame)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont

from src.keithley_2461 import Keithley2461
from src.rigol_dp711 import RigolDP711
from src.data_logger import DataLogger
from src.theme_manager import ThemeManager, ThemeStyleSheet
from src.instrument_base import InstrumentManager
# 使用Professional版本Widget
from widgets.keithley_widget_professional import ProfessionalKeithleyWidget
from widgets.rigol_widget import RigolControlWidget


class InstrumentStatusWidget(QFrame):
    """儀器狀態顯示 widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.instrument_manager = InstrumentManager()
        
    def setup_ui(self):
        """設置狀態欄 UI"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # 儀器狀態標籤
        self.keithley_status = QLabel("🔴 Keithley 2461: 未連接")
        self.keithley_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        layout.addWidget(self.keithley_status)
        
        layout.addWidget(QLabel(" | "))
        
        self.dp711_status = QLabel("🔴 Rigol DP711: 未連接")
        self.dp711_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        layout.addWidget(self.dp711_status)
        
        # 彈性空間
        layout.addStretch()
        
        # 控制按鈕
        self.disconnect_all_btn = QPushButton("全部斷開")
        self.disconnect_all_btn.setMaximumWidth(100)
        self.disconnect_all_btn.clicked.connect(self.disconnect_all)
        layout.addWidget(self.disconnect_all_btn)
        
        self.emergency_stop_btn = QPushButton("緊急停止")
        self.emergency_stop_btn.setMaximumWidth(100)
        self.emergency_stop_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        layout.addWidget(self.emergency_stop_btn)
        
        # 設置框架樣式
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        
    def update_keithley_status(self, connected: bool, info: str = ""):
        """更新 Keithley 狀態"""
        if connected:
            self.keithley_status.setText(f"🟢 Keithley 2461: 已連接 {info}")
            self.keithley_status.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.keithley_status.setText("🔴 Keithley 2461: 未連接")
            self.keithley_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            
    def update_dp711_status(self, connected: bool, info: str = ""):
        """更新 DP711 狀態"""
        if connected:
            self.dp711_status.setText(f"🟢 Rigol DP711: 已連接 {info}")
            self.dp711_status.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.dp711_status.setText("🔴 Rigol DP711: 未連接")
            self.dp711_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            
    def disconnect_all(self):
        """安全斷開所有儀器連接"""
        # 檢查是否有儀器正在輸出
        active_outputs = []
        
        # 使用正確的主視窗引用
        if hasattr(self, 'main_window') and self.main_window:
            main_window = self.main_window
            
            # 檢查Keithley是否正在測量
            kw = main_window.keithley_widget
            if hasattr(kw, 'is_measuring') and kw.is_measuring:
                active_outputs.append("Keithley 2461")
                
            # 檢查Rigol是否正在輸出
            rw = main_window.rigol_widget  
            if hasattr(rw, 'output_enabled') and getattr(rw, 'output_enabled', False):
                active_outputs.append("Rigol DP711")
        
        # 如果有活動輸出，先警告用戶
        if active_outputs:
            reply = QMessageBox.question(
                self,
                "安全確認",
                f"檢測到以下儀器正在輸出:\n{', '.join(active_outputs)}\n\n"
                "斷開連接將自動關閉所有輸出。\n是否繼續？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            # 安全斷開序列
            self.instrument_manager.disconnect_all()
            self.update_keithley_status(False)
            self.update_dp711_status(False)
            
            # 通知各個 widget 斷開連接
            if hasattr(self, 'main_window') and self.main_window:
                main_window = self.main_window
                
                # 停止Keithley測量並斷開
                if hasattr(main_window, 'keithley_widget'):
                    main_window.keithley_widget.stop_measurement()
                    main_window.keithley_widget.disconnect_device()
                    
                # 停止Rigol輸出並斷開
                if hasattr(main_window, 'rigol_widget'):
                    main_window.rigol_widget.disconnect_device()
            
            # 顯示操作完成提示
            if active_outputs:
                QMessageBox.information(self, "斷開完成", "所有儀器輸出已安全關閉並斷開連接。")
                    
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"斷開連接時發生錯誤: {str(e)}")
            
    def emergency_stop(self):
        """緊急停止所有儀器輸出"""
        reply = QMessageBox.question(
            self,
            "緊急停止",
            "確定要緊急停止所有儀器輸出嗎？\n這將立即關閉所有電源輸出！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 緊急關閉所有輸出
            if hasattr(self, 'main_window') and self.main_window:
                main_window = self.main_window
                
                try:
                    # 緊急停止Keithley
                    if hasattr(main_window, 'keithley_widget'):
                        kw = main_window.keithley_widget
                        kw.stop_measurement()  # 停止測量
                        if kw.keithley and kw.keithley.connected:
                            kw.keithley.output_off()  # 關閉輸出
                            
                    # 緊急停止Rigol
                    if hasattr(main_window, 'rigol_widget'):
                        rw = main_window.rigol_widget
                        if rw.dp711 and hasattr(rw.dp711, 'output_off'):
                            rw.dp711.output_off()
                            
                except Exception as e:
                    print(f"緊急停止錯誤: {e}")
                    
            QMessageBox.information(self, "緊急停止", "所有儀器輸出已緊急關閉！")





class InstrumentManagementWidget(QWidget):
    """儀器管理 widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """設置儀器管理介面"""
        layout = QVBoxLayout(self)
        
        title = QLabel("儀器管理中心")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 占位內容
        placeholder = QLabel("儀器設定、診斷、校準功能\n(待實作)")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(placeholder)
        
        layout.addStretch()


class DataCenterWidget(QWidget):
    """數據中心 widget"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """設置數據中心介面"""
        layout = QVBoxLayout(self)
        
        title = QLabel("數據中心")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 占位內容
        placeholder = QLabel("綜合圖表、數據匯出、比較分析\n(待實作)")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(placeholder)
        
        layout.addStretch()


class MultiInstrumentGUI(QMainWindow):
    """多儀器控制系統主視窗"""
    
    def __init__(self):
        super().__init__()
        
        # 設置 logger
        self.logger = logging.getLogger(__name__)
        
        # 主題管理
        self.theme_manager = ThemeManager()
        self.current_theme = self.theme_manager.get_current_theme()
        
        # 數據記錄器
        self.data_logger = DataLogger()
        
        self.setup_ui()
        self.setup_logging()
        
    def setup_ui(self):
        """設置用戶介面"""
        self.setWindowTitle("多儀器控制系統 - Keithley 2461 & Rigol DP711")
        
        # 設置視窗尺寸限制，避免幾何警告
        self.setMinimumSize(1200, 700)  # 設置最小尺寸
        self.resize(1400, 900)  # 設置預設尺寸，讓系統自動調整
        
        # 讓視窗居中顯示
        QTimer.singleShot(100, self.center_on_screen)  # 延遲執行以確保視窗已創建
        
        # 創建中央 widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 創建標籤頁 widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        
        # 創建各個控制 widget
        self.keithley_widget = ProfessionalKeithleyWidget()
        self.keithley_widget.set_theme(self.current_theme)
        
        self.rigol_widget = RigolControlWidget()
        self.rigol_widget.set_theme(self.current_theme)
        
        self.management_widget = InstrumentManagementWidget()
        self.data_center_widget = DataCenterWidget()
        
        # 添加標籤頁
        self.tab_widget.addTab(self.keithley_widget, "Keithley 2461")
        self.tab_widget.addTab(self.rigol_widget, "Rigol DP711")
        self.tab_widget.addTab(self.management_widget, "儀器管理")
        self.tab_widget.addTab(self.data_center_widget, "數據中心")
        
        main_layout.addWidget(self.tab_widget)
        
        # 儀器狀態欄
        self.status_widget = InstrumentStatusWidget()
        # 將主視窗的參考傳給狀態欄
        self.status_widget.main_window = self
        main_layout.addWidget(self.status_widget)
        
        # 連接信號
        self.keithley_widget.connection_changed.connect(self.status_widget.update_keithley_status)
        self.rigol_widget.connection_changed.connect(self.status_widget.update_dp711_status)
        
        # 將主視窗的參考傳給狀態欄，讓按鈕能正確訪問widgets
        self.status_widget.main_window = self
        
        # 應用主題
        self.apply_theme()
        
        # 狀態欄
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage(f"多儀器控制系統已啟動 - 主題: {self.current_theme}")
        
    def setup_logging(self):
        """設置日誌系統"""
        # 簡化的日誌設置
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('multi_instrument_control.log')
            ]
        )
        
        self.logger.info("多儀器控制系統啟動")
        self.logger.info(f"系統主題: {self.current_theme}")
        
    def apply_theme(self):
        """應用主題樣式"""
        stylesheet = ThemeStyleSheet.get_stylesheet(self.current_theme)
        self.setStyleSheet(stylesheet)
        
        # 標籤頁特殊樣式
        tab_style = """
            QTabWidget::pane {
                border: 1px solid #cccccc;
                border-radius: 4px;
                margin-top: -1px;
            }
            QTabBar::tab {
                background: #f0f0f0;
                border: 1px solid #cccccc;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom-color: #ffffff;
            }
            QTabBar::tab:hover {
                background: #e6e6e6;
            }
        """
        
        if self.current_theme == "dark":
            tab_style = tab_style.replace("#f0f0f0", "#404040")
            tab_style = tab_style.replace("#ffffff", "#2b2b2b")
            tab_style = tab_style.replace("#cccccc", "#555555")
            tab_style = tab_style.replace("#e6e6e6", "#4a4a4a")
            
        self.tab_widget.setStyleSheet(tab_style)
        
    def closeEvent(self, event):
        """關閉事件處理"""
        reply = QMessageBox.question(
            self,
            "確認退出",
            "確定要退出多儀器控制系統嗎？\n程式將自動斷開所有儀器連接",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 直接斷開所有連接，無需再次確認
            try:
                # 停止所有測量工作
                if hasattr(self.keithley_widget, 'measurement_worker') and self.keithley_widget.measurement_worker:
                    self.keithley_widget.measurement_worker.stop_measurement()
                if hasattr(self.rigol_widget, 'measurement_worker') and self.rigol_widget.measurement_worker:
                    self.rigol_widget.measurement_worker.stop_measurement()
                
                # 斷開儀器連接
                if hasattr(self.keithley_widget, 'keithley') and self.keithley_widget.keithley:
                    self.keithley_widget.keithley.disconnect()
                if hasattr(self.rigol_widget, 'dp711') and self.rigol_widget.dp711:
                    self.rigol_widget.dp711.disconnect()
                    
                self.logger.info("所有儀器連接已自動斷開")
            except Exception as e:
                self.logger.error(f"斷開連接時發生錯誤: {e}")
            
            self.logger.info("多儀器控制系統正常關閉")
            event.accept()
        else:
            event.ignore()
            
    def center_on_screen(self):
        """將視窗居中顯示在螢幕上"""
        try:
            # 獲取螢幕幾何資訊
            screen = QApplication.primaryScreen()
            screen_geometry = screen.availableGeometry()
            
            # 計算居中位置
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            
            # 移動視窗到居中位置
            self.move(window_geometry.topLeft())
        except Exception as e:
            self.logger.debug(f"視窗居中失敗: {e}")
            # 使用備用位置
            self.move(100, 100)


def main():
    """主程式入口"""
    app = QApplication(sys.argv)
    app.setApplicationName("Multi-Instrument Control System")
    app.setApplicationVersion("1.0")
    
    
    # 創建主視窗
    window = MultiInstrumentGUI()
    window.show()
    
    # 運行應用程式
    sys.exit(app.exec())


if __name__ == "__main__":
    main()