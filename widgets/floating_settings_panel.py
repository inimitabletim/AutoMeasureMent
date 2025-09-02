#!/usr/bin/env python3
"""
懸浮設定面板組件
為專業版提供詳細設置的彈出式界面
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLabel, QDoubleSpinBox, QComboBox, QPushButton,
                            QGridLayout, QSpinBox, QCheckBox, QTabWidget, QWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from typing import Dict, Any


class FloatingSettingsPanel(QDialog):
    """懸浮設定面板
    
    提供詳細的儀器設定選項，不佔用主界面空間
    """
    
    # 設定變更信號
    settings_applied = pyqtSignal(dict)
    
    def __init__(self, parent=None, current_settings: Dict[str, Any] = None):
        """初始化懸浮設定面板
        
        Args:
            parent: 父Widget
            current_settings: 當前設定值
        """
        super().__init__(parent)
        
        self.current_settings = current_settings or {}
        self.temp_settings = self.current_settings.copy()
        
        self._setup_ui()
        self._load_current_settings()
        self._connect_signals()
        
    def _setup_ui(self):
        """設置UI界面"""
        self.setWindowTitle("詳細儀器設定")
        self.setModal(True)
        self.setFixedSize(500, 600)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # 標題區域
        title_label = QLabel("Keithley 2461 詳細設定")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                padding: 10px;
                background-color: #ecf0f1;
                border-radius: 5px;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(title_label)
        
        # 設定標籤頁
        self.settings_tabs = QTabWidget()
        
        # 電源設定標籤頁
        power_tab = self._create_power_settings_tab()
        self.settings_tabs.addTab(power_tab, "電源設定")
        
        # 測量設定標籤頁
        measurement_tab = self._create_measurement_settings_tab()
        self.settings_tabs.addTab(measurement_tab, "測量設定")
        
        # 高級設定標籤頁
        advanced_tab = self._create_advanced_settings_tab()
        self.settings_tabs.addTab(advanced_tab, "高級設定")
        
        layout.addWidget(self.settings_tabs)
        
        # 按鈕區域
        button_layout = self._create_button_layout()
        layout.addLayout(button_layout)
        
    def _create_power_settings_tab(self) -> QWidget:
        """創建電源設定標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 電壓源詳細設定
        voltage_group = QGroupBox("電壓源設定")
        voltage_grid = QGridLayout(voltage_group)
        
        # 電壓範圍
        voltage_grid.addWidget(QLabel("電壓範圍:"), 0, 0)
        
        self.voltage_range_combo = QComboBox()
        self.voltage_range_combo.addItems(['自動', '±20V', '±200V'])
        voltage_grid.addWidget(self.voltage_range_combo, 0, 1)
        
        # 電壓解析度
        voltage_grid.addWidget(QLabel("解析度:"), 1, 0)
        
        self.voltage_resolution_combo = QComboBox()
        self.voltage_resolution_combo.addItems(['6.5位', '5.5位', '4.5位'])
        voltage_grid.addWidget(self.voltage_resolution_combo, 1, 1)
        
        # 電流限制設定
        voltage_grid.addWidget(QLabel("預設電流限制:"), 2, 0)
        
        self.default_current_limit = QDoubleSpinBox()
        self.default_current_limit.setRange(0.001, 7.000)
        self.default_current_limit.setDecimals(3)
        self.default_current_limit.setValue(0.100)
        self.default_current_limit.setSuffix(" A")
        voltage_grid.addWidget(self.default_current_limit, 2, 1)
        
        layout.addWidget(voltage_group)
        
        # 電流源詳細設定
        current_group = QGroupBox("電流源設定")
        current_grid = QGridLayout(current_group)
        
        # 電流範圍
        current_grid.addWidget(QLabel("電流範圍:"), 0, 0)
        
        self.current_range_combo = QComboBox()
        self.current_range_combo.addItems(['自動', '±100mA', '±1A', '±7A'])
        current_grid.addWidget(self.current_range_combo, 0, 1)
        
        # 電流解析度
        current_grid.addWidget(QLabel("解析度:"), 1, 0)
        
        self.current_resolution_combo = QComboBox()
        self.current_resolution_combo.addItems(['6.5位', '5.5位', '4.5位'])
        current_grid.addWidget(self.current_resolution_combo, 1, 1)
        
        # 電壓限制設定
        current_grid.addWidget(QLabel("預設電壓限制:"), 2, 0)
        
        self.default_voltage_limit = QDoubleSpinBox()
        self.default_voltage_limit.setRange(0.1, 200.0)
        self.default_voltage_limit.setDecimals(1)
        self.default_voltage_limit.setValue(10.0)
        self.default_voltage_limit.setSuffix(" V")
        current_grid.addWidget(self.default_voltage_limit, 2, 1)
        
        layout.addWidget(current_group)
        layout.addStretch()
        
        return tab
        
    def _create_measurement_settings_tab(self) -> QWidget:
        """創建測量設定標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 測量參數設定
        measurement_group = QGroupBox("測量參數")
        measurement_grid = QGridLayout(measurement_group)
        
        # 積分時間
        measurement_grid.addWidget(QLabel("積分時間:"), 0, 0)
        
        self.integration_time_combo = QComboBox()
        self.integration_time_combo.addItems(['快速 (1ms)', '中等 (10ms)', '慢速 (100ms)', '自定義'])
        measurement_grid.addWidget(self.integration_time_combo, 0, 1)
        
        # 平均次數
        measurement_grid.addWidget(QLabel("平均次數:"), 1, 0)
        
        self.average_count_spin = QSpinBox()
        self.average_count_spin.setRange(1, 100)
        self.average_count_spin.setValue(1)
        measurement_grid.addWidget(self.average_count_spin, 1, 1)
        
        # 測量延遲
        measurement_grid.addWidget(QLabel("測量延遲:"), 2, 0)
        
        self.measurement_delay_spin = QSpinBox()
        self.measurement_delay_spin.setRange(0, 10000)
        self.measurement_delay_spin.setValue(0)
        self.measurement_delay_spin.setSuffix(" ms")
        measurement_grid.addWidget(self.measurement_delay_spin, 2, 1)
        
        layout.addWidget(measurement_group)
        
        # 掃描設定
        sweep_group = QGroupBox("掃描設定")
        sweep_grid = QGridLayout(sweep_group)
        
        # 掃描點數
        sweep_grid.addWidget(QLabel("最大掃描點數:"), 0, 0)
        
        self.max_sweep_points = QSpinBox()
        self.max_sweep_points.setRange(10, 10000)
        self.max_sweep_points.setValue(1000)
        sweep_grid.addWidget(self.max_sweep_points, 0, 1)
        
        # 掃描延遲
        sweep_grid.addWidget(QLabel("掃描步驟延遲:"), 1, 0)
        
        self.sweep_step_delay = QSpinBox()
        self.sweep_step_delay.setRange(1, 10000)
        self.sweep_step_delay.setValue(100)
        self.sweep_step_delay.setSuffix(" ms")
        sweep_grid.addWidget(self.sweep_step_delay, 1, 1)
        
        layout.addWidget(sweep_group)
        layout.addStretch()
        
        return tab
        
    def _create_advanced_settings_tab(self) -> QWidget:
        """創建高級設定標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 連接設定
        connection_group = QGroupBox("連接設定")
        connection_grid = QGridLayout(connection_group)
        
        # 超時設定
        connection_grid.addWidget(QLabel("通訊超時:"), 0, 0)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(1, 60)
        self.timeout_spin.setValue(10)
        self.timeout_spin.setSuffix(" 秒")
        connection_grid.addWidget(self.timeout_spin, 0, 1)
        
        # 重試次數
        connection_grid.addWidget(QLabel("重試次數:"), 1, 0)
        
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 10)
        self.retry_count_spin.setValue(3)
        connection_grid.addWidget(self.retry_count_spin, 1, 1)
        
        layout.addWidget(connection_group)
        
        # 安全設定
        safety_group = QGroupBox("安全設定")
        safety_layout = QVBoxLayout(safety_group)
        
        self.auto_output_off_cb = QCheckBox("斷開連接時自動關閉輸出")
        self.auto_output_off_cb.setChecked(True)
        safety_layout.addWidget(self.auto_output_off_cb)
        
        self.confirm_high_power_cb = QCheckBox("高功率輸出時顯示確認對話框")
        self.confirm_high_power_cb.setChecked(True)
        safety_layout.addWidget(self.confirm_high_power_cb)
        
        self.beep_on_complete_cb = QCheckBox("測量完成時蜂鳴提醒")
        self.beep_on_complete_cb.setChecked(False)
        safety_layout.addWidget(self.beep_on_complete_cb)
        
        layout.addWidget(safety_group)
        layout.addStretch()
        
        return tab
        
    def _create_button_layout(self) -> QHBoxLayout:
        """創建按鈕區域"""
        layout = QHBoxLayout()
        
        # 重置按鈕
        reset_btn = QPushButton("重置預設")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
        
        # 取消按鈕
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)
        
        # 套用按鈕
        apply_btn = QPushButton("套用")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        apply_btn.clicked.connect(self._apply_settings)
        layout.addWidget(apply_btn)
        
        return layout
        
    def _load_current_settings(self):
        """載入當前設定值"""
        # 這裡可以根據 current_settings 載入實際數值
        # 目前使用預設值
        pass
        
    def _connect_signals(self):
        """連接信號"""
        # 設定變更時更新臨時設定
        self.voltage_range_combo.currentTextChanged.connect(self._update_temp_settings)
        self.current_range_combo.currentTextChanged.connect(self._update_temp_settings)
        # 可以添加更多信號連接
        
    def _update_temp_settings(self):
        """更新臨時設定"""
        # 收集所有設定值到 temp_settings
        self.temp_settings.update({
            'voltage_range': self.voltage_range_combo.currentText(),
            'current_range': self.current_range_combo.currentText(),
            'voltage_resolution': self.voltage_resolution_combo.currentText(),
            'current_resolution': self.current_resolution_combo.currentText(),
            'default_current_limit': self.default_current_limit.value(),
            'default_voltage_limit': self.default_voltage_limit.value(),
            'integration_time': self.integration_time_combo.currentText(),
            'average_count': self.average_count_spin.value(),
            'measurement_delay': self.measurement_delay_spin.value(),
            'max_sweep_points': self.max_sweep_points.value(),
            'sweep_step_delay': self.sweep_step_delay.value(),
            'timeout': self.timeout_spin.value(),
            'retry_count': self.retry_count_spin.value(),
            'auto_output_off': self.auto_output_off_cb.isChecked(),
            'confirm_high_power': self.confirm_high_power_cb.isChecked(),
            'beep_on_complete': self.beep_on_complete_cb.isChecked(),
        })
        
    def _reset_to_defaults(self):
        """重置為預設值"""
        # 重置所有控制項為預設值
        self.voltage_range_combo.setCurrentText('自動')
        self.current_range_combo.setCurrentText('自動')
        self.voltage_resolution_combo.setCurrentText('6.5位')
        self.current_resolution_combo.setCurrentText('6.5位')
        self.default_current_limit.setValue(0.100)
        self.default_voltage_limit.setValue(10.0)
        self.integration_time_combo.setCurrentText('中等 (10ms)')
        self.average_count_spin.setValue(1)
        self.measurement_delay_spin.setValue(0)
        self.max_sweep_points.setValue(1000)
        self.sweep_step_delay.setValue(100)
        self.timeout_spin.setValue(10)
        self.retry_count_spin.setValue(3)
        self.auto_output_off_cb.setChecked(True)
        self.confirm_high_power_cb.setChecked(True)
        self.beep_on_complete_cb.setChecked(False)
        
    def _apply_settings(self):
        """套用設定並關閉對話框"""
        self._update_temp_settings()
        self.settings_applied.emit(self.temp_settings)
        self.accept()
        
    def get_settings(self) -> Dict[str, Any]:
        """獲取當前設定值"""
        self._update_temp_settings()
        return self.temp_settings.copy()