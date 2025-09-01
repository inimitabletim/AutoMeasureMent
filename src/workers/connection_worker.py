#!/usr/bin/env python3
"""
統一連接工作執行緒
處理所有儀器的非阻塞式連接操作
"""

import time
from typing import Dict, Any, Optional, List
from PyQt6.QtCore import pyqtSignal
from .base_worker import UnifiedWorkerBase, WorkerState


class ConnectionWorker(UnifiedWorkerBase):
    """統一連接工作執行緒"""
    
    # 連接特定信號
    connection_started = pyqtSignal()
    connection_success = pyqtSignal(str, dict)  # instrument_id, connection_info
    connection_failed = pyqtSignal(str, str)    # error_type, error_message
    
    def __init__(self, instrument, connection_params: Dict[str, Any]):
        """初始化連接Worker
        
        Args:
            instrument: 儀器實例
            connection_params: 連接參數
        """
        super().__init__("Connection", instrument)
        self.connection_params = connection_params
        self.connection_info = {}
        
    def setup(self) -> bool:
        """設置連接準備"""
        self.connection_started.emit()
        self.logger.info(f"準備連接到 {self.instrument.name}")
        return True
        
    def execute_operation(self) -> bool:
        """執行連接操作"""
        try:
            self._emit_progress(10)
            
            # 嘗試連接
            success = self.instrument.connect(self.connection_params)
            
            if success:
                self._emit_progress(70)
                
                # 獲取設備信息
                try:
                    identity = self.instrument.get_identity()
                    self.connection_info = {
                        'identity': identity,
                        'connection_params': self.connection_params,
                        'connected_at': self.get_current_timestamp()
                    }
                    self._emit_progress(90)
                    
                except Exception as e:
                    self.logger.warning(f"無法獲取設備信息: {e}")
                    self.connection_info = {
                        'identity': 'Unknown',
                        'connection_params': self.connection_params,
                        'connected_at': self.get_current_timestamp()
                    }
                
                self._emit_progress(100)
                self.connection_success.emit(
                    self.instrument.name, 
                    self.connection_info
                )
                self.logger.info(f"成功連接到 {self.instrument.name}")
                return False  # 連接完成，結束Worker
                
            else:
                self.connection_failed.emit(
                    "connection_failed", 
                    f"無法連接到 {self.instrument.name}"
                )
                return False
                
        except Exception as e:
            self.connection_failed.emit("connection_error", str(e))
            return False
            
    def cleanup(self) -> None:
        """清理連接資源"""
        pass  # 連接操作不需要特殊清理


class BatchConnectionWorker(UnifiedWorkerBase):
    """批量連接工作執行緒 - 用於多設備連接"""
    
    device_connected = pyqtSignal(str, dict)  # device_id, connection_info
    device_failed = pyqtSignal(str, str)      # device_id, error_message
    batch_completed = pyqtSignal(list)        # successful_connections
    
    def __init__(self, instruments_config: List[Dict[str, Any]]):
        """初始化批量連接Worker
        
        Args:
            instruments_config: 儀器配置列表
                [{'instrument': obj, 'params': {...}}, ...]
        """
        super().__init__("BatchConnection")
        self.instruments_config = instruments_config
        self.successful_connections = []
        self.failed_connections = []
        self.current_index = 0
        
    def setup(self) -> bool:
        """設置批量連接"""
        if not self.instruments_config:
            self._emit_error("config_error", "沒有儀器需要連接")
            return False
        return True
        
    def execute_operation(self) -> bool:
        """執行批量連接中的單個連接"""
        if self.current_index >= len(self.instruments_config):
            # 所有連接完成
            self.batch_completed.emit(self.successful_connections)
            return False
            
        config = self.instruments_config[self.current_index]
        instrument = config['instrument']
        params = config['params']
        
        try:
            self.logger.info(f"正在連接 {instrument.name} ({self.current_index + 1}/{len(self.instruments_config)})")
            
            # 嘗試連接
            if instrument.connect(params):
                identity = instrument.get_identity() if hasattr(instrument, 'get_identity') else 'Unknown'
                connection_info = {
                    'identity': identity,
                    'params': params,
                    'index': self.current_index
                }
                
                self.successful_connections.append({
                    'instrument': instrument,
                    'info': connection_info
                })
                
                self.device_connected.emit(instrument.name, connection_info)
                self.logger.info(f"成功連接 {instrument.name}")
                
            else:
                self.failed_connections.append({
                    'instrument': instrument,
                    'error': '連接失敗'
                })
                self.device_failed.emit(instrument.name, "連接失敗")
                
        except Exception as e:
            error_msg = str(e)
            self.failed_connections.append({
                'instrument': instrument,
                'error': error_msg
            })
            self.device_failed.emit(instrument.name, error_msg)
            
        # 更新進度
        self.current_index += 1
        progress = int(self.current_index * 100 / len(self.instruments_config))
        self._emit_progress(progress)
        
        # 短暫延遲避免過快連接
        time.sleep(0.5)
        
        return True
        
    def cleanup(self) -> None:
        """清理批量連接"""
        self.logger.info(f"批量連接完成: 成功 {len(self.successful_connections)}, 失敗 {len(self.failed_connections)}")


class ReconnectionWorker(UnifiedWorkerBase):
    """自動重連工作執行緒"""
    
    reconnection_attempted = pyqtSignal(int)  # attempt_number
    reconnection_success = pyqtSignal(str)    # instrument_name
    max_attempts_reached = pyqtSignal()
    
    def __init__(self, instrument, connection_params: Dict[str, Any], max_attempts: int = 3):
        """初始化重連Worker
        
        Args:
            instrument: 儀器實例
            connection_params: 連接參數
            max_attempts: 最大重試次數
        """
        super().__init__("Reconnection", instrument)
        self.connection_params = connection_params
        self.max_attempts = max_attempts
        self.current_attempt = 0
        self.retry_delay_ms = 2000  # 2秒重試間隔
        
    def setup(self) -> bool:
        """設置重連準備"""
        self.current_attempt = 0
        self.logger.info(f"準備重連 {self.instrument.name}, 最大嘗試次數: {self.max_attempts}")
        return True
        
    def execute_operation(self) -> bool:
        """執行重連嘗試"""
        if self.current_attempt >= self.max_attempts:
            self.max_attempts_reached.emit()
            self.logger.warning(f"重連失敗: 已達到最大嘗試次數 ({self.max_attempts})")
            return False
            
        self.current_attempt += 1
        self.reconnection_attempted.emit(self.current_attempt)
        
        try:
            self.logger.info(f"重連嘗試 {self.current_attempt}/{self.max_attempts}")
            
            # 先斷開現有連接
            if self.instrument.is_connected():
                self.instrument.disconnect()
                time.sleep(1.0)
                
            # 嘗試重新連接
            if self.instrument.connect(self.connection_params):
                self.reconnection_success.emit(self.instrument.name)
                self.logger.info(f"重連成功: {self.instrument.name}")
                return False  # 重連成功，結束Worker
            else:
                self.logger.warning(f"重連嘗試 {self.current_attempt} 失敗")
                
        except Exception as e:
            self.logger.error(f"重連嘗試 {self.current_attempt} 錯誤: {e}")
            
        # 更新進度
        progress = int(self.current_attempt * 100 / self.max_attempts)
        self._emit_progress(progress)
        
        # 等待重試間隔
        self.msleep(self.retry_delay_ms)
        
        return True
        
    def cleanup(self) -> None:
        """清理重連資源"""
        if self.current_attempt >= self.max_attempts:
            self.logger.info("重連嘗試結束")