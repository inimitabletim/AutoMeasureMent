#!/usr/bin/env python3
"""
緩存管理器
提供高效的實時數據緩存和內存管理
"""

import threading
import sys
from collections import deque
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from src.unified_logger import get_logger


class CircularBuffer:
    """高效圓形緩存"""
    
    def __init__(self, max_size: int):
        """初始化圓形緩存
        
        Args:
            max_size: 最大緩存大小
        """
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self._lock = threading.RLock()
        
    def append(self, item: Any):
        """添加項目到緩存"""
        with self._lock:
            self.buffer.append(item)
            
    def get_recent(self, count: int) -> List[Any]:
        """獲取最近的項目
        
        Args:
            count: 項目數量
            
        Returns:
            List: 最近的項目列表
        """
        with self._lock:
            return list(self.buffer)[-count:] if count <= len(self.buffer) else list(self.buffer)
            
    def get_all(self) -> List[Any]:
        """獲取所有項目"""
        with self._lock:
            return list(self.buffer)
            
    def clear(self):
        """清空緩存"""
        with self._lock:
            self.buffer.clear()
            
    def size(self) -> int:
        """獲取當前大小"""
        return len(self.buffer)
        
    def is_full(self) -> bool:
        """檢查緩存是否已滿"""
        return len(self.buffer) >= self.max_size
        
    def get_memory_size(self) -> int:
        """估算內存使用大小（字節）"""
        if not self.buffer:
            return 0
        return sys.getsizeof(self.buffer) + sum(sys.getsizeof(item) for item in self.buffer)


class BufferManager:
    """緩存管理器 - 管理多個儀器的數據緩存"""
    
    def __init__(self):
        self.buffers: Dict[str, CircularBuffer] = {}
        self.buffer_configs: Dict[str, Dict[str, Any]] = {}
        self.logger = get_logger("BufferManager")
        self._lock = threading.RLock()
        
        # 統計信息
        self.total_points_added = 0
        self.total_points_removed = 0
        
    def create_buffer(self, instrument_id: str, max_size: int, 
                     config: Optional[Dict[str, Any]] = None):
        """為儀器創建緩存
        
        Args:
            instrument_id: 儀器標識符
            max_size: 最大緩存大小
            config: 額外配置
        """
        with self._lock:
            self.buffers[instrument_id] = CircularBuffer(max_size)
            self.buffer_configs[instrument_id] = config or {}
            self.logger.info(f"為 {instrument_id} 創建緩存，大小: {max_size}")
            
    def add_point(self, instrument_id: str, point: Any):
        """添加數據點到緩存
        
        Args:
            instrument_id: 儀器標識符
            point: 數據點
        """
        with self._lock:
            if instrument_id not in self.buffers:
                # 自動創建預設緩存
                self.create_buffer(instrument_id, 1000)
                
            self.buffers[instrument_id].append(point)
            self.total_points_added += 1
            
    def get_recent_points(self, instrument_id: str, count: int) -> List[Any]:
        """獲取最近的數據點
        
        Args:
            instrument_id: 儀器標識符
            count: 數據點數量
            
        Returns:
            List: 數據點列表
        """
        with self._lock:
            if instrument_id not in self.buffers:
                return []
            return self.buffers[instrument_id].get_recent(count)
            
    def get_all_points(self, instrument_id: str) -> List[Any]:
        """獲取所有數據點
        
        Args:
            instrument_id: 儀器標識符
            
        Returns:
            List: 所有數據點
        """
        with self._lock:
            if instrument_id not in self.buffers:
                return []
            return self.buffers[instrument_id].get_all()
            
    def get_points_in_range(self, instrument_id: str, 
                           start_time: datetime, 
                           end_time: datetime) -> List[Any]:
        """獲取時間範圍內的數據點
        
        Args:
            instrument_id: 儀器標識符
            start_time: 開始時間
            end_time: 結束時間
            
        Returns:
            List: 時間範圍內的數據點
        """
        with self._lock:
            all_points = self.get_all_points(instrument_id)
            return [
                point for point in all_points 
                if hasattr(point, 'timestamp') and start_time <= point.timestamp <= end_time
            ]
            
    def clear_buffer(self, instrument_id: str):
        """清空特定緩存
        
        Args:
            instrument_id: 儀器標識符
        """
        with self._lock:
            if instrument_id in self.buffers:
                old_size = self.buffers[instrument_id].size()
                self.buffers[instrument_id].clear()
                self.total_points_removed += old_size
                self.logger.info(f"已清空 {instrument_id} 緩存，移除 {old_size} 個點")
                
    def clear_all_buffers(self):
        """清空所有緩存"""
        with self._lock:
            total_removed = sum(buffer.size() for buffer in self.buffers.values())
            for buffer in self.buffers.values():
                buffer.clear()
            self.total_points_removed += total_removed
            self.logger.info(f"已清空所有緩存，移除 {total_removed} 個點")
            
    def resize_buffer(self, instrument_id: str, new_size: int):
        """調整緩存大小
        
        Args:
            instrument_id: 儀器標識符
            new_size: 新的緩存大小
        """
        with self._lock:
            if instrument_id in self.buffers:
                old_data = self.buffers[instrument_id].get_all()
                self.buffers[instrument_id] = CircularBuffer(new_size)
                
                # 保留最新的數據
                if old_data:
                    keep_count = min(len(old_data), new_size)
                    for point in old_data[-keep_count:]:
                        self.buffers[instrument_id].append(point)
                        
                self.logger.info(f"{instrument_id} 緩存大小已調整為 {new_size}")
                
    def get_buffer_status(self, instrument_id: str) -> Dict[str, Any]:
        """獲取緩存狀態
        
        Args:
            instrument_id: 儀器標識符
            
        Returns:
            Dict: 緩存狀態信息
        """
        with self._lock:
            if instrument_id not in self.buffers:
                return {}
                
            buffer = self.buffers[instrument_id]
            return {
                'current_size': buffer.size(),
                'max_size': buffer.max_size,
                'is_full': buffer.is_full(),
                'memory_usage_bytes': buffer.get_memory_size(),
                'utilization_percent': (buffer.size() / buffer.max_size) * 100
            }
            
    def get_memory_usage(self) -> Dict[str, Any]:
        """獲取總內存使用情況
        
        Returns:
            Dict: 內存使用統計
        """
        with self._lock:
            total_memory = 0
            buffer_stats = {}
            
            for instrument_id, buffer in self.buffers.items():
                memory_size = buffer.get_memory_size()
                total_memory += memory_size
                buffer_stats[instrument_id] = {
                    'memory_bytes': memory_size,
                    'memory_mb': memory_size / (1024 * 1024),
                    'point_count': buffer.size()
                }
                
            return {
                'total_memory_bytes': total_memory,
                'total_memory_mb': total_memory / (1024 * 1024),
                'buffer_count': len(self.buffers),
                'total_points': sum(b.size() for b in self.buffers.values()),
                'buffers': buffer_stats,
                'statistics': {
                    'points_added': self.total_points_added,
                    'points_removed': self.total_points_removed
                }
            }
            
    def optimize_memory(self):
        """優化內存使用"""
        with self._lock:
            # 清理空緩存
            empty_buffers = [
                instrument_id for instrument_id, buffer in self.buffers.items()
                if buffer.size() == 0
            ]
            
            for instrument_id in empty_buffers:
                del self.buffers[instrument_id]
                if instrument_id in self.buffer_configs:
                    del self.buffer_configs[instrument_id]
                    
            if empty_buffers:
                self.logger.info(f"已清理 {len(empty_buffers)} 個空緩存")
                
            # 檢查內存使用並適當縮減緩存
            memory_stats = self.get_memory_usage()
            if memory_stats['total_memory_mb'] > 100:  # 100MB閾值
                # 將所有緩存縮減到一半大小
                for instrument_id, buffer in self.buffers.items():
                    new_size = max(100, buffer.max_size // 2)
                    self.resize_buffer(instrument_id, new_size)
                    
                self.logger.info("內存使用過高，已縮減緩存大小")
                
    def get_oldest_point(self, instrument_id: str) -> Optional[Any]:
        """獲取最舊的數據點
        
        Args:
            instrument_id: 儀器標識符
            
        Returns:
            Any: 最舊的數據點
        """
        with self._lock:
            if instrument_id in self.buffers and self.buffers[instrument_id].size() > 0:
                return self.buffers[instrument_id].get_all()[0]
            return None
            
    def get_newest_point(self, instrument_id: str) -> Optional[Any]:
        """獲取最新的數據點
        
        Args:
            instrument_id: 儀器標識符
            
        Returns:
            Any: 最新的數據點
        """
        with self._lock:
            if instrument_id in self.buffers and self.buffers[instrument_id].size() > 0:
                return self.buffers[instrument_id].get_all()[-1]
            return None