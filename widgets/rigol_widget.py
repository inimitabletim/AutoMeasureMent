#!/usr/bin/env python3
"""
Rigol DP711 控制 Widget - 多設備支援版本
完整的電源供應器控制介面，支援多設備管理
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                            QLabel, QPushButton, QLineEdit, QGroupBox, 
                            QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QTextEdit,
                            QMessageBox, QProgressBar, QLCDNumber, QSplitter, 
                            QSizePolicy, QTabWidget, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.rigol_dp711 import RigolDP711
from src.data_logger import DataLogger
# 使用新的統一Worker系統
from src.workers import ConnectionWorker as InstrumentConnectionWorker
# ConnectionStateManager已整合到Widget基類中


class RigolMeasurementWorker(QThread):
    """Rigol 測量工作執行緒"""
    data_ready = pyqtSignal(float, float, float)  # voltage, current, power
    error_occurred = pyqtSignal(str)
    
    def __init__(self, dp711):
        super().__init__()
        self.dp711 = dp711
        self.running = False
        
    def run(self):
        """執行測量循環"""
        while self.running:
            try:
                if self.dp711 and self.dp711.connected:
                    v, i, p = self.dp711.measure_all()
                    self.data_ready.emit(v, i, p)
                    self.msleep(1000)  # 1秒間隔
                else:
                    self.msleep(2000)
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


class RigolControlWidget(QWidget):
    """Rigol DP711 完整控制 Widget - 支援多設備管理"""
    
    # 狀態更新信號
    connection_changed = pyqtSignal(bool, str)
    device_switched = pyqtSignal(str, str)  # port, device_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 多設備池管理
        self.connected_devices = {}  # port -> RigolDP711 實例
        self.active_device_port = None  # 當前活動設備端口
        self.dp711 = None  # 當前活動設備實例 (向後相容)
        
        # 連接管理 - 使用統一Worker系統，不再需要ConnectionStateManager
        self.connection_worker = None  # 當前的連接工作線程
        
        # 其他屬性
        self.data_logger = None
        self.measurement_worker = None
        
        # 數據存儲
        self.voltage_data = []
        self.current_data = []
        self.power_data = []
        self.time_data = []
        self.start_time = datetime.now()
        
        # 主題
        self.current_theme = "light"
        
        # 日誌
        self.logger = logging.getLogger(__name__)
        
        # UI 組件引用
        self.device_combo = None
        self.port_combo = None
        self.scan_btn = None
        self.device_info_label = None
        
        # 控制項組
        self.power_controls = []
        self.protection_controls = []
        self.measurement_controls = []
        self.all_controls = []
        
        self.setup_ui()
        self.setup_device_management()
        
    def setup_device_management(self):
        """設置設備管理"""
        # 初始掃描端口
        self.scan_ports()
        
    def setup_ui(self):
        """設置用戶介面 - 完全統一的Tab式布局"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 頂部：專業LCD監控面板（保持突出顯示）
        lcd_panel = self.create_enhanced_lcd_panel()
        main_layout.addWidget(lcd_panel)
        
        # 主要內容：統一的Tab界面
        self.main_tabs = QTabWidget()
        self.main_tabs.setTabPosition(QTabWidget.TabPosition.North)
        
        # 四個主要Tab標籤 - 移除icon圖示，保持簡潔
        basic_tab = self.create_basic_control_tab()
        self.main_tabs.addTab(basic_tab, "基本控制")
        
        advanced_tab = self.create_advanced_control_tab()
        self.main_tabs.addTab(advanced_tab, "進階功能")
        
        monitoring_tab = self.create_monitoring_tab()
        self.main_tabs.addTab(monitoring_tab, "狀態監控")
        
        log_tab = self.create_log_tab()
        self.main_tabs.addTab(log_tab, "操作日誌")
        
        main_layout.addWidget(self.main_tabs)
        
        # 初始化控制項引用
        self._initialize_control_references()
        
    
    def _initialize_control_references(self):
        """初始化所有控制項的引用，便於統一管理狀態"""
        # 基本控制項 (在基本控制分頁中) 
        # 注意：quick_buttons_list 在 create_basic_control_tab 中定義
        basic_controls = [
            self.voltage_spin, self.current_spin, 
            self.output_btn, self.apply_btn,
            self.custom_voltage, self.custom_current, self.apply_custom_btn
        ]
        # 添加快速按鈕（如果存在）
        if hasattr(self, 'quick_buttons_list'):
            basic_controls.extend(self.quick_buttons_list)
        self.power_controls = basic_controls
        
        # 進階功能控制項 (在進階功能分頁中)
        self.protection_controls = [
            self.ovp_spin, self.ocp_spin, 
            self.ovp_enable, self.ocp_enable
        ]
        
        self.memory_controls = [
            self.memory_combo, self.save_memory_btn, 
            self.load_memory_btn, self.refresh_memory_btn
        ] + self.quick_memory_btns
        
        self.preset_controls = [
            self.preset_combo, self.apply_preset_btn, self.save_preset_btn
        ]
        
        # 系統狀態控制項 (在系統狀態分頁中)
        self.status_controls = [
            self.track_mode_combo, self.clear_protection_btn, 
            self.refresh_status_btn
        ]
        
        self.measurement_controls = [
            self.start_measure_btn, self.stop_measure_btn,
            self.measurement_interval_spin, self.max_points_spin
        ]
        
        self.device_controls = [
            self.apply_btn, self.reset_device_btn
        ]
        
        # 統一的控制項列表，便於批量啟用/停用
        self.all_controls = (
            self.power_controls + 
            self.protection_controls + 
            self.memory_controls + 
            self.preset_controls +
            self.status_controls + 
            self.measurement_controls + 
            self.device_controls
        )
    
    def create_basic_control_tab(self):
        """創建基本控制分頁 - 日常最常用的核心功能"""
        tab_widget = QWidget()
        # 改用 GridLayout 作為主佈局，優先顯示設備連接
        main_layout = QGridLayout(tab_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(8, 8, 8, 8)
        # ================================
        # 設備連接管理 - 頂部最顯眼位置 (0,0) 橫跨兩列
        # ================================
        device_group = QGroupBox("🔗 設備連接管理 (第一步)")
        device_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 3px solid #e74c3c;
                border-radius: 8px;
                margin: 3px;
                padding-top: 10px;
                background-color: rgba(231, 76, 60, 0.05);
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #e74c3c;
            }
        """)
        device_layout = QGridLayout(device_group)
        device_layout.setSpacing(8)
        
        # 當前設備狀態
        device_layout.addWidget(QLabel("當前設備:"), 0, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItem("❌ 無設備連接")
        self.device_combo.currentTextChanged.connect(self.switch_device)
        self.device_combo.setMinimumHeight(32)
        self.device_combo.setStyleSheet("""
            QComboBox {
                font-size: 12px;
                padding: 6px;
                border: 2px solid #e74c3c;
                border-radius: 4px;
                background-color: white;
            }
        """)
        device_layout.addWidget(self.device_combo, 0, 1, 1, 3)
        
        # 新設備連接
        device_layout.addWidget(QLabel("選擇端口:"), 1, 0)
        self.port_combo = QComboBox()
        self.port_combo.setMinimumHeight(32)
        self.port_combo.setStyleSheet("font-size: 11px; padding: 4px;")
        device_layout.addWidget(self.port_combo, 1, 1)
        
        device_layout.addWidget(QLabel("波特率:"), 1, 2)
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.setCurrentText("9600")
        self.baudrate_combo.setMinimumHeight(32)
        self.baudrate_combo.setMaximumWidth(80)
        self.baudrate_combo.setStyleSheet("font-size: 11px; padding: 4px;")
        device_layout.addWidget(self.baudrate_combo, 1, 3)
        
        # 操作按鈕行
        scan_connect_layout = QHBoxLayout()
        
        self.scan_btn = QPushButton("🔄 掃描端口")
        self.scan_btn.clicked.connect(self.scan_ports)
        self.scan_btn.setMinimumHeight(36)
        self.scan_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 5px;
                background-color: #f39c12;
                color: white;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        scan_connect_layout.addWidget(self.scan_btn)
        
        self.connect_btn = QPushButton("📱 連接設備")
        self.connect_btn.clicked.connect(self.connect_new_device)
        self.connect_btn.setMinimumHeight(36)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 5px;
                background-color: #27ae60;
                color: white;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        scan_connect_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("⚠️ 斷開設備")
        self.disconnect_btn.clicked.connect(self.disconnect_current_device)
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setMinimumHeight(36)
        self.disconnect_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 5px;
                background-color: #e74c3c;
                color: white;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        scan_connect_layout.addWidget(self.disconnect_btn)
        
        device_layout.addLayout(scan_connect_layout, 2, 0, 1, 4)
        
        # 設備狀態顯示
        self.device_info_label = QLabel("狀態: 請先連接設備才能進行其他操作")
        self.device_info_label.setWordWrap(True)
        self.device_info_label.setStyleSheet("""
            color: #e74c3c; 
            padding: 8px; 
            background-color: rgba(231, 76, 60, 0.1); 
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        """)
        device_layout.addWidget(self.device_info_label, 3, 0, 1, 4)
        
        # 將設備連接放在左側 (第0列)
        main_layout.addWidget(device_group, 0, 0, 1, 1)
        
        # ================================
        # 電源設定與快速控制 - 整合版 (1,0) 橫跨兩列
        # ================================
        power_group = QGroupBox("⚡ 電源設定與快速控制")
        power_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #3498db;
                border-radius: 5px;
                margin: 3px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        power_layout = QGridLayout(power_group)
        power_layout.setSpacing(8)
        
        # 第一行：基本設定
        power_layout.addWidget(QLabel("電壓 (V):"), 0, 0)
        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(0, 30.0)
        self.voltage_spin.setDecimals(3)
        self.voltage_spin.setSingleStep(0.1)
        self.voltage_spin.setValue(5.0)
        self.voltage_spin.setEnabled(False)
        self.voltage_spin.setMinimumHeight(32)
        self.voltage_spin.setStyleSheet("font-size: 11px; padding: 4px;")
        power_layout.addWidget(self.voltage_spin, 0, 1)
        
        power_layout.addWidget(QLabel("電流 (A):"), 0, 2)
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0, 5.0)
        self.current_spin.setDecimals(3)
        self.current_spin.setSingleStep(0.01)
        self.current_spin.setValue(1.0)
        self.current_spin.setEnabled(False)
        self.current_spin.setMinimumHeight(32)
        self.current_spin.setStyleSheet("font-size: 11px; padding: 4px;")
        power_layout.addWidget(self.current_spin, 0, 3)
        
        # 第二行：主要控制按鈕
        control_button_layout = QHBoxLayout()
        self.output_btn = QPushButton("🔋 開啟輸出")
        self.output_btn.clicked.connect(self.toggle_output)
        self.output_btn.setEnabled(False)
        self.output_btn.setMinimumHeight(36)
        self.output_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px; 
                font-weight: bold; 
                padding: 6px 12px;
                border-radius: 5px;
                background-color: #27ae60;
                color: white;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        control_button_layout.addWidget(self.output_btn)
        
        self.apply_btn = QPushButton("✅ 應用設定")
        self.apply_btn.clicked.connect(self.apply_settings)
        self.apply_btn.setEnabled(False)
        self.apply_btn.setMinimumHeight(36)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                font-size: 12px; 
                font-weight: bold; 
                padding: 6px 12px;
                border-radius: 5px;
                background-color: #3498db;
                color: white;
            }
            QPushButton:hover {
                background-color: #5dade2;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        control_button_layout.addWidget(self.apply_btn)
        
        power_layout.addLayout(control_button_layout, 1, 0, 1, 4)
        
        # 第三行：快速設定按鈕
        quick_buttons = [
            ("3.3V/1A", 3.3, 1.0, "#e74c3c"),
            ("5V/1A", 5.0, 1.0, "#e67e22"), 
            ("12V/2A", 12.0, 2.0, "#3498db"),
            ("24V/3A", 24.0, 3.0, "#9b59b6")
        ]
        
        self.quick_buttons_list = []
        for i, (text, voltage, current, color) in enumerate(quick_buttons):
            btn = QPushButton(text)
            btn.clicked.connect(lambda checked, v=voltage, c=current: self.quick_set(v, c))
            btn.setEnabled(False)
            btn.setMinimumHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 4px;
                    background-color: {color};
                    color: white;
                    padding: 4px 8px;
                }}
                QPushButton:hover {{
                    background-color: {color}dd;
                }}
                QPushButton:disabled {{
                    background-color: #95a5a6;
                }}
            """)
            power_layout.addWidget(btn, 2, i)
            self.quick_buttons_list.append(btn)
        
        # 第四行：自定義快速設定
        power_layout.addWidget(QLabel("自定義:"), 3, 0)
        
        self.custom_voltage = QDoubleSpinBox()
        self.custom_voltage.setRange(0, 30.0)
        self.custom_voltage.setDecimals(1)
        self.custom_voltage.setValue(12.0)
        self.custom_voltage.setSuffix("V")
        self.custom_voltage.setEnabled(False)
        self.custom_voltage.setMinimumHeight(28)
        power_layout.addWidget(self.custom_voltage, 3, 1)
        
        self.custom_current = QDoubleSpinBox()
        self.custom_current.setRange(0, 5.0)
        self.custom_current.setDecimals(2)
        self.custom_current.setValue(1.5)
        self.custom_current.setSuffix("A")
        self.custom_current.setEnabled(False)
        self.custom_current.setMinimumHeight(28)
        power_layout.addWidget(self.custom_current, 3, 2)
        
        self.apply_custom_btn = QPushButton("套用自定義")
        self.apply_custom_btn.clicked.connect(self.apply_custom_quick_set)
        self.apply_custom_btn.setEnabled(False)
        self.apply_custom_btn.setMinimumHeight(28)
        self.apply_custom_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
                background-color: #9b59b6;
                color: white;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        power_layout.addWidget(self.apply_custom_btn, 3, 3)
        
        # 將電源控制放在右側 (第1列)，與設備連接並排
        main_layout.addWidget(power_group, 0, 1, 1, 1)
        
        # 設定列寬比例：設備連接45%，電源控制55%
        main_layout.setColumnStretch(0, 45)  # 左側設備連接
        main_layout.setColumnStretch(1, 55)  # 右側電源控制
        
        return tab_widget
    
    def create_advanced_control_tab(self):
        """創建進階功能分頁 - 保護設定、記憶體管理、預設配置"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(10)
        
        # 使用分割器創建更好的空間利用
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ================================
        # 左側：安全與保護設定
        # ================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        
        # 保護設定群組 - 增強版
        protection_group = QGroupBox("🛡️ 安全保護設定")
        protection_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #e74c3c;
                border-radius: 5px;
                margin: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        prot_layout = QGridLayout(protection_group)
        prot_layout.setSpacing(10)
        
        # 過壓保護
        prot_layout.addWidget(QLabel("過壓保護 (V):"), 0, 0)
        self.ovp_spin = QDoubleSpinBox()
        self.ovp_spin.setRange(0.01, 33.0)
        self.ovp_spin.setDecimals(2)
        self.ovp_spin.setValue(31.0)
        self.ovp_spin.setEnabled(False)
        self.ovp_spin.setMinimumHeight(30)
        self.ovp_spin.setStyleSheet("padding: 3px;")
        prot_layout.addWidget(self.ovp_spin, 0, 1)
        
        self.ovp_enable = QCheckBox("啟用過壓保護")
        self.ovp_enable.setEnabled(False)
        self.ovp_enable.setStyleSheet("font-weight: bold; color: #e74c3c;")
        prot_layout.addWidget(self.ovp_enable, 0, 2)
        
        # 過流保護
        prot_layout.addWidget(QLabel("過流保護 (A):"), 1, 0)
        self.ocp_spin = QDoubleSpinBox()
        self.ocp_spin.setRange(0.001, 5.5)
        self.ocp_spin.setDecimals(3)
        self.ocp_spin.setValue(5.2)
        self.ocp_spin.setEnabled(False)
        self.ocp_spin.setMinimumHeight(30)
        self.ocp_spin.setStyleSheet("padding: 3px;")
        prot_layout.addWidget(self.ocp_spin, 1, 1)
        
        self.ocp_enable = QCheckBox("啟用過流保護") 
        self.ocp_enable.setEnabled(False)
        self.ocp_enable.setStyleSheet("font-weight: bold; color: #e74c3c;")
        prot_layout.addWidget(self.ocp_enable, 1, 2)
        
        # 保護狀態顯示
        prot_status_layout = QHBoxLayout()
        prot_status_layout.addWidget(QLabel("保護狀態:"))
        self.protection_status_display = QLabel("正常運行")
        self.protection_status_display.setStyleSheet("""
            background-color: #d5f4e6; 
            color: #27ae60; 
            font-weight: bold; 
            padding: 5px; 
            border-radius: 3px;
        """)
        prot_status_layout.addWidget(self.protection_status_display)
        
        self.clear_protection_btn = QPushButton("清除保護")
        self.clear_protection_btn.clicked.connect(self.clear_device_protection)
        self.clear_protection_btn.setEnabled(False)
        self.clear_protection_btn.setStyleSheet("""
            QPushButton {
                background-color: #f39c12;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #e67e22;
            }
        """)
        prot_status_layout.addWidget(self.clear_protection_btn)
        prot_status_layout.addStretch()
        
        prot_layout.addLayout(prot_status_layout, 2, 0, 1, 3)
        
        left_layout.addWidget(protection_group)
        left_layout.addStretch()
        
        # ================================  
        # 右側：數據與配置管理
        # ================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(8)
        
        # 統一的配置管理群組
        config_group = QGroupBox("💾 智能配置管理")
        config_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #27ae60;
                border-radius: 5px;
                margin: 5px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        config_layout = QVBoxLayout(config_group)
        config_layout.setSpacing(10)
        
        # 配置管理標籤頁
        config_tabs = QTabWidget()
        config_tabs.setTabPosition(QTabWidget.TabPosition.North)
        
        # 記憶體管理標籤
        memory_tab = QWidget()
        memory_layout = QVBoxLayout(memory_tab)
        memory_layout.setSpacing(8)
        
        # 記憶體選擇和預覽
        memory_select_layout = QHBoxLayout()
        memory_select_layout.addWidget(QLabel("記憶體槽位:"))
        self.memory_combo = QComboBox()
        for i in range(1, 6):
            self.memory_combo.addItem(f"M{i} - 空")
        self.memory_combo.setMinimumHeight(30)
        memory_select_layout.addWidget(self.memory_combo)
        
        self.refresh_memory_btn = QPushButton("🔄 刷新")
        self.refresh_memory_btn.clicked.connect(self.refresh_memory_catalog)
        self.refresh_memory_btn.setEnabled(False)
        self.refresh_memory_btn.setToolTip("刷新記憶體內容顯示")
        memory_select_layout.addWidget(self.refresh_memory_btn)
        
        memory_layout.addLayout(memory_select_layout)
        
        # 記憶體內容預覽
        self.memory_preview = QLabel("選擇記憶體槽位以查看內容")
        self.memory_preview.setStyleSheet("""
            background-color: #f8f9fa; 
            color: #495057; 
            font-family: monospace; 
            padding: 10px; 
            border-radius: 5px;
            border: 1px solid #dee2e6;
        """)
        self.memory_preview.setWordWrap(True)
        memory_layout.addWidget(self.memory_preview)
        
        # 記憶體操作按鈕
        memory_btn_layout = QHBoxLayout()
        
        self.save_memory_btn = QPushButton("💾 保存當前")
        self.save_memory_btn.clicked.connect(self.save_current_to_memory)
        self.save_memory_btn.setEnabled(False)
        self.save_memory_btn.setToolTip("將當前設定保存到選定的記憶體槽位")
        self.save_memory_btn.setMinimumHeight(35)
        memory_btn_layout.addWidget(self.save_memory_btn)
        
        self.load_memory_btn = QPushButton("📂 載入設定")
        self.load_memory_btn.clicked.connect(self.load_from_memory)
        self.load_memory_btn.setEnabled(False)
        self.load_memory_btn.setToolTip("從選定的記憶體槽位載入設定")
        self.load_memory_btn.setMinimumHeight(35)
        memory_btn_layout.addWidget(self.load_memory_btn)
        
        memory_layout.addLayout(memory_btn_layout)
        
        # 快速記憶體按鈕 - 改進版
        memory_layout.addWidget(QLabel("快速載入:"))
        
        quick_memory_layout = QGridLayout()
        quick_memory_layout.setSpacing(8)
        
        self.quick_memory_btns = []
        for i in range(1, 6):
            btn = QPushButton(f"記憶體 M{i}")
            btn.setMinimumSize(80, 36)  # 增加按鈕大小
            btn.clicked.connect(lambda checked, mem=i: self.quick_load_memory(mem))
            btn.setEnabled(False)
            btn.setToolTip(f"快速載入記憶體 M{i} 設定")
            btn.setStyleSheet("""
                QPushButton {
                    font-weight: bold;
                    font-size: 11px;
                    border-radius: 6px;
                    background-color: #6c757d;
                    color: white;
                    padding: 6px 10px;
                    border: 1px solid #5a6268;
                }
                QPushButton:hover {
                    background-color: #5a6268;
                    border-color: #495057;
                }
                QPushButton:pressed {
                    background-color: #495057;
                }
                QPushButton:disabled {
                    background-color: #95a5a6;
                    border-color: #7f8c8d;
                    color: #ecf0f1;
                }
            """)
            self.quick_memory_btns.append(btn)
            
            # 按鈕排列：前3個在第一行，後2個在第二行
            if i <= 3:
                quick_memory_layout.addWidget(btn, 0, i-1)
            else:
                quick_memory_layout.addWidget(btn, 1, i-4)
        
        memory_layout.addLayout(quick_memory_layout)
        
        config_tabs.addTab(memory_tab, "記憶體")
        
        # 預設配置標籤
        preset_tab = QWidget()
        preset_layout = QVBoxLayout(preset_tab)
        preset_layout.setSpacing(8)
        
        # 預設選擇
        preset_select_layout = QHBoxLayout()
        preset_select_layout.addWidget(QLabel("預設選項:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("選擇預設配置...")
        self.preset_combo.setMinimumHeight(30)
        
        # 載入預設選項
        try:
            import json
            import os
            preset_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rigol_presets.json')
            if os.path.exists(preset_file):
                with open(preset_file, 'r', encoding='utf-8') as f:
                    self.presets = json.load(f)
                for preset_name in self.presets.keys():
                    self.preset_combo.addItem(preset_name)
            else:
                self.presets = {}
        except Exception as e:
            self.logger.warning(f"載入預設配置文件失敗: {e}")
            self.presets = {}
            
        preset_select_layout.addWidget(self.preset_combo)
        preset_layout.addLayout(preset_select_layout)
        
        # 預設資訊顯示
        self.preset_info_label = QLabel("選擇預設以查看詳細資訊")
        self.preset_info_label.setWordWrap(True)
        self.preset_info_label.setStyleSheet("""
            background-color: #f8f9fa; 
            color: #495057; 
            padding: 10px; 
            border-radius: 5px;
            border: 1px solid #dee2e6;
        """)
        preset_layout.addWidget(self.preset_info_label)
        
        # 預設操作按鈕
        preset_btn_layout = QHBoxLayout()
        
        self.apply_preset_btn = QPushButton("⚡ 套用預設")
        self.apply_preset_btn.clicked.connect(self.apply_preset_configuration)
        self.apply_preset_btn.setEnabled(False)
        self.apply_preset_btn.setToolTip("套用選定的預設配置到當前設定")
        self.apply_preset_btn.setMinimumHeight(35)
        preset_btn_layout.addWidget(self.apply_preset_btn)
        
        self.save_preset_btn = QPushButton("💾 保存預設")
        self.save_preset_btn.clicked.connect(self.save_custom_preset)
        self.save_preset_btn.setEnabled(False) 
        self.save_preset_btn.setToolTip("將當前設定保存為自訂預設")
        self.save_preset_btn.setMinimumHeight(35)
        preset_btn_layout.addWidget(self.save_preset_btn)
        
        preset_layout.addLayout(preset_btn_layout)
        
        # 連接預設選擇變化信號
        self.preset_combo.currentTextChanged.connect(self.on_preset_selection_changed)
        
        config_tabs.addTab(preset_tab, "預設配置")
        
        config_layout.addWidget(config_tabs)
        right_layout.addWidget(config_group)
        
        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([300, 400])  # 左側較小，右側較大
        
        layout.addWidget(main_splitter)
        
        return tab_widget
    
    def create_monitoring_tab(self):
        """創建狀態監控分頁 - 整合設備狀態、測量控制、數據圖表"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(8)
        
        # 左右分割：狀態控制 | 圖表顯示
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ================================
        # 左側：狀態控制區域
        # ================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(8)
        
        # 設備狀態監控群組
        status_group = QGroupBox("📊 設備狀態監控")
        status_layout = QGridLayout(status_group)
        
        # 保護狀態顯示
        status_layout.addWidget(QLabel("保護狀態:"), 0, 0)
        self.protection_status_label = QLabel("正常")
        self.protection_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        status_layout.addWidget(self.protection_status_label, 0, 1)
        
        self.clear_protection_btn = QPushButton("清除保護")
        self.clear_protection_btn.clicked.connect(self.clear_device_protection)
        self.clear_protection_btn.setEnabled(False)
        self.clear_protection_btn.setVisible(False)
        status_layout.addWidget(self.clear_protection_btn, 0, 2)
        
        # 追蹤模式顯示
        status_layout.addWidget(QLabel("追蹤模式:"), 1, 0)
        self.track_mode_combo = QComboBox()
        self.track_mode_combo.addItems(["INDEP (獨立)", "SER (串聯)", "PARA (並聯)"])
        self.track_mode_combo.currentTextChanged.connect(self.set_track_mode)
        self.track_mode_combo.setEnabled(False)
        status_layout.addWidget(self.track_mode_combo, 1, 1, 1, 2)
        
        # 設備溫度顯示
        status_layout.addWidget(QLabel("設備溫度:"), 2, 0)
        self.temperature_label = QLabel("--°C")
        self.temperature_label.setStyleSheet("color: #3498db; font-family: monospace;")
        status_layout.addWidget(self.temperature_label, 2, 1)
        
        # 狀態刷新按鈕
        self.refresh_status_btn = QPushButton("🔄 刷新狀態")
        self.refresh_status_btn.clicked.connect(self.refresh_device_status)
        self.refresh_status_btn.setEnabled(False)
        status_layout.addWidget(self.refresh_status_btn, 2, 2)
        
        left_layout.addWidget(status_group)
        
        # 測量控制群組
        measurement_group = QGroupBox("🔬 測量控制")
        measure_layout = QGridLayout(measurement_group)
        
        # 測量按鈕
        self.start_measure_btn = QPushButton("📈 開始測量")
        self.start_measure_btn.clicked.connect(self.toggle_measurement)
        self.start_measure_btn.setEnabled(False)
        measure_layout.addWidget(self.start_measure_btn, 0, 0)
        
        self.stop_measure_btn = QPushButton("⏹️ 停止測量")
        self.stop_measure_btn.clicked.connect(self.stop_measurement)
        self.stop_measure_btn.setEnabled(False)
        measure_layout.addWidget(self.stop_measure_btn, 0, 1)
        
        # 測量間隔設定
        measure_layout.addWidget(QLabel("測量間隔(秒):"), 1, 0)
        self.measurement_interval_spin = QDoubleSpinBox()
        self.measurement_interval_spin.setRange(0.1, 60.0)
        self.measurement_interval_spin.setDecimals(1)
        self.measurement_interval_spin.setValue(1.0)
        self.measurement_interval_spin.setEnabled(False)
        measure_layout.addWidget(self.measurement_interval_spin, 1, 1)
        
        # 測量點數限制
        measure_layout.addWidget(QLabel("最大測量點:"), 2, 0)
        self.max_points_spin = QSpinBox()
        self.max_points_spin.setRange(100, 10000)
        self.max_points_spin.setValue(1000)
        self.max_points_spin.setEnabled(False)
        measure_layout.addWidget(self.max_points_spin, 2, 1)
        
        left_layout.addWidget(measurement_group)
        
        # 設備控制群組
        device_group = QGroupBox("🔧 設備控制")
        device_layout = QVBoxLayout(device_group)
        
        # 應用設定按鈕
        apply_layout = QHBoxLayout()
        self.apply_btn = QPushButton("✅ 應用設定")
        self.apply_btn.clicked.connect(self.apply_settings)
        self.apply_btn.setEnabled(False)
        apply_layout.addWidget(self.apply_btn)
        
        # 重置設備按鈕
        self.reset_device_btn = QPushButton("🔄 重置設備")
        self.reset_device_btn.clicked.connect(self.reset_device)
        self.reset_device_btn.setEnabled(False)
        self.reset_device_btn.setToolTip("重置設備到出廠預設狀態")
        apply_layout.addWidget(self.reset_device_btn)
        
        device_layout.addLayout(apply_layout)
        left_layout.addWidget(device_group)
        
        left_layout.addStretch()
        left_panel.setMaximumWidth(350)  # 限制寬度
        
        # ================================
        # 右側：數據圖表區域
        # ================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 創建繪圖區域
        self.plot_widget = self.create_plot_area()
        right_layout.addWidget(self.plot_widget)
        
        # 添加到分割器
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([350, 450])  # 左側:右側 比例
        
        layout.addWidget(splitter)
        
        return tab_widget
    
    def create_log_tab(self):
        """創建操作日誌分頁"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        layout.setSpacing(8)
        
        # 日誌控制面板
        control_panel = QGroupBox("📋 日誌控制")
        control_layout = QHBoxLayout(control_panel)
        
        # 清除日誌按鈕
        self.clear_log_btn = QPushButton("🗑️ 清除日誌")
        self.clear_log_btn.clicked.connect(self.clear_log)
        control_layout.addWidget(self.clear_log_btn)
        
        # 導出日誌按鈕
        self.export_log_btn = QPushButton("💾 導出日誌")
        self.export_log_btn.clicked.connect(self.export_log)
        control_layout.addWidget(self.export_log_btn)
        
        # 自動滾動開關
        self.auto_scroll_check = QCheckBox("自動滾動")
        self.auto_scroll_check.setChecked(True)
        control_layout.addWidget(self.auto_scroll_check)
        
        control_layout.addStretch()
        layout.addWidget(control_panel)
        
        # 日誌顯示區域
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 9))  # 使用等寬字體
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        
        layout.addWidget(self.log_display)
        
        return tab_widget
    
    def create_enhanced_lcd_panel(self):
        """創建增強的LCD監控面板 - 電源供應器主要監控區域"""
        panel_widget = QGroupBox("🔋 電源監控中心")
        panel_widget.setStyleSheet("QGroupBox { font-size: 14px; font-weight: bold; }")
        layout = QHBoxLayout(panel_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 15, 20, 15)
        
        # 主要LCD顯示矩陣 - 加大尺寸
        lcd_container = QWidget()
        lcd_layout = QGridLayout(lcd_container)
        lcd_layout.setSpacing(15)
        
        # 創建加大版本的LCD顯示器
        self.voltage_lcd_frame = self.create_professional_lcd_large("電壓", "V", "#e74c3c")
        lcd_layout.addWidget(self.voltage_lcd_frame, 0, 0)
        
        self.current_lcd_frame = self.create_professional_lcd_large("電流", "A", "#3498db")
        lcd_layout.addWidget(self.current_lcd_frame, 0, 1)
        
        self.power_lcd_frame = self.create_professional_lcd_large("功率", "W", "#f39c12")
        lcd_layout.addWidget(self.power_lcd_frame, 1, 0)
        
        self.efficiency_lcd_frame = self.create_professional_lcd_large("效率", "%", "#9b59b6")
        lcd_layout.addWidget(self.efficiency_lcd_frame, 1, 1)
        
        # 保存LCD引用以便後續更新
        self.voltage_lcd = self.voltage_lcd_frame.lcd_display
        self.current_lcd = self.current_lcd_frame.lcd_display
        self.power_lcd = self.power_lcd_frame.lcd_display
        self.efficiency_lcd = self.efficiency_lcd_frame.lcd_display
        
        layout.addWidget(lcd_container, 3)
        
        # 右側快速狀態指示
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setSpacing(10)
        
        # 輸出狀態大型指示
        output_status_group = QGroupBox("輸出狀態")
        output_layout = QVBoxLayout(output_status_group)
        
        self.output_status = QLabel("●")
        self.output_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_status.setStyleSheet("font-size: 48px; color: #e74c3c; font-weight: bold;")
        output_layout.addWidget(self.output_status)
        
        self.output_status_text = QLabel("關閉")
        self.output_status_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_status_text.setStyleSheet("font-size: 14px; font-weight: bold; color: #e74c3c;")
        output_layout.addWidget(self.output_status_text)
        
        status_layout.addWidget(output_status_group)
        
        # 保護狀態指示
        protection_status_group = QGroupBox("保護狀態")
        protection_layout = QVBoxLayout(protection_status_group)
        
        self.protection_status_label = QLabel("正常")
        self.protection_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.protection_status_label.setStyleSheet("font-size: 12px; color: #27ae60; font-weight: bold;")
        protection_layout.addWidget(self.protection_status_label)
        
        status_layout.addWidget(protection_status_group)
        
        layout.addWidget(status_container, 1)
        
        return panel_widget
    
    def create_compact_status_panel(self):
        """創建緊湊狀態面板 - 取代原本的大型右側面板"""
        panel_widget = QWidget()
        layout = QVBoxLayout(panel_widget)
        layout.setSpacing(10)
        
        # 設備狀態快覽
        status_group = QGroupBox("設備狀態")
        status_layout = QGridLayout(status_group)
        
        # 追蹤模式
        status_layout.addWidget(QLabel("追蹤模式:"), 0, 0)
        self.track_mode_combo = QComboBox()
        self.track_mode_combo.addItems(["INDEP (獨立)", "SER (串聯)", "PARA (並聯)"])
        self.track_mode_combo.setCurrentText("INDEP (獨立)")
        self.track_mode_combo.currentTextChanged.connect(self.set_track_mode)
        self.track_mode_combo.setEnabled(False)
        status_layout.addWidget(self.track_mode_combo, 0, 1)
        
        # 設備溫度
        status_layout.addWidget(QLabel("設備溫度:"), 1, 0)
        self.temperature_label = QLabel("--°C")
        self.temperature_label.setStyleSheet("color: #3498db; font-family: monospace;")
        status_layout.addWidget(self.temperature_label, 1, 1)
        
        # 狀態按鈕
        btn_layout = QHBoxLayout()
        self.refresh_status_btn = QPushButton("刷新狀態")
        self.refresh_status_btn.clicked.connect(self.refresh_device_status)
        self.refresh_status_btn.setEnabled(False)
        btn_layout.addWidget(self.refresh_status_btn)
        
        self.clear_protection_btn = QPushButton("清除保護")
        self.clear_protection_btn.clicked.connect(self.clear_device_protection)
        self.clear_protection_btn.setEnabled(False)
        self.clear_protection_btn.setVisible(False)
        btn_layout.addWidget(self.clear_protection_btn)
        
        status_layout.addLayout(btn_layout, 2, 0, 1, 2)
        
        layout.addWidget(status_group)
        
        # 操作日誌 (縮小版)
        log_group = QGroupBox("操作日誌")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)  # 限制高度
        self.log_text.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10px;")
        log_layout.addWidget(self.log_text)
        
        # 清除日誌按鈕
        clear_log_btn = QPushButton("清除日誌")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_group)
        
        # 儲存狀態控制引用
        self.status_controls = [self.track_mode_combo, self.clear_protection_btn, 
                               self.refresh_status_btn]
        
        return panel_widget
    
    def create_display_panel(self):
        """創建右側顯示面板"""
        display_widget = QWidget()
        layout = QVBoxLayout(display_widget)
        
        # 實時數據顯示
        data_group = QGroupBox("實時監控數據")
        data_layout = QGridLayout(data_group)
        
        # 專業級LCD顯示器 - 2x2 網格佈局
        self.voltage_lcd_frame = self.create_professional_lcd("電壓", "V", "#e74c3c")
        data_layout.addWidget(self.voltage_lcd_frame, 0, 0)
        
        self.current_lcd_frame = self.create_professional_lcd("電流", "A", "#3498db")
        data_layout.addWidget(self.current_lcd_frame, 0, 1)
        
        self.power_lcd_frame = self.create_professional_lcd("功率", "W", "#f39c12")
        data_layout.addWidget(self.power_lcd_frame, 1, 0)
        
        self.efficiency_lcd_frame = self.create_professional_lcd("效率", "%", "#9b59b6")
        data_layout.addWidget(self.efficiency_lcd_frame, 1, 1)
        
        # 保存LCD引用以便後續更新
        self.voltage_lcd = self.voltage_lcd_frame.lcd_display
        self.current_lcd = self.current_lcd_frame.lcd_display
        self.power_lcd = self.power_lcd_frame.lcd_display
        self.efficiency_lcd = self.efficiency_lcd_frame.lcd_display
        
        layout.addWidget(data_group)
        
        # 工作狀態指示
        status_group = QGroupBox("工作狀態")
        status_layout = QGridLayout(status_group)
        
        # 狀態指示燈
        self.output_status = QLabel("●")
        self.output_status.setStyleSheet("color: red; font-size: 20px;")
        status_layout.addWidget(QLabel("輸出狀態:"), 0, 0)
        status_layout.addWidget(self.output_status, 0, 1)
        status_layout.addWidget(QLabel("關閉"), 0, 2)
        
        self.protection_status = QLabel("●")
        self.protection_status.setStyleSheet("color: green; font-size: 20px;")
        status_layout.addWidget(QLabel("保護狀態:"), 1, 0)
        status_layout.addWidget(self.protection_status, 1, 1)
        status_layout.addWidget(QLabel("正常"), 1, 2)
        
        layout.addWidget(status_group)
        
        # 圖表顯示
        chart_group = QGroupBox("電源監控圖表")
        chart_layout = QVBoxLayout(chart_group)
        
        # 創建圖表
        self.plot_widget = PlotWidget()
        self.plot_widget.setBackground('w')
        self.plot_widget.setLabel('left', '數值', color='black')
        self.plot_widget.setLabel('bottom', '時間 (秒)', color='black')
        self.plot_widget.addLegend()
        
        # 設置圖表曲線
        self.voltage_curve = self.plot_widget.plot(pen=pg.mkPen(color='blue', width=2), name='電壓 (V)')
        self.current_curve = self.plot_widget.plot(pen=pg.mkPen(color='orange', width=2), name='電流 (A)')
        self.power_curve = self.plot_widget.plot(pen=pg.mkPen(color='green', width=2), name='功率 (W)')
        
        chart_layout.addWidget(self.plot_widget)
        layout.addWidget(chart_group)
        
        # 簡化的日誌顯示
        log_group = QGroupBox("操作日誌")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        return display_widget
    
    # 設備管理方法
    def scan_ports(self):
        """掃描可用端口"""
        try:
            # 清空現有選項
            self.port_combo.clear()
            
            # 獲取可用設備 - 先執行掃描確保數據是最新的
            from src.port_manager import get_port_manager
            port_manager = get_port_manager()
            port_manager.scan_ports()  # 強制重新掃描
            available_devices = port_manager.get_available_ports(exclude_connected=False)  # 暫時不排除已連接的
            
            if available_devices:
                for device_info in available_devices:
                    display_text = f"{device_info.port} - {device_info.description}"
                    self.port_combo.addItem(display_text, device_info.port)
                    
                self.log_message(f"掃描到 {len(available_devices)} 個可用端口")
            else:
                self.port_combo.addItem("無可用端口")
                self.log_message("未發現可用的 DP711 端口")
                
        except Exception as e:
            self.logger.error(f"掃描端口時發生錯誤: {e}")
            self.log_message(f"端口掃描錯誤: {e}")
    
    def connect_new_device(self):
        """連接新設備 - 使用模組化非阻塞連接"""
        if self.port_combo.count() == 0 or self.port_combo.currentData() is None:
            QMessageBox.warning(self, "警告", "請先掃描端口並選擇一個有效的端口")
            return
            
        port = self.port_combo.currentData()
        baudrate = int(self.baudrate_combo.currentText())
        
        # 檢查是否已經連接此端口
        if port in self.connected_devices:
            # 切換到已連接的設備
            self.active_device_port = port
            self.dp711 = self.connected_devices[port]
            self.log_message(f"切換到已連接設備: {port}")
            self._update_device_ui()
            return
        
        # 檢查是否正在連接中
        if self.connection_manager.is_connecting:
            QMessageBox.warning(self, "警告", "正在連接中，請稍後...")
            return
        
        # 設置連接狀態
        self.connection_manager.is_connecting = True
        
        # 禁用連接按鈕，顯示連接狀態
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText("連接中...")
        self.log_message(f"正在連接到 {port}...")
        
        # 創建連接參數
        connection_params = {
            'port': port,
            'baudrate': baudrate,
            'timeout': 5.0  # 5秒超時
        }
        
        # 創建Rigol設備實例
        rigol_device = RigolDP711()
        
        # 創建並配置連接工作線程（使用新的統一Worker）
        self.connection_worker = InstrumentConnectionWorker(rigol_device, connection_params)
        
        # 連接信號到對應的處理方法（新的Worker信號格式）
        self.connection_worker.connection_started.connect(self.on_connection_started)
        self.connection_worker.progress_updated.connect(lambda p: self.on_connection_progress(f"進度: {p}%"))
        self.connection_worker.connection_success.connect(lambda name, info: self.on_connection_success(info.get('identity', '已連接')))
        self.connection_worker.connection_failed.connect(lambda err_type, msg: self.on_connection_failed(msg))
        self.connection_worker.error_occurred.connect(lambda err_type, msg: self.on_connection_timeout() if 'timeout' in msg.lower() else None)
        
        # 連接完成信號
        self.connection_worker.finished.connect(self.on_connection_finished)
        
        # 保存設備實例引用
        self.pending_device = rigol_device
        
        # 啟動連接線程
        self.connection_worker.start()
    
    # 連接狀態回調方法
    def on_connection_started(self):
        """連接開始時的回調"""
        self.log_message("開始建立連接...")
        
    def on_connection_progress(self, message: str):
        """連接進度更新的回調"""
        self.log_message(f"連接進度: {message}")
        # 可以更新狀態標籤或進度條
        if hasattr(self, 'device_info_label'):
            self.device_info_label.setText(f"⏳ {message}")
            
    def on_connection_success(self, message: str):
        """連接成功的回調"""
        if hasattr(self, 'pending_device'):
            # 使用保存的設備實例
            device = self.pending_device
            if device and device.is_connected():
                # 獲取連接參數
                port = self.port_combo.currentData()
                
                # 添加到設備池
                self.connected_devices[port] = device
                self.active_device_port = port
                self.dp711 = device
                
                # 記錄成功訊息
                self.log_message(f"✓ 連接成功: {port}")
                self.log_message(message)
                
                # 更新UI
                self._update_device_ui()
                self._update_device_list()
                
                # 顯示輕量提示而非彈窗
                self.device_info_label.setText(f"✓ 已連接: {port}")
                
    def on_connection_failed(self, error_message: str):
        """連接失敗的回調"""
        self.log_message(f"✗ 連接失敗: {error_message}")
        QMessageBox.warning(self, "連接失敗", error_message)
        
    def on_connection_timeout(self):
        """連接超時的回調"""
        self.log_message("連接超時，請檢查設備是否正常")
        QMessageBox.warning(self, "連接超時", 
            "連接超時，請檢查：\n"
            "1. 設備是否已開機\n"
            "2. USB 線是否正確連接\n"
            "3. 驅動程式是否已安裝")
            
    def on_connection_finished(self):
        """連接過程結束的回調（無論成功或失敗）"""
        # 恢復按鈕狀態
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText("連接設備")
        
        # 重置連接狀態
        self.connection_manager.is_connecting = False
        
        # 清理工作線程引用
        if self.connection_worker:
            self.connection_worker.deleteLater()
            self.connection_worker = None
            
        self.log_message("連接過程完成")
    
    def disconnect_current_device(self):
        """斷開當前設備"""
        if not self.active_device_port or self.active_device_port not in self.connected_devices:
            QMessageBox.warning(self, "警告", "沒有活動的設備")
            return
            
        try:
            port = self.active_device_port
            device = self.connected_devices[port]
            
            device.disconnect()
            
            # 從設備池移除
            del self.connected_devices[port]
            
            # 切換到其他設備或清空
            if self.connected_devices:
                # 切換到第一個可用設備
                self.active_device_port = list(self.connected_devices.keys())[0]
                self.dp711 = self.connected_devices[self.active_device_port]
                self.log_message(f"設備 {port} 已斷開，切換到 {self.active_device_port}")
            else:
                # 沒有設備了
                self.active_device_port = None
                self.dp711 = None
                self.log_message("所有設備已斷開")
                
            self._update_device_ui()
            self._update_device_list()
            
            QMessageBox.information(self, "斷開成功", 
                f"設備 {port} 已斷開\n剩餘設備: {len(self.connected_devices)}台")
                
        except Exception as e:
            self.logger.error(f"斷開設備時發生錯誤: {e}")
            QMessageBox.warning(self, "斷開失敗", f"斷開設備時發生錯誤: {str(e)}")
            
    def _update_device_ui(self):
        """更新設備相關UI狀態"""
        has_devices = len(self.connected_devices) > 0
        has_active = self.dp711 is not None
        
        # 更新按鈕狀態
        self.connect_btn.setEnabled(True)  # 總是可以添加新設備
        self.disconnect_btn.setEnabled(has_active)
        
        # 更新設備控制區域
        self.update_device_controls()
        
    def update_device_controls(self):
        """更新設備控制項狀態"""
        has_active_device = self.dp711 is not None
        
        # 啟用/禁用所有控制項
        self.enable_controls(has_active_device)
        
        # 更新設備資訊顯示
        if has_active_device and self.active_device_port:
            try:
                identity = self.dp711.get_identity()
                device_id = identity.split(',')[0] if ',' in identity else identity
                self.device_info_label.setText(f"活動設備: {device_id}\n端口: {self.active_device_port}")
            except:
                self.device_info_label.setText(f"活動設備: DP711\n端口: {self.active_device_port}")
        else:
            self.device_info_label.setText("狀態: 無設備連接")
        
    def _update_device_list(self):
        """更新設備列表顯示"""
        # 這裡可以添加設備列表UI更新邏輯
        if hasattr(self, 'device_list_combo'):
            self.device_list_combo.clear()
            for port, device in self.connected_devices.items():
                active_mark = " (活動)" if port == self.active_device_port else ""
                try:
                    identity = device.get_identity()
                    display_text = f"{port} - {identity.split(',')[0]}{active_mark}"
                except:
                    display_text = f"{port} - DP711{active_mark}"
                self.device_list_combo.addItem(display_text, port)
                
    def switch_active_device(self, port: str):
        """切換活動設備"""
        if port in self.connected_devices:
            self.active_device_port = port
            self.dp711 = self.connected_devices[port]
            self._update_device_ui()
            self._update_device_list()
            self.log_message(f"切換到設備: {port}")
        else:
            self.log_message(f"設備 {port} 未連接")
            
    def disconnect_all_devices(self):
        """斷開所有設備"""
        try:
            disconnected_count = 0
            ports_to_disconnect = list(self.connected_devices.keys())
            
            for port in ports_to_disconnect:
                device = self.connected_devices[port]
                device.disconnect()
                disconnected_count += 1
                
            self.connected_devices.clear()
            self.active_device_port = None
            self.dp711 = None
            
            self._update_device_ui()
            self._update_device_list()
            
            self.log_message(f"已斷開所有設備 ({disconnected_count}台)")
            QMessageBox.information(self, "斷開成功", f"已斷開所有設備 ({disconnected_count}台)")
            
        except Exception as e:
            self.logger.error(f"斷開所有設備時發生錯誤: {e}")
            QMessageBox.warning(self, "斷開失敗", f"斷開設備時發生錯誤: {str(e)}")
    
    def switch_device(self, device_text):
        """切換當前設備"""
        if device_text == "無設備連接":
            return
            
        # 從顯示文本中提取端口信息
        try:
            # 解析設備選擇文本格式：[端口] - [設備ID] (活動中)
            if " - " in device_text:
                port = device_text.split(" - ")[0]
                # 直接切換到指定端口的設備
                if port in self.connected_devices:
                    self.switch_active_device(port)
                    self.log_message(f"切換到設備: {device_text}")
                else:
                    self.log_message(f"切換設備失敗: {port}")
        except Exception as e:
            self.logger.error(f"切換設備時發生錯誤: {e}")
            
    # 多設備管理器信號處理
    def update_device_list(self, device_list):
        """更新設備列表"""
        current_text = self.device_combo.currentText()
        self.device_combo.clear()
        
        if not device_list:
            self.device_combo.addItem("無設備連接")
            self.disconnect_all_btn.setEnabled(False)
        else:
            for device in device_list:
                display_text = f"{device['port']} - {device['device_id']}"
                if device['is_active']:
                    display_text += " (活動中)"
                self.device_combo.addItem(display_text)
                
            self.disconnect_all_btn.setEnabled(True)
            
            # 嘗試恢復之前的選擇
            for i in range(self.device_combo.count()):
                if current_text in self.device_combo.itemText(i):
                    self.device_combo.setCurrentIndex(i)
                    break
    
    
    def enable_controls(self, enabled):
        """啟用或停用控制項"""
        for control in self.all_controls:
            control.setEnabled(enabled)
            
    # 原有的設備控制方法保持不變
    def quick_set(self, voltage, current):
        """快速設定電壓和電流"""
        self.voltage_spin.setValue(voltage)
        self.current_spin.setValue(current)
        self.apply_settings()
        
    def apply_custom_quick_set(self):
        """應用自定義快速設定"""
        if not self.is_device_connected():
            return
            
        voltage = self.custom_voltage.value()
        current = self.custom_current.value()
        self.quick_set(voltage, current)
        
    def apply_settings(self):
        """應用設定到設備"""
        if not self.dp711:
            QMessageBox.warning(self, "警告", "沒有連接的設備")
            return
        
        try:
            voltage = self.voltage_spin.value()
            current = self.current_spin.value()
            
            self.dp711.set_voltage(voltage)
            self.dp711.set_current_limit(current)
            
            if self.ovp_enable.isChecked():
                self.dp711.set_ovp(self.ovp_spin.value())
                
            if self.ocp_enable.isChecked():
                self.dp711.set_ocp(self.ocp_spin.value())
                
            self.log_message(f"設定已應用: V={voltage}V, I={current}A")
            
        except Exception as e:
            self.logger.error(f"應用設定時發生錯誤: {e}")
            QMessageBox.critical(self, "設定錯誤", f"應用設定失敗: {str(e)}")
            
    def toggle_output(self):
        """切換輸出狀態"""
        if not self.dp711:
            QMessageBox.warning(self, "警告", "沒有連接的設備")
            return
        
        try:
            if self.dp711.is_output_on():
                self.dp711.set_output(False)
                self.output_btn.setText("開啟輸出")
                self.output_status.setStyleSheet("color: red; font-size: 20px;")
                self.log_message("輸出已關閉")
            else:
                self.dp711.set_output(True)
                self.output_btn.setText("關閉輸出")
                self.output_status.setStyleSheet("color: green; font-size: 20px;")
                self.log_message("輸出已開啟")
                
        except Exception as e:
            self.logger.error(f"切換輸出時發生錯誤: {e}")
            QMessageBox.critical(self, "輸出控制錯誤", f"無法切換輸出狀態: {str(e)}")
    
    def toggle_measurement(self):
        """切換測量狀態"""
        if not self.measurement_worker or not self.measurement_worker.isRunning():
            self.start_measurement()
        else:
            self.stop_measurement()
            
    def start_measurement(self):
        """開始測量"""
        if not self.dp711:
            QMessageBox.warning(self, "警告", "沒有連接的設備")
            return
            
        try:
            if self.measurement_worker:
                self.measurement_worker.stop_measurement()
                
            self.measurement_worker = RigolMeasurementWorker(self.dp711)
            self.measurement_worker.data_ready.connect(self.update_measurements)
            self.measurement_worker.error_occurred.connect(self.handle_measurement_error)
            
            # 重置數據
            self.voltage_data.clear()
            self.current_data.clear()
            self.power_data.clear()
            self.time_data.clear()
            self.start_time = datetime.now()
            
            self.measurement_worker.start_measurement()
            self.start_measure_btn.setText("停止測量")
            self.stop_measure_btn.setEnabled(True)
            
            self.log_message("測量已開始")
            
            # 初始化數據記錄器
            if not self.data_logger:
                self.data_logger = DataLogger()
                session_name = self.data_logger.start_session()
                self.log_message(f"開始數據記錄會話: {session_name}")
                
        except Exception as e:
            self.logger.error(f"啟動測量時發生錯誤: {e}")
            QMessageBox.critical(self, "測量錯誤", f"無法啟動測量: {str(e)}")
            
    def stop_measurement(self):
        """停止測量"""
        try:
            if self.measurement_worker:
                self.measurement_worker.stop_measurement()
                
            self.start_measure_btn.setText("開始測量")
            self.stop_measure_btn.setEnabled(False)
            
            if self.data_logger:
                self.data_logger.stop_session()
                
            self.log_message("測量已停止")
            
        except Exception as e:
            self.logger.error(f"停止測量時發生錯誤: {e}")
            
    def update_measurements(self, voltage, current, power):
        """更新測量數據"""
        try:
            # 更新 LCD 顯示
            self.voltage_lcd.display(f"{voltage:.3f}")
            self.current_lcd.display(f"{current:.3f}")
            self.power_lcd.display(f"{power:.3f}")
            
            # 計算效率 (簡化計算)
            efficiency = (power / (voltage * current)) * 100 if voltage * current > 0 else 0
            self.efficiency_lcd.display(f"{efficiency:.1f}")
            
            # 記錄數據
            current_time = (datetime.now() - self.start_time).total_seconds()
            self.time_data.append(current_time)
            self.voltage_data.append(voltage)
            self.current_data.append(current)
            self.power_data.append(power)
            
            # 限制數據點數量
            max_points = 1000
            if len(self.time_data) > max_points:
                self.time_data = self.time_data[-max_points:]
                self.voltage_data = self.voltage_data[-max_points:]
                self.current_data = self.current_data[-max_points:]
                self.power_data = self.power_data[-max_points:]
                
            # 更新圖表
            self.voltage_curve.setData(self.time_data, self.voltage_data)
            self.current_curve.setData(self.time_data, self.current_data)
            self.power_curve.setData(self.time_data, self.power_data)
            
            # 記錄到數據記錄器
            if self.data_logger:
                self.data_logger.log_measurement({
                    'timestamp': datetime.now().isoformat(),
                    'voltage': voltage,
                    'current': current,
                    'power': power,
                    'device_id': f'DP711_{self.active_device_port}' if self.active_device_port else 'unknown'
                })
                
        except Exception as e:
            self.logger.error(f"更新測量數據時發生錯誤: {e}")
            
    def handle_measurement_error(self, error_msg):
        """處理測量錯誤"""
        self.logger.error(f"測量錯誤: {error_msg}")
        self.log_message(f"測量錯誤: {error_msg}")
        self.stop_measurement()
        
    def log_message(self, message):
        """記錄訊息到日誌顯示"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.log_text.append(formatted_message)
        self.logger.info(message)
        
    def closeEvent(self, event):
        """關閉事件處理"""
        try:
            # 停止測量
            if self.measurement_worker:
                self.measurement_worker.stop_measurement()
                
            # 停止數據記錄
            if self.data_logger:
                self.data_logger.stop_session()
                
            # 斷開所有設備
            self.disconnect_all_devices()
            
            self.logger.info("Rigol 控制 Widget 正常關閉")
            
        except Exception as e:
            self.logger.error(f"關閉時發生錯誤: {e}")
            
        super().closeEvent(event)
        
    def set_theme(self, theme_name):
        """設置主題 (保持向後相容)"""
        self.current_theme = theme_name
        # 可以在這裡實現主題切換邏輯，目前保持簡單實現
        self.logger.debug(f"Rigol widget 主題設置為: {theme_name}")
        
    # 向後相容方法 - 支持舊版 API
    def connect_device(self):
        """向後相容: 連接設備 (使用第一個可用端口)"""
        if self.port_combo.count() > 0 and self.port_combo.currentData():
            self.connect_new_device()
        else:
            self.scan_ports()
            if self.port_combo.count() > 0:
                self.connect_new_device()
            else:
                QMessageBox.warning(self, "警告", "沒有發現可用的 DP711 端口")
                
    def disconnect_device(self):
        """向後相容: 斷開設備"""
        self.disconnect_current_device()
        
    # ================================
    # 專業化功能實現方法
    # ================================
    
    def save_current_to_memory(self):
        """保存當前設定到選定的記憶體"""
        if not self.dp711:
            QMessageBox.warning(self, "警告", "沒有連接的設備")
            return
            
        try:
            memory_index = self.memory_combo.currentIndex() + 1
            success = self.dp711.save_memory_state(memory_index)
            
            if success:
                self.log_message(f"設定已保存到記憶體 M{memory_index}")
                self.refresh_memory_catalog()  # 刷新顯示
                QMessageBox.information(self, "保存成功", 
                    f"當前設定已保存到記憶體 M{memory_index}")
            else:
                QMessageBox.warning(self, "保存失敗", "無法保存設定到記憶體")
                
        except Exception as e:
            self.logger.error(f"保存記憶體時發生錯誤: {e}")
            QMessageBox.critical(self, "保存錯誤", f"保存記憶體失敗: {str(e)}")
            
    def load_from_memory(self):
        """從選定的記憶體載入設定"""
        if not self.dp711:
            QMessageBox.warning(self, "警告", "沒有連接的設備")
            return
            
        try:
            memory_index = self.memory_combo.currentIndex() + 1
            success = self.dp711.recall_memory_state(memory_index)
            
            if success:
                # 更新GUI顯示以反映載入的設定
                self._update_gui_from_device()
                self.log_message(f"已從記憶體 M{memory_index} 載入設定")
                QMessageBox.information(self, "載入成功", 
                    f"已從記憶體 M{memory_index} 載入設定")
            else:
                QMessageBox.warning(self, "載入失敗", "無法從記憶體載入設定")
                
        except Exception as e:
            self.logger.error(f"載入記憶體時發生錯誤: {e}")
            QMessageBox.critical(self, "載入錯誤", f"載入記憶體失敗: {str(e)}")
            
    def quick_load_memory(self, memory_number: int):
        """快速載入指定記憶體"""
        if not self.dp711:
            return
            
        try:
            success = self.dp711.recall_memory_state(memory_number)
            if success:
                self._update_gui_from_device()
                self.log_message(f"快速載入記憶體 M{memory_number}")
                
                # 更新記憶體選擇器
                self.memory_combo.setCurrentIndex(memory_number - 1)
            else:
                self.log_message(f"載入記憶體 M{memory_number} 失敗")
                
        except Exception as e:
            self.logger.error(f"快速載入記憶體 M{memory_number} 時發生錯誤: {e}")
            self.log_message(f"載入記憶體 M{memory_number} 錯誤: {e}")
            
    def refresh_memory_catalog(self):
        """刷新記憶體內容目錄"""
        if not self.dp711:
            return
            
        try:
            self.refresh_memory_btn.setText("刷新中...")
            self.refresh_memory_btn.setEnabled(False)
            
            # 獲取記憶體目錄
            memory_catalog = self.dp711.get_memory_catalog()
            
            # 更新記憶體選擇器顯示
            for i, (mem_num, mem_info) in enumerate(memory_catalog.items()):
                if 'error' not in mem_info:
                    voltage = mem_info.get('voltage', 0.0)
                    current = mem_info.get('current', 0.0)
                    display_text = f"M{mem_num} - {voltage:.2f}V/{current:.2f}A"
                    
                    # 更新快速按鈕提示
                    if i < len(self.quick_memory_btns):
                        self.quick_memory_btns[i].setToolTip(
                            f"M{mem_num}: {voltage:.2f}V, {current:.2f}A"
                        )
                else:
                    display_text = f"M{mem_num} - 空"
                    if i < len(self.quick_memory_btns):
                        self.quick_memory_btns[i].setToolTip(f"M{mem_num}: 空槽位")
                
                # 更新下拉選單
                if i < self.memory_combo.count():
                    self.memory_combo.setItemText(i, display_text)
                    
            # 更新當前選中記憶體的預覽
            self._update_memory_preview()
            
            self.log_message("記憶體目錄已刷新")
            
        except Exception as e:
            self.logger.error(f"刷新記憶體目錄時發生錯誤: {e}")
            self.log_message(f"刷新記憶體目錄失敗: {e}")
            
        finally:
            self.refresh_memory_btn.setText("🔄 刷新")
            self.refresh_memory_btn.setEnabled(True)
            
    def _update_memory_preview(self):
        """更新記憶體內容預覽"""
        if not self.dp711:
            self.memory_preview.setText("V: -.---V, I: -.---A")
            return
            
        try:
            memory_index = self.memory_combo.currentIndex() + 1
            current_text = self.memory_combo.currentText()
            
            if " - " in current_text and "空" not in current_text:
                # 從顯示文本中提取數值
                preview_part = current_text.split(" - ")[1]
                self.memory_preview.setText(preview_part)
            else:
                self.memory_preview.setText("V: -.---V, I: -.---A")
                
        except Exception as e:
            self.logger.debug(f"更新記憶體預覽時發生錯誤: {e}")
            
    def _update_gui_from_device(self):
        """從設備讀取設定並更新GUI顯示"""
        if not self.dp711:
            return
            
        try:
            # 讀取並更新電壓設定
            voltage = self.dp711.get_set_voltage()
            self.voltage_spin.setValue(voltage)
            
            # 讀取並更新電流設定
            current = self.dp711.get_set_current()
            self.current_spin.setValue(current)
            
            # 更新保護設定
            try:
                ovp_level = self.dp711.get_ovp_level()
                if ovp_level > 0:
                    self.ovp_spin.setValue(ovp_level)
            except:
                pass
                
            try:
                ocp_level = self.dp711.get_ocp_level()
                if ocp_level > 0:
                    self.ocp_spin.setValue(ocp_level)
            except:
                pass
                
            # 更新追蹤模式
            try:
                track_mode = self.dp711.get_track_mode()
                mode_mapping = {
                    'INDEP': 0,
                    'SER': 1, 
                    'PARA': 2
                }
                if track_mode in mode_mapping:
                    self.track_mode_combo.setCurrentIndex(mode_mapping[track_mode])
            except:
                pass
                
            self.log_message("GUI 顯示已同步設備設定")
            
        except Exception as e:
            self.logger.error(f"從設備更新GUI時發生錯誤: {e}")
            
    def set_track_mode(self, mode_text: str):
        """設定追蹤模式"""
        if not self.dp711:
            return
            
        try:
            # 從顯示文本中提取模式
            mode = mode_text.split()[0]  # 取第一個單詞
            success = self.dp711.set_track_mode(mode)
            
            if success:
                self.log_message(f"追蹤模式已設定為: {mode}")
            else:
                self.log_message(f"設定追蹤模式失敗: {mode}")
                
        except Exception as e:
            self.logger.error(f"設定追蹤模式時發生錯誤: {e}")
            self.log_message(f"設定追蹤模式錯誤: {e}")
            
    def clear_device_protection(self):
        """清除設備保護狀態"""
        if not self.dp711:
            return
            
        try:
            success = self.dp711.clear_protection()
            if success:
                self.log_message("保護狀態已清除")
                self.clear_protection_btn.setVisible(False)
                self.refresh_device_status()  # 刷新狀態顯示
            else:
                self.log_message("清除保護狀態失敗")
                
        except Exception as e:
            self.logger.error(f"清除保護狀態時發生錯誤: {e}")
            self.log_message(f"清除保護狀態錯誤: {e}")
            
    def refresh_device_status(self):
        """刷新設備狀態顯示"""
        if not self.dp711:
            return
            
        try:
            # 獲取保護狀態
            protection_status = self.dp711.get_protection_status()
            
            if protection_status.get('protection_clear', True):
                self.protection_status_label.setText("正常")
                self.protection_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                self.clear_protection_btn.setVisible(False)
            else:
                status_text = []
                if protection_status.get('ovp_triggered'):
                    status_text.append("過壓")
                if protection_status.get('ocp_triggered'):
                    status_text.append("過流")
                if protection_status.get('otp_triggered'):
                    status_text.append("過溫")
                if protection_status.get('unregulated'):
                    status_text.append("調節失效")
                    
                if status_text:
                    self.protection_status_label.setText("保護: " + ", ".join(status_text))
                else:
                    self.protection_status_label.setText("保護觸發")
                    
                self.protection_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.clear_protection_btn.setVisible(True)
                
            # 獲取設備溫度
            temperature = self.dp711.get_device_temperature()
            if temperature > 0:
                self.temperature_label.setText(f"{temperature:.1f}°C")
                
                # 根據溫度設定顏色
                if temperature > 60:
                    temp_color = "#e74c3c"  # 紅色 - 高溫
                elif temperature > 45:
                    temp_color = "#f39c12"  # 橙色 - 溫熱
                else:
                    temp_color = "#3498db"  # 藍色 - 正常
                    
                self.temperature_label.setStyleSheet(f"color: {temp_color}; font-family: monospace;")
            else:
                self.temperature_label.setText("--°C")
                self.temperature_label.setStyleSheet("color: #7f8c8d; font-family: monospace;")
                
            self.log_message("設備狀態已刷新")
            
        except Exception as e:
            self.logger.error(f"刷新設備狀態時發生錯誤: {e}")
            self.log_message(f"刷新設備狀態失敗: {e}")
            
    def update_device_controls(self):
        """更新設備控制項狀態 - 增強版本"""
        # 調用原有方法
        super_method = getattr(super(), 'update_device_controls', None)
        if super_method:
            super_method()
        else:
            # 如果沒有父類方法，執行基本更新
            has_active_device = self.dp711 is not None
            self.enable_controls(has_active_device)
            
        # 專業化功能的額外初始化
        if self.dp711:
            try:
                # 初始載入記憶體目錄
                self.refresh_memory_catalog()
                
                # 初始載入設備狀態
                self.refresh_device_status()
                
                # 設置記憶體組合框變化監聽
                self.memory_combo.currentIndexChanged.connect(self._update_memory_preview)
                
            except Exception as e:
                self.logger.warning(f"初始化專業化功能時發生警告: {e}")
                
    def create_professional_lcd(self, label_text: str, unit: str, color: str):
        """
        創建專業級LCD顯示器組件
        
        Args:
            label_text: 顯示標籤文字
            unit: 單位符號  
            color: 主題顏色 (hex格式)
        
        Returns:
            包含LCD顯示器的QGroupBox組件
        """
        # 創建群組框
        group = QGroupBox(label_text)
        group.setStyleSheet(f"QGroupBox {{ font-weight: bold; color: {color}; }}")
        
        # 使用水平佈局，讓LCD充滿整個群組框
        layout = QHBoxLayout(group)
        layout.setContentsMargins(5, 3, 5, 3)  # 減小內邊距
        
        # 創建LCD顯示器 - 6位數顯示
        lcd_display = QLCDNumber(6)
        lcd_display.setStyleSheet(f"""
            QLCDNumber {{ 
                color: {color}; 
                background-color: #34495e;
                border: 2px solid {color};
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                font-size: 14px;
            }}
        """)
        
        # LCD顯示設定
        lcd_display.setDigitCount(6)
        lcd_display.setMode(QLCDNumber.Mode.Dec)
        lcd_display.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)
        lcd_display.display("0.0000")
        
        # 設定尺寸策略
        lcd_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lcd_display.setMinimumHeight(40)
        
        layout.addWidget(lcd_display)
        
        # 創建單位標籤
        unit_label = QLabel(unit)
        unit_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                font-size: 12px;
                font-family: Arial;
                margin-left: 5px;
            }}
        """)
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        unit_label.setMinimumWidth(30)
        
        layout.addWidget(unit_label)
        
        # 將LCD引用儲存到群組框中以便後續存取
        group.lcd_display = lcd_display
        group.unit_label = unit_label
        
        return group
    
    def create_professional_lcd_large(self, label_text: str, unit: str, color: str):
        """
        創建大型專業級LCD顯示器組件 - 用於主要監控面板
        
        Args:
            label_text: 顯示標籤文字
            unit: 單位符號  
            color: 主題顏色 (hex格式)
        
        Returns:
            包含LCD顯示器的QGroupBox組件
        """
        # 創建群組框
        group = QGroupBox(label_text)
        group.setStyleSheet(f"""
            QGroupBox {{ 
                font-weight: bold; 
                font-size: 13px;
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 1ex;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 10px;
            }}
        """)
        
        # 使用水平佈局，讓LCD充滿整個群組框
        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 創建大型LCD顯示器 - 8位數顯示，加大尺寸
        lcd_display = QLCDNumber(8)
        lcd_display.setStyleSheet(f"""
            QLCDNumber {{ 
                color: {color}; 
                background-color: #1a1a1a;
                border: 3px solid {color};
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                font-size: 18px;
            }}
        """)
        
        # LCD顯示設定 - 加大版本
        lcd_display.setDigitCount(8)
        lcd_display.setMode(QLCDNumber.Mode.Dec)
        lcd_display.setSegmentStyle(QLCDNumber.SegmentStyle.Filled)
        lcd_display.display("0.000000")
        
        # 設定尺寸策略 - 更大的尺寸
        lcd_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        lcd_display.setMinimumHeight(60)  # 增加高度
        lcd_display.setMinimumWidth(180)  # 增加寬度
        
        layout.addWidget(lcd_display)
        
        # 創建單位標籤 - 加大版本
        unit_label = QLabel(unit)
        unit_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                font-weight: bold;
                font-size: 16px;
                font-family: Arial;
                margin-left: 8px;
            }}
        """)
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        unit_label.setMinimumWidth(40)
        
        layout.addWidget(unit_label)
        
        # 將LCD引用儲存到群組框中以便後續存取
        group.lcd_display = lcd_display
        group.unit_label = unit_label
        
        return group
        
    def set_theme(self, theme_name: str):
        """
        設定專業主題樣式
        
        Args:
            theme_name: 主題名稱 ('light' 或 'dark')
        """
        self.current_theme = theme_name
        
        # 基礎樣式設定
        if theme_name == "dark":
            main_bg = "#2b2b2b"
            widget_bg = "#404040" 
            text_color = "#ffffff"
            border_color = "#555555"
            group_bg = "#353535"
        else:
            main_bg = "#f8f9fa"
            widget_bg = "#ffffff"
            text_color = "#2c3e50"
            border_color = "#bdc3c7"
            group_bg = "#ecf0f1"
        
        # 應用主題樣式
        professional_style = f"""
            RigolControlWidget {{
                background-color: {main_bg};
                color: {text_color};
            }}
            QGroupBox {{
                font-weight: bold;
                font-size: 12px;
                border: 2px solid {border_color};
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 10px;
                background-color: {group_bg};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 8px;
                background-color: {widget_bg};
                border-radius: 3px;
            }}
            QWidget {{
                background-color: {main_bg};
                color: {text_color};
                font-family: "Segoe UI", Arial, sans-serif;
            }}
            QPushButton {{
                background-color: {widget_bg};
                border: 1px solid {border_color};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
                min-height: 20px;
            }}
            QPushButton:hover {{
                background-color: {"#4a4a4a" if theme_name == "dark" else "#e8f4f8"};
                border-color: {"#666666" if theme_name == "dark" else "#3498db"};
            }}
            QPushButton:pressed {{
                background-color: {"#555555" if theme_name == "dark" else "#d5e8f0"};
            }}
            QComboBox, QLineEdit, QDoubleSpinBox {{
                background-color: {widget_bg};
                border: 1px solid {border_color};
                border-radius: 3px;
                padding: 4px 8px;
                min-height: 18px;
            }}
            QTextEdit {{
                background-color: {widget_bg};
                border: 1px solid {border_color};
                border-radius: 3px;
                padding: 4px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 11px;
            }}
        """
        
        self.setStyleSheet(professional_style)
        self.logger.info(f"DP711 專業主題已切換至: {theme_name}")
        
        # 如果LCD已創建，也更新其樣式
        if hasattr(self, 'voltage_lcd_frame'):
            self._update_lcd_theme()
            
    def _update_lcd_theme(self):
        """更新LCD顯示器的主題樣式"""
        if not hasattr(self, 'voltage_lcd_frame'):
            return
            
        # 根據主題重新設定LCD樣式
        theme_colors = {
            "voltage": "#e74c3c",
            "current": "#3498db", 
            "power": "#f39c12",
            "efficiency": "#9b59b6"
        }
        
        bg_color = "#34495e" if self.current_theme == "dark" else "#2c3e50"
        
        # 更新各個LCD組件的樣式
        lcd_frames = [
            (self.voltage_lcd_frame, theme_colors["voltage"]),
            (self.current_lcd_frame, theme_colors["current"]),
            (self.power_lcd_frame, theme_colors["power"]),
            (self.efficiency_lcd_frame, theme_colors["efficiency"])
        ]
        
        for frame, color in lcd_frames:
            frame.lcd_display.setStyleSheet(f"""
                QLCDNumber {{ 
                    color: {color}; 
                    background-color: {bg_color};
                    border: 2px solid {color};
                    border-radius: 5px;
                    font-family: 'Courier New', monospace;
                    font-size: 14px;
                }}
            """)
            frame.unit_label.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    font-weight: bold;
                    font-size: 12px;
                    font-family: Arial;
                    margin-left: 5px;
                }}
            """)
            
    # ================================
    # 專業預設配置功能
    # ================================
    
    def on_preset_selection_changed(self, preset_name: str):
        """預設選擇變化處理"""
        if preset_name and preset_name != "選擇預設配置..." and preset_name in self.presets:
            preset_config = self.presets[preset_name]
            
            # 顯示預設詳細資訊
            voltage = preset_config.get('voltage', 0)
            current = preset_config.get('current', 0)
            description = preset_config.get('description', '無描述')
            
            info_text = f"""
            📝 {description}
            ⚡ 電壓: {voltage}V
            🔌 電流限制: {current}A
            💡 功率: {voltage * current:.2f}W
            """
            
            self.preset_info_label.setText(info_text.strip())
            self.preset_info_label.setStyleSheet("color: #2980b9; font-weight: 500; margin: 5px;")
            self.apply_preset_btn.setEnabled(True)
        else:
            self.preset_info_label.setText("選擇預設以查看詳細資訊")
            self.preset_info_label.setStyleSheet("color: #7f8c8d; font-style: italic; margin: 5px;")
            self.apply_preset_btn.setEnabled(False)
            
    def apply_preset_configuration(self):
        """套用預設配置"""
        preset_name = self.preset_combo.currentText()
        
        if not preset_name or preset_name == "選擇預設配置..." or preset_name not in self.presets:
            QMessageBox.warning(self, "警告", "請先選擇一個有效的預設配置")
            return
            
        try:
            preset_config = self.presets[preset_name]
            
            # 套用電壓設定
            voltage = preset_config.get('voltage', 0)
            self.voltage_spin.setValue(voltage)
            
            # 套用電流限制設定
            current = preset_config.get('current', 0) 
            self.current_spin.setValue(current)
            
            # 自動設定保護值 (稍微高於設定值)
            self.ovp_spin.setValue(voltage * 1.1)  # 過壓保護設為110%
            self.ocp_spin.setValue(current * 1.05) # 過流保護設為105%
            
            self.log_message(f"✅ 已套用預設配置: {preset_name}")
            self.log_message(f"   電壓: {voltage}V, 電流限制: {current}A")
            
            # 自動套用設定到設備 (如果已連接)
            if self.dp711:
                self.apply_settings()
                
        except Exception as e:
            self.logger.error(f"套用預設配置時發生錯誤: {e}")
            QMessageBox.critical(self, "錯誤", f"套用預設配置失敗: {str(e)}")
            
    def save_custom_preset(self):
        """保存自訂預設配置"""
        from PyQt6.QtWidgets import QInputDialog
        
        # 獲取當前設定
        current_voltage = self.voltage_spin.value()
        current_current = self.current_spin.value()
        
        # 輸入自訂預設名稱
        preset_name, ok = QInputDialog.getText(
            self, "保存自訂預設", 
            "請輸入預設配置名稱:",
            text=f"Custom_{current_voltage}V_{current_current}A"
        )
        
        if not ok or not preset_name.strip():
            return
            
        preset_name = preset_name.strip()
        
        # 輸入描述
        description, ok = QInputDialog.getText(
            self, "預設描述",
            "請輸入預設配置描述:",
            text=f"{current_voltage}V/{current_current}A 自訂配置"
        )
        
        if not ok:
            return
            
        try:
            # 創建預設配置
            new_preset = {
                "voltage": current_voltage,
                "current": current_current,
                "description": description.strip() or f"{preset_name} 自訂配置"
            }
            
            # 添加到預設字典
            self.presets[preset_name] = new_preset
            
            # 更新下拉框
            self.preset_combo.addItem(preset_name)
            self.preset_combo.setCurrentText(preset_name)
            
            # 保存到文件
            try:
                import json
                import os
                preset_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'rigol_presets.json')
                with open(preset_file, 'w', encoding='utf-8') as f:
                    json.dump(self.presets, f, ensure_ascii=False, indent=2)
                    
                self.log_message(f"✅ 自訂預設已保存: {preset_name}")
                QMessageBox.information(self, "成功", f"預設配置 '{preset_name}' 已成功保存")
                
            except Exception as e:
                self.logger.warning(f"保存預設文件時發生警告: {e}")
                self.log_message(f"⚠️ 預設已添加但未保存到文件: {e}")
                
        except Exception as e:
            self.logger.error(f"保存自訂預設時發生錯誤: {e}")
            QMessageBox.critical(self, "錯誤", f"保存預設配置失敗: {str(e)}")
    
    def reset_device(self):
        """重置設備到出廠預設狀態"""
        if not self.current_device or not self.is_connected:
            QMessageBox.warning(self, "警告", "沒有連接的設備")
            return
            
        reply = QMessageBox.question(
            self,
            "確認重置",
            "確定要將設備重置到出廠預設狀態嗎？\n這將清除所有自訂設定！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 首先關閉輸出
                if self.output_enabled:
                    self.current_device.output_off()
                    
                # 發送重置指令
                self.current_device.send_command("*RST")
                
                # 重新初始化設備
                self.current_device.initialize()
                
                # 重設UI狀態
                self.voltage_spin.setValue(5.0)
                self.current_spin.setValue(1.0)
                self.ovp_spin.setValue(31.0)
                self.ocp_spin.setValue(5.2)
                self.ovp_enable.setChecked(False)
                self.ocp_enable.setChecked(False)
                self.track_mode_combo.setCurrentText("INDEP (獨立)")
                
                self.output_enabled = False
                self.update_ui_state()
                
                self.log_message("🔄 設備已重置到出廠預設狀態")
                QMessageBox.information(self, "成功", "設備已重置到出廠預設狀態")
                
            except Exception as e:
                self.logger.error(f"重置設備時發生錯誤: {e}")
                self.log_message(f"❌ 重置設備失敗: {e}")
                QMessageBox.critical(self, "錯誤", f"重置設備失敗: {str(e)}")
    
    def clear_device_protection(self):
        """清除設備保護狀態"""
        if not self.current_device or not self.is_connected:
            return
            
        try:
            # 清除保護狀態的SCPI指令
            self.current_device.send_command("OUTP:PROT:CLE")
            
            self.protection_status_label.setText("正常")
            self.protection_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.clear_protection_btn.setVisible(False)
            
            self.log_message("✅ 設備保護狀態已清除")
            
        except Exception as e:
            self.logger.error(f"清除保護狀態時發生錯誤: {e}")
            self.log_message(f"❌ 清除保護失敗: {e}")
    
    def set_track_mode(self, mode_text: str):
        """設定追蹤模式"""
        if not self.current_device or not self.is_connected:
            return
            
        try:
            # 解析模式
            if "INDEP" in mode_text:
                mode = "INDEP"
            elif "SER" in mode_text:
                mode = "SER"
            elif "PARA" in mode_text:
                mode = "PARA"
            else:
                return
                
            # 發送追蹤模式指令 (如果設備支援)
            self.current_device.send_command(f"OUTP:TRACK {mode}")
            
            self.log_message(f"🔗 追蹤模式已設為: {mode}")
            
        except Exception as e:
            self.logger.error(f"設定追蹤模式時發生錯誤: {e}")
            self.log_message(f"❌ 設定追蹤模式失敗: {e}")
    
    def refresh_device_status(self):
        """刷新設備狀態"""
        if not self.current_device or not self.is_connected:
            return
            
        try:
            # 查詢設備溫度 (如果支援)
            try:
                temp_response = self.current_device.send_query("SYST:TEMP?")
                if temp_response:
                    temp = float(temp_response.strip())
                    self.temperature_label.setText(f"{temp:.1f}°C")
                    # 根據溫度設定顏色
                    if temp > 60:
                        self.temperature_label.setStyleSheet("color: #e74c3c; font-family: monospace; font-weight: bold;")
                    elif temp > 45:
                        self.temperature_label.setStyleSheet("color: #f39c12; font-family: monospace; font-weight: bold;")
                    else:
                        self.temperature_label.setStyleSheet("color: #3498db; font-family: monospace;")
            except:
                self.temperature_label.setText("N/A°C")
                
            # 查詢保護狀態 (如果支援)
            try:
                prot_response = self.current_device.send_query("SYST:ERR?")
                if prot_response and "No error" not in prot_response:
                    self.protection_status_label.setText("保護中")
                    self.protection_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                    self.clear_protection_btn.setVisible(True)
                else:
                    self.protection_status_label.setText("正常")
                    self.protection_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                    self.clear_protection_btn.setVisible(False)
            except:
                pass
                
            self.log_message("🔄 設備狀態已刷新")
            
        except Exception as e:
            self.logger.error(f"刷新設備狀態時發生錯誤: {e}")
            self.log_message(f"❌ 刷新狀態失敗: {e}")
    
    def clear_log(self):
        """清除操作日誌"""
        self.log_display.clear()
        self.log_message("🗑️ 操作日誌已清除")
    
    def export_log(self):
        """導出操作日誌"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            from datetime import datetime
            
            # 獲取保存路徑
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "導出日誌",
                f"rigol_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                "文本文件 (*.txt);;所有文件 (*.*)"
            )
            
            if filename:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.log_display.toPlainText())
                    
                self.log_message(f"✅ 日誌已導出到: {filename}")
                QMessageBox.information(self, "成功", f"日誌已成功導出到:\n{filename}")
                
        except Exception as e:
            self.logger.error(f"導出日誌時發生錯誤: {e}")
            self.log_message(f"❌ 導出日誌失敗: {e}")
            QMessageBox.critical(self, "錯誤", f"導出日誌失敗: {str(e)}")
    
    def log_message(self, message: str):
        """添加日誌消息 - 重新實現以支援新的日誌Tab"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 添加到日誌顯示區域
        if hasattr(self, 'log_display'):
            self.log_display.append(formatted_message)
            
            # 自動滾動到底部（如果啟用）
            if self.auto_scroll_check.isChecked():
                cursor = self.log_display.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                self.log_display.setTextCursor(cursor)
        
        # 同時記錄到logger
        self.logger.info(message.replace("✅", "").replace("❌", "").replace("⚠️", "").replace("🔄", "").strip())
    
    def create_plot_area(self):
        """創建數據圖表區域"""
        # 創建pyqtgraph繪圖widget
        plot_widget = pg.PlotWidget()
        plot_widget.setBackground('#2b2b2b')
        plot_widget.setLabel('left', '電流 (A)', color='white', size='12pt')
        plot_widget.setLabel('bottom', '時間 (s)', color='white', size='12pt')
        plot_widget.setTitle('電源供應器監控數據', color='white', size='14pt')
        
        # 設置網格
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # 設置圖例
        plot_widget.addLegend()
        
        # 創建數據曲線
        self.voltage_curve = plot_widget.plot(
            pen=pg.mkPen(color='#e74c3c', width=2), 
            name='電壓 (V)'
        )
        self.current_curve = plot_widget.plot(
            pen=pg.mkPen(color='#3498db', width=2), 
            name='電流 (A)'
        )
        self.power_curve = plot_widget.plot(
            pen=pg.mkPen(color='#2ecc71', width=2), 
            name='功率 (W)'
        )
        
        # 數據存儲
        self.plot_data = {
            'time': [],
            'voltage': [],
            'current': [],
            'power': []
        }
        
        return plot_widget