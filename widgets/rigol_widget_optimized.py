#!/usr/bin/env python3
"""
Rigol DP711 優化Widget
使用新的統一架構重構的Rigol控制介面
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLabel, QDoubleSpinBox, QComboBox, QPushButton,
                            QListWidget, QListWidgetItem, QSplitter)
from PyQt6.QtCore import pyqtSignal, QTimer

from widgets.base import InstrumentWidgetBase
from src.rigol_dp711 import RigolDP711
from src.workers import MeasurementWorker
from src.workers.measurement_worker import ContinuousMeasurementStrategy
from src.workers.base_worker import UnifiedWorkerBase
from src.multi_device_manager import get_multi_device_manager
from src.port_manager import DeviceInfo
from src.config import get_config


class OptimizedRigolWidget(InstrumentWidgetBase):
    """優化的Rigol DP711控制Widget
    
    使用新的統一架構，支援多設備管理：
    - 繼承InstrumentWidgetBase獲得標準功能
    - 整合多設備管理系統
    - 使用統一的Worker系統進行測量
    - 標準化的UI組件和主題支援
    """
    
    # 多設備特定信號
    device_list_changed = pyqtSignal(list)
    active_device_changed = pyqtSignal(str, str)  # port, device_id
    
    def __init__(self, parent=None):
        """初始化優化Rigol Widget"""
        # 初始化基類 (暫時不傳入儀器實例，因為支援多設備)
        super().__init__("rigol_dp711", None, parent)
        
        # 多設備管理
        self.device_manager = get_multi_device_manager()
        self.available_devices: List[DeviceInfo] = []
        self.current_device_info: Optional[DeviceInfo] = None
        
        # 設備掃描定時器
        self.device_scan_timer = QTimer()
        self.device_scan_timer.timeout.connect(self._scan_devices)
        self.device_scan_timer.start(3000)  # 每3秒掃描一次
        
        # Rigol特定屬性
        self.output_enabled = False
        
    def _setup_instrument_ui(self):
        """設置Rigol特定的UI組件"""
        # 確保attributes已初始化
        if not hasattr(self, 'available_devices'):
            self.available_devices: List[DeviceInfo] = []
        if not hasattr(self, 'current_device_info'):
            self.current_device_info: Optional[DeviceInfo] = None
            
        # 創建多設備管理面板
        device_panel = self._create_device_management_panel()
        self.instrument_controls_layout.addWidget(device_panel)
        
        # 創建Rigol控制面板
        controls_widget = self.create_instrument_controls()
        self.instrument_controls_layout.addWidget(controls_widget)
        
        # 載入Rigol特定配置
        self._load_rigol_settings()
        
        # 連接Rigol特定信號
        self._connect_rigol_signals()
        
        # 初始掃描設備 - 使用QTimer延遲執行確保完全初始化
        QTimer.singleShot(100, self._scan_devices)
        
    def _create_device_management_panel(self) -> QGroupBox:
        """創建多設備管理面板"""
        device_group = QGroupBox("設備管理")
        layout = QVBoxLayout(device_group)
        
        # 設備列表
        list_layout = QHBoxLayout()
        list_layout.addWidget(QLabel("可用設備:"))
        
        self.device_list = QListWidget()
        self.device_list.itemClicked.connect(self._on_device_selected)
        list_layout.addWidget(self.device_list)
        
        # 設備控制按鈕
        button_layout = QVBoxLayout()
        
        self.scan_devices_btn = QPushButton("掃描設備")
        self.scan_devices_btn.clicked.connect(self._manual_scan_devices)
        button_layout.addWidget(self.scan_devices_btn)
        
        self.connect_device_btn = QPushButton("連接選中設備")
        self.connect_device_btn.clicked.connect(self._connect_selected_device)
        self.connect_device_btn.setEnabled(False)
        button_layout.addWidget(self.connect_device_btn)
        
        button_layout.addStretch()
        list_layout.addLayout(button_layout)
        
        layout.addLayout(list_layout)
        
        # 當前設備信息
        self.current_device_label = QLabel("當前設備: 未選中")
        self.current_device_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        layout.addWidget(self.current_device_label)
        
        return device_group
        
    def create_instrument_controls(self) -> QWidget:
        """創建Rigol特定控制組件"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 輸出設置
        output_group = QGroupBox("輸出設置")
        output_layout = QVBoxLayout(output_group)
        
        # 電壓設置
        voltage_layout = QHBoxLayout()
        voltage_layout.addWidget(QLabel("輸出電壓:"))
        
        self.voltage_spinbox = QDoubleSpinBox()
        self.voltage_spinbox.setRange(0.0, 30.0)
        self.voltage_spinbox.setDecimals(2)
        self.voltage_spinbox.setSuffix(" V")
        self.voltage_spinbox.valueChanged.connect(self._on_voltage_changed)
        voltage_layout.addWidget(self.voltage_spinbox)
        
        output_layout.addLayout(voltage_layout)
        
        # 電流限制設置
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel("電流限制:"))
        
        self.current_limit_spinbox = QDoubleSpinBox()
        self.current_limit_spinbox.setRange(0.01, 5.0)
        self.current_limit_spinbox.setDecimals(2)
        self.current_limit_spinbox.setValue(1.0)
        self.current_limit_spinbox.setSuffix(" A")
        self.current_limit_spinbox.valueChanged.connect(self._on_current_limit_changed)
        current_layout.addWidget(self.current_limit_spinbox)
        
        output_layout.addLayout(current_layout)
        
        layout.addWidget(output_group)
        
        # 輸出控制
        control_group = QGroupBox("輸出控制")
        control_layout = QVBoxLayout(control_group)
        
        # 輸出開關
        self.output_button = QPushButton("開啟輸出")
        self.output_button.setCheckable(True)
        self.output_button.clicked.connect(self._on_output_toggle)
        self.output_button.setEnabled(False)  # 需要先連接設備
        control_layout.addWidget(self.output_button)
        
        # 輸出狀態顯示
        self.output_status_label = QLabel("輸出: 關閉")
        self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        control_layout.addWidget(self.output_status_label)
        
        layout.addWidget(control_group)
        
        # 安全設置
        safety_group = QGroupBox("安全設置")
        safety_layout = QVBoxLayout(safety_group)
        
        # OVP (Over Voltage Protection)
        ovp_layout = QHBoxLayout()
        ovp_layout.addWidget(QLabel("過壓保護:"))
        
        self.ovp_spinbox = QDoubleSpinBox()
        self.ovp_spinbox.setRange(0.1, 33.0)
        self.ovp_spinbox.setDecimals(1)
        self.ovp_spinbox.setValue(31.0)
        self.ovp_spinbox.setSuffix(" V")
        ovp_layout.addWidget(self.ovp_spinbox)
        
        safety_layout.addLayout(ovp_layout)
        
        # OCP (Over Current Protection)
        ocp_layout = QHBoxLayout()
        ocp_layout.addWidget(QLabel("過流保護:"))
        
        self.ocp_spinbox = QDoubleSpinBox()
        self.ocp_spinbox.setRange(0.01, 5.5)
        self.ocp_spinbox.setDecimals(2)
        self.ocp_spinbox.setValue(5.2)
        self.ocp_spinbox.setSuffix(" A")
        ocp_layout.addWidget(self.ocp_spinbox)
        
        safety_layout.addLayout(ocp_layout)
        
        layout.addWidget(safety_group)
        
        return widget
        
    def get_connection_params(self) -> Dict[str, Any]:
        """獲取Rigol連接參數"""
        # 從ConnectionMixin獲取基本參數
        params = self.get_current_connection_params()
        
        # 如果有選中的設備，使用設備信息
        if self.current_device_info:
            params['port'] = self.current_device_info.port
            params['baudrate'] = getattr(self.current_device_info, 'baudrate', 9600)
        
        # 設置Rigol特定的預設值
        if 'baudrate' not in params:
            config = self.config.get_instrument_config('rigol_dp711')
            params['baudrate'] = config.get('connection', {}).get('default_baudrate', 9600)
            
        if 'timeout' not in params:
            params['timeout'] = 5.0
            
        return params
        
    def _create_measurement_worker(self) -> Optional[UnifiedWorkerBase]:
        """創建Rigol測量Worker"""
        if not self.is_connected or not self.instrument:
            return None
            
        # Rigol主要使用連續測量
        measurement_params = self.get_current_measurement_params()
        strategy = ContinuousMeasurementStrategy()
        return MeasurementWorker(self.instrument, strategy, measurement_params)
        
    def _load_rigol_settings(self):
        """載入Rigol特定設置"""
        config = self.config.get_instrument_config('rigol_dp711')
        
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
            self.ovp_spinbox.setMaximum(safety_config['max_voltage'] + 3)
        if safety_config.get('max_current'):
            self.current_limit_spinbox.setMaximum(safety_config['max_current'])
            self.ocp_spinbox.setMaximum(safety_config['max_current'] + 0.5)
            
    def _connect_rigol_signals(self):
        """連接Rigol特定信號"""
        # 設備管理信號
        self.device_list_changed.connect(self._update_device_list)
        self.active_device_changed.connect(self._on_active_device_changed)
        
        # 標準連接信號
        self.connection_requested.connect(self._connect_selected_device)
        self.disconnection_requested.connect(self.disconnect_instrument)
        
        # 測量控制信號
        self.measurement_started.connect(self.start_measurement)
        self.measurement_stopped.connect(self.stop_measurement)
        self.single_measurement_requested.connect(self._perform_single_measurement)
        
    def _scan_devices(self):
        """掃描可用的Rigol設備"""
        try:
            # 使用端口管理器掃描COM端口
            from src.port_manager import get_port_manager
            port_manager = get_port_manager()
            
            # 獲取所有可用端口
            available_ports = port_manager.get_available_ports()
            
            # 過濾出可能的Rigol設備 (簡化實現)
            rigol_devices = []
            for port_info in available_ports:
                # 這裡可以添加更智能的設備識別邏輯
                if not port_info.is_connected:
                    rigol_devices.append(port_info)
                    
            # 更新設備列表
            if rigol_devices != self.available_devices:
                self.available_devices = rigol_devices
                self.device_list_changed.emit(rigol_devices)
                
        except Exception as e:
            self.logger.error(f"設備掃描失敗: {e}")
            
    def _manual_scan_devices(self):
        """手動掃描設備"""
        self.scan_devices_btn.setText("掃描中...")
        self.scan_devices_btn.setEnabled(False)
        
        self._scan_devices()
        
        # 重置按鈕狀態
        QTimer.singleShot(1000, lambda: (
            self.scan_devices_btn.setText("掃描設備"),
            self.scan_devices_btn.setEnabled(True)
        ))
        
    def _update_device_list(self, devices: List[DeviceInfo]):
        """更新設備列表顯示"""
        self.device_list.clear()
        
        for device in devices:
            item = QListWidgetItem(str(device))
            item.setData(32, device)  # Qt.UserRole = 32
            self.device_list.addItem(item)
            
        self.status_changed.emit(f"發現 {len(devices)} 個可用設備")
        
    def _on_device_selected(self, item: QListWidgetItem):
        """設備選擇處理"""
        device_info = item.data(32)
        self.current_device_info = device_info
        self.connect_device_btn.setEnabled(True)
        
        self.current_device_label.setText(f"選中設備: {device_info.port}")
        self.current_device_label.setStyleSheet("color: #3498db; font-weight: bold;")
        
    def _connect_selected_device(self):
        """連接選中的設備"""
        if not self.current_device_info:
            self.error_occurred.emit("no_device_selected", "請先選擇要連接的設備")
            return
            
        try:
            # 創建Rigol儀器實例
            self.instrument = RigolDP711(port=self.current_device_info.port)
            
            # 嘗試連接
            connection_params = self.get_connection_params()
            if self.instrument.connect(connection_params):
                self.is_connected = True
                self.connection_changed.emit(True, f"已連接到 {self.current_device_info.port}")
                
                # 更新UI狀態
                self.connect_device_btn.setText("斷開設備")
                self.connect_device_btn.clicked.disconnect()
                self.connect_device_btn.clicked.connect(self.disconnect_instrument)
                
                self.output_button.setEnabled(True)
                
                # 發送設備變更信號
                device_id = getattr(self.current_device_info, 'device_id', self.current_device_info.port)
                self.active_device_changed.emit(self.current_device_info.port, device_id)
                
                self.status_changed.emit("設備連接成功")
            else:
                self.error_occurred.emit("connection_failed", "無法連接到選中的設備")
                
        except Exception as e:
            self.error_occurred.emit("connection_error", str(e))
            
    def _on_active_device_changed(self, port: str, device_id: str):
        """當前設備變更處理"""
        self.current_device_label.setText(f"當前設備: {port} ({device_id})")
        self.current_device_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        
    def _on_voltage_changed(self, voltage: float):
        """電壓值變化處理"""
        if self.is_connected and self.instrument:
            try:
                self.instrument.set_voltage(voltage)
                self.status_changed.emit(f"電壓設定為 {voltage:.2f}V")
            except Exception as e:
                self.error_occurred.emit("voltage_set_error", str(e))
                
    def _on_current_limit_changed(self, current: float):
        """電流限制變化處理"""
        if self.is_connected and self.instrument:
            try:
                self.instrument.set_current(current)
                self.status_changed.emit(f"電流限制設定為 {current:.2f}A")
            except Exception as e:
                self.error_occurred.emit("current_limit_error", str(e))
                
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
                self.output_enabled = True
                self.status_changed.emit("輸出已開啟")
            else:
                self.instrument.output_off()
                self.output_button.setText("開啟輸出")
                self.output_status_label.setText("輸出: 關閉")
                self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.output_enabled = False
                self.status_changed.emit("輸出已關閉")
                
        except Exception as e:
            self.error_occurred.emit("output_control_error", str(e))
            self.output_button.setChecked(False)
            
    def _perform_single_measurement(self):
        """執行單次測量"""
        if not self.is_connected or not self.instrument:
            return
            
        try:
            # 測量電壓、電流和功率
            voltage = self.instrument.measure_voltage()
            current = self.instrument.measure_current()
            power = voltage * current
            
            # 創建測量數據點
            measurement_data = {
                'timestamp': datetime.now(),
                'voltage': voltage,
                'current': current,
                'power': power,
                'measurement_type': 'single'
            }
            
            # 發送數據
            self.measurement_data.emit(measurement_data)
            self.status_changed.emit(f"單次測量: V={voltage:.3f}V, I={current:.3f}A, P={power:.3f}W")
            
        except Exception as e:
            self.error_occurred.emit("single_measurement_error", str(e))
            
    def disconnect_instrument(self):
        """斷開儀器連接 - 覆蓋基類以添加Rigol特定清理"""
        # 安全關閉輸出
        if self.is_connected and self.instrument:
            try:
                self.instrument.output_off()
                self.output_button.setChecked(False)
                self.output_button.setText("開啟輸出")
                self.output_status_label.setText("輸出: 關閉")
                self.output_status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
                self.output_enabled = False
            except:
                pass
                
        # 重置設備連接狀態
        self.output_button.setEnabled(False)
        
        # 重置連接按鈕
        self.connect_device_btn.setText("連接選中設備")
        self.connect_device_btn.clicked.disconnect()
        self.connect_device_btn.clicked.connect(self._connect_selected_device)
        
        # 調用基類斷開方法
        super().disconnect_instrument()
        
        # 清除當前設備
        self.current_device_info = None
        self.current_device_label.setText("當前設備: 未連接")
        self.current_device_label.setStyleSheet("color: #e74c3c; font-style: italic;")
        
    def closeEvent(self, event):
        """關閉事件處理 - 添加Rigol特定清理"""
        # 停止設備掃描
        self.device_scan_timer.stop()
        
        # 調用基類關閉處理
        super().closeEvent(event)