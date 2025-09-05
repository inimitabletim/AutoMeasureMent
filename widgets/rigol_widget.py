#!/usr/bin/env python3
"""
Rigol DP711 Professional Power Supply Control Widget
專業級電源供應器控制介面 - 基於Keithley 2461統一架構
支援多設備管理、專業LCD顯示、統一Worker系統
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
                            QFrame, QLCDNumber, QSizePolicy, QScrollArea,
                            QSpacerItem)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.rigol_dp711 import RigolDP711
from src.enhanced_data_system import EnhancedDataLogger
from widgets.unit_input_widget import UnitInputWidget, UnitDisplayWidget
from widgets.connection_status_widget import ConnectionStatusWidget
from widgets.floating_settings_panel import FloatingSettingsPanel


class ContinuousMeasurementWorker(QThread):
    """連續測量工作執行緒 - 與Keithley架構統一"""
    data_ready = pyqtSignal(float, float, float)  # voltage, current, power
    error_occurred = pyqtSignal(str)
    
    def __init__(self, rigol_device):
        super().__init__()
        self.rigol = rigol_device
        self.running = False
        
    def run(self):
        """執行連續測量"""
        measurement_count = 0
        while self.running:
            try:
                if self.rigol and self.rigol.is_connected():
                    v, i, p = self.rigol.measure_all()
                    self.data_ready.emit(v, i, p)
                    measurement_count += 1
                    self.msleep(1000)  # 1000ms間隔 (1秒)
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


class ProfessionalRigolWidget(QWidget):
    """Rigol DP711 專業控制 Widget - 基於Keithley統一架構"""
    
    # 狀態更新信號
    connection_changed = pyqtSignal(bool, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rigol = None
        self.data_logger = None
        self.continuous_worker = None
        self.connection_worker = None
        
        # 連接狀態Widget - 統一的連接管理
        self.connection_status_widget = None
        
        # 測量數據存儲
        self.measurement_data = []  # [(time, voltage, current, power), ...]
        self.start_time = datetime.now()
        
        # 操作狀態
        self.is_measuring = False
        
        # 主題
        self.current_theme = "dark"
        
        # 日誌
        self.logger = logging.getLogger(__name__)
        
        # 狀態更新定時器
        self.status_update_timer = QTimer()
        self.status_update_timer.timeout.connect(self.update_runtime_display)
        
        # 統計數據緩存
        self._voltage_buffer = []
        self._current_buffer = []
        self._power_buffer = []
        self.buffer_size = 100
        
        # 懸浮設定面板
        self.floating_settings = None
        self.instrument_settings = {}
        
        # 設備管理
        self.connected_devices = {}
        self.active_device_port = None
        
        # 專業連接設定 (對應Keithley的IP輸入，但這裡用於串口設置)
        self.port_input = None
        self.baudrate_setting = 9600  # 預設波特率
        self.connection_timeout = 5   # 連接超時
        self.connection_retries = 3   # 重試次數
        
        self.setup_ui()
        
    def setup_ui(self):
        """設置專業用戶介面 - 與Keithley統一佈局"""
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
        
        # 設定分割比例 (6:4)
        main_splitter.setSizes([600, 400])
        main_splitter.setChildrenCollapsible(False)
        
    def create_control_panel(self):
        """創建左側控制面板 - 基於Keithley架構"""
        # 主控制面板容器
        control_widget = QWidget()
        control_widget.setMaximumWidth(380)
        control_widget.setMinimumWidth(350)
        
        # 創建滾動區域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        
        # 滾動內容容器
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # ===== 設備連接 =====
        connection_group = self.create_connection_group()
        layout.addWidget(connection_group)
        
        # ===== 電源控制 =====
        power_control_group = self.create_power_control_group()
        layout.addWidget(power_control_group)
        
        # ===== 測量控制 =====
        measurement_group = self.create_measurement_control_group()
        layout.addWidget(measurement_group)
        
        # ===== 記憶體管理 =====
        memory_group = self.create_memory_management_group()
        layout.addWidget(memory_group)
        
        # ===== 數據管理 =====
        data_group = self.create_data_management_group()
        layout.addWidget(data_group)
        
        # 彈性空間
        layout.addStretch()
        
        # 設置滾動區域
        scroll_area.setWidget(scroll_content)
        
        # 主控制面板布局
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.addWidget(scroll_area)
        
        return control_widget
        
    def create_connection_group(self):
        """創建專業設備連接群組 - 參考Keithley 2461設計，適配串口連接"""
        group = QGroupBox("[CONN] 設備連接")
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QGridLayout(group)
        
        # 串口輸入 (對應Keithley的IP地址輸入)
        layout.addWidget(QLabel("串口:"), 0, 0)
        self.port_input = QComboBox()
        self.port_input.setEditable(True)  # 允許手動輸入
        self.port_input.setPlaceholderText("例如: COM3")
        self.port_input.addItem("COM3")  # 預設選項
        layout.addWidget(self.port_input, 0, 1)
        
        # 自動掃描按鈕 (緊湊設計)
        self.auto_scan_btn = QPushButton("[SCAN] 掃描")
        self.auto_scan_btn.setMaximumWidth(70)
        self.auto_scan_btn.clicked.connect(self.auto_scan_and_detect)
        self.auto_scan_btn.setToolTip("自動掃描並識別DP711設備")
        self.auto_scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(self.auto_scan_btn, 0, 2)
        
        # 進階設定按鈕 (對應波特率等設定)
        self.advanced_connection_btn = QPushButton("[SET] 進階連接設定")
        self.advanced_connection_btn.clicked.connect(self.show_advanced_connection_settings)
        self.advanced_connection_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                margin-top: 5px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        layout.addWidget(self.advanced_connection_btn, 1, 0, 1, 3)
        
        # 統一的連接狀態Widget (與Keithley完全一致)
        try:
            self.connection_status_widget = ConnectionStatusWidget()
            layout.addWidget(self.connection_status_widget, 2, 0, 1, 3)
            # 連接信號處理
            self.connection_status_widget.connection_requested.connect(self._handle_connection_request)
            self.connection_status_widget.disconnection_requested.connect(self._handle_disconnection_request)
            self.connection_status_widget.connection_cancelled.connect(self._handle_connection_cancel)
        except Exception as e:
            self.logger.warning(f"無法創建統一連接狀態Widget: {e}")
            # 後備方案 - 使用簡單狀態顯示
            self.connection_status_widget = QLabel("連接狀態載入中...")
            layout.addWidget(self.connection_status_widget, 2, 0, 1, 3)
            # 創建基本連接按鈕
            self.connect_btn = QPushButton("連接設備")
            self.connect_btn.clicked.connect(self._handle_connection_request)
            layout.addWidget(self.connect_btn, 3, 0, 1, 3)
        
        # 隱藏的波特率設定 (在進階設定中顯示)
        self.baudrate_setting = 9600  # 預設波特率
        
        return group
        
    def create_power_control_group(self):
        """創建電源控制群組"""
        group = QGroupBox("[PWR] 電源控制")
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QGridLayout(group)
        
        # 電壓設定
        layout.addWidget(QLabel("輸出電壓:"), 0, 0)
        self.voltage_input = UnitInputWidget(unit_symbol="V")
        self.voltage_input.set_base_value(5.0)
        layout.addWidget(self.voltage_input, 0, 1)
        
        # 電流限制
        layout.addWidget(QLabel("電流限制:"), 1, 0)
        self.current_input = UnitInputWidget(unit_symbol="A")
        self.current_input.set_base_value(1.0)
        layout.addWidget(self.current_input, 1, 1)
        
        # 控制按鈕
        button_layout = QHBoxLayout()
        
        # 應用設定按鈕
        self.apply_settings_btn = QPushButton("📝 應用設定")
        self.apply_settings_btn.setEnabled(False)
        self.apply_settings_btn.clicked.connect(self.apply_settings)
        button_layout.addWidget(self.apply_settings_btn)
        
        # 輸出控制按鈕
        self.output_btn = QPushButton("開啟輸出")
        self.output_btn.setEnabled(False)
        self.output_btn.clicked.connect(self.toggle_output)
        self.output_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                min-height: 25px;
            }
        """)
        button_layout.addWidget(self.output_btn)
        
        layout.addLayout(button_layout, 2, 0, 1, 2)
        
        return group
        
    def create_measurement_control_group(self):
        """創建測量控制群組"""
        group = QGroupBox("[MEAS] 測量控制")
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(group)
        
        # 測量按鈕
        button_layout = QHBoxLayout()
        
        self.start_measurement_btn = QPushButton("[START] 開始測量")
        self.start_measurement_btn.setEnabled(False)
        self.start_measurement_btn.clicked.connect(self.toggle_measurement)
        button_layout.addWidget(self.start_measurement_btn)
        
        self.stop_measurement_btn = QPushButton("[STOP] 停止")
        self.stop_measurement_btn.setEnabled(False)
        self.stop_measurement_btn.clicked.connect(self.stop_measurement)
        button_layout.addWidget(self.stop_measurement_btn)
        
        layout.addLayout(button_layout)
        
        return group
        
    def create_memory_management_group(self):
        """創建記憶體管理群組"""
        group = QGroupBox("💾 記憶體管理")
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(group)
        
        # 記憶體選擇
        memory_layout = QHBoxLayout()
        memory_layout.addWidget(QLabel("槽位:"))
        
        self.memory_combo = QComboBox()
        for i in range(1, 6):
            self.memory_combo.addItem(f"M{i}")
        memory_layout.addWidget(self.memory_combo)
        
        self.refresh_memory_btn = QPushButton("[REF]")
        self.refresh_memory_btn.setMaximumWidth(40)
        self.refresh_memory_btn.setEnabled(False)
        self.refresh_memory_btn.clicked.connect(self.refresh_memory_catalog)
        self.refresh_memory_btn.setToolTip("刷新記憶體目錄")
        memory_layout.addWidget(self.refresh_memory_btn)
        
        layout.addLayout(memory_layout)
        
        # 記憶體操作按鈕
        memory_ops_layout = QHBoxLayout()
        
        self.save_memory_btn = QPushButton("💾 保存")
        self.save_memory_btn.setEnabled(False)
        self.save_memory_btn.clicked.connect(self.save_to_memory)
        memory_ops_layout.addWidget(self.save_memory_btn)
        
        self.load_memory_btn = QPushButton("📂 載入")
        self.load_memory_btn.setEnabled(False)
        self.load_memory_btn.clicked.connect(self.load_from_memory)
        memory_ops_layout.addWidget(self.load_memory_btn)
        
        layout.addLayout(memory_ops_layout)
        
        return group
        
    def create_data_management_group(self):
        """創建數據管理群組"""
        group = QGroupBox("📁 數據管理")
        group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(group)
        
        # 數據導出按鈕
        export_layout = QHBoxLayout()
        
        self.export_csv_btn = QPushButton("📄 導出CSV")
        self.export_csv_btn.clicked.connect(self.export_csv)
        export_layout.addWidget(self.export_csv_btn)
        
        self.clear_data_btn = QPushButton("[CLR] 清除")
        self.clear_data_btn.clicked.connect(self.clear_measurement_data)
        export_layout.addWidget(self.clear_data_btn)
        
        layout.addLayout(export_layout)
        
        return group
        
    def create_display_panel(self):
        """創建右側顯示面板 - 專業LCD顯示"""
        display_widget = QWidget()
        layout = QVBoxLayout(display_widget)
        layout.setSpacing(10)
        
        # ===== 專業LCD顯示區域 =====
        lcd_group = self.create_professional_lcd_group()
        layout.addWidget(lcd_group)
        
        # ===== 狀態指示區域 =====
        status_group = self.create_status_group()
        layout.addWidget(status_group)
        
        # ===== 圖表顯示區域 =====
        chart_group = self.create_chart_group()
        layout.addWidget(chart_group)
        
        return display_widget
        
    def create_professional_lcd_group(self):
        """創建專業LCD顯示群組 - 與Keithley統一風格"""
        group = QGroupBox("[MON] 電源監控中心")
        layout = QGridLayout(group)
        
        # 電壓顯示
        self.voltage_display = self.create_professional_lcd("電壓", "V", "#e74c3c")
        layout.addWidget(self.voltage_display, 0, 0)
        
        # 電流顯示
        self.current_display = self.create_professional_lcd("電流", "A", "#3498db")
        layout.addWidget(self.current_display, 0, 1)
        
        # 功率顯示
        self.power_display = self.create_professional_lcd("功率", "W", "#f39c12")
        layout.addWidget(self.power_display, 1, 0)
        
        # 效率顯示（預留）
        self.efficiency_display = self.create_professional_lcd("效率", "%", "#9b59b6")
        layout.addWidget(self.efficiency_display, 1, 1)
        
        return group
        
    def create_professional_lcd(self, label_text: str, unit: str, color: str):
        """創建專業級LCD顯示器組件 - 與Keithley統一"""
        # 創建群組框
        group = QGroupBox(label_text)
        group.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {color};
                border-radius: 5px;
                margin-top: 1ex;
                padding: 5px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: {color};
            }}
        """)
        
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 15, 10, 10)
        
        # LCD數字顯示
        lcd = QLCDNumber(8)
        lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        lcd.setDigitCount(8)
        lcd.display("0.000000")
        lcd.setStyleSheet(f"""
            QLCDNumber {{
                background-color: #2c3e50;
                color: {color};
                border: 2px solid #34495e;
                border-radius: 3px;
            }}
        """)
        lcd.setMinimumHeight(60)
        layout.addWidget(lcd)
        
        # 單位標籤
        unit_label = QLabel(unit)
        unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        unit_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: bold;
            color: {color};
            margin: 2px;
        """)
        layout.addWidget(unit_label)
        
        return group
        
    def create_status_group(self):
        """創建狀態指示群組"""
        group = QGroupBox("🚥 設備狀態")
        layout = QGridLayout(group)
        
        # 輸出狀態
        layout.addWidget(QLabel("輸出狀態:"), 0, 0)
        self.output_status_label = QLabel("關閉")
        self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        layout.addWidget(self.output_status_label, 0, 1)
        
        # 保護狀態
        layout.addWidget(QLabel("保護狀態:"), 1, 0)
        self.protection_status_label = QLabel("正常")
        self.protection_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        layout.addWidget(self.protection_status_label, 1, 1)
        
        return group
        
    def create_chart_group(self):
        """創建圖表顯示群組"""
        group = QGroupBox("📈 實時監控")
        layout = QVBoxLayout(group)
        
        # 創建圖表
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('#2b2b2b')
        self.plot_widget.setLabel('left', '數值', color='white', size='12pt')
        self.plot_widget.setLabel('bottom', '時間 (s)', color='white', size='12pt')
        self.plot_widget.setTitle('電源供應器監控數據', color='white', size='14pt')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        
        # 添加圖例
        self.plot_widget.addLegend()
        
        # 數據曲線
        self.voltage_curve = self.plot_widget.plot([], [], pen='r', name='電壓 (V)')
        self.current_curve = self.plot_widget.plot([], [], pen='b', name='電流 (A)')
        self.power_curve = self.plot_widget.plot([], [], pen='g', name='功率 (W)')
        
        # 數據存儲
        self.plot_time_data = []
        self.plot_voltage_data = []
        self.plot_current_data = []
        self.plot_power_data = []
        
        layout.addWidget(self.plot_widget)
        
        return group

    # ===== 專業連接管理方法 =====
    def auto_scan_and_detect(self):
        """自動掃描並智能識別Rigol DP711設備 - 專業模式"""
        self.auto_scan_btn.setEnabled(False)
        self.auto_scan_btn.setText("掃描中...")
        
        try:
            from src.port_manager import get_port_manager
            port_manager = get_port_manager()
            port_manager.scan_ports()
            
            # 清空現有選項
            self.port_input.clear()
            
            # 獲取所有可用端口
            available_devices = port_manager.get_available_ports()
            
            # 智能識別DP711設備
            dp711_ports = []
            other_ports = []
            
            for device_info in available_devices:
                # 檢查設備描述是否包含常見的DP711相關關鍵詞
                description = device_info.description.upper()
                if any(keyword in description for keyword in ['SERIAL', 'COM', 'USB', 'PROLIFIC']):
                    # 進一步檢查是否為DP711 (這裡可以擴展更精確的識別邏輯)
                    dp711_ports.append(device_info)
                else:
                    other_ports.append(device_info)
            
            # 優先添加識別到的DP711端口
            for device_info in dp711_ports:
                display_text = f"{device_info.port} - {device_info.description}"
                self.port_input.addItem(display_text, device_info.port)
            
            # 添加其他端口
            for device_info in other_ports:
                display_text = f"{device_info.port} - {device_info.description}"
                self.port_input.addItem(display_text, device_info.port)
            
            if dp711_ports:
                # 自動選擇第一個可能的DP711端口
                self.port_input.setCurrentIndex(0)
                self.log_message(f"[SUCCESS] 發現 {len(dp711_ports)} 個潛在的DP711設備")
                
                # 顯示友好的提示信息
                if hasattr(self, 'connection_status_widget') and hasattr(self.connection_status_widget, 'set_message'):
                    self.connection_status_widget.set_message(f"發現 {len(dp711_ports)} 個設備，可嘗試連接")
                    
            elif other_ports:
                self.port_input.setCurrentIndex(0)
                self.log_message(f"掃描到 {len(other_ports)} 個串口，請手動選擇")
            else:
                self.port_input.addItem("未發現可用端口")
                self.log_message("未發現任何可用的串口設備")
                
        except Exception as e:
            self.logger.error(f"自動掃描時發生錯誤: {e}")
            self.port_input.addItem("掃描失敗")
            self.log_message(f"掃描失敗: {str(e)}")
        finally:
            self.auto_scan_btn.setEnabled(True)
            self.auto_scan_btn.setText("[SCAN] 掃描")

    def show_advanced_connection_settings(self):
        """顯示進階連接設定對話框 - 專業級配置"""
        from PyQt6.QtWidgets import QDialog, QFormLayout, QSpinBox, QDialogButtonBox
        
        dialog = QDialog(self)
        dialog.setWindowTitle("進階連接設定")
        dialog.setModal(True)
        dialog.resize(350, 200)
        
        layout = QFormLayout(dialog)
        
        # 波特率設定
        baudrate_spin = QSpinBox()
        baudrate_spin.setRange(1200, 115200)
        baudrate_spin.setValue(self.baudrate_setting)
        baudrate_spin.setSingleStep(1200)
        common_rates = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
        baudrate_spin.setSpecialValueText("自定義")
        layout.addRow("波特率:", baudrate_spin)
        
        # 超時設定
        timeout_spin = QSpinBox()
        timeout_spin.setRange(1, 30)
        timeout_spin.setValue(5)
        timeout_spin.setSuffix(" 秒")
        layout.addRow("連接超時:", timeout_spin)
        
        # 重試次數
        retry_spin = QSpinBox()
        retry_spin.setRange(1, 10)
        retry_spin.setValue(3)
        retry_spin.setSuffix(" 次")
        layout.addRow("重試次數:", retry_spin)
        
        # 按鈕
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        # 樣式設定
        dialog.setStyleSheet("""
            QDialog {
                background-color: #f8f9fa;
            }
            QLabel {
                font-weight: bold;
                color: #2c3e50;
            }
            QSpinBox {
                padding: 5px;
                border: 1px solid #bdc3c7;
                border-radius: 3px;
                background-color: white;
            }
        """)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 保存設定
            self.baudrate_setting = baudrate_spin.value()
            self.connection_timeout = timeout_spin.value()
            self.connection_retries = retry_spin.value()
            
            self.log_message(f"進階設定已更新: {self.baudrate_setting} baud, {self.connection_timeout}s timeout")

    def scan_ports(self):
        """掃描可用串口"""
        try:
            from src.port_manager import get_port_manager
            port_manager = get_port_manager()
            port_manager.scan_ports()
            
            current_text = self.port_combo.currentText()
            self.port_combo.clear()
            
            available_devices = port_manager.get_available_ports()
            
            if available_devices:
                for device_info in available_devices:
                    display_text = f"{device_info.port}"
                    self.port_combo.addItem(display_text, device_info.port)
                    
                # 嘗試恢復之前的選擇
                index = self.port_combo.findText(current_text)
                if index >= 0:
                    self.port_combo.setCurrentIndex(index)
                    
                self.log_message(f"掃描到 {len(available_devices)} 個可用端口")
            else:
                self.port_combo.addItem("無可用端口")
                self.log_message("未發現可用的設備端口")
                
        except Exception as e:
            self.logger.error(f"掃描端口時發生錯誤: {e}")
            QMessageBox.warning(self, "掃描錯誤", f"無法掃描端口: {str(e)}")

    def _handle_connection_request(self):
        """處理連接請求 - 專業級非阻塞式連接"""
        # 獲取端口信息
        port_text = self.port_input.currentText()
        if not port_text or port_text in ["未發現可用端口", "掃描失敗"]:
            error_msg = "請先掃描並選擇有效的串口"
            if hasattr(self, 'connection_status_widget') and hasattr(self.connection_status_widget, 'set_connection_failed_state'):
                self.connection_status_widget.set_connection_failed_state(error_msg)
            else:
                QMessageBox.warning(self, "連接錯誤", error_msg)
            return
            
        # 智能提取端口名稱
        if " - " in port_text:
            port = port_text.split(" - ")[0].strip()
        else:
            port = port_text.strip()
            
        # 驗證端口格式
        if not port.upper().startswith('COM') and not port.startswith('/dev/'):
            error_msg = f"無效的端口格式: {port}"
            if hasattr(self, 'connection_status_widget') and hasattr(self.connection_status_widget, 'set_connection_failed_state'):
                self.connection_status_widget.set_connection_failed_state(error_msg)
            else:
                QMessageBox.warning(self, "連接錯誤", error_msg)
            return
            
        # 使用進階設定中的波特率
        baudrate = getattr(self, 'baudrate_setting', 9600)
        
        try:
            # 使用統一的連接Worker
            from src.workers import ConnectionWorker
            
            # 創建Rigol設備實例
            rigol_device = RigolDP711(port=port, baudrate=baudrate)
            
            # 創建連接參數
            connection_params = {
                'port': port,
                'baudrate': baudrate,
                'timeout': 5.0
            }
            
            # 創建並配置連接工作線程
            self.connection_worker = ConnectionWorker(rigol_device, connection_params)
            
            # 連接工作執行緒信號
            self.connection_worker.connection_started.connect(self._on_connection_started)
            self.connection_worker.progress_updated.connect(lambda p: self._on_connection_progress(f"進度: {p}%"))
            self.connection_worker.connection_success.connect(lambda name, info: self._on_connection_success(info.get('identity', '已連接')))
            self.connection_worker.connection_failed.connect(lambda err_type, msg: self._on_connection_failed(msg))
            self.connection_worker.finished.connect(self._on_connection_finished)
            
            # 保存設備實例引用
            self.pending_device = rigol_device
            
            # 啟動工作執行緒
            self.connection_worker.start()
            
        except Exception as e:
            error_msg = f"連接初始化失敗: {str(e)}"
            if hasattr(self, 'connection_status_widget'):
                self.connection_status_widget.set_connection_failed_state(error_msg)
            else:
                QMessageBox.warning(self, "連接錯誤", error_msg)

    def _on_connection_started(self):
        """連接開始時的回調 - 專業級狀態管理"""
        port = self.port_input.currentText().split(" - ")[0] if " - " in self.port_input.currentText() else self.port_input.currentText()
        self.log_message(f"開始建立連接到 {port}...")
        
        # 禁用掃描按鈕，防止干擾
        self.auto_scan_btn.setEnabled(False)
        
        if hasattr(self, 'connection_status_widget') and hasattr(self.connection_status_widget, 'set_connecting_state'):
            self.connection_status_widget.set_connecting_state()

    def _on_connection_progress(self, message: str):
        """連接進度更新的回調 - 增強反饋"""
        self.log_message(f"連接進度: {message}")
        # 可以在這裡添加進度條更新邏輯

    def _on_connection_success(self, identity: str):
        """連接成功的回調 - 專業級成功處理"""
        if hasattr(self, 'pending_device'):
            self.rigol = self.pending_device
            port = self.port_input.currentText().split(" - ")[0] if " - " in self.port_input.currentText() else self.port_input.currentText()
            
            # 保存成功的連接信息
            self.connected_devices[port] = self.rigol
            self.active_device_port = port
            
            # 更新UI狀態
            self.enable_controls(True)
            
            # 格式化設備識別信息
            if identity and identity != "已連接":
                display_identity = identity.replace("RIGOL TECHNOLOGIES,", "").replace("DP711,", "DP711 ").strip()
                success_msg = f"[SUCCESS] 成功連接到 {display_identity}"
                status_msg = f"已連接 - {display_identity}"
            else:
                success_msg = f"[SUCCESS] 成功連接到 {port}"
                status_msg = f"已連接 - {port}"
            
            self.log_message(success_msg)
            
            # 更新連接狀態顯示
            if hasattr(self, 'connection_status_widget') and hasattr(self.connection_status_widget, 'set_connected_state'):
                self.connection_status_widget.set_connected_state(status_msg)
            
            # 重新啟用掃描按鈕
            self.auto_scan_btn.setEnabled(True)
            
            # 發送連接狀態信號
            self.connection_changed.emit(True, identity)

    def _on_connection_failed(self, error_message: str):
        """連接失敗的回調 - 專業級錯誤處理"""
        port = self.port_input.currentText().split(" - ")[0] if " - " in self.port_input.currentText() else self.port_input.currentText()
        
        # 智能錯誤信息處理
        user_friendly_message = self._format_connection_error(error_message, port)
        
        self.log_message(f"✗ 連接失敗: {user_friendly_message}")
        
        # 顯示用戶友好的錯誤信息
        if hasattr(self, 'connection_status_widget') and hasattr(self.connection_status_widget, 'set_connection_failed_state'):
            self.connection_status_widget.set_connection_failed_state(user_friendly_message)
        else:
            QMessageBox.warning(self, "連接失敗", user_friendly_message)
        
        # 重新啟用掃描按鈕，允許重新掃描
        self.auto_scan_btn.setEnabled(True)
        
        # 提供解決建議
        self._show_connection_troubleshooting(error_message, port)

    def _format_connection_error(self, error_message: str, port: str) -> str:
        """將技術錯誤信息轉換為用戶友好的信息"""
        error_lower = error_message.lower()
        
        if "timeout" in error_lower or "tmo" in error_lower:
            return f"連接超時 - 請檢查 {port} 是否有設備連接"
        elif "access" in error_lower or "permission" in error_lower:
            return f"無法訪問 {port} - 端口可能被其他程式占用"
        elif "not found" in error_lower or "no such" in error_lower:
            return f"端口 {port} 不存在 - 請重新掃描設備"
        elif "resource" in error_lower:
            return f"無法打開 {port} - 設備可能未準備好"
        else:
            return f"連接到 {port} 失敗: {error_message}"

    def _show_connection_troubleshooting(self, error_message: str, port: str):
        """顯示連接問題排除建議"""
        # 只在嚴重錯誤時顯示詳細建議
        if "timeout" in error_message.lower():
            # 可以在這裡添加自動重試邏輯或顯示詳細的故障排除指南
            pass

    def _on_connection_finished(self):
        """連接過程結束的回調"""
        # 清理工作線程引用
        if self.connection_worker:
            self.connection_worker.deleteLater()
            self.connection_worker = None

    def _handle_disconnection_request(self):
        """處理斷開請求"""
        try:
            # 停止測量
            if self.is_measuring:
                self.stop_measurement()
            
            # 關閉輸出
            if self.rigol and self.rigol.is_connected():
                self.rigol.output_off()
                self.rigol.disconnect()
            
            # 重置狀態
            self.rigol = None
            self.enable_controls(False)
            self.log_message("設備已斷開連接")
            
            if hasattr(self, 'connection_status_widget'):
                self.connection_status_widget.set_disconnected_state()
            
            # 發送連接狀態信號
            self.connection_changed.emit(False, "")
            
        except Exception as e:
            self.logger.error(f"斷開連接時發生錯誤: {e}")

    def _handle_connection_cancel(self):
        """處理連接取消"""
        if self.connection_worker:
            self.connection_worker.quit()
            self.connection_worker.wait()
            self.connection_worker = None
        self.log_message("連接已取消")

    # ===== 控制方法 =====
    def enable_controls(self, enabled: bool):
        """啟用/禁用控制項"""
        self.output_btn.setEnabled(enabled)
        self.apply_settings_btn.setEnabled(enabled)
        self.start_measurement_btn.setEnabled(enabled)
        self.refresh_memory_btn.setEnabled(enabled)
        self.save_memory_btn.setEnabled(enabled)
        self.load_memory_btn.setEnabled(enabled)

    def apply_settings(self):
        """應用電源設定"""
        if not self.rigol:
            return
        
        try:
            voltage = self.voltage_input.get_base_value()
            current = self.current_input.get_base_value()
            
            self.rigol.set_voltage(voltage)
            self.rigol.set_current(current)
            
            self.log_message(f"已應用設定: {voltage:.3f}V, {current:.3f}A")
            
        except Exception as e:
            self.logger.error(f"應用設定時發生錯誤: {e}")
            QMessageBox.critical(self, "設定錯誤", f"應用設定失敗: {str(e)}")

    def toggle_output(self):
        """切換輸出狀態"""
        if not self.rigol:
            return
            
        try:
            if self.rigol.is_output_on():
                self.rigol.output_off()
                self.output_btn.setText("開啟輸出")
                self.output_status_label.setText("關閉")
                self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.log_message("輸出已關閉")
            else:
                self.rigol.output_on()
                self.output_btn.setText("關閉輸出")
                self.output_status_label.setText("開啟")
                self.output_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                self.log_message("輸出已開啟")
                
        except Exception as e:
            self.logger.error(f"切換輸出時發生錯誤: {e}")
            QMessageBox.critical(self, "輸出控制錯誤", f"無法切換輸出狀態: {str(e)}")

    def toggle_measurement(self):
        """切換測量狀態"""
        if self.is_measuring:
            self.stop_measurement()
        else:
            self.start_measurement()

    def start_measurement(self):
        """開始連續測量"""
        if not self.rigol:
            return
            
        try:
            # 創建並啟動測量工作執行緒
            self.continuous_worker = ContinuousMeasurementWorker(self.rigol)
            self.continuous_worker.data_ready.connect(self.on_measurement_data)
            self.continuous_worker.error_occurred.connect(self.on_measurement_error)
            self.continuous_worker.start_measurement()
            
            self.is_measuring = True
            self.start_measurement_btn.setText("[PAUSE] 暫停測量")
            self.stop_measurement_btn.setEnabled(True)
            self.log_message("開始連續測量")
            
            # 重置圖表起始時間
            self.chart_start_time = datetime.now()
            
        except Exception as e:
            self.logger.error(f"啟動測量時發生錯誤: {e}")

    def stop_measurement(self):
        """停止測量"""
        if self.continuous_worker:
            self.continuous_worker.stop_measurement()
            self.continuous_worker = None
            
        self.is_measuring = False
        self.start_measurement_btn.setText("[START] 開始測量")
        self.stop_measurement_btn.setEnabled(False)
        self.log_message("測量已停止")

    def on_measurement_data(self, voltage, current, power):
        """處理測量數據"""
        # 更新LCD顯示
        voltage_lcd = self.voltage_display.findChild(QLCDNumber)
        if voltage_lcd:
            voltage_lcd.display(f"{voltage:.6f}")
                
        current_lcd = self.current_display.findChild(QLCDNumber)
        if current_lcd:
            current_lcd.display(f"{current:.6f}")
                
        power_lcd = self.power_display.findChild(QLCDNumber)
        if power_lcd:
            power_lcd.display(f"{power:.6f}")
        
        # 計算效率 (簡化計算，實際需要負載信息)
        efficiency = 85.0  # 預設效率值
        efficiency_lcd = self.efficiency_display.findChild(QLCDNumber)
        if efficiency_lcd:
            efficiency_lcd.display(f"{efficiency:.2f}")
        
        # 更新圖表
        self.update_chart(voltage, current, power)
        
        # 存儲數據
        timestamp = datetime.now()
        self.measurement_data.append((timestamp, voltage, current, power))
        
        # 保持數據緩存大小
        if len(self.measurement_data) > 1000:
            self.measurement_data = self.measurement_data[-1000:]

    def on_measurement_error(self, error_message):
        """處理測量錯誤"""
        self.logger.error(f"測量錯誤: {error_message}")
        self.stop_measurement()

    def update_chart(self, voltage, current, power):
        """更新圖表顯示"""
        if not hasattr(self, 'chart_start_time'):
            self.chart_start_time = datetime.now()
            
        # 計算時間軸
        current_time = datetime.now()
        elapsed_seconds = (current_time - self.chart_start_time).total_seconds()
        
        # 添加數據點
        self.plot_time_data.append(elapsed_seconds)
        self.plot_voltage_data.append(voltage)
        self.plot_current_data.append(current)
        self.plot_power_data.append(power)
        
        # 保持數據點數量
        max_points = 100
        if len(self.plot_time_data) > max_points:
            self.plot_time_data = self.plot_time_data[-max_points:]
            self.plot_voltage_data = self.plot_voltage_data[-max_points:]
            self.plot_current_data = self.plot_current_data[-max_points:]
            self.plot_power_data = self.plot_power_data[-max_points:]
        
        # 更新曲線
        self.voltage_curve.setData(self.plot_time_data, self.plot_voltage_data)
        self.current_curve.setData(self.plot_time_data, self.plot_current_data)
        self.power_curve.setData(self.plot_time_data, self.plot_power_data)

    # ===== 記憶體管理方法 =====
    def refresh_memory_catalog(self):
        """刷新記憶體目錄"""
        if not self.rigol:
            return
        self.log_message("記憶體目錄功能將在後續版本完善")

    def save_to_memory(self):
        """保存到記憶體"""
        if not self.rigol:
            return
        
        try:
            memory_index = self.memory_combo.currentIndex() + 1
            success = self.rigol.save_memory_state(memory_index)
            
            if success:
                self.log_message(f"設定已保存到記憶體 M{memory_index}")
                QMessageBox.information(self, "保存成功", 
                    f"當前設定已保存到記憶體 M{memory_index}")
            else:
                QMessageBox.warning(self, "保存失敗", "無法保存設定到記憶體")
                
        except Exception as e:
            self.logger.error(f"保存記憶體時發生錯誤: {e}")
            QMessageBox.critical(self, "保存錯誤", f"保存記憶體失敗: {str(e)}")

    def load_from_memory(self):
        """從記憶體載入"""
        if not self.rigol:
            return
            
        try:
            memory_index = self.memory_combo.currentIndex() + 1
            success = self.rigol.recall_memory_state(memory_index)
            
            if success:
                # 更新UI顯示當前設定
                try:
                    voltage = self.rigol.get_set_voltage()
                    current = self.rigol.get_set_current()
                    
                    self.voltage_input.set_base_value(voltage)
                    self.current_input.set_base_value(current)
                    
                    self.log_message(f"已從記憶體 M{memory_index} 載入設定: {voltage:.3f}V, {current:.3f}A")
                except Exception:
                    self.log_message(f"已從記憶體 M{memory_index} 載入設定")
                    
            else:
                QMessageBox.warning(self, "載入失敗", "無法載入記憶體設定")
                
        except Exception as e:
            self.logger.error(f"載入記憶體時發生錯誤: {e}")
            QMessageBox.critical(self, "載入錯誤", f"載入記憶體失敗: {str(e)}")

    # ===== 數據管理方法 =====
    def export_csv(self):
        """導出CSV數據"""
        if not self.measurement_data:
            QMessageBox.information(self, "信息", "沒有可導出的測量數據")
            return
            
        try:
            from PyQt6.QtWidgets import QFileDialog
            
            filename, _ = QFileDialog.getSaveFileName(
                self, 
                "保存測量數據", 
                f"rigol_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV文件 (*.csv)"
            )
            
            if filename:
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['時間', '電壓(V)', '電流(A)', '功率(W)'])
                    
                    for timestamp, voltage, current, power in self.measurement_data:
                        writer.writerow([
                            timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                            f"{voltage:.6f}",
                            f"{current:.6f}",
                            f"{power:.6f}"
                        ])
                
                self.log_message(f"數據已導出到: {filename}")
                QMessageBox.information(self, "導出完成", f"數據已導出到:\n{filename}")
                
        except Exception as e:
            self.logger.error(f"導出CSV時發生錯誤: {e}")
            QMessageBox.critical(self, "導出錯誤", f"導出失敗: {str(e)}")

    def clear_measurement_data(self):
        """清除測量數據"""
        self.measurement_data.clear()
        
        # 清除圖表數據
        self.plot_time_data.clear()
        self.plot_voltage_data.clear()
        self.plot_current_data.clear()
        self.plot_power_data.clear()
        
        # 更新圖表顯示
        self.voltage_curve.setData([], [])
        self.current_curve.setData([], [])
        self.power_curve.setData([], [])
        
        self.log_message("測量數據已清除")

    # ===== 輔助方法 =====
    def log_message(self, message):
        """日誌記錄"""
        self.logger.info(message)
        print(f"Rigol Widget: {message}")

    def update_runtime_display(self):
        """更新運行時間顯示"""
        # 預留給未來實現
        pass


# 別名以保持向後兼容性
RigolControlWidget = ProfessionalRigolWidget