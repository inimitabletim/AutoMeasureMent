#!/usr/bin/env python3
"""
統一數據管理器
整合 DataLogger 和 EnhancedDataLogger 的功能
提供高性能、統一的數據管理介面
"""

import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from collections import defaultdict
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from .buffer_manager import BufferManager
from .storage_backends import StorageBackend, CSVStorage, JSONStorage, SQLiteStorage
from .export_manager import ExportManager, ExportFormat
from src.config import get_config
from src.unified_logger import get_logger


@dataclass
class MeasurementPoint:
    """標準化測量數據點"""
    timestamp: datetime
    instrument_id: str
    voltage: float
    current: float
    resistance: Optional[float] = None
    power: Optional[float] = None
    temperature: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """計算衍生值"""
        if self.resistance is None and self.current != 0:
            self.resistance = self.voltage / self.current
        if self.power is None:
            self.power = self.voltage * self.current
            
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result


class DataAnalytics:
    """實時數據分析器"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.analysis_functions: List[Callable] = []
        self.anomaly_threshold = 3.0  # 標準差倍數
        
    def add_analysis_function(self, func: Callable):
        """添加分析函數"""
        self.analysis_functions.append(func)
        
    def analyze_point(self, point: MeasurementPoint, 
                     historical_data: List[MeasurementPoint]) -> Dict[str, Any]:
        """分析數據點"""
        analysis_result = {
            'timestamp': point.timestamp,
            'anomalies': [],
            'statistics': {},
            'alerts': []
        }
        
        # 基本統計分析
        if len(historical_data) >= 10:
            analysis_result['statistics'] = self._calculate_statistics(historical_data)
            analysis_result['anomalies'] = self._detect_anomalies(point, historical_data)
            
        # 執行自定義分析函數
        for func in self.analysis_functions:
            try:
                custom_result = func(point, historical_data)
                if custom_result:
                    analysis_result.update(custom_result)
            except Exception as e:
                pass  # 忽略分析函數錯誤
                
        return analysis_result
        
    def _calculate_statistics(self, data: List[MeasurementPoint]) -> Dict[str, Dict[str, float]]:
        """計算統計數據"""
        import numpy as np
        
        stats = {}
        recent_data = data[-self.window_size:]
        
        for param in ['voltage', 'current', 'power', 'resistance']:
            values = [getattr(point, param) for point in recent_data 
                     if getattr(point, param) is not None]
            
            if values:
                values_array = np.array(values)
                stats[param] = {
                    'mean': float(np.mean(values_array)),
                    'std': float(np.std(values_array)),
                    'min': float(np.min(values_array)),
                    'max': float(np.max(values_array)),
                    'median': float(np.median(values_array)),
                    'count': len(values)
                }
                
        return stats
        
    def _detect_anomalies(self, point: MeasurementPoint, 
                         data: List[MeasurementPoint]) -> List[str]:
        """檢測異常值"""
        import numpy as np
        
        anomalies = []
        recent_data = data[-self.window_size:]
        
        for param in ['voltage', 'current', 'power']:
            current_value = getattr(point, param)
            if current_value is None:
                continue
                
            historical_values = [getattr(p, param) for p in recent_data 
                                if getattr(p, param) is not None]
            
            if len(historical_values) >= 10:
                mean = np.mean(historical_values)
                std = np.std(historical_values)
                
                if std > 0 and abs(current_value - mean) > self.anomaly_threshold * std:
                    anomalies.append(f"{param}_anomaly")
                    
        return anomalies


class UnifiedDataManager(QObject):
    """統一數據管理器
    
    整合了原有的 DataLogger 和 EnhancedDataLogger 功能：
    - 實時數據緩存
    - 持久化存儲
    - 數據分析
    - 靈活導出
    """
    
    # 信號
    data_point_added = pyqtSignal(dict)  # 新數據點
    session_started = pyqtSignal(str)    # 會話開始
    session_ended = pyqtSignal(str, dict)  # 會話結束，統計信息
    analysis_ready = pyqtSignal(str, dict)  # 分析結果
    storage_error = pyqtSignal(str)      # 存儲錯誤
    
    def __init__(self):
        super().__init__()
        self.config = get_config()
        self.logger = get_logger("UnifiedDataManager")
        
        # 緩存管理
        self.buffer_manager = BufferManager()
        
        # 存儲後端
        self._setup_storage_backends()
        
        # 導出管理
        self.export_manager = ExportManager()
        
        # 數據分析
        self.analytics = DataAnalytics()
        
        # 會話管理
        self.current_session: Optional[str] = None
        self.session_data: Dict[str, List[MeasurementPoint]] = defaultdict(list)
        
        # 自動保存定時器
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self._auto_save)
        self._setup_auto_save()
        
        # 線程安全
        self._lock = threading.RLock()
        
    def _setup_storage_backends(self):
        """設置存儲後端"""
        data_config = self.config.get_data_config('storage')
        
        self.storage_backends = {
            'csv': CSVStorage(base_path=data_config['base_path']),
            'json': JSONStorage(base_path=data_config['base_path']),
            'sqlite': SQLiteStorage(base_path=data_config['base_path'])
        }
        
        self.default_storage = self.storage_backends[data_config['default_format']]
        
    def _setup_auto_save(self):
        """設置自動保存"""
        data_config = self.config.get_data_config('storage')
        
        if data_config['auto_save']:
            interval_ms = data_config['auto_save_interval'] * 1000
            self.auto_save_timer.start(interval_ms)
            self.logger.info(f"自動保存已啟用，間隔: {data_config['auto_save_interval']}秒")
            
    def register_instrument(self, instrument_id: str, 
                          buffer_size: Optional[int] = None) -> bool:
        """註冊儀器以進行數據管理
        
        Args:
            instrument_id: 儀器標識符
            buffer_size: 緩存大小，None使用預設值
            
        Returns:
            bool: 註冊是否成功
        """
        try:
            with self._lock:
                if buffer_size is None:
                    buffer_size = self.config.get('data.buffer.real_time_buffer_size', 1000)
                    
                self.buffer_manager.create_buffer(instrument_id, buffer_size)
                self.logger.info(f"已註冊儀器: {instrument_id}, 緩存大小: {buffer_size}")
                return True
                
        except Exception as e:
            self.logger.error(f"註冊儀器失敗: {e}")
            return False
            
    def add_measurement(self, point: MeasurementPoint) -> bool:
        """添加測量數據點
        
        Args:
            point: 測量數據點
            
        Returns:
            bool: 添加是否成功
        """
        try:
            with self._lock:
                # 添加到緩存
                self.buffer_manager.add_point(point.instrument_id, point)
                
                # 添加到會話數據
                if self.current_session:
                    self.session_data[point.instrument_id].append(point)
                    
                # 執行實時分析
                historical_data = self.buffer_manager.get_recent_points(
                    point.instrument_id, 100
                )
                analysis_result = self.analytics.analyze_point(point, historical_data)
                
                # 發送信號
                self.data_point_added.emit(point.to_dict())
                
                if analysis_result.get('anomalies') or analysis_result.get('alerts'):
                    self.analysis_ready.emit(point.instrument_id, analysis_result)
                    
                # 持久化存儲（如果啟用）
                if self.config.get('data.storage.auto_save', True):
                    self.default_storage.save_point(point)
                    
                return True
                
        except Exception as e:
            self.logger.error(f"添加數據點失敗: {e}")
            self.storage_error.emit(str(e))
            return False
            
    def start_session(self, session_name: Optional[str] = None) -> str:
        """開始新的數據會話
        
        Args:
            session_name: 會話名稱，None為自動生成
            
        Returns:
            str: 會話ID
        """
        with self._lock:
            if session_name is None:
                session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
            self.current_session = session_name
            self.session_data.clear()
            
            self.session_started.emit(session_name)
            self.logger.info(f"會話已開始: {session_name}")
            
            return session_name
            
    def end_session(self) -> Optional[Dict[str, Any]]:
        """結束當前會話
        
        Returns:
            Dict: 會話統計信息
        """
        if not self.current_session:
            return None
            
        with self._lock:
            session_name = self.current_session
            session_stats = self._calculate_session_statistics()
            
            # 保存會話數據
            self._save_session_data(session_name)
            
            # 清理
            self.current_session = None
            self.session_data.clear()
            
            self.session_ended.emit(session_name, session_stats)
            self.logger.info(f"會話已結束: {session_name}")
            
            return session_stats
            
    def _calculate_session_statistics(self) -> Dict[str, Any]:
        """計算會話統計信息"""
        stats = {
            'session_name': self.current_session,
            'start_time': None,
            'end_time': datetime.now(),
            'instruments': {},
            'total_measurements': 0
        }
        
        for instrument_id, points in self.session_data.items():
            if not points:
                continue
                
            if stats['start_time'] is None or points[0].timestamp < stats['start_time']:
                stats['start_time'] = points[0].timestamp
                
            instrument_stats = {
                'measurement_count': len(points),
                'duration': (points[-1].timestamp - points[0].timestamp).total_seconds(),
                'avg_voltage': sum(p.voltage for p in points) / len(points),
                'avg_current': sum(p.current for p in points) / len(points),
                'max_power': max(p.power for p in points if p.power),
                'total_energy': sum(p.power for p in points if p.power) * len(points) / 3600  # Wh估算
            }
            
            stats['instruments'][instrument_id] = instrument_stats
            stats['total_measurements'] += len(points)
            
        return stats
        
    def _save_session_data(self, session_name: str):
        """保存會話數據"""
        try:
            # 合併所有儀器的數據
            all_points = []
            for points in self.session_data.values():
                all_points.extend(points)
                
            if all_points:
                # 按時間排序
                all_points.sort(key=lambda p: p.timestamp)
                
                # 保存到預設格式
                filename = self.default_storage.save_session(session_name, all_points)
                self.logger.info(f"會話數據已保存: {filename}")
                
        except Exception as e:
            self.logger.error(f"保存會話數據失敗: {e}")
            self.storage_error.emit(str(e))
            
    def get_real_time_data(self, instrument_id: str, 
                          count: int = 100) -> List[MeasurementPoint]:
        """獲取實時數據
        
        Args:
            instrument_id: 儀器ID
            count: 數據點數量
            
        Returns:
            List[MeasurementPoint]: 最近的數據點
        """
        return self.buffer_manager.get_recent_points(instrument_id, count)
        
    def get_session_data(self, instrument_id: Optional[str] = None) -> List[MeasurementPoint]:
        """獲取會話數據
        
        Args:
            instrument_id: 儀器ID，None返回所有數據
            
        Returns:
            List[MeasurementPoint]: 會話數據
        """
        with self._lock:
            if instrument_id:
                return self.session_data.get(instrument_id, []).copy()
            else:
                all_data = []
                for points in self.session_data.values():
                    all_data.extend(points)
                return sorted(all_data, key=lambda p: p.timestamp)
                
    def export_data(self, format: ExportFormat, 
                   instrument_id: Optional[str] = None,
                   time_range: Optional[Tuple[datetime, datetime]] = None,
                   filename: Optional[str] = None) -> Optional[str]:
        """導出數據
        
        Args:
            format: 導出格式
            instrument_id: 儀器ID過濾
            time_range: 時間範圍過濾
            filename: 自定義檔案名
            
        Returns:
            str: 導出檔案路徑
        """
        try:
            # 獲取要導出的數據
            if self.current_session:
                data = self.get_session_data(instrument_id)
            else:
                data = self.get_real_time_data(instrument_id or 'all', 10000)
                
            # 時間過濾
            if time_range:
                start_time, end_time = time_range
                data = [p for p in data if start_time <= p.timestamp <= end_time]
                
            # 執行導出
            return self.export_manager.export_data(data, format, filename)
            
        except Exception as e:
            self.logger.error(f"導出數據失敗: {e}")
            self.storage_error.emit(str(e))
            return None
            
    def get_statistics(self, instrument_id: str, 
                      time_range: Optional[timedelta] = None) -> Dict[str, Any]:
        """獲取統計信息
        
        Args:
            instrument_id: 儀器ID
            time_range: 統計時間範圍
            
        Returns:
            Dict: 統計信息
        """
        with self._lock:
            data = self.get_real_time_data(instrument_id, 1000)
            
            if time_range:
                cutoff_time = datetime.now() - time_range
                data = [p for p in data if p.timestamp >= cutoff_time]
                
            return self.analytics._calculate_statistics(data)
            
    def clear_data(self, instrument_id: Optional[str] = None):
        """清除數據
        
        Args:
            instrument_id: 儀器ID，None清除所有數據
        """
        with self._lock:
            if instrument_id:
                self.buffer_manager.clear_buffer(instrument_id)
                if instrument_id in self.session_data:
                    del self.session_data[instrument_id]
            else:
                self.buffer_manager.clear_all_buffers()
                self.session_data.clear()
                
            self.logger.info(f"數據已清除: {instrument_id or '全部'}")
            
    def _auto_save(self):
        """自動保存處理"""
        if self.current_session and self.session_data:
            try:
                # 創建備份點
                backup_name = f"{self.current_session}_backup_{datetime.now().strftime('%H%M%S')}"
                self._save_session_data(backup_name)
            except Exception as e:
                self.logger.error(f"自動保存失敗: {e}")
                
    def get_memory_usage(self) -> Dict[str, int]:
        """獲取內存使用情況
        
        Returns:
            Dict: 內存使用統計
        """
        return self.buffer_manager.get_memory_usage()
        
    def optimize_memory(self):
        """優化內存使用"""
        with self._lock:
            self.buffer_manager.optimize_memory()
            
            # 清理過期的會話數據
            if self.current_session:
                max_session_points = self.config.get('data.buffer.persistent_buffer_size', 10000)
                for instrument_id in self.session_data:
                    if len(self.session_data[instrument_id]) > max_session_points:
                        # 保留最新的數據點
                        self.session_data[instrument_id] = self.session_data[instrument_id][-max_session_points:]
                        
            self.logger.info("內存優化完成")


# 全局數據管理器實例
_data_manager = None

def get_data_manager() -> UnifiedDataManager:
    """獲取全局數據管理器實例
    
    Returns:
        UnifiedDataManager: 數據管理器實例
    """
    global _data_manager
    if _data_manager is None:
        _data_manager = UnifiedDataManager()
    return _data_manager