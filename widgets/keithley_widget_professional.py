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
                            QFrame, QLCDNumber)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.keithley_2461 import Keithley2461
from src.data_logger import DataLogger
from widgets.unit_input_widget import UnitInputWidget, UnitDisplayWidget


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
        """創建設備連接群組"""
        group = QGroupBox("🔌 設備連接")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit("192.168.0.100")
        layout.addWidget(self.ip_input, 0, 1)
        
        self.connect_btn = QPushButton("連接")
        self.connect_btn.clicked.connect(self.connect_device)
        layout.addWidget(self.connect_btn, 1, 0, 1, 2)
        
        # 狀態指示
        self.connection_status = QLabel("🔴 未連接")
        self.connection_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        layout.addWidget(self.connection_status, 2, 0, 1, 2)
        
        return group
        
    def create_measurement_mode_group(self):
        """創建測量模式群組"""
        group = QGroupBox("📊 測量模式")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("模式:"), 0, 0)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["連續監控", "IV特性掃描", "時間序列"])
        self.mode_combo.currentTextChanged.connect(self.on_measurement_mode_changed)
        layout.addWidget(self.mode_combo, 0, 1)
        
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
        
        # 默認隱藏（只在IV掃描模式顯示）
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
        display_splitter.setSizes([250, 750])
        
        layout.addWidget(display_splitter)
        
        return display_widget
        
    def create_status_bar(self):
        """創建數據顯示區域（原狀態欄）"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        # 移除固定高度限制，讓它使用分配的空間
        layout = QHBoxLayout(frame)
        
        # 實時數值顯示
        values_layout = QGridLayout()
        
        # 電壓顯示 - 專業級樣式
        voltage_label = QLabel("電壓:")
        voltage_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        values_layout.addWidget(voltage_label, 0, 0)
        self.voltage_display = QLCDNumber(10)  # 增加數字位數
        self.voltage_display.setStyleSheet("""
            QLCDNumber { 
                color: #2980b9; 
                background-color: #34495e;
                border: 2px solid #2980b9;
                border-radius: 5px;
                font-size: 16px;
                min-height: 50px;
            }
        """)
        values_layout.addWidget(self.voltage_display, 0, 1)
        unit_v = QLabel("V")
        unit_v.setStyleSheet("font-weight: bold; color: #2980b9; font-size: 14px;")
        values_layout.addWidget(unit_v, 0, 2)
        
        # 電流顯示 - 專業級樣式
        current_label = QLabel("電流:")
        current_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        values_layout.addWidget(current_label, 0, 3)
        self.current_display = QLCDNumber(10)  # 增加數字位數
        self.current_display.setStyleSheet("""
            QLCDNumber { 
                color: #e74c3c; 
                background-color: #34495e;
                border: 2px solid #e74c3c;
                border-radius: 5px;
                font-size: 16px;
                min-height: 50px;
            }
        """)
        values_layout.addWidget(self.current_display, 0, 4)
        unit_a = QLabel("A")
        unit_a.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 14px;")
        values_layout.addWidget(unit_a, 0, 5)
        
        # 功率顯示 - 專業級樣式 (移至第一排)
        power_label = QLabel("功率:")
        power_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        values_layout.addWidget(power_label, 0, 6)
        self.power_display = QLCDNumber(10)  # 增加數字位數
        self.power_display.setStyleSheet("""
            QLCDNumber { 
                color: #f39c12; 
                background-color: #34495e;
                border: 2px solid #f39c12;
                border-radius: 5px;
                font-size: 16px;
                min-height: 50px;
            }
        """)
        values_layout.addWidget(self.power_display, 0, 7)
        unit_w = QLabel("W")
        unit_w.setStyleSheet("font-weight: bold; color: #f39c12; font-size: 14px;")
        values_layout.addWidget(unit_w, 0, 8)
        
        # 電阻顯示 - 專業級樣式 (移至第一排)
        resistance_label = QLabel("電阻:")
        resistance_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        values_layout.addWidget(resistance_label, 0, 9)
        self.resistance_display = QLCDNumber(10)  # 增加數字位數
        self.resistance_display.setStyleSheet("""
            QLCDNumber { 
                color: #27ae60; 
                background-color: #34495e;
                border: 2px solid #27ae60;
                border-radius: 5px;
                font-size: 16px;
                min-height: 50px;
            }
        """)
        values_layout.addWidget(self.resistance_display, 0, 10)
        unit_ohm = QLabel("Ω")
        unit_ohm.setStyleSheet("font-weight: bold; color: #27ae60; font-size: 14px;")
        values_layout.addWidget(unit_ohm, 0, 11)
        
        # 狀態信息 - 整合到第二排
        self.measurement_status = QLabel("⏸️ 待機中")
        self.measurement_status.setStyleSheet("font-weight: bold; font-size: 16px; color: #34495e;")
        values_layout.addWidget(self.measurement_status, 1, 0, 1, 6)  # 跨越6列
        
        self.data_points_label = QLabel("數據點: 0")
        self.data_points_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #7f8c8d;")
        values_layout.addWidget(self.data_points_label, 1, 6, 1, 6)  # 跨越剩餘6列
        
        layout.addLayout(values_layout)
        
        return frame
        
    def create_chart_tab(self):
        """創建圖表分頁"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # 圖表類型選擇
        chart_control = QHBoxLayout()
        chart_control.addWidget(QLabel("圖表類型:"))
        
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["IV特性曲線", "電壓時間序列", "電流時間序列", "功率曲線"])
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
    
    def setup_chart_system(self):
        """初始化圖表系統"""
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
        """連接設備"""
        if not self.keithley or not self.keithley.connected:
            ip_address = self.ip_input.text().strip()
            if not ip_address:
                QMessageBox.warning(self, "錯誤", "請輸入IP地址")
                return
                
            try:
                self.keithley = Keithley2461(ip_address=ip_address)
                if self.keithley.connect():
                    self.connection_status.setText("🟢 已連接")
                    self.connection_status.setStyleSheet("color: #27ae60; font-weight: bold;")
                    self.connect_btn.setText("斷開連接")
                    self.start_btn.setEnabled(True)
                    
                    self.log_message(f"✅ 成功連接到設備: {ip_address}")
                    
                    # 初始化數據記錄器
                    self.data_logger = DataLogger()
                    session_name = self.data_logger.start_session()
                    self.log_message(f"📊 開始數據記錄會話: {session_name}")
                    
                    # 發送連接狀態信號
                    self.connection_changed.emit(True, ip_address)
                    
                else:
                    QMessageBox.critical(self, "連接失敗", f"無法連接到設備: {ip_address}")
                    
            except Exception as e:
                QMessageBox.critical(self, "連接錯誤", f"連接過程中發生錯誤: {str(e)}")
                self.log_message(f"❌ 連接錯誤: {e}")
        else:
            self.disconnect_device()
            
    def disconnect_device(self):
        """斷開設備連接"""
        try:
            # 停止所有測量
            self.stop_measurement()
            
            if self.keithley and self.keithley.connected:
                self.keithley.output_off()
                self.keithley.disconnect()
                
            self.keithley = None
            
            # 更新UI狀態
            self.connection_status.setText("🔴 未連接")
            self.connection_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.connect_btn.setText("連接")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            
            # 發送連接狀態信號
            self.connection_changed.emit(False, "")
            self.log_message("🔌 設備已斷開連接")
            
        except Exception as e:
            self.log_message(f"❌ 斷開連接時發生錯誤: {e}")
    
    def start_measurement(self):
        """開始測量"""
        if not self.keithley or not self.keithley.connected:
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
            
            self.log_message("⏹️ 測量已停止，輸出已關閉")
            
        except Exception as e:
            self.log_message(f"❌ 停止測量時發生錯誤: {e}")
    
    # ==================== 數據更新方法 ====================
    
    def update_iv_data(self, voltage, current, resistance, power, point_num):
        """更新IV數據 (使用儀器計算的功率值)"""
        # power 參數現在來自儀器的 SCPI 計算，不再本地重新計算
        
        # 存儲數據
        self.iv_data.append((voltage, current, resistance, power))
        
        # 更新LCD顯示
        self.voltage_display.display(f"{voltage:.6f}")
        self.current_display.display(f"{current:.6f}")
        self.resistance_display.display(f"{resistance:.2f}")
        self.power_display.display(f"{power:.6f}")
        
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
        self.data_points_label.setText(f"數據點: {len(self.iv_data)}")
    
    def update_continuous_data(self, voltage, current, resistance, power):
        """更新連續測量數據"""
        current_time = (datetime.now() - self.start_time).total_seconds()
        
        # 存儲數據
        self.time_series_data.append((current_time, voltage, current, resistance, power))
        
        # 更新LCD顯示
        self.voltage_display.display(f"{voltage:.6f}")
        self.current_display.display(f"{current:.6f}")
        self.resistance_display.display(f"{resistance:.2f}")
        self.power_display.display(f"{power:.6f}")
        
        # 更新時間序列圖表
        chart_type = self.chart_type_combo.currentText()
        if chart_type in ["電壓時間序列", "電流時間序列", "時間序列"]:
            times = [data[0] for data in self.time_series_data[-100:]]  # 只顯示最近100個點
            voltages = [data[1] for data in self.time_series_data[-100:]]
            currents = [data[2] for data in self.time_series_data[-100:]]
            resistances = [data[3] for data in self.time_series_data[-100:]]
            powers = [data[4] for data in self.time_series_data[-100:]]
            
            # 根據圖表類型更新對應的曲線
            if chart_type == "電壓時間序列" and hasattr(self, 'voltage_time_curve'):
                self.voltage_time_curve.setData(times, voltages)
                if hasattr(self, 'resistance_time_curve'):
                    self.resistance_time_curve.setData(times, resistances)
            elif chart_type == "電流時間序列" and hasattr(self, 'current_time_curve'):
                self.current_time_curve.setData(times, currents)
                if hasattr(self, 'power_time_curve'):
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
        self.data_points_label.setText(f"數據點: {len(self.time_series_data)}")
    
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
            if self.data_logger and self.data_logger.session_data:
                csv_file = self.data_logger.save_session_csv()
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
            self.data_points_label.setText("數據點: 0")
            
            # 清除記錄器數據
            if self.data_logger:
                self.data_logger.session_data.clear()
                
            self.log_message("🔄 所有測量數據已清除")
    
    def log_message(self, message):
        """添加日誌訊息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
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
                self.plot_widget.setBackground('#2b2b2b')
                self.plot_widget.getAxis('left').setPen('#ffffff')
                self.plot_widget.getAxis('bottom').setPen('#ffffff')
                self.plot_widget.getAxis('left').setTextPen('#ffffff')
                self.plot_widget.getAxis('bottom').setTextPen('#ffffff')
            else:
                # 淺色主題
                self.plot_widget.setBackground('#ffffff')
                self.plot_widget.getAxis('left').setPen('#000000')
                self.plot_widget.getAxis('bottom').setPen('#000000')
                self.plot_widget.getAxis('left').setTextPen('#000000')
                self.plot_widget.getAxis('bottom').setTextPen('#000000')
                
        except Exception as e:
            self.logger.error(f"更新圖表主題失敗: {e}")