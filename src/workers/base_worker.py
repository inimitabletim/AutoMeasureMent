#!/usr/bin/env python3
"""
統一工作執行緒基類
提供標準化的執行緒管理、錯誤處理和資源管理
"""

from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Any, Optional, Dict
from PyQt6.QtCore import QThread, pyqtSignal
from src.unified_logger import get_logger


class WorkerState(Enum):
    """工作執行緒狀態"""
    IDLE = "idle"
    RUNNING = "running" 
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
    COMPLETED = "completed"


class WorkerMeta(type(QThread), ABCMeta):
    """解決QThread和ABC的元類衝突"""
    pass


class UnifiedWorkerBase(QThread, metaclass=WorkerMeta):
    """統一的工作執行緒基類
    
    提供所有Worker的標準功能：
    - 狀態管理
    - 錯誤處理 
    - 資源清理
    - 信號標準化
    """
    
    # 標準信號
    state_changed = pyqtSignal(str)  # WorkerState
    progress_updated = pyqtSignal(int)  # 0-100 進度百分比
    error_occurred = pyqtSignal(str, str)  # error_type, error_message
    operation_completed = pyqtSignal(dict)  # 完成信息
    data_ready = pyqtSignal(dict)  # 數據準備就緒
    
    def __init__(self, worker_name: str, instrument=None):
        """初始化統一Worker
        
        Args:
            worker_name: Worker識別名稱
            instrument: 關聯的儀器實例 (可選)
        """
        super().__init__()
        self.worker_name = worker_name
        self.instrument = instrument
        self.state = WorkerState.IDLE
        self.logger = get_logger(f"Worker.{worker_name}")
        
        # 控制變量
        self._should_stop = False
        self._is_paused = False
        
        # 統計信息
        self.start_time = None
        self.operation_count = 0
        self.error_count = 0
        
    def run(self):
        """主執行方法 - 模板方法模式"""
        try:
            self._change_state(WorkerState.RUNNING)
            self.logger.info(f"Worker {self.worker_name} 開始執行")
            
            # 執行初始化
            if not self.setup():
                self._change_state(WorkerState.ERROR)
                return
                
            # 主要工作循環
            while not self._should_stop:
                if self._is_paused:
                    self.msleep(100)
                    continue
                    
                if not self.execute_operation():
                    break
                    
                self.operation_count += 1
                
            # 清理工作
            self.cleanup()
            
            if not self._should_stop:
                self._change_state(WorkerState.COMPLETED)
                self.operation_completed.emit({
                    'worker_name': self.worker_name,
                    'operation_count': self.operation_count,
                    'error_count': self.error_count
                })
            else:
                self._change_state(WorkerState.IDLE)
                
        except Exception as e:
            self.logger.error(f"Worker執行錯誤: {e}")
            self.error_occurred.emit("execution_error", str(e))
            self._change_state(WorkerState.ERROR)
        finally:
            self.cleanup()
            
    @abstractmethod
    def setup(self) -> bool:
        """初始化設置 - 子類必須實現
        
        Returns:
            bool: 設置是否成功
        """
        pass
        
    @abstractmethod  
    def execute_operation(self) -> bool:
        """執行一次操作 - 子類必須實現
        
        Returns:
            bool: 是否繼續執行
        """
        pass
        
    @abstractmethod
    def cleanup(self) -> None:
        """清理資源 - 子類必須實現"""
        pass
        
    def start_work(self):
        """開始工作"""
        if self.state == WorkerState.IDLE:
            self.start()
        elif self.state == WorkerState.PAUSED:
            self.resume()
            
    def stop_work(self):
        """停止工作"""
        self._should_stop = True
        self._change_state(WorkerState.STOPPING)
        self.quit()
        self.wait(5000)  # 等待5秒
        
    def pause_work(self):
        """暫停工作"""
        if self.state == WorkerState.RUNNING:
            self._is_paused = True
            self._change_state(WorkerState.PAUSED)
            
    def resume_work(self):
        """恢復工作"""
        if self.state == WorkerState.PAUSED:
            self._is_paused = False
            self._change_state(WorkerState.RUNNING)
            
    def _change_state(self, new_state: WorkerState):
        """改變Worker狀態"""
        old_state = self.state
        self.state = new_state
        self.state_changed.emit(new_state.value)
        self.logger.debug(f"狀態變更: {old_state.value} -> {new_state.value}")
        
    def _emit_progress(self, progress: int):
        """發送進度更新"""
        self.progress_updated.emit(max(0, min(100, progress)))
        
    def _emit_data(self, data: Dict[str, Any]):
        """發送數據"""
        data['worker_name'] = self.worker_name
        data['timestamp'] = self.get_current_timestamp()
        self.data_ready.emit(data)
        
    def _emit_error(self, error_type: str, error_message: str):
        """發送錯誤信息"""
        self.error_count += 1
        self.error_occurred.emit(error_type, error_message)
        self.logger.error(f"{error_type}: {error_message}")
        
    def get_current_timestamp(self) -> str:
        """獲取當前時間戳"""
        from datetime import datetime
        return datetime.now().isoformat()
        
    def get_worker_info(self) -> Dict[str, Any]:
        """獲取Worker信息"""
        return {
            'name': self.worker_name,
            'state': self.state.value,
            'operation_count': self.operation_count,
            'error_count': self.error_count,
            'has_instrument': self.instrument is not None
        }