#!/usr/bin/env python3
"""
測量控制Mixin
提供標準化的測量操作UI和邏輯
"""

from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QDoubleSpinBox, QComboBox,
                            QCheckBox, QSpinBox, QTabWidget, QWidget,
                            QFormLayout, QSlider)
from PyQt6.QtCore import pyqtSignal, Qt


class MeasurementMixin:
    """測量控制功能混入類"""
    
    # 測量相關信號
    measurement_started = pyqtSignal()
    measurement_stopped = pyqtSignal()
    measurement_params_changed = pyqtSignal(dict)
    single_measurement_requested = pyqtSignal()
    sweep_measurement_requested = pyqtSignal(dict)
    
    def create_measurement_panel(self) -> QGroupBox:
        """創建標準化測量面板
        
        Returns:
            QGroupBox: 測量控制面板
        """
        measurement_group = QGroupBox("測量控制")
        layout = QVBoxLayout(measurement_group)
        
        # 使用標籤頁組織不同的測量模式
        self.measurement_tabs = QTabWidget()
        
        # 基本測量標籤頁
        basic_tab = self._create_basic_measurement_tab()
        self.measurement_tabs.addTab(basic_tab, "基本測量")
        
        # 掃描測量標籤頁
        sweep_tab = self._create_sweep_measurement_tab()
        self.measurement_tabs.addTab(sweep_tab, "掃描測量")
        
        # 高級設置標籤頁
        advanced_tab = self._create_advanced_settings_tab()
        self.measurement_tabs.addTab(advanced_tab, "高級設置")
        
        layout.addWidget(self.measurement_tabs)
        
        # 測量控制按鈕
        control_layout = self._create_measurement_control_layout()
        layout.addLayout(control_layout)
        
        return measurement_group
        
    def _create_basic_measurement_tab(self) -> QWidget:
        """創建基本測量標籤頁"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # 測量模式選擇
        self.measurement_mode = QComboBox()
        self.measurement_mode.addItems(['連續測量', '單次測量', '定時測量'])
        self.measurement_mode.currentTextChanged.connect(self._on_measurement_params_changed)
        layout.addRow("測量模式:", self.measurement_mode)
        
        # 測量間隔
        self.measurement_interval = QSpinBox()
        self.measurement_interval.setRange(100, 60000)  # 100ms to 60s
        self.measurement_interval.setValue(1000)
        self.measurement_interval.setSuffix(" ms")
        self.measurement_interval.valueChanged.connect(self._on_measurement_params_changed)
        layout.addRow("測量間隔:", self.measurement_interval)
        
        # 最大測量次數
        self.max_measurements = QSpinBox()
        self.max_measurements.setRange(0, 1000000)
        self.max_measurements.setValue(0)  # 0表示無限制
        self.max_measurements.setSpecialValueText("無限制")
        self.max_measurements.valueChanged.connect(self._on_measurement_params_changed)
        layout.addRow("最大次數:", self.max_measurements)
        
        # 自動量程
        self.auto_range_cb = QCheckBox("自動量程")
        self.auto_range_cb.setChecked(True)
        self.auto_range_cb.toggled.connect(self._on_measurement_params_changed)
        layout.addRow("", self.auto_range_cb)
        
        return tab
        
    def _create_sweep_measurement_tab(self) -> QWidget:
        """創建掃描測量標籤頁"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # 掃描類型
        self.sweep_type = QComboBox()
        self.sweep_type.addItems(['電壓掃描', '電流掃描'])
        self.sweep_type.currentTextChanged.connect(self._on_measurement_params_changed)
        layout.addRow("掃描類型:", self.sweep_type)
        
        # 起始值
        self.sweep_start = QDoubleSpinBox()
        self.sweep_start.setRange(-1000, 1000)
        self.sweep_start.setValue(0.0)
        self.sweep_start.setDecimals(3)
        self.sweep_start.valueChanged.connect(self._on_measurement_params_changed)
        layout.addRow("起始值:", self.sweep_start)
        
        # 結束值
        self.sweep_stop = QDoubleSpinBox()
        self.sweep_stop.setRange(-1000, 1000)
        self.sweep_stop.setValue(10.0)
        self.sweep_stop.setDecimals(3)
        self.sweep_stop.valueChanged.connect(self._on_measurement_params_changed)
        layout.addRow("結束值:", self.sweep_stop)
        
        # 步長
        self.sweep_step = QDoubleSpinBox()
        self.sweep_step.setRange(0.001, 100)
        self.sweep_step.setValue(1.0)
        self.sweep_step.setDecimals(3)
        self.sweep_step.valueChanged.connect(self._on_measurement_params_changed)
        layout.addRow("步長:", self.sweep_step)
        
        # 延遲時間
        self.sweep_delay = QSpinBox()
        self.sweep_delay.setRange(10, 10000)
        self.sweep_delay.setValue(100)
        self.sweep_delay.setSuffix(" ms")
        self.sweep_delay.valueChanged.connect(self._on_measurement_params_changed)
        layout.addRow("延遲時間:", self.sweep_delay)
        
        # 限制設置
        limit_group = QGroupBox("限制設置")
        limit_layout = QFormLayout(limit_group)
        
        if self._supports_voltage_source():
            self.current_limit = QDoubleSpinBox()
            self.current_limit.setRange(0.001, 10.0)
            self.current_limit.setValue(0.1)
            self.current_limit.setDecimals(3)
            self.current_limit.setSuffix(" A")
            self.current_limit.valueChanged.connect(self._on_measurement_params_changed)
            limit_layout.addRow("電流限制:", self.current_limit)
            
        if self._supports_current_source():
            self.voltage_limit = QDoubleSpinBox()
            self.voltage_limit.setRange(0.1, 200.0)
            self.voltage_limit.setValue(10.0)
            self.voltage_limit.setDecimals(1)
            self.voltage_limit.setSuffix(" V")
            self.voltage_limit.valueChanged.connect(self._on_measurement_params_changed)
            limit_layout.addRow("電壓限制:", self.voltage_limit)
            
        layout.addRow(limit_group)
        
        return tab
        
    def _create_advanced_settings_tab(self) -> QWidget:
        """創建高級設置標籤頁"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # 積分時間
        self.integration_time = QComboBox()
        self.integration_time.addItems(['快速', '中等', '慢速', '自定義'])
        self.integration_time.currentTextChanged.connect(self._on_measurement_params_changed)
        layout.addRow("積分時間:", self.integration_time)
        
        # 平均次數
        self.average_count = QSpinBox()
        self.average_count.setRange(1, 100)
        self.average_count.setValue(1)
        self.average_count.valueChanged.connect(self._on_measurement_params_changed)
        layout.addRow("平均次數:", self.average_count)
        
        # 數字濾波
        self.digital_filter_cb = QCheckBox("數字濾波")
        self.digital_filter_cb.toggled.connect(self._on_measurement_params_changed)
        layout.addRow("", self.digital_filter_cb)
        
        # 四線測量 (如果支持)
        if self._supports_four_wire():
            self.four_wire_cb = QCheckBox("四線測量")
            self.four_wire_cb.toggled.connect(self._on_measurement_params_changed)
            layout.addRow("", self.four_wire_cb)
            
        # 溫度補償 (如果支持)
        if self._supports_temperature_compensation():
            self.temp_compensation_cb = QCheckBox("溫度補償")
            self.temp_compensation_cb.toggled.connect(self._on_measurement_params_changed)
            layout.addRow("", self.temp_compensation_cb)
            
        return tab
        
    def _create_measurement_control_layout(self) -> QHBoxLayout:
        """創建測量控制按鈕區域"""
        layout = QHBoxLayout()
        
        # 開始測量按鈕
        self.start_measurement_btn = QPushButton("開始測量")
        self.start_measurement_btn.clicked.connect(self._on_start_measurement)
        layout.addWidget(self.start_measurement_btn)
        
        # 停止測量按鈕
        self.stop_measurement_btn = QPushButton("停止測量")
        self.stop_measurement_btn.clicked.connect(self._on_stop_measurement)
        self.stop_measurement_btn.setEnabled(False)
        layout.addWidget(self.stop_measurement_btn)
        
        # 單次測量按鈕
        self.single_measurement_btn = QPushButton("單次測量")
        self.single_measurement_btn.clicked.connect(self._on_single_measurement)
        layout.addWidget(self.single_measurement_btn)
        
        return layout
        
    def _supports_voltage_source(self) -> bool:
        """檢查是否支援電壓源 - 子類覆蓋"""
        return True
        
    def _supports_current_source(self) -> bool:
        """檢查是否支援電流源 - 子類覆蓋"""
        return hasattr(self, 'instrument_type') and 'keithley' in getattr(self, 'instrument_type', '')
        
    def _supports_four_wire(self) -> bool:
        """檢查是否支援四線測量 - 子類覆蓋"""
        return hasattr(self, 'instrument_type') and 'keithley' in getattr(self, 'instrument_type', '')
        
    def _supports_temperature_compensation(self) -> bool:
        """檢查是否支援溫度補償 - 子類覆蓋"""
        return False
        
    def _on_start_measurement(self):
        """開始測量處理"""
        self.start_measurement_btn.setEnabled(False)
        self.stop_measurement_btn.setEnabled(True)
        self.single_measurement_btn.setEnabled(False)
        
        # 根據當前標籤頁決定測量類型
        current_tab = self.measurement_tabs.currentIndex()
        
        if current_tab == 0:  # 基本測量
            self.measurement_started.emit()
        elif current_tab == 1:  # 掃描測量
            sweep_params = self.get_sweep_parameters()
            self.sweep_measurement_requested.emit(sweep_params)
        else:  # 其他標籤頁
            self.measurement_started.emit()
            
    def _on_stop_measurement(self):
        """停止測量處理"""
        self.start_measurement_btn.setEnabled(True)
        self.stop_measurement_btn.setEnabled(False)
        self.single_measurement_btn.setEnabled(True)
        
        self.measurement_stopped.emit()
        
    def _on_single_measurement(self):
        """單次測量處理"""
        self.single_measurement_requested.emit()
        
    def _on_measurement_params_changed(self):
        """測量參數變化處理"""
        params = self.get_current_measurement_params()
        self.measurement_params_changed.emit(params)
        
    def get_current_measurement_params(self) -> Dict[str, Any]:
        """獲取當前測量參數"""
        params = {}
        
        # 基本測量參數
        if hasattr(self, 'measurement_mode'):
            params['mode'] = self.measurement_mode.currentText()
            
        if hasattr(self, 'measurement_interval'):
            params['interval_ms'] = self.measurement_interval.value()
            
        if hasattr(self, 'max_measurements'):
            params['max_measurements'] = self.max_measurements.value() if self.max_measurements.value() > 0 else None
            
        if hasattr(self, 'auto_range_cb'):
            params['auto_range'] = self.auto_range_cb.isChecked()
            
        # 掃描參數
        if hasattr(self, 'sweep_type'):
            params['sweep_type'] = self.sweep_type.currentText()
            
        if hasattr(self, 'sweep_start'):
            params['sweep_start'] = self.sweep_start.value()
            
        if hasattr(self, 'sweep_stop'):
            params['sweep_stop'] = self.sweep_stop.value()
            
        if hasattr(self, 'sweep_step'):
            params['sweep_step'] = self.sweep_step.value()
            
        if hasattr(self, 'sweep_delay'):
            params['sweep_delay'] = self.sweep_delay.value()
            
        # 限制參數
        if hasattr(self, 'current_limit'):
            params['current_limit'] = self.current_limit.value()
            
        if hasattr(self, 'voltage_limit'):
            params['voltage_limit'] = self.voltage_limit.value()
            
        # 高級參數
        if hasattr(self, 'integration_time'):
            params['integration_time'] = self.integration_time.currentText()
            
        if hasattr(self, 'average_count'):
            params['average_count'] = self.average_count.value()
            
        if hasattr(self, 'digital_filter_cb'):
            params['digital_filter'] = self.digital_filter_cb.isChecked()
            
        if hasattr(self, 'four_wire_cb'):
            params['four_wire'] = self.four_wire_cb.isChecked()
            
        if hasattr(self, 'temp_compensation_cb'):
            params['temperature_compensation'] = self.temp_compensation_cb.isChecked()
            
        return params
        
    def get_sweep_parameters(self) -> Dict[str, Any]:
        """獲取掃描測量參數"""
        return {
            'start': self.sweep_start.value() if hasattr(self, 'sweep_start') else 0,
            'stop': self.sweep_stop.value() if hasattr(self, 'sweep_stop') else 10,
            'step': self.sweep_step.value() if hasattr(self, 'sweep_step') else 1,
            'delay': self.sweep_delay.value() if hasattr(self, 'sweep_delay') else 100,
            'current_limit': self.current_limit.value() if hasattr(self, 'current_limit') else 0.1,
            'voltage_limit': self.voltage_limit.value() if hasattr(self, 'voltage_limit') else 10.0,
        }
        
    def update_measurement_status(self, active: bool):
        """更新測量狀態顯示"""
        if active:
            self.start_measurement_btn.setEnabled(False)
            self.stop_measurement_btn.setEnabled(True)
            self.single_measurement_btn.setEnabled(False)
        else:
            self.start_measurement_btn.setEnabled(True)
            self.stop_measurement_btn.setEnabled(False)
            self.single_measurement_btn.setEnabled(True)
            
    def load_measurement_settings(self, settings: Dict[str, Any]):
        """載入測量設置"""
        if hasattr(self, 'measurement_interval') and 'interval_ms' in settings:
            self.measurement_interval.setValue(settings['interval_ms'])
            
        if hasattr(self, 'max_measurements') and 'max_measurements' in settings:
            max_val = settings['max_measurements'] or 0
            self.max_measurements.setValue(max_val)
            
        if hasattr(self, 'auto_range_cb') and 'auto_range' in settings:
            self.auto_range_cb.setChecked(settings['auto_range'])
            
        # 載入掃描設置
        if hasattr(self, 'sweep_start') and 'sweep_start' in settings:
            self.sweep_start.setValue(settings['sweep_start'])
            
        if hasattr(self, 'sweep_stop') and 'sweep_stop' in settings:
            self.sweep_stop.setValue(settings['sweep_stop'])
            
        if hasattr(self, 'sweep_step') and 'sweep_step' in settings:
            self.sweep_step.setValue(settings['sweep_step'])