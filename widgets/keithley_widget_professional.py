#!/usr/bin/env python3
"""
Keithley 2461 Professional SourceMeter Control Widget
專業級源測量單元控制介面 - 支援IV特性曲線、掃描測量等專業功能
"""

import logging
import time
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QLabel, QPushButton, QLineEdit, QGroupBox, 
                            QComboBox, QDoubleSpinBox, QCheckBox, QTextEdit,
                            QMessageBox, QProgressBar, QSplitter, QTabWidget,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QFrame, QLCDNumber, QSizePolicy)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.keithley_2461 import Keithley2461
from src.enhanced_data_system import EnhancedDataLogger
from widgets.unit_input_widget import UnitInputWidget, UnitDisplayWidget
from widgets.connection_status_widget import ConnectionStatusWidget
from src.connection_worker import ConnectionStateManager


class SweepMeasurementWorker(QThread):
    """掃描測量工作執行緒"""
    data_point_ready = pyqtSignal(float, float, float, float, int)  # voltage, current, resistance, power, point_number
    sweep_completed = pyqtSignal()
    sweep_progress = pyqtSignal(int)  # percentage
    error_occurred = pyqtSignal(str)
    
    def __init__(self, keithley, sweep_params):
        super().__init__()
        self.keithley = keithley
        self.sweep_params = sweep_params
        self.running = False
        
    def run(self):
        """執行掃描測量"""
        self.running = True
        start_v = self.sweep_params['start']
        stop_v = self.sweep_params['stop'] 
        step_v = self.sweep_params['step']
        delay_ms = self.sweep_params['delay']
        current_limit = self.sweep_params['current_limit']
        
        try:
            # 計算掃描點數
            voltage_points = np.arange(start_v, stop_v + step_v, step_v)
            total_points = len(voltage_points)
            
            # 設定為電壓源模式
            self.keithley.set_source_function("VOLT")
            self.keithley.output_on()
            
            for i, voltage in enumerate(voltage_points):
                if not self.running:
                    break
                    
                # 設定電壓
                self.keithley.set_voltage(str(voltage), current_limit=current_limit)
                
                # 等待穩定
                time.sleep(delay_ms / 1000.0)
                
                # 測量
                v, i, r, p = self.keithley.measure_all()
                
                # 發送數據點 (包含儀器計算的功率值)
                self.data_point_ready.emit(v, i, r, p, i+1)
                
                # 更新進度
                progress = int((i + 1) * 100 / total_points)
                self.sweep_progress.emit(progress)
                
            # 關閉輸出
            self.keithley.output_off()
            
            if self.running:
                self.sweep_completed.emit()
                
        except Exception as e:
            self.error_occurred.emit(str(e))
            try:
                self.keithley.output_off()
            except:
                pass
                
    def stop_sweep(self):
        """停止掃描"""
        self.running = False


class ContinuousMeasurementWorker(QThread):
    """連續測量工作執行緒"""
    data_ready = pyqtSignal(float, float, float, float)  # voltage, current, resistance, power
    error_occurred = pyqtSignal(str)
    
    def __init__(self, keithley):
        super().__init__()
        self.keithley = keithley
        self.running = False
        
    def run(self):
        """執行連續測量"""
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
                break
                
    def start_measurement(self):
        """開始測量"""
        self.running = True
        self.start()
        
    def stop_measurement(self):
        """停止測量"""
        self.running = False
        self.quit()
        self.wait()


class ProfessionalKeithleyWidget(QWidget):
    """Keithley 2461 專業控制 Widget"""
    
    # 狀態更新信號
    connection_changed = pyqtSignal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.keithley = None
        self.data_logger = None
        self.sweep_worker = None
        self.continuous_worker = None
        
        # 非阻塞式連線管理器
        self.connection_manager = ConnectionStateManager()
        
        # 測量數據存儲
        self.iv_data = []  # [(voltage, current, resistance, power), ...]
        self.time_series_data = []  # [(time, voltage, current), ...]
        self.start_time = datetime.now()
        
        # 操作狀態
        self.is_measuring = False
        self.measurement_mode = "continuous"  # "continuous", "iv_sweep"
        
        # 主題
        self.current_theme = "dark"
        
        # 日誌
        self.logger = logging.getLogger(__name__)
        
        # 狀態更新定時器
        self.status_update_timer = QTimer()
        self.status_update_timer.timeout.connect(self.update_runtime_display)
        
        # 統計數據緩存
        self._last_avg_voltage = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """設置專業用戶介面"""
        # 主布局 - 使用分割器
        main_layout = QHBoxLayout(self)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # 左側控制面板
        left_panel = self.create_control_panel()
        main_splitter.addWidget(left_panel)
        
        # 右側顯示面板
        right_panel = self.create_display_panel()
        main_splitter.addWidget(right_panel)
        
        # 設定分割比例 (3:7)
        main_splitter.setSizes([300, 700])
        
    def create_control_panel(self):
        """創建左側控制面板"""
        control_widget = QWidget()
        control_widget.setMaximumWidth(350)
        control_widget.setMinimumWidth(300)
        layout = QVBoxLayout(control_widget)
        
        # ===== 設備連接 =====
        connection_group = self.create_connection_group()
        layout.addWidget(connection_group)
        
        # ===== 測量模式 =====
        mode_group = self.create_measurement_mode_group()
        layout.addWidget(mode_group)
        
        # ===== 源設定 =====
        self.source_params_container = QWidget()
        self.source_params_layout = QVBoxLayout(self.source_params_container)
        self.source_params_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.source_params_container)
        
        # ===== 掃描設定 =====
        self.sweep_group = self.create_sweep_settings_group()
        layout.addWidget(self.sweep_group)
        
        # ===== 操作控制 =====
        control_group = self.create_operation_control_group()
        layout.addWidget(control_group)
        
        # ===== 數據管理 =====
        data_group = self.create_data_management_group()
        layout.addWidget(data_group)
        
        # 初始化源參數區域
        self.update_source_parameters()
        
        # 添加彈性空間
        layout.addStretch()
        
        return control_widget
        
    def create_connection_group(self):
        """創建增強的設備連接群組 - 支援非阻塞式連線 [v2.0]"""
        group = QGroupBox("🔌 設備連接")
        layout = QGridLayout(group)
        
        # IP地址輸入
        layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit("192.168.0.100")
        self.ip_input.setPlaceholderText("例如: 192.168.0.100")
        layout.addWidget(self.ip_input, 0, 1)
        
        # 使用增強的連線狀態Widget
        try:
            self.connection_status_widget = ConnectionStatusWidget()
            layout.addWidget(self.connection_status_widget, 1, 0, 1, 2)
            # 成功創建，不輸出避免編碼問題
        except Exception as e:
            # 如果創建失敗，使用簡單的替代UI
            self.connection_status_widget = QLabel("連線狀態載入中...")
            layout.addWidget(self.connection_status_widget, 1, 0, 1, 2)
            # 記錄錯誤到日誌而不是控制台
            if hasattr(self, 'logger'):
                self.logger.error(f"創建連線狀態Widget失敗: {e}")
        
        # 連接信號（僅當widget創建成功時）
        if hasattr(self.connection_status_widget, 'connection_requested'):
            self.connection_status_widget.connection_requested.connect(self._handle_connection_request)
            self.connection_status_widget.disconnection_requested.connect(self._handle_disconnection_request)
            self.connection_status_widget.connection_cancelled.connect(self._handle_connection_cancel)
        else:
            print("⚠️ 連線狀態Widget信號連接失敗，使用舊連線機制")
        
        # 舊的連線UI元素已完全移除，僅保留變數以防程式崩潰
        self.connect_btn = None  # 移除舊按鈕
        self.connection_status = None  # 移除舊狀態標籤
        
        return group
        
    def create_measurement_mode_group(self):
        """創建測量模式群組"""
        group = QGroupBox("📊 測量模式")
        layout = QGridLayout(group)
        
        # 測量模式 - 漸進式設計：暫時固定為連續監控
        layout.addWidget(QLabel("模式:"), 0, 0)
        
        # TODO: 未來有多個模式時，取消註解並移除固定標籤
        # self.mode_combo = QComboBox()
        # self.mode_combo.addItems(["連續監控", "時間序列"])
        # self.mode_combo.currentTextChanged.connect(self.on_measurement_mode_changed)
        # layout.addWidget(self.mode_combo, 0, 1)
        
        # 暫時使用固定標籤
        mode_label = QLabel("連續監控")
        mode_label.setStyleSheet("font-weight: bold; color: #27ae60; background-color: #e8f5e8; padding: 3px 8px; border-radius: 3px;")
        layout.addWidget(mode_label, 0, 1)
        
        layout.addWidget(QLabel("源類型:"), 1, 0)
        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(["電壓源", "電流源"])
        self.source_type_combo.currentTextChanged.connect(self.update_source_parameters)
        layout.addWidget(self.source_type_combo, 1, 1)
        
        return group
        
    def create_sweep_settings_group(self):
        """創建掃描設定群組"""
        group = QGroupBox("🔄 掃描設定")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("起始值:"), 0, 0)
        self.start_input = UnitInputWidget("V", "", 3)
        self.start_input.set_base_value(0.0)
        layout.addWidget(self.start_input, 0, 1)
        
        layout.addWidget(QLabel("終止值:"), 1, 0)
        self.stop_input = UnitInputWidget("V", "", 3)
        self.stop_input.set_base_value(5.0)
        layout.addWidget(self.stop_input, 1, 1)
        
        layout.addWidget(QLabel("步進:"), 2, 0)
        self.step_input = UnitInputWidget("V", "m", 3)
        self.step_input.set_base_value(0.1)
        layout.addWidget(self.step_input, 2, 1)
        
        layout.addWidget(QLabel("延時:"), 3, 0)
        self.delay_input = QDoubleSpinBox()
        self.delay_input.setRange(10, 10000)
        self.delay_input.setValue(100)
        self.delay_input.setSuffix(" ms")
        layout.addWidget(self.delay_input, 3, 1)
        
        # IV 功能暫時隱藏，掃描設定也隱藏
        group.setVisible(False)
        return group
        
    def create_operation_control_group(self):
        """創建操作控制群組"""
        group = QGroupBox("⚡ 操作控制")
        layout = QVBoxLayout(group)
        
        # 主控制按鈕
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶️ 開始測量")
        self.start_btn.clicked.connect(self.start_measurement)
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #bdc3c7;
            }
        """)
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.clicked.connect(self.stop_measurement)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #bdc3c7;
            }
        """)
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        
        # 進度條
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        return group
        
    def create_data_management_group(self):
        """創建數據管理群組"""
        group = QGroupBox("💾 數據管理")
        layout = QVBoxLayout(group)
        
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("📊 導出數據")
        self.export_btn.clicked.connect(self.export_data)
        button_layout.addWidget(self.export_btn)
        
        self.clear_btn = QPushButton("🔄 清除數據")
        self.clear_btn.clicked.connect(self.clear_data)
        button_layout.addWidget(self.clear_btn)
        
        layout.addLayout(button_layout)
        
        # 數據記錄選項
        self.record_data_cb = QCheckBox("記錄數據到文件")
        self.record_data_cb.setChecked(True)
        layout.addWidget(self.record_data_cb)
        
        return group
        
    def update_source_parameters(self):
        """更新源參數區域"""
        # 清空現有內容
        while self.source_params_layout.count():
            child = self.source_params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        source_type = self.source_type_combo.currentText()
        
        if source_type == "電壓源":
            self.create_voltage_source_params()
        else:
            self.create_current_source_params()
            
        # 智慧圖表類型切換
        self.smart_chart_switching(source_type)
            
    def create_voltage_source_params(self):
        """創建電壓源參數"""
        group = QGroupBox("🔋 電壓源參數")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("輸出電壓:"), 0, 0)
        self.output_voltage = UnitInputWidget("V", "", 6)
        self.output_voltage.set_base_value(5.0)
        layout.addWidget(self.output_voltage, 0, 1)
        
        layout.addWidget(QLabel("電流限制:"), 1, 0)
        self.current_limit = UnitInputWidget("A", "m", 3)
        self.current_limit.set_base_value(0.1)
        layout.addWidget(self.current_limit, 1, 1)
        
        layout.addWidget(QLabel("電壓範圍:"), 2, 0)
        self.voltage_range_combo = QComboBox()
        self.voltage_range_combo.addItems(["自動", "20V", "200V"])
        layout.addWidget(self.voltage_range_combo, 2, 1)
        
        layout.addWidget(QLabel("測量速度:"), 3, 0)
        self.measurement_speed_combo = QComboBox()
        self.measurement_speed_combo.addItems(["快速 (0.1 NPLC)", "標準 (1.0 NPLC)", "精確 (10 NPLC)"])
        self.measurement_speed_combo.setCurrentIndex(1)
        layout.addWidget(self.measurement_speed_combo, 3, 1)
        
        self.source_params_layout.addWidget(group)
        
    def create_current_source_params(self):
        """創建電流源參數"""
        group = QGroupBox("⚡ 電流源參數")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("輸出電流:"), 0, 0)
        self.output_current = UnitInputWidget("A", "m", 6)
        self.output_current.set_base_value(0.01)
        layout.addWidget(self.output_current, 0, 1)
        
        layout.addWidget(QLabel("電壓限制:"), 1, 0)
        self.voltage_limit = UnitInputWidget("V", "", 3)
        self.voltage_limit.set_base_value(21.0)
        layout.addWidget(self.voltage_limit, 1, 1)
        
        layout.addWidget(QLabel("電流範圍:"), 2, 0)
        self.current_range_combo = QComboBox()
        self.current_range_combo.addItems(["自動", "1mA", "10mA", "100mA", "1A"])
        layout.addWidget(self.current_range_combo, 2, 1)
        
        layout.addWidget(QLabel("測量速度:"), 3, 0)
        self.measurement_speed_combo = QComboBox()
        self.measurement_speed_combo.addItems(["快速 (0.1 NPLC)", "標準 (1.0 NPLC)", "精確 (10 NPLC)"])
        self.measurement_speed_combo.setCurrentIndex(1)
        layout.addWidget(self.measurement_speed_combo, 3, 1)
        
        self.source_params_layout.addWidget(group)
        
    def create_display_panel(self):
        """創建右側顯示面板 - 數據與圖表 5:5 分割"""
        display_widget = QWidget()
        layout = QVBoxLayout(display_widget)
        
        # 使用分割器實現數據顯示與圖表的 5:5 分割
        display_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 上半部 (50%) - 數據顯示區域
        data_display_frame = self.create_status_bar()
        display_splitter.addWidget(data_display_frame)
        
        # 下半部 (50%) - 圖表顯示區域
        self.display_tabs = QTabWidget()
        
        # 圖表分頁
        chart_tab = self.create_chart_tab()
        self.display_tabs.addTab(chart_tab, "📊 圖表顯示")
        
        # 數據表分頁
        data_tab = self.create_data_table_tab()
        self.display_tabs.addTab(data_tab, "📋 數據記錄")
        
        # 日誌分頁
        log_tab = self.create_log_tab()
        self.display_tabs.addTab(log_tab, "📝 操作日誌")
        
        display_splitter.addWidget(self.display_tabs)
        
        # 設定上下分割比例為 5:5
        display_splitter.setSizes([200, 800])
        
        layout.addWidget(display_splitter)
        
        return display_widget
        
    def create_status_bar(self):
        """創建數據顯示區域 - 使用 GroupBox 統一容器設計"""
        # 創建主容器
        status_widget = QWidget()
        main_layout = QVBoxLayout(status_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # 創建實時數據顯示 GroupBox
        data_group = QGroupBox("📊 實時數據顯示")
        # 不設定特殊樣式，使用與左側 GroupBox 一致的預設主題樣式
        # data_group 將自動繼承應用程式的深色主題
        
        # 實時數值顯示 - 使用 QGridLayout
        values_layout = QGridLayout(data_group)
        
        # 電壓顯示 - 專業級樣式
        voltage_label = QLabel("電壓:")
        voltage_label.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 16px;")
        values_layout.addWidget(voltage_label, 0, 0)
        self.voltage_display = QLCDNumber(6)  # 優化為6位數以正確顯示 999.99
        self.voltage_display.setStyleSheet("""
            QLCDNumber { 
                color: #2980b9; 
                background-color: #34495e;
                border: 2px solid #2980b9;
                border-radius: 5px;
            }
        """)
        values_layout.addWidget(self.voltage_display, 0, 1)
        self.voltage_unit_label = QLabel("V")
        self.voltage_unit_label.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 14px;")
        values_layout.addWidget(self.voltage_unit_label, 0, 2)
        
        # 電流顯示 - 專業級樣式
        current_label = QLabel("電流:")
        current_label.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 16px;")
        values_layout.addWidget(current_label, 0, 3)
        self.current_display = QLCDNumber(6)  # 優化為6位數以正確顯示 999.99
        self.current_display.setStyleSheet("""
            QLCDNumber { 
                color: #e74c3c; 
                background-color: #34495e;
                border: 2px solid #e74c3c;
                border-radius: 5px;
            }
        """)
        values_layout.addWidget(self.current_display, 0, 4)
        self.current_unit_label = QLabel("A")
        self.current_unit_label.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 14px;")
        values_layout.addWidget(self.current_unit_label, 0, 5)
        
        # 功率顯示 - 專業級樣式 (移至第一排)
        power_label = QLabel("功率:")
        power_label.setStyleSheet("font-weight: bold; color: #f39c12; font-size: 16px;")
        values_layout.addWidget(power_label, 0, 6)
        self.power_display = QLCDNumber(6)  # 優化為6位數以正確顯示 999.99
        self.power_display.setStyleSheet("""
            QLCDNumber { 
                color: #f39c12; 
                background-color: #34495e;
                border: 2px solid #f39c12;
                border-radius: 5px;
            }
        """)
        values_layout.addWidget(self.power_display, 0, 7)
        self.power_unit_label = QLabel("W")
        self.power_unit_label.setStyleSheet("font-weight: bold; color: #f39c12; font-size: 14px;")
        values_layout.addWidget(self.power_unit_label, 0, 8)
        
        # 電阻顯示 - 專業級樣式 (移至第一排)
        resistance_label = QLabel("電阻:")
        resistance_label.setStyleSheet("font-weight: bold; color: #27ae60; font-size: 16px;")
        values_layout.addWidget(resistance_label, 0, 9)
        self.resistance_display = QLCDNumber(6)  # 優化為6位數以正確顯示 999.99
        self.resistance_display.setStyleSheet("""
            QLCDNumber { 
                color: #27ae60; 
                background-color: #34495e;
                border: 2px solid #27ae60;
                border-radius: 5px;
            }
        """)
        values_layout.addWidget(self.resistance_display, 0, 10)
        self.resistance_unit_label = QLabel("Ω")
        self.resistance_unit_label.setStyleSheet("font-weight: bold; color: #27ae60; font-size: 14px;")
        values_layout.addWidget(self.resistance_unit_label, 0, 11)
        
        # 設置 QGridLayout 的拉伸係數，讓 LCD 顯示器能夠響應式縮放
        # 為 LCD 顯示器所在的列設置拉伸係數
        values_layout.setColumnStretch(1, 2)   # 電壓 LCD 列
        values_layout.setColumnStretch(4, 2)   # 電流 LCD 列  
        values_layout.setColumnStretch(7, 2)   # 功率 LCD 列
        values_layout.setColumnStretch(10, 2)  # 電阻 LCD 列
        
        # 狀態信息 - 使用專業的居中顯示設計
        # 創建狀態容器以實現更好的控制
        status_container = QWidget()
        status_layout = QHBoxLayout(status_container)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        # 測量狀態 - 居中對齊，響應式字體，更醒目的顏色
        self.measurement_status = QLabel("⏸️ 待機中")
        self.measurement_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.measurement_status.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 18px;
                color: #2c3e50;
                background-color: #ecf0f1;
                border: 2px solid #95a5a6;
                border-radius: 8px;
                padding: 8px 15px;
                min-height: 25px;
            }
        """)
        self.measurement_status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # 分隔符
        separator = QLabel("|")
        separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separator.setStyleSheet("color: #95a5a6; font-size: 20px; font-weight: bold;")
        
        # 移除重複的數據點標籤，統一使用狀態欄顯示
        
        # 添加到水平佈局
        status_layout.addWidget(self.measurement_status, 1)
        status_layout.addWidget(separator)
        # 數據點計數統一在狀態欄顯示，不再需要單獨標籤
        
        # 將狀態容器添加到 GroupBox 佈局
        values_layout.addWidget(status_container, 1, 0, 1, 12)  # 跨越所有列
        
        # 將 GroupBox 添加到主佈局
        main_layout.addWidget(data_group)
        
        return status_widget
    
    def update_status_style(self, status_type='idle'):
        """
        更新測量狀態的樣式
        Args:
            status_type: 'idle', 'running', 'completed', 'error'
        """
        style_configs = {
            'idle': {
                'color': '#2c3e50',
                'bg_color': '#ecf0f1',
                'border_color': '#95a5a6'
            },
            'running': {
                'color': '#e67e22',
                'bg_color': '#fdf2e9',
                'border_color': '#e67e22'
            },
            'completed': {
                'color': '#27ae60',
                'bg_color': '#e8f8f5',
                'border_color': '#27ae60'
            },
            'error': {
                'color': '#c0392b',
                'bg_color': '#fadbd8',
                'border_color': '#c0392b'
            }
        }
        
        config = style_configs.get(status_type, style_configs['idle'])
        font_size = self.get_responsive_font_size()
        
        self.measurement_status.setStyleSheet(f"""
            QLabel {{
                font-weight: bold;
                font-size: {font_size}px;
                color: {config['color']};
                background-color: {config['bg_color']};
                border: 2px solid {config['border_color']};
                border-radius: 8px;
                padding: 8px 15px;
                min-height: 25px;
            }}
        """)
        
    def get_responsive_font_size(self):
        """
        根據窗口大小計算響應式字體大小
        Returns:
            int: 字體大小（像素）
        """
        # 獲取當前窗口寬度
        window_width = self.width() if self.width() > 0 else 1200
        
        # 基礎字體大小計算：根據窗口寬度動態調整
        if window_width >= 1400:
            return 20  # 大螢幕
        elif window_width >= 1200:
            return 18  # 中等螢幕  
        elif window_width >= 1000:
            return 16  # 小螢幕
        else:
            return 14  # 極小螢幕
            
    def resizeEvent(self, event):
        """窗口大小改變時更新響應式字體"""
        super().resizeEvent(event)
        
        # 更新狀態顯示字體大小
        if hasattr(self, 'measurement_status'):
            font_size = self.get_responsive_font_size()
            
            # 更新測量狀態字體（保持當前顏色樣式）
            current_style = self.measurement_status.styleSheet()
            if current_style:
                # 替換字體大小
                import re
                new_style = re.sub(r'font-size:\s*\d+px', f'font-size: {font_size}px', current_style)
                self.measurement_status.setStyleSheet(new_style)
            
            # 數據點計數已統一在狀態欄顯示
        
    def create_chart_tab(self):
        """創建圖表分頁"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # 圖表類型選擇
        chart_control = QHBoxLayout()
        chart_control.addWidget(QLabel("圖表類型:"))
        
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["電壓時間序列", "電流時間序列"])  # 移除有問題的功率曲線
        self.chart_type_combo.currentTextChanged.connect(self.update_chart_display)
        chart_control.addWidget(self.chart_type_combo)
        
        chart_control.addStretch()
        layout.addLayout(chart_control)
        
        # 使用分割器創建左右並排圖表顯示
        chart_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 左側圖表 - 主要顯示
        self.main_plot_widget = PlotWidget()
        self.main_plot_widget.setBackground('w')
        self.main_plot_widget.showGrid(True, True)
        self.main_plot_widget.addLegend()
        chart_splitter.addWidget(self.main_plot_widget)
        
        # 右側圖表 - 輔助顯示
        self.aux_plot_widget = PlotWidget()
        self.aux_plot_widget.setBackground('w')
        self.aux_plot_widget.showGrid(True, True)
        self.aux_plot_widget.addLegend()
        chart_splitter.addWidget(self.aux_plot_widget)
        
        # 設定左右圖表比例 (1:1 平均分配)
        chart_splitter.setSizes([500, 500])
        
        layout.addWidget(chart_splitter)
        
        # 設置初始圖表
        self.setup_chart_system()
        
        return tab_widget
        
    def create_data_table_tab(self):
        """創建數據表分頁"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # 表格控制
        table_control = QHBoxLayout()
        table_control.addWidget(QLabel(f"數據記錄表"))
        table_control.addStretch()
        
        self.table_auto_scroll = QCheckBox("自動滾動")
        self.table_auto_scroll.setChecked(True)
        table_control.addWidget(self.table_auto_scroll)
        
        layout.addLayout(table_control)
        
        # 數據表格
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(6)
        self.data_table.setHorizontalHeaderLabels(["點#", "電壓 (V)", "電流 (A)", "電阻 (Ω)", "功率 (W)", "時間"])
        
        # 設置表格屬性
        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        layout.addWidget(self.data_table)
        
        return tab_widget
        
    def create_log_tab(self):
        """創建日誌分頁"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # 日誌控制
        log_control = QHBoxLayout()
        log_control.addWidget(QLabel("操作日誌"))
        log_control.addStretch()
        
        self.clear_log_btn = QPushButton("清除日誌")
        self.clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_control.addWidget(self.clear_log_btn)
        
        layout.addLayout(log_control)
        
        # 日誌顯示區域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # 設定最大行數限制（使用較舊的API相容性方法）
        try:
            self.log_text.setMaximumBlockCount(1000)
        except:
            pass  # 如果不支持則跳過
        layout.addWidget(self.log_text)
        
        return tab_widget

    # ==================== 事件處理方法 ====================
    
    def on_measurement_mode_changed(self, mode_text):
        """測量模式改變處理"""
        if mode_text == "IV特性掃描":
            self.sweep_group.setVisible(True)
            self.measurement_mode = "iv_sweep"
            self.log_message("🔄 切換到IV特性掃描模式")
        else:
            self.sweep_group.setVisible(False)
            self.measurement_mode = "continuous"
            if mode_text == "連續監控":
                self.log_message("📈 切換到連續監控模式")
            else:
                self.log_message("⏱️ 切換到時間序列模式")
                
        # 智慧圖表配合
        self.auto_select_optimal_chart(mode_text)
        self.update_chart_display()
        
    def auto_select_optimal_chart(self, mode_text):
        """根據測量模式自動選擇最佳圖表"""
        chart_mapping = {
            "IV特性掃描": {
                "primary": "IV特性曲線",
                "reason": "IV掃描適合觀察電流-電壓特性和尋找特徵點（如導通點、崩潰點）"
            },
            "連續監控": {
                "primary": "電壓時間序列", 
                "reason": "連續監控適合觀察電壓隨時間的穩定性和漂移趨勢"
            },
            "時間序列": {
                "primary": "電流時間序列",
                "reason": "時間序列模式適合分析電流動態變化和響應特性"
            }
        }
        
        config = chart_mapping.get(mode_text)
        if config:
            current_chart = self.chart_type_combo.currentText()
            optimal_chart = config["primary"]
            
            # 只有在當前圖表不是最佳選擇時才切換
            if current_chart != optimal_chart:
                self.chart_type_combo.setCurrentText(optimal_chart)
                self.log_message(f"📊 智慧選擇「{optimal_chart}」圖表 - {config['reason']}")
    
    def smart_chart_switching(self, source_type):
        """根據源類型智慧切換圖表類型"""
        # 檢查chart_type_combo是否已經創建
        if not hasattr(self, 'chart_type_combo'):
            return
            
        # 定義源類型與最佳圖表的對應關係
        source_chart_mapping = {
            "電壓源": {
                "chart": "電流時間序列",
                "reason": "電壓源模式下，觀察電流響應最為重要"
            },
            "電流源": {
                "chart": "電壓時間序列", 
                "reason": "電流源模式下，觀察電壓響應最為重要"
            }
        }
        
        config = source_chart_mapping.get(source_type)
        if config:
            current_chart = self.chart_type_combo.currentText()
            optimal_chart = config["chart"]
            
            # 只有在當前圖表不是最佳選擇時才切換
            if current_chart != optimal_chart:
                self.chart_type_combo.setCurrentText(optimal_chart)
                self.log_message(f"🔄 源類型智慧切換 - {config['reason']}")
    
    def setup_chart_system(self):
        """初始化圖表系統"""
        # 根據預設的電壓源模式進行初始智慧切換
        initial_source_type = self.source_type_combo.currentText()
        self.smart_chart_switching(initial_source_type)
        
        self.update_chart_display()
        
    def update_chart_display(self):
        """更新圖表顯示"""
        chart_type = self.chart_type_combo.currentText()
        
        if chart_type == "IV特性曲線":
            self.setup_iv_chart()
        elif chart_type == "電壓時間序列":
            self.setup_voltage_time_series()
        elif chart_type == "電流時間序列":  
            self.setup_current_time_series()
        else:
            self.setup_power_chart()
            
    def setup_iv_chart(self):
        """設置IV特性曲線 - 修復版本"""
        # 清空兩個圖表
        self.main_plot_widget.clear()
        self.aux_plot_widget.clear()
        
        # 主圖表：IV特性曲線 - 專業級設定
        self.main_plot_widget.setLabel('left', '電流 (A)', **{'font-size': '12pt', 'font-weight': 'bold'})
        self.main_plot_widget.setLabel('bottom', '電壓 (V)', **{'font-size': '12pt', 'font-weight': 'bold'})  
        self.main_plot_widget.setTitle('IV特性曲線', **{'font-size': '14pt', 'font-weight': 'bold'})
        
        # 設定主圖表網格樣式
        self.main_plot_widget.getAxis('left').setPen(pg.mkPen('#34495e', width=2))
        self.main_plot_widget.getAxis('bottom').setPen(pg.mkPen('#34495e', width=2))
        
        # 輔助圖表：功率曲線 - 專業級設定
        self.aux_plot_widget.setLabel('left', '功率 (W)', **{'font-size': '10pt', 'font-weight': 'bold'})
        self.aux_plot_widget.setLabel('bottom', '電壓 (V)', **{'font-size': '10pt', 'font-weight': 'bold'})
        self.aux_plot_widget.setTitle('功率特性曲線', **{'font-size': '12pt', 'font-weight': 'bold'})
        
        # 設定輔助圖表網格樣式
        self.aux_plot_widget.getAxis('left').setPen(pg.mkPen('#7f8c8d', width=1))
        self.aux_plot_widget.getAxis('bottom').setPen(pg.mkPen('#7f8c8d', width=1))
        
        # 創建主要曲線對象 - 增強視覺效果
        self.iv_curve = self.main_plot_widget.plot(
            pen=pg.mkPen(color='#e74c3c', width=4),  # 增加線條粗細
            symbol='o',
            symbolSize=8,  # 增大符號
            symbolBrush='#e74c3c',
            symbolPen=pg.mkPen('#c0392b', width=2),
            name='I-V曲線'
        )
        
        self.power_curve = self.aux_plot_widget.plot(
            pen=pg.mkPen(color='#f39c12', width=3),
            symbol='s', 
            symbolSize=5,
            symbolBrush='#f39c12',
            name='P-V曲線'
        )
        
    def setup_voltage_time_series(self):
        """設置電壓時間序列"""
        self.main_plot_widget.clear()
        self.aux_plot_widget.clear()
        
        # 主圖表：電壓時間序列
        self.main_plot_widget.setLabel('left', '電壓 (V)')
        self.main_plot_widget.setLabel('bottom', '時間 (s)')
        self.main_plot_widget.setTitle('電壓時間序列')
        
        # 輔助圖表：電阻時間序列
        self.aux_plot_widget.setLabel('left', '電阻 (Ω)')
        self.aux_plot_widget.setLabel('bottom', '時間 (s)')
        self.aux_plot_widget.setTitle('電阻時間序列')
        
        self.voltage_time_curve = self.main_plot_widget.plot(
            pen=pg.mkPen(color='#3498db', width=2),
            name='電壓'
        )
        
        self.resistance_time_curve = self.aux_plot_widget.plot(
            pen=pg.mkPen(color='#27ae60', width=2),
            name='電阻'
        )
        
    def setup_current_time_series(self):
        """設置電流時間序列"""
        self.main_plot_widget.clear()
        self.aux_plot_widget.clear()
        
        # 主圖表：電流時間序列
        self.main_plot_widget.setLabel('left', '電流 (A)')
        self.main_plot_widget.setLabel('bottom', '時間 (s)')
        self.main_plot_widget.setTitle('電流時間序列')
        
        # 輔助圖表：功率時間序列  
        self.aux_plot_widget.setLabel('left', '功率 (W)')
        self.aux_plot_widget.setLabel('bottom', '時間 (s)')
        self.aux_plot_widget.setTitle('功率時間序列')
        
        self.current_time_curve = self.main_plot_widget.plot(
            pen=pg.mkPen(color='#e74c3c', width=2),
            name='電流'
        )
        
        self.power_time_curve = self.aux_plot_widget.plot(
            pen=pg.mkPen(color='#f39c12', width=2),
            name='功率'
        )
        
    def setup_power_chart(self):
        """設置功率曲線"""
        self.main_plot_widget.clear()
        self.aux_plot_widget.clear()
        
        # 主圖表：功率-電壓曲線
        self.main_plot_widget.setLabel('left', '功率 (W)')
        self.main_plot_widget.setLabel('bottom', '電壓 (V)')
        self.main_plot_widget.setTitle('功率特性曲線')
        
        # 輔助圖表：效率曲線（功率密度）
        self.aux_plot_widget.setLabel('left', '功率密度 (W/V)')
        self.aux_plot_widget.setLabel('bottom', '電壓 (V)')
        self.aux_plot_widget.setTitle('功率密度曲線')
        
        self.power_voltage_curve = self.main_plot_widget.plot(
            pen=pg.mkPen(color='#f39c12', width=3),
            symbol='s',
            symbolSize=5,
            symbolBrush='#f39c12', 
            name='P-V曲線'
        )
        
        self.power_density_curve = self.aux_plot_widget.plot(
            pen=pg.mkPen(color='#9b59b6', width=2),
            name='功率密度'
        )

    # ==================== 核心功能方法 ====================
    
    def connect_device(self):
        """連接設備 - 統一使用非阻塞式連線機制"""
        # 強制使用新的非阻塞式連線機制
        if hasattr(self, '_handle_connection_request'):
            self.log_message("🔄 使用非阻塞式連線機制")
            self._handle_connection_request()
        else:
            self.log_message("❌ 非阻塞式連線機制未初始化")
            QMessageBox.critical(self, "系統錯誤", "連線系統未正確初始化，請重新啟動程式")
            
    def disconnect_device(self):
        """斷開設備連接 - 統一使用非阻塞式連線機制"""
        # 強制使用新的非阻塞式斷線機制
        if hasattr(self, '_handle_disconnection_request'):
            self.log_message("🔄 使用非阻塞式斷線機制")
            self._handle_disconnection_request()
        else:
            # 基本斷線邏輯（後備方案）
            try:
                if self.keithley and self.keithley.connected:
                    self.keithley.output_off()
                    self.keithley.disconnect()
                    
                self.keithley = None
                self.connection_changed.emit(False, "")
                self.log_message("✅ 設備已斷開連接")
                
            except Exception as e:
                self.log_message(f"❌ 斷開連接時發生錯誤: {e}")
    
    # ==================== 新的非阻塞式連線方法 ====================
    
    def _handle_connection_request(self):
        """處理連線請求 - 非阻塞式"""
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            self.connection_status_widget.set_connection_failed_state("請輸入IP地址")
            return
            
        # 驗證IP格式（簡單檢查）
        if not self._is_valid_ip(ip_address):
            self.connection_status_widget.set_connection_failed_state("IP地址格式不正確")
            return
            
        try:
            # 開始非阻塞連線
            connection_params = {
                'ip_address': ip_address,
                'port': 5025,
                'timeout': 5.0  # 5秒超時
            }
            
            worker = self.connection_manager.start_connection('keithley', connection_params)
            
            # 連接工作執行緒信號
            worker.connection_started.connect(self._on_connection_started)
            worker.connection_progress.connect(self._on_connection_progress)
            worker.connection_success.connect(self._on_connection_success)
            worker.connection_failed.connect(self._on_connection_failed)
            
            # 啟動工作執行緒
            worker.start()
            
        except RuntimeError as e:
            self.connection_status_widget.set_connection_failed_state(str(e))
            
    def _handle_disconnection_request(self):
        """處理斷線請求"""
        try:
            # 停止所有測量
            self.stop_measurement()
            
            if self.keithley and self.keithley.connected:
                self.keithley.output_off()
                self.keithley.disconnect()
                
            self.keithley = None
            
            # 關閉數據記錄會話
            if self.data_logger:
                try:
                    self.data_logger.close_session()
                    self.data_logger = None
                    self.log_message("📊 數據記錄會話已關閉")
                except Exception as e:
                    self.log_message(f"❌ 關閉數據會話錯誤: {e}")
                    
            self.connection_status_widget.set_disconnected_state()
            
            # 更新UI狀態
            if hasattr(self, 'start_btn'):
                self.start_btn.setEnabled(False)
            if hasattr(self, 'stop_btn'):
                self.stop_btn.setEnabled(False)
                
            # 發送信號通知父組件
            self.connection_changed.emit(False, "")
            
            self.log_message("✅ 已安全斷開設備連線")
            
        except Exception as e:
            self.log_message(f"❌ 斷線時發生錯誤: {e}")
            
    def _handle_connection_cancel(self):
        """處理連線取消"""
        self.connection_manager.cancel_connection()
        self.connection_status_widget.set_disconnected_state()
        self.log_message("⚠️ 用戶取消連線")
        
    def _on_connection_started(self):
        """連線開始回調"""
        self.connection_status_widget.set_connecting_state()
        self.log_message("🔄 開始連線儀器...")
        
    def _on_connection_progress(self, message: str):
        """連線進度回調"""
        self.connection_status_widget.update_connection_progress(message)
        self.log_message(f"🔄 {message}")
        
    def _on_connection_success(self, device_info: str):
        """連線成功回調"""
        # 獲取儀器實例
        worker = self.connection_manager.connection_worker
        if worker:
            self.keithley = worker.get_instrument()
            
        # 更新UI狀態
        device_name = device_info.split('\n')[0] if device_info else ""
        self.connection_status_widget.set_connected_state(device_name)
        
        if hasattr(self, 'start_btn'):
            self.start_btn.setEnabled(True)
            
        # 初始化數據記錄器
        self._initialize_enhanced_data_logger()
        
        # 發送信號通知父組件
        self.connection_changed.emit(True, device_info)
        
        self.log_message(f"✅ 連線成功: {device_info}")
        
    def _on_connection_failed(self, error_message: str):
        """連線失敗回調"""
        self.connection_status_widget.set_connection_failed_state(error_message)
        self.keithley = None
        
        if hasattr(self, 'start_btn'):
            self.start_btn.setEnabled(False)
            
        # 發送信號通知父組件
        self.connection_changed.emit(False, "")
        
        self.log_message(f"❌ 連線失敗: {error_message}")
        
    def _initialize_enhanced_data_logger(self):
        """初始化增強版數據記錄器"""
        try:
            if self.data_logger is None:
                self.data_logger = EnhancedDataLogger(
                    base_path="data",
                    auto_save_interval=300,  # 5分鐘自動保存
                    max_memory_points=5000   # 5000個數據點內存限制
                )
                
                # 連接數據系統信號
                if hasattr(self.data_logger, 'data_saved'):
                    self.data_logger.data_saved.connect(self.on_data_saved)
                if hasattr(self.data_logger, 'statistics_updated'):
                    self.data_logger.statistics_updated.connect(self.on_statistics_updated)
                if hasattr(self.data_logger, 'anomaly_detected'):
                    self.data_logger.anomaly_detected.connect(self.on_anomaly_detected)
                if hasattr(self.data_logger, 'storage_warning'):
                    self.data_logger.storage_warning.connect(self.on_storage_warning)
                    
                # 準備會話配置
                ip_address = self.ip_input.text().strip()
                instrument_config = {
                    'instrument': 'Keithley 2461',
                    'ip_address': ip_address,
                    'connection_time': datetime.now().isoformat()
                }
                
                session_name = self.data_logger.start_session(
                    description=f"Keithley 2461 測量會話 - {ip_address}",
                    instrument_config=instrument_config
                )
                self.log_message(f"📊 開始增強型數據記錄會話: {session_name}")
                    
        except ImportError:
            self.log_message("⚠️ 增強型數據系統不可用，使用基本功能")
        except Exception as e:
            self.log_message(f"⚠️ 數據記錄器初始化警告: {e}")
            
    def _is_valid_ip(self, ip_address: str) -> bool:
        """檢查IP地址格式"""
        try:
            parts = ip_address.split('.')
            if len(parts) != 4:
                return False
                
            for part in parts:
                num = int(part)
                if not 0 <= num <= 255:
                    return False
                    
            return True
        except (ValueError, AttributeError):
            return False
    
    def start_measurement(self):
        """開始測量"""
        # 檢查連線狀態 - 支援新舊連線機制
        is_connected = False
        
        # 優先檢查儀器物件的連線狀態
        if self.keithley and hasattr(self.keithley, 'connected') and self.keithley.connected:
            is_connected = True
        # 如果沒有儀器物件，檢查新的連線狀態widget
        elif hasattr(self, 'connection_status_widget'):
            status_text = self.connection_status_widget.status_text.text()
            is_connected = "已連接" in status_text
        # 舊的連線狀態標籤已移除
            
        if not is_connected:
            # 添加詳細的調試信息
            debug_info = []
            if self.keithley:
                debug_info.append(f"keithley物件存在: {hasattr(self.keithley, 'connected')}")
                if hasattr(self.keithley, 'connected'):
                    debug_info.append(f"keithley.connected: {self.keithley.connected}")
            else:
                debug_info.append("keithley物件為None")
                
            if hasattr(self, 'connection_status_widget'):
                status_text = self.connection_status_widget.status_text.text()
                debug_info.append(f"新狀態widget: {status_text}")
            
            # 舊狀態標籤已移除，跳過檢查
                
            self.log_message(f"🔍 連線狀態檢查: {'; '.join(debug_info)}")
            QMessageBox.warning(self, "警告", "請先連接設備")
            return
            
        try:
            self.is_measuring = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            
            # 清除舊數據
            self.iv_data.clear()
            self.time_series_data.clear()
            self.start_time = datetime.now()
            
            # 啟動狀態更新定時器
            self.status_update_timer.start(1000)  # 每秒更新一次
            
            if self.measurement_mode == "iv_sweep":
                self.start_iv_sweep()
            else:
                self.start_continuous_measurement()
                
        except Exception as e:
            QMessageBox.critical(self, "測量錯誤", f"啟動測量時發生錯誤: {str(e)}")
            self.log_message(f"❌ 測量啟動錯誤: {e}")
            self.is_measuring = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def start_iv_sweep(self):
        """開始IV掃描"""
        try:
            # 獲取掃描參數
            start_text = self.start_input.value_edit.text()
            start_unit = self.start_input.get_current_prefix() 
            start_str = f"{start_text}{start_unit}" if start_unit else start_text
            start_value = float(self.keithley._convert_unit_format(start_str))
            
            stop_text = self.stop_input.value_edit.text()
            stop_unit = self.stop_input.get_current_prefix()
            stop_str = f"{stop_text}{stop_unit}" if stop_unit else stop_text
            stop_value = float(self.keithley._convert_unit_format(stop_str))
            
            step_text = self.step_input.value_edit.text()
            step_unit = self.step_input.get_current_prefix()
            step_str = f"{step_text}{step_unit}" if step_unit else step_text
            step_value = float(self.keithley._convert_unit_format(step_str))
            
            delay_ms = self.delay_input.value()
            
            # 獲取電流限制
            current_limit_text = self.current_limit.value_edit.text()
            current_limit_unit = self.current_limit.get_current_prefix()
            current_limit_str = f"{current_limit_text}{current_limit_unit}" if current_limit_unit else current_limit_text
            
            sweep_params = {
                'start': start_value,
                'stop': stop_value,
                'step': step_value,
                'delay': delay_ms,
                'current_limit': current_limit_str
            }
            
            # 啟動掃描工作執行緒
            self.sweep_worker = SweepMeasurementWorker(self.keithley, sweep_params)
            self.sweep_worker.data_point_ready.connect(self.update_iv_data)
            self.sweep_worker.sweep_progress.connect(self.update_progress)
            self.sweep_worker.sweep_completed.connect(self.on_sweep_completed)
            self.sweep_worker.error_occurred.connect(self.handle_measurement_error)
            
            self.sweep_worker.start()
            
            self.progress_bar.setVisible(True)
            self.measurement_status.setText("🔄 IV掃描進行中...")
            self.update_status_style('running')
            self.log_message(f"🚀 開始IV掃描: {start_value}V → {stop_value}V, 步進: {step_value}V")
            
        except Exception as e:
            raise Exception(f"IV掃描參數錯誤: {e}")
    
    def start_continuous_measurement(self):
        """開始連續測量"""
        try:
            # 應用源設定
            self.apply_source_settings()
            
            # 啟動連續測量工作執行緒
            self.continuous_worker = ContinuousMeasurementWorker(self.keithley)
            self.continuous_worker.data_ready.connect(self.update_continuous_data)
            self.continuous_worker.error_occurred.connect(self.handle_measurement_error)
            
            self.continuous_worker.start_measurement()
            
            self.measurement_status.setText("📈 連續測量中...")
            self.update_status_style('running')
            self.log_message("▶️ 開始連續測量")
            
        except Exception as e:
            raise Exception(f"連續測量啟動錯誤: {e}")
    
    def apply_source_settings(self):
        """應用源設定"""
        source_type = self.source_type_combo.currentText()
        
        # 設定測量速度
        speed_text = self.measurement_speed_combo.currentText()
        if "0.1" in speed_text:
            nplc = 0.1
        elif "10" in speed_text:
            nplc = 10.0
        else:
            nplc = 1.0
        self.keithley.set_measurement_speed(nplc)
        
        if source_type == "電壓源":
            self.apply_voltage_source_settings()
        else:
            self.apply_current_source_settings()
            
        # 開啟輸出
        self.keithley.output_on()
        self.log_message("⚡ 輸出已開啟")
    
    def apply_voltage_source_settings(self):
        """應用電壓源設定"""
        # 獲取電壓值
        voltage_text = self.output_voltage.value_edit.text()
        voltage_unit = self.output_voltage.get_current_prefix()
        voltage_str = f"{voltage_text}{voltage_unit}" if voltage_unit else voltage_text
        
        # 獲取電流限制
        current_limit_text = self.current_limit.value_edit.text()
        current_limit_unit = self.current_limit.get_current_prefix()
        current_limit_str = f"{current_limit_text}{current_limit_unit}" if current_limit_unit else current_limit_text
        
        # 設定範圍
        voltage_range = self.voltage_range_combo.currentText()
        if voltage_range != "自動":
            range_value = voltage_range.replace("V", "")
            self.keithley.send_command(f":SOUR:VOLT:RANG {range_value}")
        else:
            self.keithley.send_command(":SOUR:VOLT:RANG:AUTO ON")
            
        # 應用設定
        self.keithley.set_voltage(voltage_str, current_limit=current_limit_str)
        self.log_message(f"🔋 電壓源設定: {voltage_str}V, 限制: {current_limit_str}A, 範圍: {voltage_range}")
        
    def apply_current_source_settings(self):
        """應用電流源設定"""
        # 獲取電流值
        current_text = self.output_current.value_edit.text()
        current_unit = self.output_current.get_current_prefix()
        current_str = f"{current_text}{current_unit}" if current_unit else current_text
        
        # 獲取電壓限制
        voltage_limit_text = self.voltage_limit.value_edit.text()
        voltage_limit_unit = self.voltage_limit.get_current_prefix()
        voltage_limit_str = f"{voltage_limit_text}{voltage_limit_unit}" if voltage_limit_unit else voltage_limit_text
        
        # 設定範圍
        current_range = self.current_range_combo.currentText()
        if current_range != "自動":
            range_value = current_range.replace("A", "").replace("mA", "m")
            range_converted = self.keithley._convert_unit_format(range_value)
            self.keithley.send_command(f":SOUR:CURR:RANG {range_converted}")
        else:
            self.keithley.send_command(":SOUR:CURR:RANG:AUTO ON")
            
        # 應用設定
        self.keithley.set_current(current_str, voltage_limit=voltage_limit_str)
        self.log_message(f"⚡ 電流源設定: {current_str}A, 限制: {voltage_limit_str}V, 範圍: {current_range}")
    
    def stop_measurement(self):
        """停止測量"""
        try:
            self.is_measuring = False
            
            # 停止狀態更新定時器
            self.status_update_timer.stop()
            
            # 停止工作執行緒
            if self.sweep_worker:
                self.sweep_worker.stop_sweep()
                self.sweep_worker = None
                
            if self.continuous_worker:
                self.continuous_worker.stop_measurement()
                self.continuous_worker = None
            
            # 關閉輸出
            if self.keithley and self.keithley.connected:
                self.keithley.output_off()
                
            # 更新UI狀態
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.progress_bar.setVisible(False)
            self.measurement_status.setText("⏸️ 測量已停止")
            self.update_status_style('idle')
            
            self.log_message("⏹️ 測量已停止，輸出已關閉")
            
        except Exception as e:
            self.log_message(f"❌ 停止測量時發生錯誤: {e}")
    
    # ==================== 數據更新方法 ====================
    
    def format_engineering_value(self, value, unit_type='V'):
        """
        將數值轉換為工程計數法格式
        Args:
            value: 原始數值
            unit_type: 單位類型 ('V', 'A', 'W', 'Ω')
        Returns:
            tuple: (formatted_value, unit_string)
        """
        if value == 0:
            return "0.00", unit_type
        
        abs_value = abs(value)
        sign = '-' if value < 0 else ''
        
        # 定義單位前綴和範圍 - 優化閾值以適應6位LCD顯示
        if unit_type in ['V', 'A', 'W']:
            # 電壓、電流、功率使用標準單位前綴
            # 調整閾值：當值 >= 100 時就轉換，確保顯示不超過6位（含負號）
            if abs_value >= 1000:
                return f"{sign}{abs_value/1000:.2f}", f"k{unit_type}"
            elif abs_value >= 100:
                # 100-999 範圍：如果保持原單位會需要6-7位，轉換為較大單位
                if len(f"{sign}{abs_value:.2f}") > 6:
                    return f"{sign}{abs_value/1000:.3f}", f"k{unit_type}"
                else:
                    return f"{sign}{abs_value:.2f}", unit_type
            elif abs_value >= 1:
                return f"{sign}{abs_value:.2f}", unit_type
            elif abs_value >= 0.001:
                return f"{sign}{abs_value*1000:.2f}", f"m{unit_type}"
            elif abs_value >= 0.000001:
                return f"{sign}{abs_value*1000000:.2f}", f"μ{unit_type}"
            else:
                return f"{sign}{abs_value*1000000000:.2f}", f"n{unit_type}"
        elif unit_type == 'Ω':
            # 電阻使用不同的單位範圍 - 優化閾值以適應6位LCD顯示
            if abs_value >= 1000000:
                return f"{sign}{abs_value/1000000:.2f}", "MΩ"
            elif abs_value >= 1000:
                return f"{sign}{abs_value/1000:.2f}", "kΩ"
            elif abs_value >= 100:
                # 100-999 範圍：檢查是否會超過6位
                if len(f"{sign}{abs_value:.2f}") > 6:
                    return f"{sign}{abs_value/1000:.3f}", "kΩ"
                else:
                    return f"{sign}{abs_value:.2f}", "Ω"
            elif abs_value >= 1:
                return f"{sign}{abs_value:.2f}", "Ω"
            else:
                return f"{sign}{abs_value*1000:.2f}", "mΩ"
        
        return f"{sign}{abs_value:.2f}", unit_type
    
    def update_iv_data(self, voltage, current, resistance, power, point_num):
        """更新IV數據 (使用儀器計算的功率值)"""
        # power 參數現在來自儀器的 SCPI 計算，不再本地重新計算
        
        # 存儲數據
        self.iv_data.append((voltage, current, resistance, power))
        
        # 更新LCD顯示 - 使用工程計數法格式
        v_val, v_unit = self.format_engineering_value(voltage, 'V')
        self.voltage_display.display(v_val)
        self.voltage_unit_label.setText(v_unit)
        
        i_val, i_unit = self.format_engineering_value(current, 'A')
        self.current_display.display(i_val)
        self.current_unit_label.setText(i_unit)
        
        r_val, r_unit = self.format_engineering_value(resistance, 'Ω')
        self.resistance_display.display(r_val)
        self.resistance_unit_label.setText(r_unit)
        
        p_val, p_unit = self.format_engineering_value(power, 'W')
        self.power_display.display(p_val)
        self.power_unit_label.setText(p_unit)
        
        # 更新圖表
        if self.chart_type_combo.currentText() == "IV特性曲線":
            voltages = [data[0] for data in self.iv_data]
            currents = [data[1] for data in self.iv_data]
            self.iv_curve.setData(voltages, currents)
        elif self.chart_type_combo.currentText() == "功率曲線":
            voltages = [data[0] for data in self.iv_data]
            powers = [data[3] for data in self.iv_data]
            self.power_curve.setData(voltages, powers)
        
        # 更新數據表
        self.add_data_to_table(point_num, voltage, current, resistance, power)
        
        # 記錄數據
        if self.record_data_cb.isChecked() and self.data_logger:
            self.data_logger.log_measurement(voltage, current, resistance, power)
        
        # 更新狀態
        # 數據點統一在狀態欄顯示
    
    def update_continuous_data(self, voltage, current, resistance, power):
        """更新連續測量數據"""
        current_time = (datetime.now() - self.start_time).total_seconds()
        
        # 存儲數據
        self.time_series_data.append((current_time, voltage, current, resistance, power))
        
        # 更新LCD顯示 - 使用工程計數法格式
        v_val, v_unit = self.format_engineering_value(voltage, 'V')
        self.voltage_display.display(v_val)
        self.voltage_unit_label.setText(v_unit)
        
        i_val, i_unit = self.format_engineering_value(current, 'A')
        self.current_display.display(i_val)
        self.current_unit_label.setText(i_unit)
        
        r_val, r_unit = self.format_engineering_value(resistance, 'Ω')
        self.resistance_display.display(r_val)
        self.resistance_unit_label.setText(r_unit)
        
        p_val, p_unit = self.format_engineering_value(power, 'W')
        self.power_display.display(p_val)
        self.power_unit_label.setText(p_unit)
        
        # 更新時間序列圖表
        chart_type = self.chart_type_combo.currentText()
        if chart_type in ["電壓時間序列", "電流時間序列", "時間序列"]:
            times = [data[0] for data in self.time_series_data[-100:]]  # 只顯示最近100個點
            voltages = [data[1] for data in self.time_series_data[-100:]]
            currents = [data[2] for data in self.time_series_data[-100:]]
            resistances = [data[3] for data in self.time_series_data[-100:]]
            powers = [data[4] for data in self.time_series_data[-100:]]
            
            # 根據圖表類型更新對應的曲線 - 強化輔助圖表更新
            if chart_type == "電壓時間序列":
                # 主圖表：電壓
                if hasattr(self, 'voltage_time_curve') and self.voltage_time_curve is not None:
                    self.voltage_time_curve.setData(times, voltages)
                # 輔助圖表：電阻
                if hasattr(self, 'resistance_time_curve') and self.resistance_time_curve is not None:
                    self.resistance_time_curve.setData(times, resistances)
            elif chart_type == "電流時間序列":
                # 主圖表：電流
                if hasattr(self, 'current_time_curve') and self.current_time_curve is not None:
                    self.current_time_curve.setData(times, currents)
                # 輔助圖表：功率
                if hasattr(self, 'power_time_curve') and self.power_time_curve is not None:
                    self.power_time_curve.setData(times, powers)
            elif chart_type == "時間序列" and hasattr(self, 'voltage_curve'):
                # 舊版相容性
                self.voltage_curve.setData(times, voltages)
                if hasattr(self, 'current_curve'):
                    self.current_curve.setData(times, currents)
        
        # 更新數據表 (每5個點添加一次，避免表格過度增長)
        if len(self.time_series_data) % 5 == 0:
            point_num = len(self.time_series_data) // 5
            self.add_data_to_table(point_num, voltage, current, resistance, power)
        
        # 記錄數據
        if self.record_data_cb.isChecked() and self.data_logger:
            self.data_logger.log_measurement(voltage, current, resistance, power)
        
        # 更新狀態
        # 數據點統一在狀態欄顯示
    
    def add_data_to_table(self, point_num, voltage, current, resistance, power):
        """添加數據到表格"""
        row_count = self.data_table.rowCount()
        self.data_table.insertRow(row_count)
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        self.data_table.setItem(row_count, 0, QTableWidgetItem(f"{point_num:03d}"))
        self.data_table.setItem(row_count, 1, QTableWidgetItem(f"{voltage:.6f}"))
        self.data_table.setItem(row_count, 2, QTableWidgetItem(f"{current:.6f}"))
        self.data_table.setItem(row_count, 3, QTableWidgetItem(f"{resistance:.2f}"))
        self.data_table.setItem(row_count, 4, QTableWidgetItem(f"{power:.6f}"))
        self.data_table.setItem(row_count, 5, QTableWidgetItem(timestamp))
        
        # 自動滾動
        if self.table_auto_scroll.isChecked():
            self.data_table.scrollToBottom()
    
    def update_progress(self, percentage):
        """更新進度條"""
        self.progress_bar.setValue(percentage)
    
    def on_sweep_completed(self):
        """掃描完成處理"""
        self.measurement_status.setText("✅ IV掃描已完成")
        self.update_status_style('completed')
        self.progress_bar.setVisible(False)
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.is_measuring = False
        
        total_points = len(self.iv_data)
        self.log_message(f"✅ IV掃描完成，共獲得 {total_points} 個數據點")
        
        # 關閉輸出
        if self.keithley:
            self.keithley.output_off()
            self.log_message("⚡ 輸出已關閉")
    
    def handle_measurement_error(self, error_message):
        """處理測量錯誤"""
        self.log_message(f"❌ 測量錯誤: {error_message}")
        self.stop_measurement()
        QMessageBox.critical(self, "測量錯誤", f"測量過程中發生錯誤:\n{error_message}")
    
    # ==================== 數據管理方法 ====================
    
    def export_data(self):
        """導出數據"""
        if not self.iv_data and not self.time_series_data:
            QMessageBox.information(self, "提示", "沒有數據可導出")
            return
            
        try:
            if self.data_logger:
                # 使用增強數據系統的匯出功能
                csv_file = self.data_logger.export_session_data('csv')
                QMessageBox.information(self, "成功", f"數據已導出到:\n{csv_file}")
                self.log_message(f"📊 數據已導出到: {csv_file}")
            else:
                # 如果沒有data_logger，創建臨時導出
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"keithley_data_{timestamp}.csv"
                
                with open(filename, 'w', newline='') as f:
                    f.write("Point,Voltage(V),Current(A),Resistance(Ω),Power(W),Timestamp\n")
                    
                    if self.measurement_mode == "iv_sweep":
                        for i, (v, i_val, r, p) in enumerate(self.iv_data):
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            f.write(f"{i+1},{v:.6f},{i_val:.6f},{r:.2f},{p:.6f},{timestamp}\n")
                    else:
                        for i, (t, v, i_val, r, p) in enumerate(self.time_series_data):
                            timestamp = (self.start_time + timedelta(seconds=t)).strftime("%Y-%m-%d %H:%M:%S")
                            f.write(f"{i+1},{v:.6f},{i_val:.6f},{r:.2f},{p:.6f},{timestamp}\n")
                
                QMessageBox.information(self, "成功", f"數據已導出到:\n{filename}")
                self.log_message(f"📊 數據已導出到: {filename}")
                
        except Exception as e:
            QMessageBox.critical(self, "導出錯誤", f"導出數據時發生錯誤:\n{str(e)}")
            self.log_message(f"❌ 導出錯誤: {e}")
    
    def clear_data(self):
        """清除數據"""
        reply = QMessageBox.question(
            self, "確認", "確定要清除所有測量數據嗎？", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 清除內存數據
            self.iv_data.clear()
            self.time_series_data.clear()
            
            # 清除圖表
            if hasattr(self, 'iv_curve'):
                self.iv_curve.clear()
            if hasattr(self, 'voltage_curve'):
                self.voltage_curve.clear()
            if hasattr(self, 'current_curve'):
                self.current_curve.clear()
            if hasattr(self, 'power_curve'):
                self.power_curve.clear()
            
            # 清除數據表
            self.data_table.setRowCount(0)
            
            # 重置顯示
            self.voltage_display.display(0)
            self.current_display.display(0)
            self.resistance_display.display(0)
            self.power_display.display(0)
            # 數據點計數由增強數據系統管理
            
            # 清除增強數據系統的內存緩存
            if self.data_logger:
                try:
                    with self.data_logger.data_lock:
                        self.data_logger.memory_buffer.clear()
                        self.data_logger.total_points = 0
                        self.log_message("💾 內存數據已清除")
                except Exception as e:
                    self.log_message(f"❌ 清除數據錯誤: {e}")
                
            self.log_message("🔄 所有測量數據已清除")
    
    def on_data_saved(self, message):
        """處理數據保存完成信號"""
        self.log_message(f"💾 {message}")
        
    def update_runtime_display(self):
        """使用QTimer更新運行時間顯示"""
        if not self.is_measuring or not hasattr(self, 'start_time') or not self.start_time:
            return
            
        try:
            # 計算運行時間
            duration = (datetime.now() - self.start_time).total_seconds()
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            
            # 獲取數據點數量
            if self.data_logger and hasattr(self.data_logger, 'total_points'):
                total_points = self.data_logger.total_points
            else:
                total_points = len(self.time_series_data) if hasattr(self, 'time_series_data') else 0
            
            # 構建狀態文字
            status_text = f"📊 數據點: {total_points} | 運行時間: {hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # 如果有最近的統計數據，添加平均值顯示
            if hasattr(self, '_last_avg_voltage') and self._last_avg_voltage is not None:
                status_text += f" | 平均電壓: {self._last_avg_voltage:.3f}V"
            
            self.measurement_status.setText(status_text)
            
        except Exception as e:
            self.logger.debug(f"運行時間更新錯誤: {e}")
    
    def on_statistics_updated(self, stats):
        """處理統計數據更新信號"""
        try:
            # 保存統計數據供QTimer使用
            voltage_stats = stats.get('voltage', {})
            if voltage_stats.get('count', 0) > 0:
                self._last_avg_voltage = voltage_stats.get('mean', 0)
            else:
                self._last_avg_voltage = None
                
        except Exception as e:
            self.logger.error(f"統計更新錯誤: {e}")
    
    def on_anomaly_detected(self, message, data):
        """處理異常檢測信號"""
        self.log_message(f"⚠️ 異常檢測: {message}")
        
        # 可選：顯示更詳細的異常信息
        try:
            v = data.get('voltage_v', 0)
            i = data.get('current_a', 0)
            self.log_message(f"   異常數據點: V={v:.6f}V, I={i:.6f}A")
        except:
            pass
    
    def on_storage_warning(self, message):
        """處理存儲警告信號"""
        self.log_message(f"💽 存儲警告: {message}")
        
        # 顯示用戶友好的提醒
        try:
            if hasattr(self, 'data_logger') and self.data_logger:
                stats = self.data_logger.get_session_statistics()
                session_info = stats.get('session_info', {})
                total_points = session_info.get('total_points', 0)
                
                if total_points > 4000:  # 接近內存限制
                    self.log_message("💡 建議：數據點較多，系統將自動保存到數據庫")
        except:
            pass
    
    def log_message(self, message):
        """添加日誌訊息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 檢查log_text是否已創建
        if hasattr(self, 'log_text'):
            self.log_text.append(formatted_message)
            
            # 自動滾動到底部
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)
        
        # 同時輸出到控制台日誌
        self.logger.info(message)

    def set_theme(self, theme):
        """設置主題"""
        self.current_theme = theme
        self.update_plot_theme()
    
    def update_plot_theme(self):
        """更新圖表主題"""
        try:
            if self.current_theme == "dark":
                # 深色主題
                if hasattr(self, 'main_plot_widget'):
                    self.main_plot_widget.setBackground('#2b2b2b')
                    self.main_plot_widget.getAxis('left').setPen('#ffffff')
                    self.main_plot_widget.getAxis('bottom').setPen('#ffffff')
                    self.main_plot_widget.getAxis('left').setTextPen('#ffffff')
                    self.main_plot_widget.getAxis('bottom').setTextPen('#ffffff')
                if hasattr(self, 'aux_plot_widget'):
                    self.aux_plot_widget.setBackground('#2b2b2b')
                    self.aux_plot_widget.getAxis('left').setPen('#ffffff')
                    self.aux_plot_widget.getAxis('bottom').setPen('#ffffff')
                    self.aux_plot_widget.getAxis('left').setTextPen('#ffffff')
                    self.aux_plot_widget.getAxis('bottom').setTextPen('#ffffff')
            else:
                # 淺色主題
                if hasattr(self, 'main_plot_widget'):
                    self.main_plot_widget.setBackground('#ffffff')
                    self.main_plot_widget.getAxis('left').setPen('#000000')
                    self.main_plot_widget.getAxis('bottom').setPen('#000000')
                    self.main_plot_widget.getAxis('left').setTextPen('#000000')
                    self.main_plot_widget.getAxis('bottom').setTextPen('#000000')
                if hasattr(self, 'aux_plot_widget'):
                    self.aux_plot_widget.setBackground('#ffffff')
                    self.aux_plot_widget.getAxis('left').setPen('#000000')
                    self.aux_plot_widget.getAxis('bottom').setPen('#000000')
                    self.aux_plot_widget.getAxis('left').setTextPen('#000000')
                    self.aux_plot_widget.getAxis('bottom').setTextPen('#000000')
                
        except Exception as e:
            self.logger.error(f"更新圖表主題失敗: {e}")