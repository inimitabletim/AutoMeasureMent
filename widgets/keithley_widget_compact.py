#!/usr/bin/env python3
"""
Keithley Widget 簡潔專業版
專業儀器控制界面設計，注重實用性和專業外觀
"""

import time
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import pyqtgraph as pg

from widgets.base.instrument_widget_base import InstrumentWidgetBase
from widgets.unit_input_widget import UnitInputWidget
from src.workers.measurement_worker import MeasurementWorker, ContinuousMeasurementStrategy
from src.workers.base_worker import UnifiedWorkerBase


class CompactKeithleyWidget(InstrumentWidgetBase):
    """Keithley 2461 簡潔專業控制界面
    
    設計理念：
    - 信息密度適中，避免視覺混亂
    - 操作流程清晰，符合專業用戶習慣
    - 數據展示直觀，重點突出
    """
    
    def __init__(self, instrument=None, parent=None):
        # 初始化模式設定
        self.keithley_measurement_mode = "continuous"
        self.source_function = "VOLT"
        self.keithley_measurement_data = []
        
        super().__init__("keithley_2461", instrument, parent)
        
        # 專業主題設定
        self.setStyleSheet(self._get_professional_stylesheet())
        
    def _setup_instrument_ui(self):
        """設置簡潔專業的儀器界面"""
        # 清空預設的儀器控制區域
        layout = self.instrument_controls_layout
        
        # === 頂部狀態欄 ===
        self._create_status_header()
        
        # === 主要內容區域 ===
        main_content = QWidget()
        main_layout = QHBoxLayout(main_content)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        
        # 左側控制面板 (30%)
        self._create_control_panel(main_layout)
        
        # 右側數據顯示區 (70%)  
        self._create_data_display_panel(main_layout)
        
        layout.addWidget(main_content)
        
        # === 底部快速控制 ===
        self._create_quick_controls()
        
    def _create_status_header(self):
        """創建簡潔的頂部狀態欄"""
        header = QFrame()
        header.setFrameStyle(QFrame.Shape.StyledPanel)
        header.setMaximumHeight(50)
        header_layout = QHBoxLayout(header)
        
        # 儀器標識
        instrument_info = QLabel("KEITHLEY 2461")
        instrument_info.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        instrument_info.setStyleSheet("color: #2E86AB; font-weight: bold;")
        
        # 連接狀態（簡潔版）
        self.compact_status = QLabel("🔴 離線")
        self.compact_status.setFont(QFont("Arial", 10))
        
        # 測量狀態
        self.measure_status = QLabel("⏸️ 待機")
        self.measure_status.setFont(QFont("Arial", 10))
        
        # 彈性空間
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        header_layout.addWidget(instrument_info)
        header_layout.addItem(spacer)
        header_layout.addWidget(self.compact_status)
        header_layout.addWidget(self.measure_status)
        
        self.instrument_controls_layout.addWidget(header)
        
    def _create_control_panel(self, parent_layout):
        """創建緊湊的控制面板"""
        control_panel = QFrame()
        control_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        control_panel.setMaximumWidth(300)
        control_layout = QVBoxLayout(control_panel)
        
        # === 源設定區域 ===
        source_group = QGroupBox("電源設定")
        source_layout = QGridLayout(source_group)
        
        # 輸出電壓
        source_layout.addWidget(QLabel("電壓(V):"), 0, 0)
        self.voltage_input = UnitInputWidget(
            unit_symbol="V", default_prefix="", precision=6
        )
        self.voltage_input.set_base_value(1.8)
        source_layout.addWidget(self.voltage_input, 0, 1)
        
        # 電流限制
        source_layout.addWidget(QLabel("電流限制:"), 1, 0)
        self.current_limit_input = UnitInputWidget(
            unit_symbol="A", default_prefix="m", precision=3
        )
        self.current_limit_input.set_base_value(0.002)
        source_layout.addWidget(self.current_limit_input, 1, 1)
        
        # 輸出控制按鈕
        output_layout = QHBoxLayout()
        self.output_btn = QPushButton("輸出 OFF")
        self.output_btn.setCheckable(True)
        self.output_btn.clicked.connect(self._toggle_output)
        self.output_btn.setStyleSheet("""
            QPushButton { 
                background-color: #E74C3C; 
                color: white; 
                font-weight: bold; 
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:checked { 
                background-color: #27AE60; 
            }
        """)
        output_layout.addWidget(self.output_btn)
        
        source_layout.addLayout(output_layout, 2, 0, 1, 2)
        control_layout.addWidget(source_group)
        
        # === 測量控制 ===
        measure_group = QGroupBox("測量控制")
        measure_layout = QVBoxLayout(measure_group)
        
        # 測量間隔
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("間隔(ms):"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(1000)
        interval_layout.addWidget(self.interval_spin)
        measure_layout.addLayout(interval_layout)
        
        # 測量按鈕
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 開始")
        self.stop_btn = QPushButton("⏹ 停止")
        self.single_btn = QPushButton("◉ 單次")
        
        self.start_btn.clicked.connect(self._start_measurement)
        self.stop_btn.clicked.connect(self._stop_measurement)
        self.single_btn.clicked.connect(self._single_measurement)
        
        for btn in [self.start_btn, self.stop_btn, self.single_btn]:
            btn.setMinimumHeight(35)
            
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.single_btn)
        measure_layout.addLayout(button_layout)
        
        control_layout.addWidget(measure_group)
        
        # === 統計信息（簡化版）===
        stats_group = QGroupBox("測量統計")
        stats_layout = QGridLayout(stats_group)
        
        self.stats_labels = {}
        stats_items = [
            ("測量次數", "count"),
            ("平均電壓", "avg_v"),
            ("平均電流", "avg_i"),
            ("平均功率", "avg_p")
        ]
        
        for i, (label, key) in enumerate(stats_items):
            stats_layout.addWidget(QLabel(f"{label}:"), i, 0)
            self.stats_labels[key] = QLabel("--")
            self.stats_labels[key].setStyleSheet("font-weight: bold; color: #2E86AB;")
            stats_layout.addWidget(self.stats_labels[key], i, 1)
            
        control_layout.addWidget(stats_group)
        
        # 彈性空間
        control_layout.addStretch()
        
        parent_layout.addWidget(control_panel)
        
    def _create_data_display_panel(self, parent_layout):
        """創建數據顯示面板"""
        display_panel = QFrame()
        display_panel.setFrameStyle(QFrame.Shape.StyledPanel)
        display_layout = QVBoxLayout(display_panel)
        
        # === LCD 數值顯示（緊湊版）===
        lcd_frame = QFrame()
        lcd_frame.setMaximumHeight(120)
        lcd_layout = QGridLayout(lcd_frame)
        
        # 創建四個LCD顯示器
        self.lcd_displays = {}
        lcd_configs = [
            ("電壓", "voltage", "V", 0, 0, "#2E86AB"),
            ("電流", "current", "mA", 0, 1, "#E74C3C"),
            ("電阻", "resistance", "Ω", 1, 0, "#F39C12"),
            ("功率", "power", "mW", 1, 1, "#27AE60")
        ]
        
        for label, key, unit, row, col, color in lcd_configs:
            container = QFrame()
            container.setFrameStyle(QFrame.Shape.StyledPanel)
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(5, 2, 5, 2)
            
            # 標籤
            label_widget = QLabel(label)
            label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label_widget.setFont(QFont("Arial", 9))
            
            # LCD 顯示
            lcd = QLCDNumber(8)
            lcd.setDigitCount(8)
            lcd.setSegmentStyle(QLCDNumber.SegmentStyle.Flat)
            lcd.setMinimumHeight(40)
            lcd.setStyleSheet(f"""
                QLCDNumber {{
                    background-color: #2C3E50;
                    color: {color};
                    border: 1px solid #34495E;
                }}
            """)
            lcd.display("0.000000")
            self.lcd_displays[key] = lcd
            
            # 單位標籤
            unit_label = QLabel(unit)
            unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            unit_label.setFont(QFont("Arial", 8))
            unit_label.setStyleSheet(f"color: {color}; font-weight: bold;")
            
            container_layout.addWidget(label_widget)
            container_layout.addWidget(lcd)
            container_layout.addWidget(unit_label)
            
            lcd_layout.addWidget(container, row, col)
            
        display_layout.addWidget(lcd_frame)
        
        # === 實時圖表 ===
        self._create_compact_chart(display_layout)
        
        parent_layout.addWidget(display_panel)
        
    def _create_compact_chart(self, parent_layout):
        """創建緊湊的實時圖表"""
        # 圖表容器
        chart_widget = pg.PlotWidget()
        chart_widget.setBackground('#2C3E50')
        chart_widget.setLabel('left', '電流 (mA)', color='#ECF0F1')
        chart_widget.setLabel('bottom', '時間 (s)', color='#ECF0F1')
        chart_widget.showGrid(x=True, y=True, alpha=0.3)
        chart_widget.setMinimumHeight(300)
        
        # 設定專業的軸線樣式
        chart_widget.getAxis('left').setPen(pg.mkPen(color='#ECF0F1', width=1))
        chart_widget.getAxis('bottom').setPen(pg.mkPen(color='#ECF0F1', width=1))
        chart_widget.getAxis('left').setTextPen(pg.mkPen(color='#ECF0F1'))
        chart_widget.getAxis('bottom').setTextPen(pg.mkPen(color='#ECF0F1'))
        
        # 數據曲線
        self.current_curve = chart_widget.plot(
            pen=pg.mkPen(color='#E74C3C', width=2),
            symbol='o', symbolSize=4, symbolBrush='#E74C3C'
        )
        
        # 數據存儲
        self.time_data = []
        self.current_data = []
        self.max_points = 100  # 限制顯示點數
        
        self.chart_widget = chart_widget
        parent_layout.addWidget(chart_widget)
        
    def _create_quick_controls(self):
        """創建底部快速控制欄"""
        quick_panel = QFrame()
        quick_panel.setMaximumHeight(40)
        quick_layout = QHBoxLayout(quick_panel)
        
        # 數據管理按鈕
        self.save_btn = QPushButton("💾 保存數據")
        self.clear_btn = QPushButton("🗑️ 清除")
        self.export_btn = QPushButton("📤 導出")
        
        self.save_btn.clicked.connect(self._save_data)
        self.clear_btn.clicked.connect(self._clear_data)
        self.export_btn.clicked.connect(self._export_data)
        
        quick_layout.addWidget(self.save_btn)
        quick_layout.addWidget(self.clear_btn)
        quick_layout.addWidget(self.export_btn)
        quick_layout.addStretch()
        
        self.instrument_controls_layout.addWidget(quick_panel)
        
    def _get_professional_stylesheet(self):
        """專業儀器風格樣式表"""
        return """
        QWidget {
            background-color: #34495E;
            color: #ECF0F1;
            font-family: 'Arial', sans-serif;
        }
        
        QGroupBox {
            font-weight: bold;
            border: 2px solid #2C3E50;
            border-radius: 5px;
            margin-top: 1ex;
            padding: 5px;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
            color: #3498DB;
        }
        
        QPushButton {
            background-color: #3498DB;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #2980B9;
        }
        
        QPushButton:pressed {
            background-color: #21618C;
        }
        
        QSpinBox, QDoubleSpinBox {
            background-color: #2C3E50;
            border: 1px solid #34495E;
            border-radius: 3px;
            padding: 5px;
            color: #ECF0F1;
        }
        
        QLabel {
            color: #BDC3C7;
        }
        
        QFrame[frameShape="4"] {
            border: 1px solid #2C3E50;
            background-color: #2C3E50;
        }
        """
        
    # === 核心功能實現 ===
    def get_connection_params(self) -> Dict[str, Any]:
        """獲取連接參數"""
        return {
            'ip_address': '192.168.0.100',
            'port': 5025,
            'timeout': 10
        }
        
    def create_instrument_controls(self) -> QWidget:
        """創建儀器控制組件"""
        return QWidget()  # 已在 _setup_instrument_ui 中實現
        
    def _create_measurement_worker(self) -> Optional[UnifiedWorkerBase]:
        """創建測量Worker"""
        if not self.is_connected:
            return None
            
        strategy = ContinuousMeasurementStrategy()
        params = {'interval_ms': self.interval_spin.value()}
        
        try:
            worker = MeasurementWorker(self.instrument, strategy, params)
            worker.data_ready.connect(self._on_compact_data_ready)
            return worker
        except Exception as e:
            self.logger.error(f"Worker創建失敗: {e}")
            return None
            
    # === 事件處理 ===
    def _toggle_output(self):
        """切換輸出狀態"""
        if not self.is_connected:
            return
            
        if self.output_btn.isChecked():
            # 應用設定並開啟輸出
            voltage = self.voltage_input.get_base_value()
            current_limit = self.current_limit_input.get_base_value()
            
            self.instrument.set_voltage(voltage, current_limit)
            self.instrument.output_on()
            
            self.output_btn.setText("輸出 ON")
            self.output_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #27AE60; 
                    color: white; 
                    font-weight: bold; 
                    padding: 8px;
                    border-radius: 4px;
                }
            """)
        else:
            self.instrument.output_off()
            self.output_btn.setText("輸出 OFF")
            self.output_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #E74C3C; 
                    color: white; 
                    font-weight: bold; 
                    padding: 8px;
                    border-radius: 4px;
                }
            """)
            
    def _start_measurement(self):
        """開始測量"""
        self.start_measurement()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.measure_status.setText("▶ 測量中")
        
    def _stop_measurement(self):
        """停止測量"""
        self.stop_measurement()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.measure_status.setText("⏸️ 待機")
        
    def _single_measurement(self):
        """單次測量"""
        if not self.is_connected:
            return
            
        try:
            v, i, r, p = self.instrument.measure_all()
            self._update_displays(v, i, r, p)
        except Exception as e:
            self.logger.error(f"單次測量失敗: {e}")
            
    def _on_compact_data_ready(self, data: Dict[str, Any]):
        """處理測量數據（簡潔版）"""
        v = data.get('voltage', 0)
        i = data.get('current', 0) 
        r = data.get('resistance', 0)
        p = data.get('power', 0)
        
        self._update_displays(v, i, r, p)
        self._update_chart(i)
        self._update_compact_statistics()
        
    def _update_displays(self, voltage, current, resistance, power):
        """更新LCD顯示"""
        self.lcd_displays['voltage'].display(f"{voltage:.6f}")
        self.lcd_displays['current'].display(f"{current*1000:.3f}")  # 轉換為mA
        self.lcd_displays['resistance'].display(f"{resistance:.2f}")
        self.lcd_displays['power'].display(f"{power*1000:.3f}")  # 轉換為mW
        
    def _update_chart(self, current):
        """更新圖表"""
        current_time = time.time()
        if not hasattr(self, 'start_time'):
            self.start_time = current_time
            
        elapsed = current_time - self.start_time
        
        self.time_data.append(elapsed)
        self.current_data.append(current * 1000)  # 轉換為mA
        
        # 限制數據點數量
        if len(self.time_data) > self.max_points:
            self.time_data.pop(0)
            self.current_data.pop(0)
            
        # 更新曲線
        self.current_curve.setData(self.time_data, self.current_data)
        
    def _update_compact_statistics(self):
        """更新統計信息（簡潔版）"""
        if not self.current_data:
            return
            
        self.stats_labels['count'].setText(str(len(self.current_data)))
        
        if len(self.current_data) > 0:
            # 計算最近數據的統計
            recent_data = self.current_data[-20:]  # 最近20個點
            avg_current = np.mean(recent_data)
            
            self.stats_labels['avg_i'].setText(f"{avg_current:.3f} mA")
            
        # 更新其他統計（簡化）
        if hasattr(self, 'lcd_displays'):
            voltage_val = float(self.lcd_displays['voltage'].value())
            power_val = float(self.lcd_displays['power'].value())
            
            self.stats_labels['avg_v'].setText(f"{voltage_val:.3f} V")
            self.stats_labels['avg_p'].setText(f"{power_val:.3f} mW")
            
    # === 數據管理 ===
    def _save_data(self):
        """保存數據"""
        # TODO: 實現數據保存邏輯
        pass
        
    def _clear_data(self):
        """清除數據"""
        self.time_data.clear()
        self.current_data.clear()
        self.current_curve.setData([], [])
        
        # 重置統計
        for label in self.stats_labels.values():
            label.setText("--")
            
    def _export_data(self):
        """導出數據"""
        # TODO: 實現數據導出邏輯
        pass
        
    # === 連接狀態處理 ===
    def _on_connection_changed(self, connected: bool, info: str):
        """連接狀態變化處理"""
        super()._on_connection_changed(connected, info)
        
        if connected:
            self.compact_status.setText("🟢 在線")
            self.compact_status.setStyleSheet("color: #27AE60; font-weight: bold;")
        else:
            self.compact_status.setText("🔴 離線")
            self.compact_status.setStyleSheet("color: #E74C3C; font-weight: bold;")