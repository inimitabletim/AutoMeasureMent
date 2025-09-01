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
                            QComboBox, QDoubleSpinBox, QCheckBox, QTextEdit,
                            QMessageBox, QProgressBar, QLCDNumber, QSplitter)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPalette
import pyqtgraph as pg
from pyqtgraph import PlotWidget

from src.rigol_dp711 import RigolDP711
from src.data_logger import DataLogger


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
        """設置用戶介面"""
        # 主布局
        main_layout = QHBoxLayout(self)
        
        # 左側控制面板
        left_panel = self.create_control_panel()
        main_layout.addWidget(left_panel, 1)
        
        # 右側顯示面板
        right_panel = self.create_display_panel()
        main_layout.addWidget(right_panel, 2)
        
    def create_control_panel(self):
        """創建左側控制面板"""
        control_widget = QWidget()
        layout = QVBoxLayout(control_widget)
        
        # 設備管理群組
        device_group = QGroupBox("設備管理")
        device_layout = QGridLayout(device_group)
        
        # 已連接設備選擇
        device_layout.addWidget(QLabel("當前設備:"), 0, 0)
        self.device_combo = QComboBox()
        self.device_combo.addItem("無設備連接")
        self.device_combo.currentTextChanged.connect(self.switch_device)
        device_layout.addWidget(self.device_combo, 0, 1, 1, 2)
        
        # 設備資訊顯示
        self.device_info_label = QLabel("狀態: 無設備連接")
        self.device_info_label.setWordWrap(True)
        device_layout.addWidget(self.device_info_label, 1, 0, 1, 3)
        
        layout.addWidget(device_group)
        
        # 連接控制群組
        connection_group = QGroupBox("新設備連接")
        conn_layout = QGridLayout(connection_group)
        
        conn_layout.addWidget(QLabel("可用端口:"), 0, 0)
        self.port_combo = QComboBox()
        conn_layout.addWidget(self.port_combo, 0, 1)
        
        self.scan_btn = QPushButton("🔄 掃描")
        self.scan_btn.clicked.connect(self.scan_ports)
        conn_layout.addWidget(self.scan_btn, 0, 2)
        
        conn_layout.addWidget(QLabel("波特率:"), 1, 0)
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.setCurrentText("9600")
        conn_layout.addWidget(self.baudrate_combo, 1, 1, 1, 2)
        
        self.connect_btn = QPushButton("連接設備")
        self.connect_btn.clicked.connect(self.connect_new_device)
        conn_layout.addWidget(self.connect_btn, 2, 0, 1, 3)
        
        # 設備控制按鈕
        control_layout = QHBoxLayout()
        self.disconnect_btn = QPushButton("斷開當前設備")
        self.disconnect_btn.clicked.connect(self.disconnect_current_device)
        self.disconnect_btn.setEnabled(False)
        
        self.disconnect_all_btn = QPushButton("斷開所有設備")
        self.disconnect_all_btn.clicked.connect(self.disconnect_all_devices)
        self.disconnect_all_btn.setEnabled(False)
        
        control_layout.addWidget(self.disconnect_btn)
        control_layout.addWidget(self.disconnect_all_btn)
        conn_layout.addLayout(control_layout, 3, 0, 1, 3)
        
        layout.addWidget(connection_group)
        
        # 電源輸出控制群組 (僅在有設備時啟用)
        power_group = QGroupBox("電源輸出控制")
        power_layout = QGridLayout(power_group)
        
        power_layout.addWidget(QLabel("電壓設定 (V):"), 0, 0)
        self.voltage_spin = QDoubleSpinBox()
        self.voltage_spin.setRange(0, 30.0)
        self.voltage_spin.setDecimals(3)
        self.voltage_spin.setSingleStep(0.1)
        self.voltage_spin.setValue(5.0)
        self.voltage_spin.setEnabled(False)
        power_layout.addWidget(self.voltage_spin, 0, 1)
        
        power_layout.addWidget(QLabel("電流限制 (A):"), 1, 0)
        self.current_spin = QDoubleSpinBox()
        self.current_spin.setRange(0, 5.0)
        self.current_spin.setDecimals(3)
        self.current_spin.setSingleStep(0.01)
        self.current_spin.setValue(1.0)
        self.current_spin.setEnabled(False)
        power_layout.addWidget(self.current_spin, 1, 1)
        
        # 快速設定按鈕
        quick_layout = QHBoxLayout()
        self.quick_3v3_btn = QPushButton("3.3V")
        self.quick_3v3_btn.clicked.connect(lambda: self.quick_set(3.3, 1.0))
        self.quick_3v3_btn.setEnabled(False)
        self.quick_5v_btn = QPushButton("5V")
        self.quick_5v_btn.clicked.connect(lambda: self.quick_set(5.0, 1.0))
        self.quick_5v_btn.setEnabled(False)
        self.quick_12v_btn = QPushButton("12V")
        self.quick_12v_btn.clicked.connect(lambda: self.quick_set(12.0, 1.0))
        self.quick_12v_btn.setEnabled(False)
        
        quick_layout.addWidget(self.quick_3v3_btn)
        quick_layout.addWidget(self.quick_5v_btn)
        quick_layout.addWidget(self.quick_12v_btn)
        power_layout.addLayout(quick_layout, 2, 0, 1, 2)
        
        # 輸出開關
        self.output_btn = QPushButton("開啟輸出")
        self.output_btn.clicked.connect(self.toggle_output)
        self.output_btn.setEnabled(False)
        power_layout.addWidget(self.output_btn, 3, 0, 1, 2)
        
        layout.addWidget(power_group)
        
        # 儲存控制面板引用以便更新狀態
        self.power_controls = [self.voltage_spin, self.current_spin, 
                              self.quick_3v3_btn, self.quick_5v_btn, 
                              self.quick_12v_btn, self.output_btn]
        
        # 保護設定群組
        protection_group = QGroupBox("保護設定")
        prot_layout = QGridLayout(protection_group)
        
        prot_layout.addWidget(QLabel("過壓保護 (V):"), 0, 0)
        self.ovp_spin = QDoubleSpinBox()
        self.ovp_spin.setRange(0.01, 33.0)
        self.ovp_spin.setDecimals(2)
        self.ovp_spin.setValue(31.0)
        self.ovp_spin.setEnabled(False)
        prot_layout.addWidget(self.ovp_spin, 0, 1)
        
        prot_layout.addWidget(QLabel("過流保護 (A):"), 1, 0)
        self.ocp_spin = QDoubleSpinBox()
        self.ocp_spin.setRange(0.001, 5.5)
        self.ocp_spin.setDecimals(3)
        self.ocp_spin.setValue(5.2)
        self.ocp_spin.setEnabled(False)
        prot_layout.addWidget(self.ocp_spin, 1, 1)
        
        self.ovp_enable = QCheckBox("啟用過壓保護")
        self.ovp_enable.setEnabled(False)
        self.ocp_enable = QCheckBox("啟用過流保護")
        self.ocp_enable.setEnabled(False)
        prot_layout.addWidget(self.ovp_enable, 2, 0, 1, 2)
        prot_layout.addWidget(self.ocp_enable, 3, 0, 1, 2)
        
        layout.addWidget(protection_group)
        
        # 儲存保護控制引用
        self.protection_controls = [self.ovp_spin, self.ocp_spin, 
                                   self.ovp_enable, self.ocp_enable]
        
        # 應用設定按鈕
        apply_layout = QHBoxLayout()
        self.apply_btn = QPushButton("應用設定")
        self.apply_btn.clicked.connect(self.apply_settings)
        self.apply_btn.setEnabled(False)
        apply_layout.addWidget(self.apply_btn)
        
        layout.addLayout(apply_layout)
        
        # 測量按鈕
        measure_layout = QHBoxLayout()
        self.start_measure_btn = QPushButton("開始測量")
        self.start_measure_btn.clicked.connect(self.toggle_measurement)
        self.start_measure_btn.setEnabled(False)
        self.stop_measure_btn = QPushButton("停止測量")
        self.stop_measure_btn.clicked.connect(self.stop_measurement)
        self.stop_measure_btn.setEnabled(False)
        
        measure_layout.addWidget(self.start_measure_btn)
        measure_layout.addWidget(self.stop_measure_btn)
        layout.addLayout(measure_layout)
        
        # 加入測量控制到控制項列表
        self.measurement_controls = [self.start_measure_btn]
        
        # 儲存所有需要啟用/停用的控制項
        self.all_controls = (self.power_controls + self.protection_controls + 
                            self.measurement_controls + [self.apply_btn])
        
        return control_widget
    
    def create_display_panel(self):
        """創建右側顯示面板"""
        display_widget = QWidget()
        layout = QVBoxLayout(display_widget)
        
        # 實時數據顯示
        data_group = QGroupBox("實時監控數據")
        data_layout = QGridLayout(data_group)
        
        # LCD 顯示器
        data_layout.addWidget(QLabel("電壓 (V):"), 0, 0)
        self.voltage_lcd = QLCDNumber(6)
        self.voltage_lcd.setStyleSheet("QLCDNumber { color: #2196F3; background-color: #000000; }")
        self.voltage_lcd.display("0.000")
        data_layout.addWidget(self.voltage_lcd, 0, 1)
        
        data_layout.addWidget(QLabel("電流 (A):"), 1, 0)
        self.current_lcd = QLCDNumber(6)
        self.current_lcd.setStyleSheet("QLCDNumber { color: #FF9800; background-color: #000000; }")
        self.current_lcd.display("0.000")
        data_layout.addWidget(self.current_lcd, 1, 1)
        
        data_layout.addWidget(QLabel("功率 (W):"), 2, 0)
        self.power_lcd = QLCDNumber(6)
        self.power_lcd.setStyleSheet("QLCDNumber { color: #4CAF50; background-color: #000000; }")
        self.power_lcd.display("0.000")
        data_layout.addWidget(self.power_lcd, 2, 1)
        
        data_layout.addWidget(QLabel("效率 (%):"), 3, 0)
        self.efficiency_lcd = QLCDNumber(6)
        self.efficiency_lcd.setStyleSheet("QLCDNumber { color: #9C27B0; background-color: #000000; }")
        self.efficiency_lcd.display("0.0")
        data_layout.addWidget(self.efficiency_lcd, 3, 1)
        
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
            
            # 獲取可用設備
            from src.port_manager import get_port_manager
            port_manager = get_port_manager()
            available_devices = port_manager.get_available_ports(exclude_connected=True)
            
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
        """連接新設備"""
        if self.port_combo.count() == 0 or self.port_combo.currentData() is None:
            QMessageBox.warning(self, "警告", "請先掃描端口並選擇一個有效的端口")
            return
            
        port = self.port_combo.currentData()
        baudrate = int(self.baudrate_combo.currentText())
        
        try:
            # 檢查是否已經連接此端口
            if port in self.connected_devices:
                # 切換到已連接的設備
                self.active_device_port = port
                self.dp711 = self.connected_devices[port]
                self.log_message(f"切換到已連接設備: {port}")
                self._update_device_ui()
                return
            
            # 創建新設備連接
            device = RigolDP711(port=port, baudrate=baudrate)
            
            if device.connect():
                # 添加到設備池
                self.connected_devices[port] = device
                self.active_device_port = port
                self.dp711 = device
                
                self.log_message(f"設備連接成功: {port}")
                self.log_message(f"設備資訊: {device.get_identity()}")
                
                # 更新UI
                self._update_device_ui()
                self._update_device_list()
                
                QMessageBox.information(self, "連接成功", 
                    f"成功連接到 Rigol DP711\n端口: {port}\n"
                    f"總連接設備: {len(self.connected_devices)}台")
            else:
                QMessageBox.critical(self, "連接失敗", f"無法連接到 {port}")
                self.log_message(f"連接失敗: {port}")
                
        except Exception as e:
            self.logger.error(f"連接設備時發生錯誤: {e}")
            QMessageBox.critical(self, "連接錯誤", f"連接過程中發生錯誤: {str(e)}")
    
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