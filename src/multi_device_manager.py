#!/usr/bin/env python3
"""
多設備管理模組
處理多個 DP711 設備的管理和切換
"""

import logging
from typing import Dict, List, Optional, Tuple
from PyQt6.QtCore import QObject, pyqtSignal
from src.port_manager import PortManager, DeviceInfo, get_port_manager
from src.rigol_dp711 import RigolDP711


class MultiDeviceManager(QObject):
    """多設備管理器"""
    
    # 信號
    device_list_changed = pyqtSignal(list)  # 設備列表變更
    active_device_changed = pyqtSignal(str, str)  # 當前設備變更 (port, device_id)
    device_status_changed = pyqtSignal(str, bool)  # 設備狀態變更 (device_id, connected)
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.port_manager = get_port_manager()
        self.devices: Dict[str, RigolDP711] = {}  # port -> device instance
        self.device_info: Dict[str, DeviceInfo] = {}  # port -> device info
        self.active_device_port: Optional[str] = None
        
        # 連接端口管理器信號
        self.port_manager.device_connected.connect(self._on_device_connected)
        self.port_manager.device_disconnected.connect(self._on_device_disconnected)
        self.port_manager.ports_updated.connect(self._on_ports_updated)
        
    def start_monitoring(self):
        """開始監控設備"""
        self.port_manager.start_monitoring()
        self.logger.info("多設備管理器開始監控")
        
    def stop_monitoring(self):
        """停止監控設備"""
        self.port_manager.stop_monitoring()
        self.logger.info("多設備管理器停止監控")
        
    def get_available_devices(self) -> List[DeviceInfo]:
        """獲取可用的 DP711 設備列表"""
        dp711_devices = []
        for port_info in self.port_manager.get_available_ports():
            # 檢查是否為 DP711 或相關設備
            if (not port_info.is_connected and 
                ("rigol" in port_info.description.lower() or
                 "dp711" in port_info.device_type.lower() or
                 self._is_likely_dp711(port_info))):
                dp711_devices.append(port_info)
                
        return dp711_devices
        
    def get_connected_devices(self) -> List[Tuple[str, DeviceInfo, RigolDP711]]:
        """獲取已連接的設備列表"""
        connected = []
        for port, device in self.devices.items():
            if port in self.device_info:
                connected.append((port, self.device_info[port], device))
        return connected
        
    def connect_device(self, port: str, baudrate: int = 9600) -> bool:
        """連接指定端口的設備"""
        try:
            # 如果設備已連接，先斷開
            if port in self.devices:
                self.disconnect_device(port)
                
            # 創建新的設備實例
            device = RigolDP711(port, baudrate)
            
            # 嘗試連接
            if device.connect():
                self.devices[port] = device
                
                # 標記端口管理器中的設備為已連接
                if self.port_manager.connect_device(port, baudrate):
                    device_info = self.port_manager.connected_devices.get(port)
                    if device_info:
                        self.device_info[port] = device_info
                        
                        # 如果這是第一個連接的設備，設為活動設備
                        if self.active_device_port is None:
                            self.set_active_device(port)
                            
                        self.device_status_changed.emit(device_info.device_id, True)
                        self.logger.info(f"DP711 設備連接成功: {port} - {device_info.device_id}")
                        self._update_device_list()
                        return True
                        
                # 如果端口管理器標記失敗，清理設備
                device.disconnect()
                del self.devices[port]
                
        except Exception as e:
            self.logger.error(f"連接設備 {port} 時發生錯誤: {e}")
            if port in self.devices:
                del self.devices[port]
                
        return False
        
    def disconnect_device(self, port: str) -> bool:
        """斷開指定設備"""
        try:
            if port in self.devices:
                device = self.devices[port]
                device_info = self.device_info.get(port)
                
                # 斷開設備連接
                device.disconnect()
                del self.devices[port]
                
                if device_info:
                    device_id = device_info.device_id
                    del self.device_info[port]
                    self.device_status_changed.emit(device_id, False)
                    self.logger.info(f"DP711 設備已斷開: {port} - {device_id}")
                    
                # 標記端口管理器中的設備為已斷開
                self.port_manager.disconnect_device(port)
                
                # 如果斷開的是活動設備，切換到其他設備
                if self.active_device_port == port:
                    self._switch_to_next_device()
                    
                self._update_device_list()
                return True
                
        except Exception as e:
            self.logger.error(f"斷開設備 {port} 時發生錯誤: {e}")
            
        return False
        
    def disconnect_all_devices(self):
        """斷開所有設備"""
        ports_to_disconnect = list(self.devices.keys())
        for port in ports_to_disconnect:
            self.disconnect_device(port)
        self.active_device_port = None
        self.logger.info("所有 DP711 設備已斷開")
        
    def set_active_device(self, port: str) -> bool:
        """設置活動設備"""
        if port in self.devices and port in self.device_info:
            old_port = self.active_device_port
            self.active_device_port = port
            device_info = self.device_info[port]
            
            self.active_device_changed.emit(port, device_info.device_id)
            self.logger.info(f"活動設備切換: {device_info.device_id} ({port})")
            
            if old_port != port:
                self._update_device_list()
                
            return True
        return False
        
    def get_active_device(self) -> Optional[Tuple[str, RigolDP711, DeviceInfo]]:
        """獲取當前活動設備"""
        if (self.active_device_port and 
            self.active_device_port in self.devices and
            self.active_device_port in self.device_info):
            
            port = self.active_device_port
            return (port, self.devices[port], self.device_info[port])
            
        return None
        
    def get_device_by_port(self, port: str) -> Optional[Tuple[RigolDP711, DeviceInfo]]:
        """根據端口獲取設備"""
        if port in self.devices and port in self.device_info:
            return (self.devices[port], self.device_info[port])
        return None
        
    def get_device_count(self) -> int:
        """獲取已連接設備數量"""
        return len(self.devices)
        
    def _is_likely_dp711(self, port_info: DeviceInfo) -> bool:
        """判斷端口是否可能是 DP711 設備"""
        # 檢查描述中的關鍵字
        desc_lower = port_info.description.lower()
        keywords = ['rigol', 'dp711', 'power', 'supply', 'usb-serial', 'ch340', 'ft232']
        
        for keyword in keywords:
            if keyword in desc_lower:
                return True
                
        # 檢查是否為通用 USB 轉串口設備
        if 'usb' in desc_lower and ('serial' in desc_lower or 'com' in desc_lower):
            return True
            
        return False
        
    def _switch_to_next_device(self):
        """切換到下一個可用設備"""
        if self.devices:
            # 選擇第一個可用設備作為新的活動設備
            next_port = next(iter(self.devices.keys()))
            self.set_active_device(next_port)
        else:
            self.active_device_port = None
            self.active_device_changed.emit("", "")
            
    def _update_device_list(self):
        """更新設備列表並發出信號"""
        device_list = []
        for port, device_info in self.device_info.items():
            is_active = (port == self.active_device_port)
            device_list.append({
                'port': port,
                'device_id': device_info.device_id,
                'device_type': device_info.device_type,
                'is_active': is_active,
                'description': str(device_info)
            })
            
        self.device_list_changed.emit(device_list)
        
    def _on_device_connected(self, port: str, device_id: str):
        """處理設備連接事件"""
        self.logger.debug(f"端口管理器報告設備連接: {port} - {device_id}")
        
    def _on_device_disconnected(self, port: str, device_id: str):
        """處理設備斷開事件"""
        self.logger.debug(f"端口管理器報告設備斷開: {port} - {device_id}")
        # 如果是我們管理的設備意外斷開，清理資源
        if port in self.devices:
            self.disconnect_device(port)
            
    def _on_ports_updated(self, ports: List[DeviceInfo]):
        """處理端口列表更新事件"""
        self.logger.debug(f"端口列表更新，共 {len(ports)} 個端口")


# 全域多設備管理器實例
_multi_device_manager = None

def get_multi_device_manager() -> MultiDeviceManager:
    """獲取全域多設備管理器實例"""
    global _multi_device_manager
    if _multi_device_manager is None:
        _multi_device_manager = MultiDeviceManager()
    return _multi_device_manager