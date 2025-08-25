#!/usr/bin/env python3
"""
COM端口管理模組
處理端口檢測、設備識別和多設備管理
"""

import logging
import threading
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import serial
import serial.tools.list_ports
from PyQt6.QtCore import QObject, pyqtSignal, QTimer


@dataclass
class DeviceInfo:
    """設備資訊"""
    port: str
    description: str
    device_type: str = "Unknown"
    device_id: str = ""
    is_connected: bool = False
    baudrate: int = 9600
    
    def __str__(self):
        status = "已連接" if self.is_connected else "未連接"
        if self.device_type != "Unknown" and self.device_id:
            return f"{self.port} - {self.device_type} ({self.device_id}) [{status}]"
        return f"{self.port} - {self.description} [{status}]"


class PortManager(QObject):
    """COM端口管理器"""
    
    # 信號
    ports_updated = pyqtSignal(list)  # 端口列表更新
    device_connected = pyqtSignal(str, str)  # 設備連接成功 (port, device_id)
    device_disconnected = pyqtSignal(str, str)  # 設備斷開連接 (port, device_id)
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.available_ports: List[DeviceInfo] = []
        self.connected_devices: Dict[str, DeviceInfo] = {}
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.scan_ports)
        self._lock = threading.Lock()
        
    def start_monitoring(self, interval_ms: int = 2000):
        """開始監控端口變化"""
        self.scan_ports()  # 初始掃描
        self.scan_timer.start(interval_ms)
        self.logger.info(f"開始監控 COM 端口，間隔 {interval_ms}ms")
        
    def stop_monitoring(self):
        """停止監控"""
        self.scan_timer.stop()
        self.logger.info("停止監控 COM 端口")
        
    def scan_ports(self) -> List[DeviceInfo]:
        """掃描可用的COM端口"""
        with self._lock:
            new_ports = []
            
            try:
                # 獲取所有可用端口
                for port_info in serial.tools.list_ports.comports():
                    device_info = DeviceInfo(
                        port=port_info.device,
                        description=port_info.description or "Unknown Device",
                    )
                    
                    # 檢查是否已連接
                    if port_info.device in self.connected_devices:
                        device_info.is_connected = True
                        device_info.device_type = self.connected_devices[port_info.device].device_type
                        device_info.device_id = self.connected_devices[port_info.device].device_id
                        
                    new_ports.append(device_info)
                    
                # 檢查端口變化
                old_port_set = {port.port for port in self.available_ports}
                new_port_set = {port.port for port in new_ports}
                
                # 記錄新增的端口
                added_ports = new_port_set - old_port_set
                if added_ports:
                    self.logger.info(f"發現新端口: {', '.join(added_ports)}")
                    
                # 記錄移除的端口
                removed_ports = old_port_set - new_port_set
                if removed_ports:
                    self.logger.info(f"端口已移除: {', '.join(removed_ports)}")
                    # 如果移除的端口有連接的設備，發出斷開信號
                    for port in removed_ports:
                        if port in self.connected_devices:
                            device = self.connected_devices[port]
                            self.device_disconnected.emit(port, device.device_id)
                            del self.connected_devices[port]
                            self.logger.warning(f"設備 {device.device_id} 在端口 {port} 意外斷開")
                            
                self.available_ports = new_ports
                self.ports_updated.emit(new_ports)
                
            except Exception as e:
                self.logger.error(f"掃描端口時發生錯誤: {e}")
                
        return self.available_ports
        
    def get_available_ports(self, exclude_connected: bool = False) -> List[DeviceInfo]:
        """獲取可用端口列表"""
        if exclude_connected:
            return [port for port in self.available_ports if not port.is_connected]
        return self.available_ports.copy()
        
    def get_connected_devices(self) -> Dict[str, DeviceInfo]:
        """獲取已連接的設備"""
        return self.connected_devices.copy()
        
    def test_port_connection(self, port: str, baudrate: int = 9600, 
                           timeout: float = 2.0) -> Tuple[bool, str]:
        """測試端口連接並嘗試識別設備"""
        try:
            with serial.Serial(port, baudrate, timeout=timeout) as ser:
                # 清空緩衝區
                ser.flushInput()
                ser.flushOutput()
                
                # 嘗試發送識別命令
                identification_commands = [
                    b'*IDN?\n',      # 標準SCPI識別命令
                    b':SYST:ERR?\n', # 錯誤查詢
                    b'*OPC?\n',      # 操作完成查詢
                ]
                
                for cmd in identification_commands:
                    try:
                        ser.write(cmd)
                        time.sleep(0.5)  # 等待響應
                        
                        if ser.in_waiting > 0:
                            response = ser.readline().decode('ascii', errors='ignore').strip()
                            if response and response != '':
                                self.logger.debug(f"端口 {port} 響應: {response}")
                                return True, response
                                
                    except Exception as e:
                        self.logger.debug(f"命令 {cmd} 在端口 {port} 失敗: {e}")
                        continue
                        
                # 如果沒有響應但端口可以打開，認為是可用的
                return True, "Device detected (no identification)"
                
        except serial.SerialException as e:
            self.logger.debug(f"端口 {port} 連接失敗: {e}")
            return False, str(e)
        except Exception as e:
            self.logger.error(f"測試端口 {port} 時發生未預期錯誤: {e}")
            return False, str(e)
            
    def identify_device(self, port: str, baudrate: int = 9600) -> Optional[DeviceInfo]:
        """識別連接在指定端口的設備"""
        success, response = self.test_port_connection(port, baudrate)
        
        if not success:
            return None
            
        device_info = DeviceInfo(
            port=port,
            description=f"Device on {port}",
            baudrate=baudrate,
            is_connected=False
        )
        
        # 解析設備識別信息
        if "rigol" in response.lower() and "dp711" in response.lower():
            device_info.device_type = "Rigol DP711"
            # 嘗試提取序號或型號
            parts = response.split(',')
            if len(parts) >= 3:
                device_info.device_id = parts[2].strip()
            else:
                device_info.device_id = "DP711-Unknown"
                
        elif "rigol" in response.lower():
            device_info.device_type = "Rigol Device"
            device_info.device_id = response
            
        else:
            # 通用設備
            device_info.device_type = "Generic SCPI Device"
            device_info.device_id = response[:50] if len(response) > 50 else response
            
        self.logger.info(f"識別到設備: {device_info}")
        return device_info
        
    def connect_device(self, port: str, baudrate: int = 9600) -> bool:
        """標記設備為已連接狀態"""
        device_info = self.identify_device(port, baudrate)
        if device_info:
            device_info.is_connected = True
            self.connected_devices[port] = device_info
            
            # 更新可用端口列表中的狀態
            for port_info in self.available_ports:
                if port_info.port == port:
                    port_info.is_connected = True
                    port_info.device_type = device_info.device_type
                    port_info.device_id = device_info.device_id
                    break
                    
            self.device_connected.emit(port, device_info.device_id)
            self.ports_updated.emit(self.available_ports)
            self.logger.info(f"設備連接成功: {device_info}")
            return True
            
        return False
        
    def disconnect_device(self, port: str) -> bool:
        """標記設備為斷開狀態"""
        if port in self.connected_devices:
            device_info = self.connected_devices[port]
            device_info.is_connected = False
            del self.connected_devices[port]
            
            # 更新可用端口列表中的狀態
            for port_info in self.available_ports:
                if port_info.port == port:
                    port_info.is_connected = False
                    port_info.device_type = "Unknown"
                    port_info.device_id = ""
                    break
                    
            self.device_disconnected.emit(port, device_info.device_id)
            self.ports_updated.emit(self.available_ports)
            self.logger.info(f"設備已斷開: {port} - {device_info.device_id}")
            return True
            
        return False
        
    def get_device_suggestions(self) -> List[str]:
        """獲取設備連接建議"""
        suggestions = []
        
        available_dp711 = [port for port in self.available_ports 
                          if not port.is_connected and 
                          ("rigol" in port.description.lower() or 
                           "dp711" in port.description.lower())]
        
        if available_dp711:
            suggestions.append(f"發現 {len(available_dp711)} 個可能的 Rigol DP711 設備")
            
        connected_count = len(self.connected_devices)
        if connected_count > 0:
            suggestions.append(f"目前有 {connected_count} 個設備已連接")
            
        return suggestions


# 全域端口管理器實例
_port_manager = None

def get_port_manager() -> PortManager:
    """獲取全域端口管理器實例"""
    global _port_manager
    if _port_manager is None:
        _port_manager = PortManager()
    return _port_manager