#!/usr/bin/env python3
"""
Keithley 2461 優化Widget
使用新的統一架構重構的Keithley控制介面
"""

from typing import Dict, Any, Optional
from datetime import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QDoubleSpinBox, QComboBox, QPushButton
from PyQt6.QtCore import pyqtSignal

from widgets.base import InstrumentWidgetBase
from src.keithley_2461 import Keithley2461
from src.workers import MeasurementWorker
from src.workers.measurement_worker import ContinuousMeasurementStrategy, SweepMeasurementStrategy
from src.workers.base_worker import UnifiedWorkerBase
from src.config import get_config


class OptimizedKeithleyWidget(InstrumentWidgetBase):
    """優化的Keithley 2461控制Widget
    
    使用新的統一架構：
    - 繼承InstrumentWidgetBase獲得標準功能
    - 使用統一的Worker系統進行測量
    - 集成配置管理和數據管理
    - 標準化的UI組件和主題支援
    """
    
    def __init__(self, instrument: Optional[Keithley2461] = None, parent=None):
        """初始化優化Keithley Widget
        
        Args:
            instrument: Keithley2461實例 (可選)
            parent: 父Widget
        """
        # 如果沒有提供儀器實例，創建一個新的
        if instrument is None:
            config = get_config()
            keithley_config = config.get_instrument_config('keithley_2461')
            default_ip = keithley_config.get('connection', {}).get('default_ip', '192.168.0.100')
            instrument = Keithley2461(ip_address=default_ip)
            
        # 初始化基類
        super().__init__("keithley_2461", instrument, parent)
        
        # Keithley特定屬性
        self.source_function = "VOLT"  # 預設為電壓源
        self.current_measurement_worker = None
        
    def _setup_instrument_ui(self):
        """設置Keithley特定的UI組件"""
        # 創建儀器特定控制面板
        controls_widget = self.create_instrument_controls()
        self.instrument_controls_layout.addWidget(controls_widget)
        
        # 載入儀器特定配置
        self._load_keithley_settings()
        
        # 連接儀器特定信號
        self._connect_keithley_signals()
        
    def create_instrument_controls(self) -> QWidget:
        """創建Keithley特定控制組件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 源功能選擇
        source_group = QGroupBox("源設置")
        source_layout = QVBoxLayout(source_group)
        
        # 源功能選擇
        function_layout = QHBoxLayout()
        function_layout.addWidget(QLabel("源功能:"))
        
        self.source_function_combo = QComboBox()
        self.source_function_combo.addItems(['電壓源', '電流源'])
        self.source_function_combo.currentTextChanged.connect(self._on_source_function_changed)
        function_layout.addWidget(self.source_function_combo)
        
        source_layout.addLayout(function_layout)
        
        # 電壓設置
        self.voltage_group = QGroupBox("電壓設置")
        voltage_layout = QHBoxLayout(self.voltage_group)
        
        voltage_layout.addWidget(QLabel("電壓值:"))
        self.voltage_spinbox = QDoubleSpinBox()
        self.voltage_spinbox.setRange(-200.0, 200.0)
        self.voltage_spinbox.setDecimals(3)
        self.voltage_spinbox.setSuffix(" V")
        self.voltage_spinbox.valueChanged.connect(self._on_voltage_changed)
        voltage_layout.addWidget(self.voltage_spinbox)
        
        voltage_layout.addWidget(QLabel("電流限制:"))
        self.current_limit_spinbox = QDoubleSpinBox()
        self.current_limit_spinbox.setRange(0.001, 7.0)
        self.current_limit_spinbox.setDecimals(3)
        self.current_limit_spinbox.setValue(0.1)
        self.current_limit_spinbox.setSuffix(" A")
        voltage_layout.addWidget(self.current_limit_spinbox)
        
        source_layout.addWidget(self.voltage_group)
        
        # 電流設置
        self.current_group = QGroupBox("電流設置")
        current_layout = QHBoxLayout(self.current_group)
        
        current_layout.addWidget(QLabel("電流值:"))
        self.current_spinbox = QDoubleSpinBox()
        self.current_spinbox.setRange(-7.0, 7.0)
        self.current_spinbox.setDecimals(3)
        self.current_spinbox.setSuffix(" A")
        self.current_spinbox.valueChanged.connect(self._on_current_changed)
        current_layout.addWidget(self.current_spinbox)
        
        current_layout.addWidget(QLabel("電壓限制:"))
        self.voltage_limit_spinbox = QDoubleSpinBox()
        self.voltage_limit_spinbox.setRange(0.1, 200.0)
        self.voltage_limit_spinbox.setDecimals(1)
        self.voltage_limit_spinbox.setValue(10.0)
        self.voltage_limit_spinbox.setSuffix(" V")
        current_layout.addWidget(self.voltage_limit_spinbox)
        
        source_layout.addWidget(self.current_group)
        
        # 預設隱藏電流設置
        self.current_group.setVisible(False)
        
        layout.addWidget(source_group)
        
        # 輸出控制
        output_group = QGroupBox("輸出控制")
        output_layout = QVBoxLayout(output_group)
        
        # 輸出開關按鈕
        self.output_button = QPushButton("開啟輸出")
        self.output_button.setCheckable(True)
        self.output_button.clicked.connect(self._on_output_toggle)
        output_layout.addWidget(self.output_button)
        
        # 輸出狀態顯示
        self.output_status_label = QLabel("輸出: 關閉")
        self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        output_layout.addWidget(self.output_status_label)
        
        layout.addWidget(output_group)
        
        return widget
        
    def get_connection_params(self) -> Dict[str, Any]:
        """獲取Keithley連接參數"""
        # 從ConnectionMixin獲取基本參數
        params = self.get_current_connection_params()
        
        # 設置Keithley特定的預設值
        if 'ip_address' not in params:
            config = self.config.get_instrument_config('keithley_2461')
            params['ip_address'] = config.get('connection', {}).get('default_ip', '192.168.0.100')
            
        if 'port' not in params:
            params['port'] = 5025
            
        if 'timeout' not in params:
            params['timeout'] = 10.0
            
        return params
        
    def _create_measurement_worker(self) -> Optional[UnifiedWorkerBase]:
        """創建Keithley測量Worker"""
        if not self.is_connected or not self.instrument:
            return None
            
        # 獲取當前測量參數
        measurement_params = self.get_current_measurement_params()
        
        # 根據測量模式創建對應的策略
        current_tab = getattr(self, 'measurement_tabs', None)
        if current_tab and current_tab.currentIndex() == 1:  # 掃描測量
            sweep_params = self.get_sweep_parameters()
            strategy = SweepMeasurementStrategy()
            return MeasurementWorker(self.instrument, strategy, sweep_params)
        else:  # 連續測量
            strategy = ContinuousMeasurementStrategy()
            return MeasurementWorker(self.instrument, strategy, measurement_params)
            
    def _load_keithley_settings(self):
        """載入Keithley特定設置"""
        config = self.config.get_instrument_config('keithley_2461')
        
        # 載入連接設置
        connection_config = config.get('connection', {})
        self.load_connection_settings(connection_config)
        
        # 載入測量設置
        measurement_config = config.get('measurement', {})
        self.load_measurement_settings(measurement_config)
        
        # 設置安全限制
        safety_config = config.get('safety', {})
        if safety_config.get('max_voltage'):
            self.voltage_spinbox.setMaximum(safety_config['max_voltage'])
        if safety_config.get('max_current'):
            self.current_spinbox.setMaximum(safety_config['max_current'])
            
    def _connect_keithley_signals(self):
        """連接Keithley特定信號"""
        # 連接標準信號處理
        self.connection_requested.connect(self.connect_instrument)
        self.disconnection_requested.connect(self.disconnect_instrument)
        
        # 測量控制信號
        self.measurement_started.connect(self.start_measurement)
        self.measurement_stopped.connect(self.stop_measurement)
        self.single_measurement_requested.connect(self._perform_single_measurement)
        self.sweep_measurement_requested.connect(self._perform_sweep_measurement)
        
    def _on_source_function_changed(self, function: str):
        """源功能變化處理"""
        if function == '電壓源':
            self.source_function = "VOLT"
            self.voltage_group.setVisible(True)
            self.current_group.setVisible(False)
        else:
            self.source_function = "CURR"
            self.voltage_group.setVisible(False)
            self.current_group.setVisible(True)
            
        # 如果已連接，設置儀器源功能
        if self.is_connected and self.instrument:
            try:
                self.instrument.set_source_function(self.source_function)
            except Exception as e:
                self.error_occurred.emit("source_function_error", str(e))
                
    def _on_voltage_changed(self, voltage: float):
        """電壓值變化處理"""
        if self.is_connected and self.instrument and self.source_function == "VOLT":
            try:
                current_limit = self.current_limit_spinbox.value()
                self.instrument.set_voltage(voltage, current_limit=current_limit)
            except Exception as e:
                self.error_occurred.emit("voltage_set_error", str(e))
                
    def _on_current_changed(self, current: float):
        """電流值變化處理"""
        if self.is_connected and self.instrument and self.source_function == "CURR":
            try:
                voltage_limit = self.voltage_limit_spinbox.value()
                self.instrument.set_current(current, voltage_limit=voltage_limit)
            except Exception as e:
                self.error_occurred.emit("current_set_error", str(e))
                
    def _on_output_toggle(self, enabled: bool):
        """輸出開關處理"""
        if not self.is_connected or not self.instrument:
            self.output_button.setChecked(False)
            return
            
        try:
            if enabled:
                self.instrument.output_on()
                self.output_button.setText("關閉輸出")
                self.output_status_label.setText("輸出: 開啟")
                self.output_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
                self.status_changed.emit("輸出已開啟")
            else:
                self.instrument.output_off()
                self.output_button.setText("開啟輸出")
                self.output_status_label.setText("輸出: 關閉")
                self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.status_changed.emit("輸出已關閉")
                
        except Exception as e:
            self.error_occurred.emit("output_control_error", str(e))
            self.output_button.setChecked(False)
            
    def _perform_single_measurement(self):
        """執行單次測量"""
        if not self.is_connected or not self.instrument:
            return
            
        try:
            # 執行測量
            voltage, current, resistance, power = self.instrument.measure_all()
            
            # 創建測量數據點
            measurement_data = {
                'timestamp': datetime.now(),
                'voltage': voltage,
                'current': current,
                'resistance': resistance,
                'power': power,
                'measurement_type': 'single'
            }
            
            # 發送數據
            self.measurement_data.emit(measurement_data)
            self.status_changed.emit(f"單次測量: V={voltage:.3f}V, I={current:.6f}A")
            
        except Exception as e:
            self.error_occurred.emit("single_measurement_error", str(e))
            
    def _perform_sweep_measurement(self, sweep_params: Dict[str, Any]):
        """執行掃描測量"""
        # 掃描測量由MeasurementWorker處理
        self.start_measurement()
        
    def disconnect_instrument(self):
        """斷開儀器連接 - 覆蓋基類以添加Keithley特定清理"""
        # 安全關閉輸出
        if self.is_connected and self.instrument:
            try:
                self.instrument.output_off()
                self.output_button.setChecked(False)
                self.output_button.setText("開啟輸出")
                self.output_status_label.setText("輸出: 關閉")
                self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            except:
                pass
                
        # 調用基類斷開方法
        super().disconnect_instrument()
        
    def _apply_theme_styles(self):
        """應用Keithley特定的主題樣式"""
        # 調用基類主題應用
        super()._apply_theme_styles()
        
        # Keithley特定的主題樣式可以在這裡添加
        if self.current_theme == "dark":
            # 深色主題特定樣式
            pass
        else:
            # 淺色主題特定樣式  
            pass