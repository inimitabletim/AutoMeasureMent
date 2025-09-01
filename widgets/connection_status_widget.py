#!/usr/bin/env python3
"""
連線狀態顯示和控制 Widget
提供豐富的視覺反饋和用戶交互
"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QProgressBar, QFrame, QMessageBox)
from PyQt6.QtCore import QTimer, pyqtSignal, QPropertyAnimation, QRect
from PyQt6.QtGui import QFont, QColor, QPalette
import time


class ConnectionStatusWidget(QFrame):
    """連線狀態顯示Widget - 提供豐富的視覺反饋"""
    
    # 自定義信號
    connection_requested = pyqtSignal()
    disconnection_requested = pyqtSignal()
    connection_cancelled = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.connection_start_time = None
        
        # 動畫效果
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self._pulse_animation)
        
    def setup_ui(self):
        """設置UI"""
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)
        
        # 狀態顯示區域
        status_layout = QHBoxLayout()
        
        # 狀態指示器
        self.status_indicator = QLabel("🔴")
        self.status_indicator.setFont(QFont("Arial", 16))
        status_layout.addWidget(self.status_indicator)
        
        # 狀態文字
        self.status_text = QLabel("未連接")
        self.status_text.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.status_text.setStyleSheet("color: #e74c3c;")
        status_layout.addWidget(self.status_text)
        
        # 彈性空間
        status_layout.addStretch()
        
        # 計時器顯示
        self.timer_label = QLabel("")
        self.timer_label.setFont(QFont("Arial", 10))
        self.timer_label.setStyleSheet("color: #7f8c8d;")
        status_layout.addWidget(self.timer_label)
        
        layout.addLayout(status_layout)
        
        # 進度條（連線時顯示）
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #3498db;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # 進度描述
        self.progress_text = QLabel("")
        self.progress_text.setVisible(False)
        self.progress_text.setFont(QFont("Arial", 10))
        self.progress_text.setStyleSheet("color: #3498db; font-style: italic;")
        layout.addWidget(self.progress_text)
        
        # 按鈕區域
        button_layout = QHBoxLayout()
        
        # 主要操作按鈕
        self.main_button = QPushButton("連接")
        self.main_button.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.main_button.clicked.connect(self._on_main_button_clicked)
        self._update_main_button_style("connect")
        button_layout.addWidget(self.main_button)
        
        # 取消按鈕（連線時顯示）
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setFont(QFont("Arial", 11))
        self.cancel_button.clicked.connect(self.connection_cancelled.emit)
        self.cancel_button.setVisible(False)
        self._update_cancel_button_style()
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # 連線計時器
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self._update_connection_time)
        
    def set_disconnected_state(self):
        """設置為未連接狀態"""
        self.status_indicator.setText("🔴")
        self.status_text.setText("未連接")
        self.status_text.setStyleSheet("color: #e74c3c;")
        
        # 隱藏連線相關UI
        self._hide_connection_ui()
        
        # 更新按鈕
        self.main_button.setText("連接")
        self.main_button.setEnabled(True)
        self._update_main_button_style("connect")
        
        # 停止動畫和計時器
        self._stop_animations()
        
    def set_connecting_state(self):
        """設置為連線中狀態"""
        self.status_indicator.setText("🟡")
        self.status_text.setText("連線中...")
        self.status_text.setStyleSheet("color: #f39c12;")
        
        # 顯示連線UI
        self._show_connection_ui()
        
        # 更新按鈕
        self.main_button.setText("連線中")
        self.main_button.setEnabled(False)
        self._update_main_button_style("connecting")
        
        # 開始動畫和計時
        self._start_connection_tracking()
        
    def set_connected_state(self, device_info: str = ""):
        """設置為已連接狀態"""
        self.status_indicator.setText("🟢")
        status_text = "已連接"
        if device_info:
            status_text += f" - {device_info}"
        self.status_text.setText(status_text)
        self.status_text.setStyleSheet("color: #27ae60;")
        
        # 隱藏連線UI
        self._hide_connection_ui()
        
        # 更新按鈕
        self.main_button.setText("斷開連接")
        self.main_button.setEnabled(True)
        self._update_main_button_style("disconnect")
        
        # 停止動畫但保持計時器（顯示連接時長）
        self.pulse_timer.stop()
        
    def set_connection_failed_state(self, error_message: str = ""):
        """設置為連線失敗狀態"""
        self.status_indicator.setText("❌")
        self.status_text.setText("連線失敗")
        self.status_text.setStyleSheet("color: #e74c3c;")
        
        # 隱藏連線UI
        self._hide_connection_ui()
        
        # 更新按鈕
        self.main_button.setText("重試連接")
        self.main_button.setEnabled(True)
        self._update_main_button_style("retry")
        
        # 停止動畫
        self._stop_animations()
        
        # 顯示錯誤提示（延遲顯示避免阻塞UI）
        if error_message:
            QTimer.singleShot(500, lambda: self._show_error_message(error_message))
    
    def update_connection_progress(self, message: str, progress: int = -1):
        """更新連線進度"""
        self.progress_text.setText(message)
        
        if progress >= 0:
            self.progress_bar.setValue(progress)
        else:
            # 使用不確定進度條
            self.progress_bar.setRange(0, 0)
            
    def _show_connection_ui(self):
        """顯示連線相關UI元素"""
        self.progress_bar.setVisible(True)
        self.progress_text.setVisible(True)
        self.cancel_button.setVisible(True)
        
        # 重設進度條
        self.progress_bar.setRange(0, 0)  # 不確定進度
        self.progress_bar.setValue(0)
        
    def _hide_connection_ui(self):
        """隱藏連線相關UI元素"""
        self.progress_bar.setVisible(False)
        self.progress_text.setVisible(False)
        self.cancel_button.setVisible(False)
        
    def _start_connection_tracking(self):
        """開始連線過程追蹤"""
        self.connection_start_time = time.time()
        self.connection_timer.start(100)  # 每100ms更新一次
        self.pulse_timer.start(800)  # 脈衝動畫
        
    def _stop_animations(self):
        """停止所有動畫和計時器"""
        self.connection_timer.stop()
        self.pulse_timer.stop()
        self.timer_label.setText("")
        
    def _update_connection_time(self):
        """更新連線時間顯示"""
        if self.connection_start_time:
            elapsed = time.time() - self.connection_start_time
            
            if elapsed < 60:
                time_text = f"{elapsed:.1f}秒"
            else:
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                time_text = f"{minutes}分{seconds}秒"
                
            if hasattr(self, 'status_text') and "已連接" in self.status_text.text():
                self.timer_label.setText(f"連接時長: {time_text}")
            else:
                self.timer_label.setText(f"正在連線: {time_text}")
                
    def _pulse_animation(self):
        """脈衝動畫效果"""
        current_color = self.status_text.styleSheet()
        if "color: #f39c12" in current_color:
            self.status_text.setStyleSheet("color: #e67e22;")
        else:
            self.status_text.setStyleSheet("color: #f39c12;")
            
    def _on_main_button_clicked(self):
        """主按鈕點擊處理"""
        button_text = self.main_button.text()
        
        if button_text in ["連接", "重試連接"]:
            self.connection_requested.emit()
        elif button_text == "斷開連接":
            self.disconnection_requested.emit()
            
    def _update_main_button_style(self, button_type: str):
        """更新主按鈕樣式"""
        base_style = """
            QPushButton {
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                border: 2px solid;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
            QPushButton:disabled {
                opacity: 0.5;
            }
        """
        
        if button_type == "connect":
            color_style = """
                background-color: #27ae60;
                border-color: #229954;
                color: white;
            """
        elif button_type == "disconnect":
            color_style = """
                background-color: #e74c3c;
                border-color: #c0392b;
                color: white;
            """
        elif button_type == "connecting":
            color_style = """
                background-color: #95a5a6;
                border-color: #7f8c8d;
                color: #bdc3c7;
            """
        elif button_type == "retry":
            color_style = """
                background-color: #f39c12;
                border-color: #e67e22;
                color: white;
            """
        else:
            color_style = ""
            
        self.main_button.setStyleSheet(base_style + color_style)
        
    def _update_cancel_button_style(self):
        """更新取消按鈕樣式"""
        self.cancel_button.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 5px;
                background-color: #95a5a6;
                border: 2px solid #7f8c8d;
                color: white;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        
    def _show_error_message(self, error_message: str):
        """顯示錯誤消息"""
        QMessageBox.warning(
            self,
            "連線錯誤",
            f"儀器連線失敗：\n\n{error_message}",
            QMessageBox.StandardButton.Ok
        )