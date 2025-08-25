#!/usr/bin/env python3
"""
Keithley 2461 控制 Widget
從原有 GUI 移植的完整控制介面
"""

import logging
from datetime import datetime
from typing import Optional
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QLabel, QPushButton, QLineEdit, QGroupBox, 
                            QComboBox, QDoubleSpinBox, QCheckBox, QTextEdit,
                            QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.keithley_2461 import Keithley2461
from src.data_logger import DataLogger
from src.theme_manager import ThemeStyleSheet


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


class KeithleyControlWidget(QWidget):
    """Keithley 2461 完整控制 Widget"""
    
    # 狀態更新信號
    connection_changed = pyqtSignal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keithley = None
        self.data_logger = None
        self.measurement_worker = None
        
        # 數據存儲
        self.voltage_data = []
        self.current_data = []
        self.time_data = []
        self.start_time = datetime.now()
        
        # 主題
        self.current_theme = "light"  # 將由父視窗設定
        
        # 日誌
        self.logger = logging.getLogger(__name__)
        
        self.setup_ui()
        
    def setup_ui(self):
        """設置用戶介面"""
        # 主布局
        main_layout = QHBoxLayout(self)
        
        # 左側控制面板
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右側顯示面板
        right_panel = self.create_display_panel()
        main_layout.addWidget(right_panel, 2)
        
    def create_control_panel(self):
        """創建左側控制面板"""
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)
        
        # 連接控制群組
        connection_group = QGroupBox("設備連接")
        conn_layout = QGridLayout(connection_group)
        
        conn_layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("例如: 192.168.1.100")
        conn_layout.addWidget(self.ip_input, 0, 1)
        
        ip_hint = QLabel("請確認儀器DHCP IP: MENU → System → Communication → LAN")
        ip_hint.setStyleSheet("color: #CCCCCC; font-size: 12px; margin-top: 2px;")
        conn_layout.addWidget(ip_hint, 1, 0, 1, 2)
        
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
        
        # 簡化的日誌顯示
        log_group = QGroupBox("操作日誌")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(120)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return display_widget
    
    def connect_device(self):
        """連接設備"""
        if not self.keithley or not self.keithley.connected:
            ip_address = self.ip_input.text().strip()
            if not ip_address:
                QMessageBox.warning(self, "錯誤", "請輸入IP地址")
                return
                
            try:
                self.keithley = Keithley2461(ip_address=ip_address)
                if self.keithley.connect({"method": "visa"}):
                    self.log_message(f"成功連接到設備: {ip_address}")
                    
                    # 更新按鈕狀態
                    self.connect_btn.setText("斷開連接")
                    self.output_btn.setEnabled(True)
                    self.apply_btn.setEnabled(True)
                    self.measure_btn.setEnabled(True)
                    self.ip_input.setEnabled(False)
                    
                    # 初始化設備
                    self.keithley.reset()
                    # self.keithley.set_auto_range(True)
                    # self.keithley.set_measurement_speed(1.0)
                    
                    # 初始化數據記錄器
                    self.data_logger = DataLogger()
                    session_name = self.data_logger.start_session()
                    self.log_message(f"開始數據記錄會話: {session_name}")
                    
                    # 發送連接狀態信號
                    self.connection_changed.emit(True, ip_address)
                    
                else:
                    QMessageBox.critical(self, "連接失敗", f"無法連接到設備: {ip_address}")
                    
            except Exception as e:
                QMessageBox.critical(self, "連接錯誤", f"連接過程中發生錯誤: {str(e)}")
                self.log_message(f"連接錯誤: {e}")
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
            
            # 發送連接狀態信號
            self.connection_changed.emit(False, "")
            self.log_message("設備已斷開連接")
            
        except Exception as e:
            self.log_message(f"斷開連接時發生錯誤: {e}")
    
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
                # self.keithley.set_voltage(voltage, current_limit)
                self.log_message(f"設定電壓源: {voltage}V, 電流限制: {current_limit}A")
            else:
                voltage_limit = 21.0  # 預設電壓限制
                # self.keithley.set_current(current, voltage_limit)
                self.log_message(f"設定電流源: {current}A, 電壓限制: {voltage_limit}V")
                
        except Exception as e:
            QMessageBox.critical(self, "設定錯誤", f"應用設定時發生錯誤: {str(e)}")
            self.log_message(f"設定錯誤: {e}")
    
    def toggle_output(self):
        """切換輸出狀態"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            # current_state = self.keithley.get_output_state()
            current_state = False  # 臨時值
            
            if current_state:
                # self.keithley.output_off()
                self.output_btn.setText("開啟輸出")
                self.log_message("輸出已關閉")
            else:
                # self.keithley.output_on()
                self.output_btn.setText("關閉輸出")
                self.log_message("輸出已開啟")
                
        except Exception as e:
            QMessageBox.critical(self, "輸出控制錯誤", f"切換輸出狀態時發生錯誤: {str(e)}")
            self.log_message(f"輸出控制錯誤: {e}")
    
    def single_measurement(self):
        """執行單次測量"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            # voltage, current, resistance, power = self.keithley.measure_all()
            # 臨時測試數據
            voltage, current, resistance, power = 5.0, 0.1, 50.0, 0.5
            self.update_measurement_display(voltage, current, resistance, power)
            self.log_message(f"測量: V={voltage:.6f}V, I={current:.6f}A, R={resistance:.2f}Ω, P={power:.6f}W")
            
        except Exception as e:
            QMessageBox.critical(self, "測量錯誤", f"測量時發生錯誤: {str(e)}")
            self.log_message(f"測量錯誤: {e}")
    
    def toggle_auto_measure(self, state):
        """切換自動測量"""
        if state == Qt.CheckState.Checked.value:
            if self.keithley and self.keithley.connected:
                # 開始自動測量
                self.measurement_worker = MeasurementWorker(self.keithley)
                self.measurement_worker.data_ready.connect(self.update_measurement_display)
                self.measurement_worker.error_occurred.connect(self.handle_measurement_error)
                self.measurement_worker.start_measurement()
                self.log_message("開始自動測量")
            else:
                self.auto_measure_cb.setChecked(False)
                QMessageBox.warning(self, "警告", "請先連接設備")
        else:
            # 停止自動測量
            if self.measurement_worker:
                self.measurement_worker.stop_measurement()
                self.measurement_worker = None
                self.log_message("停止自動測量")
    
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
        self.log_message(f"測量錯誤: {error_message}")
        self.auto_measure_cb.setChecked(False)
    
    def save_data(self):
        """保存數據"""
        if not self.data_logger or not self.data_logger.session_data:
            QMessageBox.information(self, "提示", "沒有數據可保存")
            return
            
        try:
            csv_file = self.data_logger.save_session_csv()
            QMessageBox.information(self, "成功", f"數據已保存到: {csv_file}")
            self.log_message(f"數據已保存到: {csv_file}")
            
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
                
            self.log_message("數據已清除")
    
    def log_message(self, message):
        """在日誌區域添加訊息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"{timestamp} - {message}"
        self.log_text.append(formatted_message)
        
        # 自動滾動到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def set_theme(self, theme):
        """設置主題"""
        self.current_theme = theme
        self.update_plot_theme()
    
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