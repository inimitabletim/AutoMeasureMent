#!/usr/bin/env python3
"""
數據視覺化Mixin
提供標準化的數據顯示和圖表功能
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                            QGroupBox, QLabel, QLCDNumber, QTabWidget,
                            QPushButton, QComboBox, QCheckBox, QSpinBox)
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import pyqtgraph as pg
from collections import deque


class DataVisualizationMixin:
    """數據視覺化功能混入類"""
    
    # 視覺化相關信號
    chart_type_changed = pyqtSignal(str)
    export_requested = pyqtSignal(str)  # format
    data_cleared = pyqtSignal()
    
    def create_visualization_panel(self) -> QWidget:
        """創建數據視覺化面板
        
        Returns:
            QWidget: 視覺化面板
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 數據顯示標籤頁
        self.visualization_tabs = QTabWidget()
        
        # 實時數據顯示標籤頁
        realtime_tab = self._create_realtime_display_tab()
        self.visualization_tabs.addTab(realtime_tab, "實時數據")
        
        # 圖表顯示標籤頁
        chart_tab = self._create_chart_display_tab()
        self.visualization_tabs.addTab(chart_tab, "圖表")
        
        # 數據統計標籤頁
        stats_tab = self._create_statistics_tab()
        self.visualization_tabs.addTab(stats_tab, "統計")
        
        layout.addWidget(self.visualization_tabs)
        
        # 控制按鈕區域
        control_layout = self._create_visualization_controls()
        layout.addLayout(control_layout)
        
        return panel
        
    def _create_realtime_display_tab(self) -> QWidget:
        """創建實時數據顯示標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 大字體數值顯示
        values_group = QGroupBox("當前值")
        values_layout = QHBoxLayout(values_group)
        
        # 電壓顯示
        voltage_widget = self._create_value_display("電壓", "V", "#3498db")
        values_layout.addWidget(voltage_widget)
        self.voltage_display = voltage_widget.findChild(QLCDNumber)
        
        # 電流顯示
        current_widget = self._create_value_display("電流", "A", "#e74c3c")
        values_layout.addWidget(current_widget)
        self.current_display = current_widget.findChild(QLCDNumber)
        
        # 功率顯示
        power_widget = self._create_value_display("功率", "W", "#f39c12")
        values_layout.addWidget(power_widget)
        self.power_display = power_widget.findChild(QLCDNumber)
        
        # 電阻顯示 (如果適用)
        if self._supports_resistance_measurement():
            resistance_widget = self._create_value_display("電阻", "Ω", "#9b59b6")
            values_layout.addWidget(resistance_widget)
            self.resistance_display = resistance_widget.findChild(QLCDNumber)
            
        layout.addWidget(values_group)
        
        # 測量信息
        info_group = QGroupBox("測量信息")
        info_layout = QVBoxLayout(info_group)
        
        self.measurement_count_label = QLabel("測量次數: 0")
        info_layout.addWidget(self.measurement_count_label)
        
        self.measurement_rate_label = QLabel("測量速率: 0 Hz")
        info_layout.addWidget(self.measurement_rate_label)
        
        self.last_update_label = QLabel("最後更新: --")
        info_layout.addWidget(self.last_update_label)
        
        layout.addWidget(info_group)
        layout.addStretch()
        
        return tab
        
    def _create_value_display(self, name: str, unit: str, color: str) -> QGroupBox:
        """創建單個數值顯示組件"""
        group = QGroupBox(f"{name} ({unit})")
        layout = QVBoxLayout(group)
        
        # LCD數字顯示
        lcd = QLCDNumber(8)  # 8位數字顯示
        lcd.setDigitCount(10)
        lcd.display("0.000000")
        lcd.setStyleSheet(f"""
            QLCDNumber {{
                background-color: black;
                color: {color};
                border: 2px solid {color};
                border-radius: 5px;
            }}
        """)
        layout.addWidget(lcd)
        
        return group
        
    def _create_chart_display_tab(self) -> QWidget:
        """創建圖表顯示標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 圖表控制區域
        chart_controls = QHBoxLayout()
        
        # 圖表類型選擇
        chart_controls.addWidget(QLabel("圖表類型:"))
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(['時間序列', 'IV特性', 'XY散點'])
        self.chart_type_combo.currentTextChanged.connect(self._on_chart_type_changed)
        chart_controls.addWidget(self.chart_type_combo)
        
        # 數據點限制
        chart_controls.addWidget(QLabel("顯示點數:"))
        self.plot_points_spin = QSpinBox()
        self.plot_points_spin.setRange(100, 10000)
        self.plot_points_spin.setValue(1000)
        self.plot_points_spin.valueChanged.connect(self._on_plot_points_changed)
        chart_controls.addWidget(self.plot_points_spin)
        
        # 自動縮放
        self.auto_scale_cb = QCheckBox("自動縮放")
        self.auto_scale_cb.setChecked(True)
        self.auto_scale_cb.toggled.connect(self._on_auto_scale_toggled)
        chart_controls.addWidget(self.auto_scale_cb)
        
        chart_controls.addStretch()
        layout.addLayout(chart_controls)
        
        # 圖表顯示區域
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('w')  # 白色背景
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        
        # 設置標籤
        self.plot_widget.setLabel('left', '電流 (A)')
        self.plot_widget.setLabel('bottom', '時間 (s)')
        
        layout.addWidget(self.plot_widget)
        
        # 初始化數據緩存
        self._init_plot_data()
        
        return tab
        
    def _create_statistics_tab(self) -> QWidget:
        """創建統計信息標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 基本統計
        basic_stats = QGroupBox("基本統計")
        stats_layout = QVBoxLayout(basic_stats)
        
        self.stats_labels = {}
        for param in ['電壓', '電流', '功率', '電阻']:
            param_group = QGroupBox(param)
            param_layout = QVBoxLayout(param_group)
            
            labels = {}
            for stat in ['平均值', '最大值', '最小值', '標準差']:
                label = QLabel(f"{stat}: --")
                param_layout.addWidget(label)
                labels[stat] = label
                
            self.stats_labels[param] = labels
            stats_layout.addWidget(param_group)
            
        layout.addWidget(basic_stats)
        
        # 數據會話信息
        session_group = QGroupBox("會話信息")
        session_layout = QVBoxLayout(session_group)
        
        self.session_duration_label = QLabel("持續時間: --")
        session_layout.addWidget(self.session_duration_label)
        
        self.total_points_label = QLabel("總數據點: 0")
        session_layout.addWidget(self.total_points_label)
        
        self.avg_rate_label = QLabel("平均速率: -- Hz")
        session_layout.addWidget(self.avg_rate_label)
        
        layout.addWidget(session_group)
        layout.addStretch()
        
        return tab
        
    def _create_visualization_controls(self) -> QHBoxLayout:
        """創建視覺化控制按鈕"""
        layout = QHBoxLayout()
        
        # 清空數據按鈕
        self.clear_data_btn = QPushButton("清空數據")
        self.clear_data_btn.clicked.connect(self._on_clear_data)
        layout.addWidget(self.clear_data_btn)
        
        # 導出數據按鈕
        self.export_csv_btn = QPushButton("導出CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_requested.emit('csv'))
        layout.addWidget(self.export_csv_btn)
        
        self.export_json_btn = QPushButton("導出JSON")
        self.export_json_btn.clicked.connect(lambda: self.export_requested.emit('json'))
        layout.addWidget(self.export_json_btn)
        
        # 截圖按鈕
        self.screenshot_btn = QPushButton("截圖")
        self.screenshot_btn.clicked.connect(self._on_take_screenshot)
        layout.addWidget(self.screenshot_btn)
        
        layout.addStretch()
        
        return layout
        
    def _supports_resistance_measurement(self) -> bool:
        """檢查是否支援電阻測量 - 子類覆蓋"""
        return hasattr(self, 'instrument_type') and 'keithley' in getattr(self, 'instrument_type', '')
        
    def _init_plot_data(self):
        """初始化圖表數據結構"""
        self.plot_data = {
            'time': deque(maxlen=1000),
            'voltage': deque(maxlen=1000),
            'current': deque(maxlen=1000),
            'power': deque(maxlen=1000),
            'resistance': deque(maxlen=1000)
        }
        
        # 創建繪圖曲線
        self.voltage_curve = self.plot_widget.plot([], [], pen='b', name='電壓')
        self.current_curve = self.plot_widget.plot([], [], pen='r', name='電流')
        self.power_curve = self.plot_widget.plot([], [], pen='orange', name='功率')
        
        if self._supports_resistance_measurement():
            self.resistance_curve = self.plot_widget.plot([], [], pen='purple', name='電阻')
            
        # 測量統計
        self.measurement_count = 0
        self.session_start_time = None
        self.last_measurement_time = None
        
    def update_visualization(self, measurement_point):
        """更新視覺化顯示
        
        Args:
            measurement_point: 測量數據點
        """
        current_time = datetime.now()
        
        # 更新實時數值顯示
        self._update_realtime_display(measurement_point)
        
        # 更新圖表數據
        self._update_chart_data(measurement_point, current_time)
        
        # 更新統計信息
        self._update_statistics(measurement_point, current_time)
        
    def _update_realtime_display(self, point):
        """更新實時數值顯示"""
        if hasattr(self, 'voltage_display'):
            self.voltage_display.display(f"{point.voltage:.6f}")
            
        if hasattr(self, 'current_display'):
            self.current_display.display(f"{point.current:.6f}")
            
        if hasattr(self, 'power_display') and point.power is not None:
            self.power_display.display(f"{point.power:.6f}")
            
        if hasattr(self, 'resistance_display') and point.resistance is not None:
            self.resistance_display.display(f"{point.resistance:.2f}")
            
    def _update_chart_data(self, point, current_time):
        """更新圖表數據"""
        # 計算相對時間 (秒)
        if self.session_start_time is None:
            self.session_start_time = current_time
            relative_time = 0
        else:
            relative_time = (current_time - self.session_start_time).total_seconds()
            
        # 添加數據點
        self.plot_data['time'].append(relative_time)
        self.plot_data['voltage'].append(point.voltage)
        self.plot_data['current'].append(point.current)
        
        if point.power is not None:
            self.plot_data['power'].append(point.power)
        if point.resistance is not None:
            self.plot_data['resistance'].append(point.resistance)
            
        # 更新圖表曲線
        time_data = list(self.plot_data['time'])
        
        chart_type = self.chart_type_combo.currentText() if hasattr(self, 'chart_type_combo') else '時間序列'
        
        if chart_type == '時間序列':
            self.voltage_curve.setData(time_data, list(self.plot_data['voltage']))
            self.current_curve.setData(time_data, list(self.plot_data['current']))
            self.power_curve.setData(time_data, list(self.plot_data['power']))
            
            if hasattr(self, 'resistance_curve'):
                self.resistance_curve.setData(time_data, list(self.plot_data['resistance']))
                
        elif chart_type == 'IV特性':
            # 電壓-電流特性曲線
            self.voltage_curve.setData(list(self.plot_data['voltage']), list(self.plot_data['current']))
            
        # 自動縮放
        if hasattr(self, 'auto_scale_cb') and self.auto_scale_cb.isChecked():
            self.plot_widget.autoRange()
            
    def _update_statistics(self, point, current_time):
        """更新統計信息"""
        self.measurement_count += 1
        self.last_measurement_time = current_time
        
        # 更新計數和速率
        if hasattr(self, 'measurement_count_label'):
            self.measurement_count_label.setText(f"測量次數: {self.measurement_count}")
            
        if hasattr(self, 'last_update_label'):
            self.last_update_label.setText(f"最後更新: {current_time.strftime('%H:%M:%S')}")
            
        # 計算測量速率
        if self.session_start_time and self.measurement_count > 1:
            duration = (current_time - self.session_start_time).total_seconds()
            rate = self.measurement_count / duration if duration > 0 else 0
            
            if hasattr(self, 'measurement_rate_label'):
                self.measurement_rate_label.setText(f"測量速率: {rate:.1f} Hz")
                
        # 更新統計標籤 (簡化實現)
        if hasattr(self, 'stats_labels') and len(self.plot_data['voltage']) > 1:
            self._calculate_and_display_stats()
            
    def _calculate_and_display_stats(self):
        """計算並顯示統計數據"""
        import numpy as np
        
        data_map = {
            '電壓': list(self.plot_data['voltage']),
            '電流': list(self.plot_data['current']),
            '功率': list(self.plot_data['power']),
            '電阻': list(self.plot_data['resistance'])
        }
        
        for param, values in data_map.items():
            if param in self.stats_labels and values:
                values_array = np.array([v for v in values if v is not None])
                if len(values_array) > 0:
                    stats = {
                        '平均值': np.mean(values_array),
                        '最大值': np.max(values_array),
                        '最小值': np.min(values_array),
                        '標準差': np.std(values_array)
                    }
                    
                    for stat_name, stat_value in stats.items():
                        if stat_name in self.stats_labels[param]:
                            self.stats_labels[param][stat_name].setText(f"{stat_name}: {stat_value:.6f}")
                            
    def _on_chart_type_changed(self, chart_type: str):
        """圖表類型變化處理"""
        self.chart_type_changed.emit(chart_type)
        
        # 更新軸標籤
        if chart_type == 'IV特性':
            self.plot_widget.setLabel('left', '電流 (A)')
            self.plot_widget.setLabel('bottom', '電壓 (V)')
        else:
            self.plot_widget.setLabel('left', '數值')
            self.plot_widget.setLabel('bottom', '時間 (s)')
            
    def _on_plot_points_changed(self, points: int):
        """顯示點數變化處理"""
        # 更新數據緩存大小
        for key in self.plot_data:
            self.plot_data[key] = deque(list(self.plot_data[key]), maxlen=points)
            
    def _on_auto_scale_toggled(self, enabled: bool):
        """自動縮放切換處理"""
        if enabled:
            self.plot_widget.autoRange()
            
    def _on_clear_data(self):
        """清空數據處理"""
        # 清空數據緩存
        for key in self.plot_data:
            self.plot_data[key].clear()
            
        # 清空圖表
        self.voltage_curve.setData([], [])
        self.current_curve.setData([], [])
        self.power_curve.setData([], [])
        
        if hasattr(self, 'resistance_curve'):
            self.resistance_curve.setData([], [])
            
        # 重置統計
        self.measurement_count = 0
        self.session_start_time = None
        
        # 重置顯示
        if hasattr(self, 'voltage_display'):
            self.voltage_display.display("0.000000")
        if hasattr(self, 'current_display'):
            self.current_display.display("0.000000")
        if hasattr(self, 'power_display'):
            self.power_display.display("0.000000")
        if hasattr(self, 'resistance_display'):
            self.resistance_display.display("0.00")
            
        self.data_cleared.emit()
        
    def _on_take_screenshot(self):
        """截圖處理"""
        try:
            from PyQt6.QtWidgets import QFileDialog
            from PyQt6.QtCore import QStandardPaths
            
            # 獲取保存路徑
            default_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
            filename, _ = QFileDialog.getSaveFileName(
                self, "保存截圖", 
                f"{default_path}/chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
                "PNG Files (*.png);;All Files (*)"
            )
            
            if filename:
                # 導出圖表為圖片
                exporter = pg.exporters.ImageExporter(self.plot_widget.plotItem)
                exporter.export(filename)
                
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.error(f"截圖失敗: {e}")
                
    def set_theme(self, theme: str):
        """設置視覺化主題"""
        if theme == "dark":
            self.plot_widget.setBackground('k')  # 黑色背景
            # 更新LCD顯示主題
            for display in [getattr(self, attr, None) for attr in 
                           ['voltage_display', 'current_display', 'power_display', 'resistance_display']]:
                if display:
                    display.setStyleSheet(display.styleSheet().replace('black', '#2b2b2b'))
        else:
            self.plot_widget.setBackground('w')  # 白色背景