#!/usr/bin/env python3
"""
Keithley 2461 控制 Widget
從原有 GUI 移植的完整控制介面
"""

import logging
import time
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
from widgets.unit_input_widget import UnitInputWidget, UnitDisplayWidget


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
        
        # 操作狀態追蹤
        self.settings_applied = False  # 是否已應用設定
        self.output_enabled = False    # 是否輸出開啟
        
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
        
        # 初始化按鈕狀態（在所有UI組件創建完成後）
        self.update_button_states()
        
    def create_voltage_source_params(self):
        """創建電壓源參數控制區域"""
        # 清空現有內容
        self.clear_params_layout()
        
        # 電壓源參數群組
        voltage_group = QGroupBox("🔋 電壓源參數")
        voltage_layout = QGridLayout(voltage_group)
        
        # 輸出電壓
        voltage_layout.addWidget(QLabel("輸出電壓:"), 0, 0)
        self.voltage_input = UnitInputWidget("V", "", 6)
        self.voltage_input.set_base_value(5.0)  # 預設5V，安全值
        voltage_layout.addWidget(self.voltage_input, 0, 1)
        
        # 電流限制
        voltage_layout.addWidget(QLabel("電流限制:"), 1, 0)
        self.current_limit_input = UnitInputWidget("A", "m", 3)
        self.current_limit_input.set_base_value(0.1)  # 預設100mA
        voltage_layout.addWidget(self.current_limit_input, 1, 1)
        
        # 電壓範圍
        voltage_layout.addWidget(QLabel("電壓範圍:"), 2, 0)
        self.voltage_range_combo = QComboBox()
        self.voltage_range_combo.addItems(["自動", "20V", "200V"])
        voltage_layout.addWidget(self.voltage_range_combo, 2, 1)
        
        # 測量速度
        voltage_layout.addWidget(QLabel("測量速度:"), 3, 0)
        self.nplc_combo = QComboBox()
        self.nplc_combo.addItems(["快速 (0.1)", "標準 (1.0)", "精確 (10)"])
        self.nplc_combo.setCurrentIndex(1)  # 預設標準
        voltage_layout.addWidget(self.nplc_combo, 3, 1)
        
        self.params_layout.addWidget(voltage_group)
        
    def create_current_source_params(self):
        """創建電流源參數控制區域"""
        # 清空現有內容
        self.clear_params_layout()
        
        # 電流源參數群組
        current_group = QGroupBox("⚡ 電流源參數")
        current_layout = QGridLayout(current_group)
        
        # 輸出電流
        current_layout.addWidget(QLabel("輸出電流:"), 0, 0)
        self.current_input = UnitInputWidget("A", "m", 6)
        self.current_input.set_base_value(0.01)  # 預設10mA
        current_layout.addWidget(self.current_input, 0, 1)
        
        # 電壓限制
        current_layout.addWidget(QLabel("電壓限制:"), 1, 0)
        self.voltage_limit_input = UnitInputWidget("V", "", 3)
        self.voltage_limit_input.set_base_value(21.0)  # 預設21V
        current_layout.addWidget(self.voltage_limit_input, 1, 1)
        
        # 電流範圍
        current_layout.addWidget(QLabel("電流範圍:"), 2, 0)
        self.current_range_combo = QComboBox()
        self.current_range_combo.addItems(["自動", "1mA", "10mA", "100mA", "1A"])
        current_layout.addWidget(self.current_range_combo, 2, 1)
        
        # 測量速度
        current_layout.addWidget(QLabel("測量速度:"), 3, 0)
        self.nplc_combo = QComboBox()
        self.nplc_combo.addItems(["快速 (0.1)", "標準 (1.0)", "精確 (10)"])
        self.nplc_combo.setCurrentIndex(1)  # 預設標準
        current_layout.addWidget(self.nplc_combo, 3, 1)
        
        self.params_layout.addWidget(current_group)
        
    def clear_params_layout(self):
        """清空參數佈局"""
        while self.params_layout.count():
            child = self.params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def on_function_changed(self, function_text):
        """當功能選擇改變時的處理"""
        if function_text == "電壓源":
            self.create_voltage_source_params()
            self.log_message("🔋 切換到電壓源模式")
        elif function_text == "電流源":
            self.create_current_source_params()
            self.log_message("⚡ 切換到電流源模式")
            
        # 重置應用狀態，需要重新應用設定
        self.settings_applied = False
        self.update_button_states()
        
    def update_button_states(self):
        """更新按鈕狀態 - 智能操作流程控制"""
        # 確保按鈕已創建
        if not hasattr(self, 'apply_btn') or not hasattr(self, 'output_btn'):
            return
            
        connected = bool(self.keithley and getattr(self.keithley, 'connected', False))
        
        # 連接按鈕
        if hasattr(self, 'connect_btn'):
            self.connect_btn.setText("斷開連接" if connected else "連接")
        
        # 應用設定按鈕：連接後即可使用
        self.apply_btn.setEnabled(connected)
        
        # 開啟輸出按鈕：需要連接且已應用設定
        self.output_btn.setEnabled(connected and self.settings_applied)
        
        # 測量按鈕：連接後即可使用
        if hasattr(self, 'measure_btn'):
            self.measure_btn.setEnabled(connected)
            
        # 開始執行按鈕：需要連接且已應用設定
        if hasattr(self, 'start_execution_btn'):
            self.start_execution_btn.setEnabled(connected and self.settings_applied)
        
        # IP輸入框：未連接時可編輯
        if hasattr(self, 'ip_input'):
            self.ip_input.setEnabled(not connected)
        
        # 設定輸入框：連接後可編輯
        if hasattr(self, 'voltage_input'):
            self.voltage_input.setEnabled(connected)
        if hasattr(self, 'current_input'):
            self.current_input.setEnabled(connected)  
        if hasattr(self, 'current_limit_input'):
            self.current_limit_input.setEnabled(connected)
        if hasattr(self, 'voltage_limit_input'):
            self.voltage_limit_input.setEnabled(connected)
        if hasattr(self, 'function_combo'):
            self.function_combo.setEnabled(connected)
        if hasattr(self, 'voltage_range_combo'):
            self.voltage_range_combo.setEnabled(connected)
        if hasattr(self, 'current_range_combo'):
            self.current_range_combo.setEnabled(connected)
        if hasattr(self, 'nplc_combo'):
            self.nplc_combo.setEnabled(connected)
        
        # 更新按鈕文字
        if connected and self.output_enabled:
            self.output_btn.setText("關閉輸出")
        else:
            self.output_btn.setText("開啟輸出")
            
        # 更新提示信息
        self.update_status_hint()
        
    def update_status_hint(self):
        """更新狀態提示"""
        if not (self.keithley and self.keithley.connected):
            hint = "請先連接儀器"
        elif not self.settings_applied:
            hint = "請先應用設定，再開啟輸出"
        elif not self.output_enabled:
            hint = "可以開啟輸出開始測量"
        else:
            hint = "輸出已開啟，可進行測量"
            
        # 在操作日誌中顯示提示
        if hasattr(self, 'last_hint') and self.last_hint != hint:
            self.log_message(f"💡 操作提示: {hint}")
            self.last_hint = hint
        
    def create_control_panel(self):
        """創建左側控制面板"""
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)
        
        # 連接控制群組
        connection_group = QGroupBox("設備連接")
        conn_layout = QGridLayout(connection_group)
        
        conn_layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit("192.168.0.100")
        conn_layout.addWidget(self.ip_input, 0, 1)
        
        self.connect_btn = QPushButton("連接")
        self.connect_btn.clicked.connect(self.connect_device)
        conn_layout.addWidget(self.connect_btn, 1, 0, 1, 2)
        
        layout.addWidget(connection_group)
        
        # 智能輸出控制群組 - 方案3實施
        output_group = QGroupBox("智能輸出控制")
        output_layout = QVBoxLayout(output_group)
        
        # 功能選擇區域
        function_layout = QHBoxLayout()
        function_layout.addWidget(QLabel("工作模式:"))
        self.function_combo = QComboBox()
        self.function_combo.addItems(["電壓源", "電流源"])
        self.function_combo.currentTextChanged.connect(self.on_function_changed)
        function_layout.addWidget(self.function_combo)
        function_layout.addStretch()
        output_layout.addLayout(function_layout)
        
        # 動態參數區域容器
        self.params_container = QWidget()
        self.params_layout = QVBoxLayout(self.params_container)
        self.params_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.params_container)
        
        # 初始化參數區域（預設為電壓源）
        self.create_voltage_source_params()
        
        # 操作按鈕區域
        button_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("📝 應用設定")
        self.apply_btn.clicked.connect(self.apply_settings)
        self.apply_btn.setEnabled(False)
        button_layout.addWidget(self.apply_btn)
        
        self.output_btn = QPushButton("⚡ 開啟輸出")
        self.output_btn.clicked.connect(self.toggle_output)
        self.output_btn.setEnabled(False)
        button_layout.addWidget(self.output_btn)
        
        self.start_execution_btn = QPushButton("▶️ 開始執行")
        self.start_execution_btn.clicked.connect(self.start_execution)
        self.start_execution_btn.setEnabled(False)
        self.start_execution_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        button_layout.addWidget(self.start_execution_btn)
        
        output_layout.addLayout(button_layout)
        
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
        self.voltage_display = UnitDisplayWidget("V", 6)
        data_layout.addWidget(self.voltage_display, 0, 1)
        
        data_layout.addWidget(QLabel("電流:"), 0, 2)
        self.current_display = UnitDisplayWidget("A", 6)
        data_layout.addWidget(self.current_display, 0, 3)
        
        data_layout.addWidget(QLabel("電阻:"), 1, 0)
        self.resistance_display = UnitDisplayWidget("Ω", 2)
        data_layout.addWidget(self.resistance_display, 1, 1)
        
        data_layout.addWidget(QLabel("功率:"), 1, 2)
        self.power_display = UnitDisplayWidget("W", 6)
        data_layout.addWidget(self.power_display, 1, 3)
        
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
                if self.keithley.connect():  # 現在只使用Socket
                    self.log_message(f"成功連接到設備: {ip_address}")
                    
                    # 重置狀態
                    self.settings_applied = False
                    self.output_enabled = False
                    
                    # 更新按鈕狀態
                    self.update_button_states()
                    
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
            
            # 重置狀態
            self.settings_applied = False
            self.output_enabled = False
            
            # 更新UI狀態
            self.update_button_states()
            self.auto_measure_cb.setChecked(False)
            
            # 發送連接狀態信號
            self.connection_changed.emit(False, "")
            self.log_message("設備已斷開連接")
            
        except Exception as e:
            self.log_message(f"斷開連接時發生錯誤: {e}")
    
    def apply_settings(self):
        """智能應用設定 - 根據選擇的模式動態應用參數"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            function = self.function_combo.currentText()
            
            # 設定測量速度
            nplc_text = self.nplc_combo.currentText()
            if "0.1" in nplc_text:
                nplc_value = 0.1
            elif "10" in nplc_text:
                nplc_value = 10.0
            else:
                nplc_value = 1.0
            self.keithley.set_measurement_speed(nplc_value)
            
            if function == "電壓源":
                self.apply_voltage_source_settings()
            elif function == "電流源":
                self.apply_current_source_settings()
                
            # 標記設定已應用
            self.settings_applied = True
            
            # 更新按鈕狀態
            self.update_button_states()
            self.log_message("✅ 設定應用成功")
                
        except Exception as e:
            QMessageBox.critical(self, "設定錯誤", f"應用設定時發生錯誤: {str(e)}")
            self.log_message(f"❌ 設定錯誤: {e}")
            
    def apply_voltage_source_settings(self):
        """應用電壓源設定"""
        # 獲取電壓值
        voltage_text = self.voltage_input.value_edit.text()
        voltage_unit = self.voltage_input.get_current_prefix()
        voltage_str = f"{voltage_text}{voltage_unit}" if voltage_unit else voltage_text
        
        # 獲取電流限制
        current_limit_text = self.current_limit_input.value_edit.text()
        current_limit_unit = self.current_limit_input.get_current_prefix()
        current_limit_str = f"{current_limit_text}{current_limit_unit}" if current_limit_unit else current_limit_text
        
        # 設定範圍（如果不是自動）
        voltage_range = self.voltage_range_combo.currentText()
        if voltage_range != "自動":
            range_value = voltage_range.replace("V", "")
            self.keithley.send_command(f":SOUR:VOLT:RANG {range_value}")
        else:
            self.keithley.send_command(":SOUR:VOLT:RANG:AUTO ON")
            
        # 應用電壓源設定
        self.keithley.set_voltage(voltage_str, current_limit=current_limit_str)
        self.log_message(f"🔋 電壓源設定: {voltage_str}V, 限制: {current_limit_str}A, 範圍: {voltage_range}")
        
    def apply_current_source_settings(self):
        """應用電流源設定"""
        # 獲取電流值
        current_text = self.current_input.value_edit.text()
        current_unit = self.current_input.get_current_prefix()
        current_str = f"{current_text}{current_unit}" if current_unit else current_text
        
        # 獲取電壓限制
        voltage_limit_text = self.voltage_limit_input.value_edit.text()
        voltage_limit_unit = self.voltage_limit_input.get_current_prefix()
        voltage_limit_str = f"{voltage_limit_text}{voltage_limit_unit}" if voltage_limit_unit else voltage_limit_text
        
        # 設定範圍（如果不是自動）
        current_range = self.current_range_combo.currentText()
        if current_range != "自動":
            range_value = current_range.replace("A", "").replace("mA", "m")
            range_converted = self.keithley._convert_unit_format(range_value)
            self.keithley.send_command(f":SOUR:CURR:RANG {range_converted}")
        else:
            self.keithley.send_command(":SOUR:CURR:RANG:AUTO ON")
            
        # 應用電流源設定
        self.keithley.set_current(current_str, voltage_limit=voltage_limit_str)
        self.log_message(f"⚡ 電流源設定: {current_str}A, 限制: {voltage_limit_str}V, 範圍: {current_range}")
    
    def toggle_output(self):
        """切換輸出狀態"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            # 獲取當前輸出狀態
            current_state = self.keithley.get_output_state()
            
            if current_state:
                # 關閉輸出
                self.keithley.output_off()
                self.output_enabled = False
                self.log_message("輸出已關閉")
            else:
                # 開啟輸出
                self.keithley.output_on()
                self.output_enabled = True
                self.log_message("輸出已開啟")
                
            # 更新按鈕狀態
            self.update_button_states()
                
        except Exception as e:
            QMessageBox.critical(self, "輸出控制錯誤", f"切換輸出狀態時發生錯誤: {str(e)}")
            self.log_message(f"輸出控制錯誤: {e}")
    
    def single_measurement(self):
        """執行單次測量"""
        if not self.keithley or not self.keithley.connected:
            return
            
        try:
            voltage, current, resistance, power = self.keithley.measure_all()
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
        # 更新數值顯示
        self.voltage_display.set_value(voltage)
        self.current_display.set_value(current)
        
        if abs(resistance) > 1e6:
            self.resistance_display.set_value(float('inf'))
        else:
            self.resistance_display.set_value(resistance)
            
        self.power_display.set_value(power)
        
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
        
    def start_execution(self):
        """開始執行當前模式的完整操作流程"""
        if not self.keithley or not self.keithley.connected:
            QMessageBox.warning(self, "警告", "請先連接設備")
            return
            
        if not self.settings_applied:
            QMessageBox.warning(self, "警告", "請先應用設定")
            return
            
        try:
            function = self.function_combo.currentText()
            self.log_message(f"▶️ 開始執行{function}操作...")
            self.start_execution_btn.setEnabled(False)
            self.start_execution_btn.setText("🔄 執行中...")
            
            # 先開啟輸出
            self.keithley.output_on()
            self.output_enabled = True
            self.log_message("⚡ 輸出已開啟")
            
            # 等待穩定並測量
            time.sleep(0.5)
            voltage, current, resistance, power = self.keithley.measure_all()
            
            # 更新顯示
            self.update_measurement_display(voltage, current, resistance, power)
            
            # 顯示結果
            if function == "電壓源":
                self.log_message(f"🔋 {function}執行結果:")
                self.log_message(f"  輸出電壓: {voltage:.6f} V")
                self.log_message(f"  測量電流: {current:.6f} A")
            else:
                self.log_message(f"⚡ {function}執行結果:")
                self.log_message(f"  輸出電流: {current:.6f} A") 
                self.log_message(f"  測量電壓: {voltage:.6f} V")
                
            self.log_message(f"  功率: {power:.6f} W")
            
            # 更新按鈕狀態
            self.update_button_states()
            self.log_message("✅ 執行完成！輸出保持開啟狀態")
                
        except Exception as e:
            error_msg = f"執行失敗: {str(e)}"
            self.log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "執行錯誤", error_msg)
            
        finally:
            self.start_execution_btn.setEnabled(True)
            self.start_execution_btn.setText("▶️ 開始執行")
    
    
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