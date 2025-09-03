#!/usr/bin/env python3
"""
Keithley 2461 統一架構 Widget
完整保留Professional功能，同時使用統一架構減少代碼重複
"""

import time
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, List
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                            QLabel, QPushButton, QLineEdit, QGroupBox,
                            QComboBox, QDoubleSpinBox, QCheckBox, QTextEdit,
                            QMessageBox, QProgressBar, QTabWidget,
                            QTableWidget, QTableWidgetItem, QHeaderView,
                            QFrame, QLCDNumber, QSizePolicy, QSplitter)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor
import pyqtgraph as pg

from widgets.base import InstrumentWidgetBase
from src.keithley_2461 import Keithley2461
from src.workers import MeasurementWorker, UnifiedWorkerBase
from src.workers.measurement_worker import (
    ContinuousMeasurementStrategy, 
    SweepMeasurementStrategy,
    MeasurementStrategy
)
from src.data import get_data_manager, MeasurementPoint
from widgets.unit_input_widget import UnitInputWidget, UnitDisplayWidget
from widgets.connection_status_widget import ConnectionStatusWidget
from src.unified_logger import get_logger


class KeithleyUnifiedWidget(InstrumentWidgetBase):
    """Keithley 2461 統一架構Widget
    
    完整功能特色:
    - IV特性曲線掃描測量
    - 連續測量模式
    - 專業數據分析和顯示
    - 工程單位自動轉換
    - 實時數據圖表
    - 數據導出(CSV/JSON)
    """
    
    # 專業信號
    sweep_started = pyqtSignal()
    sweep_completed = pyqtSignal(list)  # sweep data points
    sweep_progress = pyqtSignal(int)    # percentage
    
    def __init__(self, instrument: Optional[Keithley2461] = None, parent=None):
        """初始化統一Keithley Widget"""
        # 如果沒有提供儀器實例，創建新的
        if instrument is None:
            instrument = Keithley2461(ip_address="192.168.0.100")
            
        # Keithley專屬屬性 - 必須在super().__init__之前初始化
        self.source_function = "VOLT"
        self.measurement_mode = "continuous"  # continuous, sweep
        self.sweep_data = []
        self.measurement_worker = None
        
        # 專業UI組件 - 必須在super().__init__之前初始化
        self.lcd_displays = {}
        self.sweep_controls = {}
        self.professional_plots = {}
        
        # 初始化基類
        super().__init__("keithley_2461", instrument, parent)
        
        # 設定視窗標題
        self.setWindowTitle("Keithley 2461 Professional Control - 統一架構")
        self.setMinimumSize(1400, 900)
        
    def _setup_instrument_ui(self):
        """設置Keithley專屬UI組件"""
        # 清除基礎控制面板，替換為專業版面
        self._setup_professional_ui()
        
    def _setup_professional_ui(self):
        """設置專業級UI布局"""
        # 清除分割器中的現有widget
        while self.content_splitter.count() > 0:
            widget = self.content_splitter.widget(0)
            widget.setParent(None)
        
        # 左側專業控制面板
        left_panel = self._create_professional_control_panel()
        
        # 右側專業顯示面板
        right_panel = self._create_professional_display_panel()
        
        # 添加到分割器
        self.content_splitter.addWidget(left_panel)
        self.content_splitter.addWidget(right_panel)
        self.content_splitter.setSizes([500, 900])
        
    def _create_professional_control_panel(self) -> QWidget:
        """創建專業控制面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # 連接控制
        connection_widget = self._create_connection_control()
        layout.addWidget(connection_widget)
        
        # 測量模式選擇
        mode_widget = self._create_measurement_mode_control()
        layout.addWidget(mode_widget)
        
        # 源設置
        source_widget = self._create_source_control()
        layout.addWidget(source_widget)
        
        # 掃描設置 (IV曲線)
        self.sweep_widget = self._create_sweep_control()
        layout.addWidget(self.sweep_widget)
        
        # 測量控制按鈕
        control_widget = self._create_measurement_control()
        layout.addWidget(control_widget)
        
        layout.addStretch()
        return panel
        
    def _create_connection_control(self) -> QGroupBox:
        """創建連接控制組"""
        group = QGroupBox("連接設置")
        layout = QGridLayout(group)
        
        # IP地址輸入
        layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit("192.168.0.100")
        layout.addWidget(self.ip_input, 0, 1)
        
        # 連接狀態顯示
        self.connection_status_widget = ConnectionStatusWidget()
        layout.addWidget(self.connection_status_widget, 0, 2)
        
        # 連接按鈕
        self.connect_btn = QPushButton("連接")
        self.connect_btn.clicked.connect(self._handle_connection_request)
        layout.addWidget(self.connect_btn, 1, 0)
        
        self.disconnect_btn = QPushButton("斷開")
        self.disconnect_btn.clicked.connect(self.disconnect_instrument)
        self.disconnect_btn.setEnabled(False)
        layout.addWidget(self.disconnect_btn, 1, 1)
        
        # 識別信息
        self.identity_label = QLabel("未連接")
        self.identity_label.setWordWrap(True)
        layout.addWidget(self.identity_label, 2, 0, 1, 3)
        
        return group
        
    def _create_measurement_mode_control(self) -> QGroupBox:
        """創建測量模式控制組"""
        group = QGroupBox("測量模式")
        layout = QHBoxLayout(group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["連續測量", "IV掃描", "脈衝測量", "穩定性測試"])
        self.mode_combo.currentTextChanged.connect(self._on_measurement_mode_changed)
        layout.addWidget(self.mode_combo)
        
        # 模式說明
        self.mode_description = QLabel("連續測量並顯示實時數據")
        self.mode_description.setWordWrap(True)
        layout.addWidget(self.mode_description)
        
        return group
        
    def _create_source_control(self) -> QGroupBox:
        """創建源設置控制組"""
        group = QGroupBox("源設置")
        layout = QGridLayout(group)
        
        # 源功能選擇
        layout.addWidget(QLabel("源功能:"), 0, 0)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["電壓源", "電流源"])
        self.source_combo.currentTextChanged.connect(self._on_source_function_changed)
        layout.addWidget(self.source_combo, 0, 1, 1, 2)
        
        # 電壓設置
        layout.addWidget(QLabel("電壓(V):"), 1, 0)
        self.voltage_input = UnitInputWidget("V", default_prefix="", precision=6)
        layout.addWidget(self.voltage_input, 1, 1, 1, 2)
        
        # 電流限制
        layout.addWidget(QLabel("電流限制(A):"), 2, 0)
        self.current_limit_input = UnitInputWidget("A", default_prefix="m", precision=6)
        self.current_limit_input.set_base_value(0.1)
        layout.addWidget(self.current_limit_input, 2, 1, 1, 2)
        
        # 應用按鈕
        self.apply_btn = QPushButton("應用設置")
        self.apply_btn.clicked.connect(self._apply_source_settings)
        layout.addWidget(self.apply_btn, 3, 0)
        
        # 輸出開關
        self.output_btn = QPushButton("輸出 OFF")
        self.output_btn.setCheckable(True)
        self.output_btn.clicked.connect(self._toggle_output)
        self.output_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #27ae60;
            }
        """)
        layout.addWidget(self.output_btn, 3, 1, 1, 2)
        
        return group
        
    def _create_sweep_control(self) -> QGroupBox:
        """創建掃描設置控制組"""
        group = QGroupBox("IV掃描設置")
        layout = QGridLayout(group)
        
        # 起始電壓
        layout.addWidget(QLabel("起始電壓(V):"), 0, 0)
        self.sweep_start = UnitInputWidget("V", default_prefix="", precision=3)
        self.sweep_start.set_base_value(0)
        layout.addWidget(self.sweep_start, 0, 1)
        
        # 結束電壓
        layout.addWidget(QLabel("結束電壓(V):"), 1, 0)
        self.sweep_stop = UnitInputWidget("V", default_prefix="", precision=3)
        self.sweep_stop.set_base_value(5)
        layout.addWidget(self.sweep_stop, 1, 1)
        
        # 步進電壓
        layout.addWidget(QLabel("步進(V):"), 2, 0)
        self.sweep_step = UnitInputWidget("V", default_prefix="m", precision=3)
        self.sweep_step.set_base_value(0.1)
        layout.addWidget(self.sweep_step, 2, 1)
        
        # 延遲時間
        layout.addWidget(QLabel("延遲(ms):"), 3, 0)
        self.sweep_delay = QDoubleSpinBox()
        self.sweep_delay.setRange(0, 10000)
        self.sweep_delay.setValue(100)
        self.sweep_delay.setSuffix(" ms")
        layout.addWidget(self.sweep_delay, 3, 1)
        
        # 電流限制
        layout.addWidget(QLabel("電流限制(A):"), 4, 0)
        self.sweep_current_limit = UnitInputWidget("A", default_prefix="m", precision=6)
        self.sweep_current_limit.set_base_value(0.01)
        layout.addWidget(self.sweep_current_limit, 4, 1)
        
        # 掃描進度條
        self.sweep_progress_bar = QProgressBar()
        self.sweep_progress_bar.setTextVisible(True)
        layout.addWidget(self.sweep_progress_bar, 5, 0, 1, 2)
        
        # 初始隱藏掃描設置
        group.setVisible(False)
        
        return group
        
    def _create_measurement_control(self) -> QGroupBox:
        """創建測量控制組"""
        group = QGroupBox("測量控制")
        layout = QGridLayout(group)
        
        # 開始測量按鈕
        self.start_btn = QPushButton("開始測量")
        self.start_btn.clicked.connect(self._start_measurement)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(self.start_btn, 0, 0)
        
        # 停止測量按鈕
        self.stop_btn = QPushButton("停止測量")
        self.stop_btn.clicked.connect(self.stop_measurement)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        layout.addWidget(self.stop_btn, 0, 1)
        
        # 單次測量按鈕
        self.single_btn = QPushButton("單次測量")
        self.single_btn.clicked.connect(self._single_measurement)
        layout.addWidget(self.single_btn, 1, 0)
        
        # 清除數據按鈕
        self.clear_btn = QPushButton("清除數據")
        self.clear_btn.clicked.connect(self._clear_data)
        layout.addWidget(self.clear_btn, 1, 1)
        
        # 測量間隔設置
        layout.addWidget(QLabel("測量間隔(ms):"), 2, 0)
        self.interval_spin = QDoubleSpinBox()
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(1000)
        self.interval_spin.setSuffix(" ms")
        layout.addWidget(self.interval_spin, 2, 1)
        
        return group
        
    def _create_professional_display_panel(self) -> QWidget:
        """創建專業顯示面板"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 使用Tab組織不同的顯示內容
        self.display_tabs = QTabWidget()
        
        # 實時顯示標籤頁
        real_time_tab = self._create_realtime_display_tab()
        self.display_tabs.addTab(real_time_tab, "實時顯示")
        
        # IV曲線標籤頁
        iv_curve_tab = self._create_iv_curve_tab()
        self.display_tabs.addTab(iv_curve_tab, "IV特性曲線")
        
        # 數據分析標籤頁
        analysis_tab = self._create_data_analysis_tab()
        self.display_tabs.addTab(analysis_tab, "數據分析")
        
        # 數據記錄標籤頁
        log_tab = self._create_data_log_tab()
        self.display_tabs.addTab(log_tab, "數據記錄")
        
        layout.addWidget(self.display_tabs)
        
        return panel
        
    def _create_realtime_display_tab(self) -> QWidget:
        """創建實時顯示標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # LCD數字顯示
        lcd_group = QGroupBox("實時測量值")
        lcd_layout = QGridLayout(lcd_group)
        
        # 電壓顯示
        voltage_frame = self._create_lcd_display("電壓", "V", "voltage")
        lcd_layout.addWidget(voltage_frame, 0, 0)
        
        # 電流顯示
        current_frame = self._create_lcd_display("電流", "A", "current")
        lcd_layout.addWidget(current_frame, 0, 1)
        
        # 電阻顯示
        resistance_frame = self._create_lcd_display("電阻", "Ω", "resistance")
        lcd_layout.addWidget(resistance_frame, 1, 0)
        
        # 功率顯示
        power_frame = self._create_lcd_display("功率", "W", "power")
        lcd_layout.addWidget(power_frame, 1, 1)
        
        layout.addWidget(lcd_group)
        
        # 實時趨勢圖
        plot_group = QGroupBox("實時趨勢")
        plot_layout = QVBoxLayout(plot_group)
        
        # 創建實時圖表
        self.realtime_plot = pg.PlotWidget(title="實時測量數據")
        self.realtime_plot.setLabel('left', '數值')
        self.realtime_plot.setLabel('bottom', '時間 (s)')
        self.realtime_plot.addLegend()
        self.realtime_plot.showGrid(x=True, y=True)
        
        # 初始化曲線
        self.voltage_curve = self.realtime_plot.plot([], [], pen='r', name='電壓(V)')
        self.current_curve = self.realtime_plot.plot([], [], pen='b', name='電流(A)')
        
        plot_layout.addWidget(self.realtime_plot)
        layout.addWidget(plot_group)
        
        # 初始化數據緩衝
        self.time_data = []
        self.voltage_data = []
        self.current_data = []
        self.start_time = None
        
        return tab
        
    def _create_lcd_display(self, label: str, unit: str, key: str) -> QFrame:
        """創建LCD數字顯示框架"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        layout = QVBoxLayout(frame)
        
        # 標籤
        title_label = QLabel(f"{label} ({unit})")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(title_label)
        
        # LCD顯示
        lcd = QLCDNumber()
        lcd.setDigitCount(8)
        lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
        lcd.setMinimumHeight(60)
        lcd.display(0.0)
        
        # 根據主題設置LCD樣式
        if self.current_theme == "dark":
            lcd.setStyleSheet("""
                QLCDNumber {
                    background-color: #1e1e1e;
                    color: #00ff00;
                    border: 2px solid #444;
                    border-radius: 5px;
                }
            """)
        else:
            lcd.setStyleSheet("""
                QLCDNumber {
                    background-color: #f0f0f0;
                    color: #0080ff;
                    border: 2px solid #ccc;
                    border-radius: 5px;
                }
            """)
            
        layout.addWidget(lcd)
        
        # 工程單位顯示
        value_label = UnitDisplayWidget(unit)
        layout.addWidget(value_label)
        
        # 保存引用
        self.lcd_displays[key] = {
            'lcd': lcd,
            'label': value_label,
            'unit': unit
        }
        
        return frame
        
    def _create_iv_curve_tab(self) -> QWidget:
        """創建IV曲線標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # IV曲線圖
        self.iv_plot = pg.PlotWidget(title="IV特性曲線")
        self.iv_plot.setLabel('left', '電流 (A)')
        self.iv_plot.setLabel('bottom', '電壓 (V)')
        self.iv_plot.showGrid(x=True, y=True)
        
        # 初始化IV曲線
        self.iv_curve = self.iv_plot.plot([], [], 
                                         pen=None, 
                                         symbol='o',
                                         symbolBrush='b',
                                         symbolSize=8,
                                         name='IV測量點')
        
        layout.addWidget(self.iv_plot)
        
        # 掃描信息顯示
        info_group = QGroupBox("掃描信息")
        info_layout = QGridLayout(info_group)
        
        self.sweep_info_labels = {}
        info_items = [
            ("掃描範圍:", "range"),
            ("掃描點數:", "points"),
            ("開始時間:", "start_time"),
            ("結束時間:", "end_time"),
            ("掃描狀態:", "status")
        ]
        
        for i, (label_text, key) in enumerate(info_items):
            info_layout.addWidget(QLabel(label_text), i, 0)
            label = QLabel("--")
            info_layout.addWidget(label, i, 1)
            self.sweep_info_labels[key] = label
            
        layout.addWidget(info_group)
        
        return tab
        
    def _create_data_analysis_tab(self) -> QWidget:
        """創建數據分析標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 統計信息
        stats_group = QGroupBox("統計分析")
        stats_layout = QGridLayout(stats_group)
        
        self.stats_labels = {}
        stats_items = [
            ("平均電壓:", "avg_voltage"),
            ("平均電流:", "avg_current"),
            ("平均電阻:", "avg_resistance"),
            ("平均功率:", "avg_power"),
            ("最大電壓:", "max_voltage"),
            ("最大電流:", "max_current"),
            ("最小電壓:", "min_voltage"),
            ("最小電流:", "min_current"),
            ("數據點數:", "data_points"),
            ("測量時長:", "duration")
        ]
        
        for i, (label_text, key) in enumerate(stats_items):
            row = i // 2
            col = (i % 2) * 2
            stats_layout.addWidget(QLabel(label_text), row, col)
            label = QLabel("--")
            stats_layout.addWidget(label, row, col + 1)
            self.stats_labels[key] = label
            
        layout.addWidget(stats_group)
        
        # 數據表格
        table_group = QGroupBox("測量數據表")
        table_layout = QVBoxLayout(table_group)
        
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(5)
        self.data_table.setHorizontalHeaderLabels(["時間", "電壓(V)", "電流(A)", "電阻(Ω)", "功率(W)"])
        self.data_table.horizontalHeader().setStretchLastSection(True)
        
        table_layout.addWidget(self.data_table)
        layout.addWidget(table_group)
        
        # 導出按鈕
        export_layout = QHBoxLayout()
        
        export_csv_btn = QPushButton("導出CSV")
        export_csv_btn.clicked.connect(lambda: self._export_data("csv"))
        export_layout.addWidget(export_csv_btn)
        
        export_json_btn = QPushButton("導出JSON")
        export_json_btn.clicked.connect(lambda: self._export_data("json"))
        export_layout.addWidget(export_json_btn)
        
        export_layout.addStretch()
        layout.addLayout(export_layout)
        
        return tab
        
    def _create_data_log_tab(self) -> QWidget:
        """創建數據記錄標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 日誌顯示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # QTextEdit 沒有 setMaximumBlockCount，使用 document() 設置
        self.log_text.document().setMaximumBlockCount(1000)  # 限制行數
        
        layout.addWidget(self.log_text)
        
        # 日誌控制
        control_layout = QHBoxLayout()
        
        clear_log_btn = QPushButton("清除日誌")
        clear_log_btn.clicked.connect(self.log_text.clear)
        control_layout.addWidget(clear_log_btn)
        
        save_log_btn = QPushButton("保存日誌")
        save_log_btn.clicked.connect(self._save_log)
        control_layout.addWidget(save_log_btn)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        return tab
        
    def get_connection_params(self) -> Dict[str, Any]:
        """獲取連接參數"""
        return {
            'ip_address': self.ip_input.text(),
            'port': 5025,
            'timeout': 5000,
            'method': 'visa'
        }
        
    def create_instrument_controls(self) -> QWidget:
        """創建儀器特定控制組件 - 由基類要求實現"""
        # 這個方法已經通過_setup_professional_ui實現
        return QWidget()
        
    def _create_measurement_worker(self) -> Optional[UnifiedWorkerBase]:
        """創建測量Worker - 使用統一Worker系統"""
        if not self.is_connected:
            return None
            
        # 根據測量模式創建對應的Worker
        if self.measurement_mode == "continuous":
            # 連續測量策略
            strategy = ContinuousMeasurementStrategy(
                self.instrument,
                interval_ms=int(self.interval_spin.value())
            )
        elif self.measurement_mode == "sweep":
            # IV掃描策略
            sweep_params = {
                'start': self.sweep_start.get_base_value(),
                'stop': self.sweep_stop.get_base_value(),
                'step': self.sweep_step.get_base_value(),
                'delay_ms': int(self.sweep_delay.value()),
                'current_limit': self.sweep_current_limit.get_base_value()
            }
            strategy = KeithleySweepStrategy(
                self.instrument,
                sweep_params
            )
        else:
            return None
            
        # 創建統一測量Worker
        worker = MeasurementWorker(strategy, "Keithley2461", self.instrument)
        
        # 連接專業信號
        if self.measurement_mode == "sweep":
            worker.progress_updated.connect(self.sweep_progress.emit)
            worker.operation_completed.connect(self._on_sweep_completed)
            
        return worker
        
    # 事件處理方法
    def _handle_connection_request(self):
        """處理連接請求"""
        # 更新儀器IP
        self.instrument.ip_address = self.ip_input.text()
        
        # 更新UI狀態
        self.connect_btn.setEnabled(False)
        self.connection_status_widget.set_connecting_state()
        
        # 調用基類的連接方法
        self.connect_instrument()
        
    def _on_connection_success(self, instrument_name: str, connection_info: Dict[str, Any]):
        """連接成功處理"""
        super()._on_connection_success(instrument_name, connection_info)
        
        # 更新UI
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        self.connection_status_widget.set_connected_state(connection_info.get('identity', '已連接'))
        
        # 顯示設備信息
        identity = connection_info.get('identity', '未知設備')
        self.identity_label.setText(f"設備: {identity}")
        
        # 啟用控制按鈕
        self.apply_btn.setEnabled(True)
        self.output_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        self.single_btn.setEnabled(True)
        
        self.add_log(f"✅ 已連接到 {identity}")
        
    def _on_connection_failed(self, error_type: str, error_message: str):
        """連接失敗處理"""
        super()._on_connection_failed(error_type, error_message)
        
        # 更新UI
        self.connect_btn.setEnabled(True)
        self.connection_status_widget.set_disconnected_state()
        
        self.add_log(f"❌ 連接失敗: {error_message}")
        
    def _on_measurement_mode_changed(self, mode_text: str):
        """測量模式變化處理"""
        mode_map = {
            "連續測量": "continuous",
            "IV掃描": "sweep",
            "脈衝測量": "pulse",
            "穩定性測試": "stability"
        }
        
        self.measurement_mode = mode_map.get(mode_text, "continuous")
        
        # 顯示/隱藏相應的控制組
        self.sweep_widget.setVisible(self.measurement_mode == "sweep")
        
        # 更新模式說明
        descriptions = {
            "continuous": "連續測量並顯示實時數據",
            "sweep": "執行電壓掃描並繪製IV特性曲線",
            "pulse": "執行脈衝測量序列",
            "stability": "長時間穩定性測試"
        }
        
        self.mode_description.setText(descriptions.get(self.measurement_mode, ""))
        
        # 切換到相應的顯示標籤頁
        if self.measurement_mode == "sweep":
            self.display_tabs.setCurrentIndex(1)  # IV曲線頁
        else:
            self.display_tabs.setCurrentIndex(0)  # 實時顯示頁
            
    def _on_source_function_changed(self, function_text: str):
        """源功能變化處理"""
        self.source_function = "VOLT" if "電壓" in function_text else "CURR"
        
        # 更新UI標籤
        if self.source_function == "VOLT":
            self.voltage_input.setEnabled(True)
            self.current_limit_input.setEnabled(True)
        else:
            # 電流源模式 - 交換輸入框
            pass  # TODO: 實現電流源UI切換
            
    def _apply_source_settings(self):
        """應用源設置"""
        if not self.is_connected:
            return
            
        try:
            voltage = self.voltage_input.get_base_value()
            current_limit = self.current_limit_input.get_base_value()
            
            # 設置源功能
            self.instrument.set_source_function(self.source_function)
            
            # 設置電壓和電流限制
            if self.source_function == "VOLT":
                self.instrument.set_voltage(str(voltage), current_limit=str(current_limit))
            
            self.add_log(f"✅ 已設置: 電壓={voltage}V, 電流限制={current_limit}A")
            
        except Exception as e:
            self.error_occurred.emit("source_setting", str(e))
            
    def _toggle_output(self):
        """切換輸出狀態"""
        if not self.is_connected:
            return
            
        try:
            if self.output_btn.isChecked():
                self.instrument.output_on()
                self.output_btn.setText("輸出 ON")
                self.add_log("✅ 輸出已開啟")
            else:
                self.instrument.output_off()
                self.output_btn.setText("輸出 OFF")
                self.add_log("⚠️ 輸出已關閉")
                
        except Exception as e:
            self.error_occurred.emit("output_control", str(e))
            self.output_btn.setChecked(not self.output_btn.isChecked())
            
    def _start_measurement(self):
        """開始測量"""
        if not self.is_connected or self.measurement_active:
            return
            
        # 重置數據
        if self.measurement_mode == "sweep":
            self.sweep_data = []
            self.sweep_progress_bar.setValue(0)
            self.sweep_info_labels["status"].setText("掃描中...")
            self.sweep_info_labels["start_time"].setText(datetime.now().strftime("%H:%M:%S"))
        else:
            self.start_time = time.time()
            self.time_data = []
            self.voltage_data = []
            self.current_data = []
            
        # 更新UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        
        # 開始測量
        self.start_measurement()
        
        self.add_log(f"🚀 開始{self.mode_combo.currentText()}")
        
    def _single_measurement(self):
        """執行單次測量"""
        if not self.is_connected:
            return
            
        try:
            # 執行測量
            v, i, r, p = self.instrument.measure_all()
            
            # 更新顯示
            self._update_lcd_displays(v, i, r, p)
            
            # 添加到數據表
            self._add_to_data_table(v, i, r, p)
            
            self.add_log(f"📊 單次測量: V={v:.6f}V, I={i:.6f}A, R={r:.3f}Ω, P={p:.6f}W")
            
        except Exception as e:
            self.error_occurred.emit("measurement", str(e))
            
    def _clear_data(self):
        """清除測量數據"""
        # 清除圖表數據
        self.time_data = []
        self.voltage_data = []
        self.current_data = []
        self.sweep_data = []
        
        # 清除圖表顯示
        self.voltage_curve.setData([], [])
        self.current_curve.setData([], [])
        self.iv_curve.setData([], [])
        
        # 清除數據表
        self.data_table.setRowCount(0)
        
        # 清除統計信息
        for label in self.stats_labels.values():
            label.setText("--")
            
        self.add_log("🗑️ 已清除所有測量數據")
        
    def _on_measurement_ready(self, data: Dict[str, Any]):
        """測量數據準備就緒"""
        super()._on_measurement_ready(data)
        
        # 提取數據
        v = data.get('voltage', 0)
        i = data.get('current', 0)
        r = data.get('resistance', 0)
        p = data.get('power', 0)
        
        # 更新LCD顯示
        self._update_lcd_displays(v, i, r, p)
        
        # 根據模式更新圖表
        if self.measurement_mode == "continuous":
            self._update_realtime_plot(v, i)
        elif self.measurement_mode == "sweep":
            point_num = data.get('metadata', {}).get('point_number', 0)
            self._update_sweep_data(v, i, r, p, point_num)
            
        # 添加到數據表
        self._add_to_data_table(v, i, r, p)
        
        # 更新統計信息
        self._update_statistics()
        
    def _update_lcd_displays(self, voltage, current, resistance, power):
        """更新LCD顯示"""
        displays = {
            'voltage': voltage,
            'current': current,
            'resistance': resistance,
            'power': power
        }
        
        for key, value in displays.items():
            if key in self.lcd_displays:
                lcd_info = self.lcd_displays[key]
                lcd_info['lcd'].display(value)
                lcd_info['label'].set_value(value)
                
    def _update_realtime_plot(self, voltage, current):
        """更新實時圖表"""
        if self.start_time is None:
            self.start_time = time.time()
            
        # 計算時間
        elapsed = time.time() - self.start_time
        
        # 添加數據
        self.time_data.append(elapsed)
        self.voltage_data.append(voltage)
        self.current_data.append(current)
        
        # 限制數據點數量
        max_points = 1000
        if len(self.time_data) > max_points:
            self.time_data = self.time_data[-max_points:]
            self.voltage_data = self.voltage_data[-max_points:]
            self.current_data = self.current_data[-max_points:]
            
        # 更新曲線
        self.voltage_curve.setData(self.time_data, self.voltage_data)
        self.current_curve.setData(self.time_data, self.current_data)
        
    def _update_sweep_data(self, voltage, current, resistance, power, point_num):
        """更新掃描數據"""
        # 添加數據點
        self.sweep_data.append({
            'voltage': voltage,
            'current': current,
            'resistance': resistance,
            'power': power,
            'point': point_num
        })
        
        # 更新IV曲線
        v_data = [p['voltage'] for p in self.sweep_data]
        i_data = [p['current'] for p in self.sweep_data]
        self.iv_curve.setData(v_data, i_data)
        
        # 更新掃描信息
        self.sweep_info_labels["points"].setText(str(len(self.sweep_data)))
        
    def _on_sweep_completed(self, completion_info: Dict[str, Any]):
        """掃描完成處理"""
        # 更新UI
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        
        # 更新掃描信息
        self.sweep_info_labels["status"].setText("完成")
        self.sweep_info_labels["end_time"].setText(datetime.now().strftime("%H:%M:%S"))
        
        # 計算掃描範圍
        if self.sweep_data:
            v_min = min(p['voltage'] for p in self.sweep_data)
            v_max = max(p['voltage'] for p in self.sweep_data)
            self.sweep_info_labels["range"].setText(f"{v_min:.3f}V ~ {v_max:.3f}V")
            
        self.sweep_completed.emit(self.sweep_data)
        self.add_log(f"✅ IV掃描完成，共{len(self.sweep_data)}個數據點")
        
    def _add_to_data_table(self, voltage, current, resistance, power):
        """添加數據到表格"""
        row = self.data_table.rowCount()
        self.data_table.insertRow(row)
        
        # 添加數據
        items = [
            datetime.now().strftime("%H:%M:%S.%f")[:-3],
            f"{voltage:.6f}",
            f"{current:.9f}",
            f"{resistance:.3f}",
            f"{power:.6f}"
        ]
        
        for col, value in enumerate(items):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.data_table.setItem(row, col, item)
            
        # 自動滾動到最新行
        self.data_table.scrollToBottom()
        
        # 限制表格行數
        max_rows = 1000
        if self.data_table.rowCount() > max_rows:
            self.data_table.removeRow(0)
            
    def _update_statistics(self):
        """更新統計信息"""
        # 從數據管理器獲取數據
        recent_data = self.data_manager.get_real_time_data(self.instrument_type, 10000)
        
        if not recent_data:
            return
            
        # 提取數值
        voltages = [d.voltage for d in recent_data if d.voltage is not None]
        currents = [d.current for d in recent_data if d.current is not None]
        resistances = [d.resistance for d in recent_data if d.resistance is not None]
        powers = [d.power for d in recent_data if d.power is not None]
        
        # 計算統計值
        if voltages:
            self.stats_labels["avg_voltage"].setText(f"{np.mean(voltages):.6f} V")
            self.stats_labels["max_voltage"].setText(f"{np.max(voltages):.6f} V")
            self.stats_labels["min_voltage"].setText(f"{np.min(voltages):.6f} V")
            
        if currents:
            self.stats_labels["avg_current"].setText(f"{np.mean(currents):.9f} A")
            self.stats_labels["max_current"].setText(f"{np.max(currents):.9f} A")
            self.stats_labels["min_current"].setText(f"{np.min(currents):.9f} A")
            
        if resistances:
            self.stats_labels["avg_resistance"].setText(f"{np.mean(resistances):.3f} Ω")
            
        if powers:
            self.stats_labels["avg_power"].setText(f"{np.mean(powers):.6f} W")
            
        self.stats_labels["data_points"].setText(str(len(recent_data)))
        
        # 計算測量時長
        if len(recent_data) >= 2:
            duration = (recent_data[-1].timestamp - recent_data[0].timestamp).total_seconds()
            self.stats_labels["duration"].setText(f"{duration:.1f} s")
            
    def _export_data(self, format_type: str):
        """導出數據"""
        try:
            from src.data import ExportFormat
            
            if format_type == "csv":
                export_format = ExportFormat.CSV
            elif format_type == "json":
                export_format = ExportFormat.JSON
            else:
                return
                
            # 導出數據
            filename = self.data_manager.export_data(
                export_format,
                instrument_id=self.instrument_type
            )
            
            self.add_log(f"✅ 數據已導出到 {filename}")
            QMessageBox.information(self, "導出成功", f"數據已導出到:\n{filename}")
            
        except Exception as e:
            self.error_occurred.emit("export", str(e))
            
    def _save_log(self):
        """保存日誌"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"logs/keithley_log_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.toPlainText())
                
            self.add_log(f"✅ 日誌已保存到 {filename}")
            
        except Exception as e:
            self.error_occurred.emit("save_log", str(e))
            
    def add_log(self, message: str):
        """添加日誌信息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        formatted_message = f"[{timestamp}] {message}"
        
        self.log_text.append(formatted_message)
        
        # 同時記錄到系統日誌
        self.logger.info(message)
        
    def stop_measurement(self):
        """停止測量 - 覆蓋基類方法"""
        super().stop_measurement()
        
        # 更新UI
        self.stop_btn.setEnabled(False)
        self.start_btn.setEnabled(True)
        
        # 更新掃描信息
        if self.measurement_mode == "sweep":
            self.sweep_info_labels["status"].setText("已停止")
            
        self.add_log("⏹️ 測量已停止")


class KeithleySweepStrategy(MeasurementStrategy):
    """Keithley掃描測量策略"""
    
    def __init__(self, instrument, sweep_params: Dict[str, Any]):
        super().__init__(instrument)
        self.sweep_params = sweep_params
        self.current_point = 0
        
    def initialize(self) -> bool:
        """初始化掃描"""
        try:
            # 設置為電壓源模式
            self.instrument.set_source_function("VOLT")
            self.instrument.output_on()
            return True
        except Exception as e:
            self.logger.error(f"掃描初始化失敗: {e}")
            return False
            
    def execute_measurement(self) -> Dict[str, Any]:
        """執行掃描測量"""
        start_v = self.sweep_params['start']
        stop_v = self.sweep_params['stop']
        step_v = self.sweep_params['step']
        delay_ms = self.sweep_params['delay_ms']
        current_limit = self.sweep_params['current_limit']
        
        # 計算掃描點
        voltage_points = np.arange(start_v, stop_v + step_v, step_v)
        
        if self.current_point >= len(voltage_points):
            # 掃描完成
            return None
            
        voltage = voltage_points[self.current_point]
        
        # 設置電壓
        self.instrument.set_voltage(str(voltage), current_limit=str(current_limit))
        
        # 延遲
        time.sleep(delay_ms / 1000.0)
        
        # 測量
        v, i, r, p = self.instrument.measure_all()
        
        self.current_point += 1
        
        # 計算進度
        progress = int(self.current_point * 100 / len(voltage_points))
        
        return {
            'voltage': v,
            'current': i,
            'resistance': r,
            'power': p,
            'metadata': {
                'point_number': self.current_point,
                'total_points': len(voltage_points),
                'progress': progress
            }
        }
        
    def cleanup(self):
        """清理資源"""
        try:
            self.instrument.output_off()
        except:
            pass
            
    def get_interval(self) -> int:
        """獲取測量間隔"""
        return 10  # 掃描測量使用最小間隔