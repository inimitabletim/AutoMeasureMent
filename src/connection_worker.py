#!/usr/bin/env python3
"""
非阻塞式儀器連線工作執行緒
解決GUI凍結問題的完整解決方案
"""

import time
import socket
from typing import Dict, Any, Optional
from PyQt6.QtCore import QThread, pyqtSignal, QTimer
from src.keithley_2461 import Keithley2461
from src.rigol_dp711 import RigolDP711
from src.unified_logger import get_logger


class InstrumentConnectionWorker(QThread):
    """儀器連線工作執行緒 - 防止UI凍結"""
    
    # 連線狀態信號
    connection_started = pyqtSignal()
    connection_progress = pyqtSignal(str)  # 進度描述
    connection_success = pyqtSignal(str)   # 成功消息
    connection_failed = pyqtSignal(str)    # 失敗消息
    connection_timeout = pyqtSignal()      # 連線超時
    
    def __init__(self, instrument_type: str, connection_params: Dict[str, Any]):
        """
        初始化連線工作執行緒
        
        Args:
            instrument_type: 儀器類型 ('keithley' or 'rigol')
            connection_params: 連線參數字典
        """
        super().__init__()
        self.instrument_type = instrument_type.lower()
        self.connection_params = connection_params
        self.instrument = None
        self.cancelled = False
        self.logger = get_logger("ConnectionWorker")
        
        # 連線超時控制
        self.timeout_seconds = connection_params.get('timeout', 5.0)  # 縮短超時時間
        
    def cancel(self):
        """取消連線操作"""
        self.cancelled = True
        self.logger.info("用戶取消連線操作")
        
    def run(self):
        """執行連線操作"""
        if self.cancelled:
            return
            
        try:
            self.connection_started.emit()
            
            # 根據儀器類型創建實例
            if self.instrument_type == 'keithley':
                self._connect_keithley()
            elif self.instrument_type == 'rigol':
                self._connect_rigol()
            else:
                self.connection_failed.emit(f"不支援的儀器類型: {self.instrument_type}")
                return
                
        except Exception as e:
            self.logger.error(f"連線執行緒異常: {e}")
            self.connection_failed.emit(f"連線時發生錯誤: {str(e)}")
            
    def _connect_keithley(self):
        """連線Keithley 2461"""
        ip_address = self.connection_params.get('ip_address', '192.168.0.100')
        port = self.connection_params.get('port', 5025)
        
        self.connection_progress.emit("正在解析IP地址...")
        
        # 檢查是否取消
        if self.cancelled:
            return
            
        # 快速網路連通性檢查
        self.connection_progress.emit("檢查網路連通性...")
        if not self._check_network_connectivity(ip_address, port):
            self.connection_failed.emit(f"無法連通 {ip_address}:{port}\n請檢查：\n1. 儀器是否已開機\n2. 網路連線是否正常\n3. IP地址是否正確")
            return
            
        if self.cancelled:
            return
            
        # 建立儀器連線
        self.connection_progress.emit("建立儀器連線...")
        try:
            self.instrument = Keithley2461(
                ip_address=ip_address,
                port=port,
                timeout=self.timeout_seconds
            )
            
            # 嘗試連線
            if self.instrument.connect():
                # 驗證儀器回應
                self.connection_progress.emit("驗證儀器回應...")
                identity = self.instrument.get_identity()
                
                if "2461" in identity:
                    self.connection_success.emit(f"成功連接到 Keithley 2461\n{identity}")
                else:
                    self.connection_failed.emit(f"儀器回應異常: {identity}")
            else:
                self.connection_failed.emit("儀器連線失敗")
                
        except socket.timeout:
            self.connection_failed.emit(f"連線超時 ({self.timeout_seconds}秒)\n儀器可能未開機或網路異常")
        except Exception as e:
            self.connection_failed.emit(f"Keithley連線錯誤: {str(e)}")
            
    def _connect_rigol(self):
        """連線Rigol DP711"""
        port = self.connection_params.get('port', 'COM3')
        baudrate = self.connection_params.get('baudrate', 9600)
        
        self.connection_progress.emit(f"正在連線到 {port}...")
        
        try:
            self.instrument = RigolDP711(port=port, baudrate=baudrate)
            
            if self.instrument.connect():
                self.connection_progress.emit("驗證儀器回應...")
                identity = self.instrument.get_identity()
                self.connection_success.emit(f"成功連接到 Rigol DP711\n{identity}")
            else:
                self.connection_failed.emit("Rigol DP711 連線失敗")
                
        except Exception as e:
            self.connection_failed.emit(f"Rigol連線錯誤: {str(e)}")
            
    def _check_network_connectivity(self, ip_address: str, port: int) -> bool:
        """
        快速網路連通性檢查
        使用短超時避免長時間等待
        """
        try:
            # 使用非常短的超時進行連通性測試
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(2.0)  # 2秒快速檢查
            
            result = test_socket.connect_ex((ip_address, port))
            test_socket.close()
            
            return result == 0  # 0表示連線成功
            
        except Exception as e:
            self.logger.debug(f"網路連通性檢查失敗: {e}")
            return False
    
    def get_instrument(self):
        """獲取成功連線的儀器實例"""
        return self.instrument


class ConnectionStateManager:
    """連線狀態管理器 - 防止重複連線"""
    
    def __init__(self):
        self.is_connecting = False
        self.connection_worker: Optional[InstrumentConnectionWorker] = None
        
    def start_connection(self, instrument_type: str, connection_params: Dict[str, Any]) -> InstrumentConnectionWorker:
        """開始連線過程"""
        if self.is_connecting:
            raise RuntimeError("已有連線在進行中，請稍候再試")
            
        self.is_connecting = True
        self.connection_worker = InstrumentConnectionWorker(instrument_type, connection_params)
        
        # 連接完成信號以重設狀態
        self.connection_worker.connection_success.connect(self._on_connection_finished)
        self.connection_worker.connection_failed.connect(self._on_connection_finished)
        
        return self.connection_worker
    
    def cancel_connection(self):
        """取消當前連線"""
        if self.connection_worker and self.is_connecting:
            self.connection_worker.cancel()
            self.connection_worker.quit()
            self.connection_worker.wait(1000)  # 等待1秒
            
        self._on_connection_finished()
        
    def _on_connection_finished(self):
        """連線完成處理"""
        self.is_connecting = False
        if self.connection_worker:
            self.connection_worker = None