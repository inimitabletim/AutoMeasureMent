#!/usr/bin/env python3
"""
Keithley 2461 儀器控制GUI主程式
使用PyQt6實現圖形化界面
"""

import sys
import logging
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QLabel, QPushButton, 
                            QLineEdit, QGroupBox, QTableWidget, QTableWidgetItem,
                            QTextEdit, QComboBox, QDoubleSpinBox, QCheckBox,
                            QMessageBox, QFileDialog, QProgressBar, QStatusBar)
from PyQt6.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap, QTextCharFormat, QColor
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.keithley_2461 import Keithley2461
from src.data_logger import DataLogger
from src.theme_manager import ThemeManager, ThemeStyleSheet


class MeasurementWorker(QThread):
    """測量工作執行緒"""
    data_ready = pyqtSignal(float, float, float, float)  # voltage, current, resistance, power
    error_occurred = pyqtSignal(str)
    
    def __init__(self, keithley):
        super().__init__()
        self.keithley = keithley
        self.running = False
        
    def run(self):
        """執行測量循環"""
        while self.running:
            try:
                if self.keithley and self.keithley.connected:
                    v, i, r, p = self.keithley.measure_all()
                    self.data_ready.emit(v, i, r, p)
                    self.msleep(500)  # 500ms間隔
                else:
                    self.msleep(1000)
            except Exception as e:
                self.error_occurred.emit(str(e))
                self.running = False
                
    def start_measurement(self):
        """開始測量"""
        self.running = True
        self.start()
        
    def stop_measurement(self):
        """停止測量"""
        self.running = False
        self.quit()
        self.wait()


class KeithleyGUI(QMainWindow):
    """Keithley 2461控制GUI主視窗"""
    
    def __init__(self):
        super().__init__()
        self.keithley = None
        self.data_logger = None
        self.measurement_worker = None
        
        # 數據存儲
        self.voltage_data = []
        self.current_data = []
        self.time_data = []
        self.start_time = datetime.now()
        
        # 設置 logger（必須在其他初始化之前）
        self.logger = logging.getLogger(__name__)
        
        # 主題管理
        self.theme_manager = ThemeManager()
        self.current_theme = self.theme_manager.get_current_theme()
        
        self.init_ui()
        self.setup_logging()
        
    def init_ui(self):
        """初始化用戶界面"""
        self.setWindowTitle("Keithley 2461 SourceMeter控制系統")
        self.setGeometry(100, 100, 1200, 800)
        
        # 創建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        
        # 左側控制面板
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右側顯示面板
        right_panel = self.create_display_panel()
        main_layout.addWidget(right_panel, 2)
        
        # 狀態欄
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就緒 - 未連接設備")
        
        # 應用主題樣式
        self.apply_theme()
        
    def create_control_panel(self):
        """創建左側控制面板"""
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)
        
        # 連接控制群組
        connection_group = QGroupBox("設備連接")
        conn_layout = QGridLayout(connection_group)
        
        conn_layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit("192.168.1.100")
        conn_layout.addWidget(self.ip_input, 0, 1)
        
        self.connect_btn = QPushButton("連接")
        self.connect_btn.clicked.connect(self.connect_device)
        conn_layout.addWidget(self.connect_btn, 1, 0, 1, 2)
        
        layout.addWidget(connection_group)
        
        # 輸出控制群組
        output_group = QGroupBox("輸出控制")
        output_layout = QGridLayout(output_group)
        
        output_layout.addWidget(QLabel("功能:"), 0, 0)
        self.function_combo = QComboBox()
        self.function_combo.addItems(["電壓源", "電流源"])
        output_layout.addWidget(self.function_combo, 0, 1)
        
        output_layout.addWidget(QLabel("電壓 (V):"), 1, 0)
        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(-100, 100)
        self.voltage_spin.setDecimals(3)
        self.voltage_spin.setSingleStep(0.1)
        output_layout.addWidget(self.voltage_spin, 1, 1)
        
        output_layout.addWidget(QLabel("電流 (A):"), 2, 0)
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(-10, 10)
        self.current_spin.setDecimals(6)
        self.current_spin.setSingleStep(0.001)
        output_layout.addWidget(self.current_spin, 2, 1)
        
        output_layout.addWidget(QLabel("電流限制 (A):"), 3, 0)
        self.current_limit_spin = QDoubleSpinBox()
        self.current_limit_spin.setRange(0, 10)
        self.current_limit_spin.setDecimals(3)
        self.current_limit_spin.setValue(0.1)
        output_layout.addWidget(self.current_limit_spin, 3, 1)
        
        self.output_btn = QPushButton("開啟輸出")
        self.output_btn.clicked.connect(self.toggle_output)
        self.output_btn.setEnabled(False)
        output_layout.addWidget(self.output_btn, 4, 0, 1, 2)
        
        self.apply_btn = QPushButton("應用設定")
        self.apply_btn.clicked.connect(self.apply_settings)
        self.apply_btn.setEnabled(False)
        output_layout.addWidget(self.apply_btn, 5, 0, 1, 2)
        
        layout.addWidget(output_group)
        
        # 測量控制群組
        measure_group = QGroupBox("測量控制")
        measure_layout = QVBoxLayout(measure_group)
        
        self.auto_measure_cb = QCheckBox("自動測量")
        self.auto_measure_cb.stateChanged.connect(self.toggle_auto_measure)
        measure_layout.addWidget(self.auto_measure_cb)
        
        self.measure_btn = QPushButton("單次測量")
        self.measure_btn.clicked.connect(self.single_measurement)
        self.measure_btn.setEnabled(False)
        measure_layout.addWidget(self.measure_btn)
        
        layout.addWidget(measure_group)
        
        # 數據記錄群組
        data_group = QGroupBox("數據記錄")
        data_layout = QVBoxLayout(data_group)
        
        self.record_cb = QCheckBox("記錄數據")
        data_layout.addWidget(self.record_cb)
        
        self.save_btn = QPushButton("保存數據")
        self.save_btn.clicked.connect(self.save_data)
        data_layout.addWidget(self.save_btn)
        
        self.clear_btn = QPushButton("清除數據")
        self.clear_btn.clicked.connect(self.clear_data)
        data_layout.addWidget(self.clear_btn)
        
        layout.addWidget(data_group)
        
        # 添加彈性空間
        layout.addStretch()
        
        return control_widget
        
    def create_display_panel(self):
        """創建右側顯示面板"""
        display_widget = QWidget()
        layout = QVBoxLayout(display_widget)
        
        # 實時數據顯示
        data_group = QGroupBox("實時測量數據")
        data_layout = QGridLayout(data_group)
        
        # 創建數據標籤
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        
        data_layout.addWidget(QLabel("電壓:"), 0, 0)
        self.voltage_label = QLabel("0.000000 V")
        self.voltage_label.setFont(font)
        self.voltage_label.setStyleSheet("color: #2196F3; background-color: white; padding: 5px; border: 1px solid #ddd;")
        data_layout.addWidget(self.voltage_label, 0, 1)
        
        data_layout.addWidget(QLabel("電流:"), 0, 2)
        self.current_label = QLabel("0.000000 A")
        self.current_label.setFont(font)
        self.current_label.setStyleSheet("color: #FF9800; background-color: white; padding: 5px; border: 1px solid #ddd;")
        data_layout.addWidget(self.current_label, 0, 3)
        
        data_layout.addWidget(QLabel("電阻:"), 1, 0)
        self.resistance_label = QLabel("∞ Ω")
        self.resistance_label.setFont(font)
        self.resistance_label.setStyleSheet("color: #4CAF50; background-color: white; padding: 5px; border: 1px solid #ddd;")
        data_layout.addWidget(self.resistance_label, 1, 1)
        
        data_layout.addWidget(QLabel("功率:"), 1, 2)
        self.power_label = QLabel("0.000000 W")
        self.power_label.setFont(font)
        self.power_label.setStyleSheet("color: #F44336; background-color: white; padding: 5px; border: 1px solid #ddd;")
        data_layout.addWidget(self.power_label, 1, 3)
        
        layout.addWidget(data_group)
        
        # 圖表顯示
        chart_group = QGroupBox("數據圖表")
        chart_layout = QVBoxLayout(chart_group)
        
        # 創建圖表
        self.plot_widget = PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', '電壓 (V)', color='black')
        self.plot_widget.setLabel('bottom', '時間 (秒)', color='black')
        self.plot_widget.addLegend()
        
        # 設置圖表曲線
        self.voltage_curve = self.plot_widget.plot(pen=pg.mkPen(color='blue', width=2), name='電壓')
        self.current_curve = self.plot_widget.plot(pen=pg.mkPen(color='red', width=2), name='電流')
        
        chart_layout.addWidget(self.plot_widget)
        layout.addWidget(chart_group)
        
        # 日誌顯示
        log_group = QGroupBox("系統日誌")
        log_layout = QVBoxLayout(log_group)
        
        # 日誌控制按鈕
        log_button_layout = QHBoxLayout()
        
        self.clear_log_btn = QPushButton("清除日誌")
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.clear_log_btn.setMaximumWidth(100)
        log_button_layout.addWidget(self.clear_log_btn)
        
        self.export_log_btn = QPushButton("導出日誌")
        self.export_log_btn.clicked.connect(self.export_log)
        self.export_log_btn.setMaximumWidth(100)
        log_button_layout.addWidget(self.export_log_btn)
        
        log_button_layout.addStretch()
        log_layout.addLayout(log_button_layout)
        
        # 日誌文字顯示區
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return display_widget
        
    def setup_logging(self):
        """設置日誌系統"""
        # 創建 logs 目錄（如果不存在）
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 設置日誌檔案名稱（包含日期）
        log_filename = log_dir / f"keithley_gui_{datetime.now().strftime('%Y%m%d')}.log"
        
        # 創建自定義 GUI 日誌處理器（帶顏色）
        class GuiLogHandler(logging.Handler):
            def __init__(self, text_widget, parent_window):
                super().__init__()
                self.text_widget = text_widget
                self.parent_window = parent_window
                self.colors = ThemeStyleSheet.get_log_colors(parent_window.current_theme)
                
            def emit(self, record):
                msg = self.format(record)
                level = record.levelname
                color = self.colors.get(level, '#000000')
                
                # 添加帶顏色的文字
                self.text_widget.setTextColor(QColor(color))
                self.text_widget.append(msg)
                
                # 自動滾動到底部
                cursor = self.text_widget.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.text_widget.setTextCursor(cursor)
        
        # 配置根日誌器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # 清除現有的處理器
        root_logger.handlers.clear()
        
        # 日誌格式
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # 檔案處理器（輪轉，最大 10MB，保留 5 個備份）
        file_handler = RotatingFileHandler(
            log_filename,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        # GUI 處理器（只顯示 INFO 及以上級別）
        self.gui_handler = GuiLogHandler(self.log_text, self)
        self.gui_handler.setLevel(logging.INFO)
        self.gui_handler.setFormatter(simple_formatter)
        root_logger.addHandler(self.gui_handler)
        
        # 控制台處理器（用於調試）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)
        
        # 創建本類專用的日誌器
        self.logger = logging.getLogger(__name__)
        
        # 記錄啟動訊息
        self.logger.info("="*50)
        self.logger.info("Keithley 2461 控制系統啟動")
        self.logger.info(f"Python 版本: {sys.version.split()[0]}")
        self.logger.info(f"PyQt6 版本: {QApplication.instance().applicationVersion() if QApplication.instance() else 'N/A'}")
        self.logger.info(f"日誌檔案: {log_filename}")
        self.logger.info("="*50)
        
    def connect_device(self):
        """連接設備"""
        if not self.keithley or not self.keithley.connected:
            ip_address = self.ip_input.text().strip()
            if not ip_address:
                QMessageBox.warning(self, "錯誤", "請輸入IP地址")
                return
                
            try:
                self.keithley = Keithley2461(ip_address=ip_address)
                if self.keithley.connect("visa"):
                    self.logger.info(f"成功連接到設備: {ip_address}")
                    self.status_bar.showMessage(f"已連接 - {ip_address}")
                    
                    # 更新按鈕狀態
                    self.connect_btn.setText("斷開連接")
                    self.output_btn.setEnabled(True)
                    self.apply_btn.setEnabled(True)
                    self.measure_btn.setEnabled(True)
                    self.ip_input.setEnabled(False)
                    
                    # 初始化設備
                    self.keithley.reset()
                    self.keithley.set_auto_range(True)
                    self.keithley.set_measurement_speed(1.0)
                    
                    # 初始化數據記錄器
                    self.data_logger = DataLogger()
                    session_name = self.data_logger.start_session()
                    self.logger.info(f"開始數據記錄會話: {session_name}")
                    
                else:
                    QMessageBox.critical(self, "連接失敗", f"無法連接到設備: {ip_address}")
                    
            except Exception as e:
                QMessageBox.critical(self, "連接錯誤", f"連接過程中發生錯誤: {str(e)}")
                self.logger.error(f"連接錯誤: {e}")
        else:
            # 斷開連接
            self.disconnect_device()
            
    def disconnect_device(self):
        """斷開設備連接"""
        try:
            # 停止自動測量
            if self.measurement_worker:
                self.measurement_worker.stop_measurement()
                
            # 關閉輸出
            if self.keithley and self.keithley.connected:
                self.keithley.output_off()
                self.keithley.disconnect()
                
            self.keithley = None
            
            # 更新UI狀態
            self.connect_btn.setText("連接")
            self.output_btn.setText("開啟輸出")
            self.output_btn.setEnabled(False)
            self.apply_btn.setEnabled(False)
            self.measure_btn.setEnabled(False)
            self.ip_input.setEnabled(True)
            self.auto_measure_cb.setChecked(False)
            
            self.status_bar.showMessage("就緒 - 未連接設備")
            self.logger.info("設備已斷開連接")
            
        except Exception as e:
            self.logger.error(f"斷開連接時發生錯誤: {e}")
            
    def apply_settings(self):
        """應用設定"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            function = self.function_combo.currentText()
            voltage = self.voltage_spin.value()
            current = self.current_spin.value()
            current_limit = self.current_limit_spin.value()
            
            if function == "電壓源":
                self.keithley.set_voltage(voltage, current_limit)
                self.logger.info(f"設定電壓源: {voltage}V, 電流限制: {current_limit}A")
            else:
                voltage_limit = 21.0  # 預設電壓限制
                self.keithley.set_current(current, voltage_limit)
                self.logger.info(f"設定電流源: {current}A, 電壓限制: {voltage_limit}V")
                
        except Exception as e:
            QMessageBox.critical(self, "設定錯誤", f"應用設定時發生錯誤: {str(e)}")
            self.logger.error(f"設定錯誤: {e}")
            
    def toggle_output(self):
        """切換輸出狀態"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            current_state = self.keithley.get_output_state()
            
            if current_state:
                self.keithley.output_off()
                self.output_btn.setText("開啟輸出")
                self.output_btn.setStyleSheet("background-color: #4CAF50;")
                self.logger.info("輸出已關閉")
            else:
                self.keithley.output_on()
                self.output_btn.setText("關閉輸出")
                self.output_btn.setStyleSheet("background-color: #F44336;")
                self.logger.info("輸出已開啟")
                
        except Exception as e:
            QMessageBox.critical(self, "輸出控制錯誤", f"切換輸出狀態時發生錯誤: {str(e)}")
            self.logger.error(f"輸出控制錯誤: {e}")
            
    def single_measurement(self):
        """執行單次測量"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            voltage, current, resistance, power = self.keithley.measure_all()
            self.update_measurement_display(voltage, current, resistance, power)
            self.logger.info(f"測量: V={voltage:.6f}V, I={current:.6f}A, R={resistance:.2f}Ω, P={power:.6f}W")
            
        except Exception as e:
            QMessageBox.critical(self, "測量錯誤", f"測量時發生錯誤: {str(e)}")
            self.logger.error(f"測量錯誤: {e}")
            
    def toggle_auto_measure(self, state):
        """切換自動測量"""
        if state == Qt.CheckState.Checked.value:
            if self.keithley and self.keithley.connected:
                # 開始自動測量
                self.measurement_worker = MeasurementWorker(self.keithley)
                self.measurement_worker.data_ready.connect(self.update_measurement_display)
                self.measurement_worker.error_occurred.connect(self.handle_measurement_error)
                self.measurement_worker.start_measurement()
                self.logger.info("開始自動測量")
            else:
                self.auto_measure_cb.setChecked(False)
                QMessageBox.warning(self, "警告", "請先連接設備")
        else:
            # 停止自動測量
            if self.measurement_worker:
                self.measurement_worker.stop_measurement()
                self.measurement_worker = None
                self.logger.info("停止自動測量")
                
    def update_measurement_display(self, voltage, current, resistance, power):
        """更新測量數據顯示"""
        # 更新數值標籤
        self.voltage_label.setText(f"{voltage:.6f} V")
        self.current_label.setText(f"{current:.6f} A")
        
        if abs(resistance) > 1e6:
            self.resistance_label.setText("∞ Ω")
        else:
            self.resistance_label.setText(f"{resistance:.2f} Ω")
            
        self.power_label.setText(f"{power:.6f} W")
        
        # 更新圖表數據
        current_time = (datetime.now() - self.start_time).total_seconds()
        self.time_data.append(current_time)
        self.voltage_data.append(voltage)
        self.current_data.append(current)
        
        # 限制數據點數量（保留最近1000個點）
        if len(self.time_data) > 1000:
            self.time_data = self.time_data[-1000:]
            self.voltage_data = self.voltage_data[-1000:]
            self.current_data = self.current_data[-1000:]
            
        # 更新圖表
        self.voltage_curve.setData(self.time_data, self.voltage_data)
        self.current_curve.setData(self.time_data, self.current_data)
        
        # 記錄數據（如果啟用）
        if self.record_cb.isChecked() and self.data_logger:
            self.data_logger.log_measurement(voltage, current, resistance, power)
            
    def handle_measurement_error(self, error_message):
        """處理測量錯誤"""
        self.logger.error(f"測量錯誤: {error_message}")
        self.auto_measure_cb.setChecked(False)
        
    def save_data(self):
        """保存數據"""
        if not self.data_logger or not self.data_logger.session_data:
            QMessageBox.information(self, "提示", "沒有數據可保存")
            return
            
        try:
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getSaveFileName(
                self, "保存數據", f"measurement_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
                "CSV Files (*.csv);;JSON Files (*.json)"
            )
            
            if file_path:
                if file_path.endswith('.csv'):
                    self.data_logger.save_session_csv(file_path.split('/')[-1])
                else:
                    self.data_logger.save_session_json(file_path.split('/')[-1])
                    
                QMessageBox.information(self, "成功", f"數據已保存到: {file_path}")
                self.logger.info(f"數據已保存到: {file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "保存錯誤", f"保存數據時發生錯誤: {str(e)}")
            
    def clear_data(self):
        """清除數據"""
        reply = QMessageBox.question(self, "確認", "確定要清除所有數據嗎？", 
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            self.time_data.clear()
            self.voltage_data.clear()
            self.current_data.clear()
            self.voltage_curve.clear()
            self.current_curve.clear()
            
            if self.data_logger:
                self.data_logger.session_data.clear()
                
            self.logger.info("數據已清除")
    
    def clear_log(self):
        """清除日誌顯示區"""
        self.log_text.clear()
        self.logger.info("日誌顯示區已清除")
    
    def export_log(self):
        """導出日誌到檔案"""
        try:
            # 取得日誌文字內容
            log_content = self.log_text.toPlainText()
            
            if not log_content:
                QMessageBox.information(self, "提示", "日誌為空，無內容可導出")
                return
            
            # 選擇儲存位置
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getSaveFileName(
                self, 
                "導出日誌", 
                f"keithley_log_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "Text Files (*.txt);;All Files (*.*)"
            )
            
            if file_path:
                # 寫入檔案
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"Keithley 2461 控制系統日誌導出\n")
                    f.write(f"導出時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*60 + "\n\n")
                    f.write(log_content)
                
                QMessageBox.information(self, "成功", f"日誌已導出到:\n{file_path}")
                self.logger.info(f"日誌已導出到: {file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "導出錯誤", f"導出日誌時發生錯誤:\n{str(e)}")
            self.logger.error(f"導出日誌失敗: {e}")
    
    def apply_theme(self):
        """應用當前主題"""
        stylesheet = ThemeStyleSheet.get_stylesheet(self.current_theme)
        self.setStyleSheet(stylesheet)
        
        # 更新圖表主題
        self.update_plot_theme()
        
        self.logger.info(f"已應用系統主題: {self.current_theme}")
    
    def update_plot_theme(self):
        """更新圖表主題"""
        try:
            if self.current_theme == "dark":
                # 深色主題圖表
                self.plot_widget.setBackground('#2b2b2b')
                self.plot_widget.getAxis('left').setPen('#ffffff')
                self.plot_widget.getAxis('bottom').setPen('#ffffff')
                self.plot_widget.getAxis('left').setTextPen('#ffffff')
                self.plot_widget.getAxis('bottom').setTextPen('#ffffff')
                
                # 更新圖表曲線顏色
                self.voltage_curve.setPen(pg.mkPen(color='#00bfff', width=2))  # 深蔚藍
                self.current_curve.setPen(pg.mkPen(color='#ff6b6b', width=2))  # 淺紅
                
            else:
                # 淺色主題圖表
                self.plot_widget.setBackground('#ffffff')
                self.plot_widget.getAxis('left').setPen('#000000')
                self.plot_widget.getAxis('bottom').setPen('#000000')
                self.plot_widget.getAxis('left').setTextPen('#000000')
                self.plot_widget.getAxis('bottom').setTextPen('#000000')
                
                # 更新圖表曲線顏色
                self.voltage_curve.setPen(pg.mkPen(color='#2196f3', width=2))  # 藍色
                self.current_curve.setPen(pg.mkPen(color='#f44336', width=2))  # 紅色
                
        except Exception as e:
            self.logger.error(f"更新圖表主題失敗: {e}")
            
    def closeEvent(self, event):
        """關閉事件處理"""
        # 總是詢問確認，避免誤關
        if self.keithley and self.keithley.connected:
            reply = QMessageBox.question(
                self, 
                "確認退出", 
                "設備仍在連接中，確定要退出嗎？\n\n"
                "• 未儲存的數據將會遺失\n"
                "• 設備連接將會中斷",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # 預設選擇 No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                try:
                    # 安全關閉所有資源
                    if self.measurement_worker:
                        self.measurement_worker.stop_measurement()
                    self.disconnect_device()
                    
                    self.logger.info("程式正常關閉")
                except Exception as e:
                    self.logger.error(f"關閉時發生錯誤: {e}")
                event.accept()
            else:
                event.ignore()
        else:
            # 即使沒連接也要確認
            reply = QMessageBox.question(
                self, 
                "確認退出", 
                "確定要退出 Keithley 控制系統嗎？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.logger.info("程式正常關閉")
                event.accept()
            else:
                event.ignore()


def main():
    """主程式入口"""
    app = QApplication(sys.argv)
    app.setApplicationName("Keithley 2461 Control")
    app.setApplicationVersion("1.0")
    
    # 創建主視窗
    window = KeithleyGUI()
    window.show()
    
    # 運行應用程式
    sys.exit(app.exec())


if __name__ == "__main__":
    main()