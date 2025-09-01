#!/usr/bin/env python3
"""
連接管理Mixin
提供標準化的儀器連接UI和邏輯
"""

from typing import Dict, Any
from PyQt6.QtWidgets import (QGroupBox, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QLineEdit, QComboBox,
                            QCheckBox, QProgressBar)
from PyQt6.QtCore import pyqtSignal


class ConnectionMixin:
    """連接管理功能混入類"""
    
    # 連接相關信號
    connection_requested = pyqtSignal()
    disconnection_requested = pyqtSignal()
    connection_params_changed = pyqtSignal(dict)
    
    def create_connection_panel(self) -> QGroupBox:
        """創建標準化連接面板
        
        Returns:
            QGroupBox: 連接控制面板
        """
        connection_group = QGroupBox("連接設置")
        layout = QVBoxLayout(connection_group)
        
        # 連接參數區域
        params_layout = self._create_connection_params_layout()
        layout.addLayout(params_layout)
        
        # 連接控制區域
        control_layout = self._create_connection_control_layout()
        layout.addLayout(control_layout)
        
        # 連接狀態區域
        status_layout = self._create_connection_status_layout()
        layout.addLayout(status_layout)
        
        return connection_group
        
    def _create_connection_params_layout(self) -> QVBoxLayout:
        """創建連接參數設置區域"""
        layout = QVBoxLayout()
        
        # IP地址輸入 (適用於網路儀器)
        if self._supports_network_connection():
            ip_layout = QHBoxLayout()
            ip_layout.addWidget(QLabel("IP地址:"))
            
            self.ip_input = QLineEdit()
            self.ip_input.setPlaceholderText("192.168.0.100")
            self.ip_input.textChanged.connect(self._on_connection_params_changed)
            ip_layout.addWidget(self.ip_input)
            
            layout.addLayout(ip_layout)
            
            # 端口輸入
            port_layout = QHBoxLayout()
            port_layout.addWidget(QLabel("端口:"))
            
            self.port_input = QLineEdit()
            self.port_input.setPlaceholderText("5025")
            self.port_input.textChanged.connect(self._on_connection_params_changed)
            port_layout.addWidget(self.port_input)
            
            layout.addLayout(port_layout)
            
        # 串口設置 (適用於串口儀器)
        if self._supports_serial_connection():
            com_layout = QHBoxLayout()
            com_layout.addWidget(QLabel("串口:"))
            
            self.com_combo = QComboBox()
            self.com_combo.setEditable(True)
            self.com_combo.currentTextChanged.connect(self._on_connection_params_changed)
            com_layout.addWidget(self.com_combo)
            
            # 掃描按鈕
            self.scan_btn = QPushButton("掃描")
            self.scan_btn.clicked.connect(self._scan_serial_ports)
            com_layout.addWidget(self.scan_btn)
            
            layout.addLayout(com_layout)
            
            # 波特率設置
            baud_layout = QHBoxLayout()
            baud_layout.addWidget(QLabel("波特率:"))
            
            self.baud_combo = QComboBox()
            self.baud_combo.addItems(['9600', '19200', '38400', '57600', '115200'])
            self.baud_combo.currentTextChanged.connect(self._on_connection_params_changed)
            baud_layout.addWidget(self.baud_combo)
            
            layout.addLayout(baud_layout)
            
        # 超時設置
        timeout_layout = QHBoxLayout()
        timeout_layout.addWidget(QLabel("超時(秒):"))
        
        self.timeout_input = QLineEdit()
        self.timeout_input.setPlaceholderText("10.0")
        self.timeout_input.textChanged.connect(self._on_connection_params_changed)
        timeout_layout.addWidget(self.timeout_input)
        
        layout.addLayout(timeout_layout)
        
        # 自動重連選項
        self.auto_reconnect_cb = QCheckBox("自動重連")
        self.auto_reconnect_cb.toggled.connect(self._on_connection_params_changed)
        layout.addWidget(self.auto_reconnect_cb)
        
        return layout
        
    def _create_connection_control_layout(self) -> QHBoxLayout:
        """創建連接控制區域"""
        layout = QHBoxLayout()
        
        # 連接按鈕
        self.connect_btn = QPushButton("連接")
        self.connect_btn.clicked.connect(self._on_connect_clicked)
        layout.addWidget(self.connect_btn)
        
        # 斷開按鈕
        self.disconnect_btn = QPushButton("斷開")
        self.disconnect_btn.clicked.connect(self._on_disconnect_clicked)
        self.disconnect_btn.setEnabled(False)
        layout.addWidget(self.disconnect_btn)
        
        # 測試連接按鈕
        self.test_btn = QPushButton("測試")
        self.test_btn.clicked.connect(self._on_test_connection)
        layout.addWidget(self.test_btn)
        
        return layout
        
    def _create_connection_status_layout(self) -> QVBoxLayout:
        """創建連接狀態顯示區域"""
        layout = QVBoxLayout()
        
        # 連接進度條
        self.connection_progress = QProgressBar()
        self.connection_progress.setVisible(False)
        layout.addWidget(self.connection_progress)
        
        # 設備信息顯示
        self.device_info_label = QLabel("設備: 未連接")
        self.device_info_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(self.device_info_label)
        
        return layout
        
    def _supports_network_connection(self) -> bool:
        """檢查是否支援網路連接 - 子類覆蓋"""
        return hasattr(self, 'instrument_type') and 'keithley' in getattr(self, 'instrument_type', '')
        
    def _supports_serial_connection(self) -> bool:
        """檢查是否支援串口連接 - 子類覆蓋"""
        return hasattr(self, 'instrument_type') and 'rigol' in getattr(self, 'instrument_type', '')
        
    def _scan_serial_ports(self):
        """掃描可用串口"""
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            
            self.com_combo.clear()
            for port in ports:
                self.com_combo.addItem(f"{port.device} - {port.description}")
                
        except ImportError:
            if hasattr(self, 'logger'):
                self.logger.warning("pyserial未安裝，無法掃描串口")
                
    def _on_connect_clicked(self):
        """連接按鈕點擊處理"""
        self.connect_btn.setEnabled(False)
        self.connection_progress.setVisible(True)
        self.connection_progress.setRange(0, 0)  # 不定進度
        
        self.connection_requested.emit()
        
    def _on_disconnect_clicked(self):
        """斷開按鈕點擊處理"""
        self.disconnect_btn.setEnabled(False)
        self.disconnection_requested.emit()
        
    def _on_test_connection(self):
        """測試連接"""
        # 簡單的連接測試
        params = self.get_current_connection_params()
        if hasattr(self, 'logger'):
            self.logger.info(f"測試連接參數: {params}")
            
    def _on_connection_params_changed(self):
        """連接參數變化處理"""
        params = self.get_current_connection_params()
        self.connection_params_changed.emit(params)
        
    def get_current_connection_params(self) -> Dict[str, Any]:
        """獲取當前連接參數"""
        params = {}
        
        # 網路參數
        if hasattr(self, 'ip_input') and self.ip_input.text():
            params['ip_address'] = self.ip_input.text().strip()
            
        if hasattr(self, 'port_input') and self.port_input.text():
            try:
                params['port'] = int(self.port_input.text().strip())
            except ValueError:
                pass
                
        # 串口參數
        if hasattr(self, 'com_combo') and self.com_combo.currentText():
            com_text = self.com_combo.currentText()
            # 提取COM端口名稱 (如果有描述的話)
            if ' - ' in com_text:
                params['port'] = com_text.split(' - ')[0]
            else:
                params['port'] = com_text
                
        if hasattr(self, 'baud_combo') and self.baud_combo.currentText():
            try:
                params['baudrate'] = int(self.baud_combo.currentText())
            except ValueError:
                pass
                
        # 通用參數
        if hasattr(self, 'timeout_input') and self.timeout_input.text():
            try:
                params['timeout'] = float(self.timeout_input.text().strip())
            except ValueError:
                pass
                
        if hasattr(self, 'auto_reconnect_cb'):
            params['auto_reconnect'] = self.auto_reconnect_cb.isChecked()
            
        return params
        
    def update_connection_status(self, connected: bool, device_info: str = ""):
        """更新連接狀態顯示"""
        if connected:
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.device_info_label.setText(f"設備: {device_info}")
            self.device_info_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.device_info_label.setText("設備: 未連接")
            self.device_info_label.setStyleSheet("color: #e74c3c; font-style: italic;")
            
        # 隱藏進度條
        self.connection_progress.setVisible(False)
        
    def update_connection_progress(self, progress: int):
        """更新連接進度"""
        if progress >= 0:
            self.connection_progress.setRange(0, 100)
            self.connection_progress.setValue(progress)
        else:
            self.connection_progress.setRange(0, 0)  # 不定進度
            
    def load_connection_settings(self, settings: Dict[str, Any]):
        """載入連接設置"""
        if hasattr(self, 'ip_input') and 'ip_address' in settings:
            self.ip_input.setText(settings['ip_address'])
            
        if hasattr(self, 'port_input') and 'port' in settings:
            self.port_input.setText(str(settings['port']))
            
        if hasattr(self, 'com_combo') and 'port' in settings:
            self.com_combo.setCurrentText(settings['port'])
            
        if hasattr(self, 'baud_combo') and 'baudrate' in settings:
            self.baud_combo.setCurrentText(str(settings['baudrate']))
            
        if hasattr(self, 'timeout_input') and 'timeout' in settings:
            self.timeout_input.setText(str(settings['timeout']))
            
        if hasattr(self, 'auto_reconnect_cb') and 'auto_reconnect' in settings:
            self.auto_reconnect_cb.setChecked(settings['auto_reconnect'])