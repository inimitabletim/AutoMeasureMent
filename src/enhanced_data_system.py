#!/usr/bin/env python3
"""
增強型數據收集與儲存系統
支援長時間運行、數據分析、異常檢測等專業功能
"""

import csv
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import deque
import os
import logging
import threading
from dataclasses import dataclass
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from pathlib import Path


@dataclass
class MeasurementPoint:
    """測量數據點"""
    timestamp: datetime
    voltage: float
    current: float
    resistance: float
    power: float
    temperature: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典格式"""
        result = {
            'timestamp': self.timestamp.isoformat(),
            'voltage_v': self.voltage,
            'current_a': self.current,
            'resistance_ohm': self.resistance,
            'power_w': self.power
        }
        if self.temperature is not None:
            result['temperature_c'] = self.temperature
        if self.metadata:
            result.update(self.metadata)
        return result


class DataAnalyzer:
    """數據分析器"""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.voltage_buffer = deque(maxlen=window_size)
        self.current_buffer = deque(maxlen=window_size)
        self.power_buffer = deque(maxlen=window_size)
        self.resistance_buffer = deque(maxlen=window_size)
        
    def add_point(self, point: MeasurementPoint):
        """添加數據點到分析緩存"""
        self.voltage_buffer.append(point.voltage)
        self.current_buffer.append(point.current)
        self.power_buffer.append(point.power)
        self.resistance_buffer.append(point.resistance)
        
    def get_statistics(self) -> Dict[str, Dict[str, float]]:
        """計算統計數據"""
        stats = {}
        
        for name, buffer in [
            ('voltage', self.voltage_buffer),
            ('current', self.current_buffer), 
            ('power', self.power_buffer),
            ('resistance', self.resistance_buffer)
        ]:
            if len(buffer) > 0:
                data = np.array(buffer)
                stats[name] = {
                    'mean': np.mean(data),
                    'std': np.std(data),
                    'min': np.min(data),
                    'max': np.max(data),
                    'median': np.median(data),
                    'count': len(data)
                }
            else:
                stats[name] = {
                    'mean': 0, 'std': 0, 'min': 0, 
                    'max': 0, 'median': 0, 'count': 0
                }
                
        return stats
        
    def detect_anomalies(self, point: MeasurementPoint, 
                        std_threshold: float = 3.0) -> List[str]:
        """檢測異常值"""
        anomalies = []
        
        if len(self.voltage_buffer) < 10:  # 需要足夠的數據點
            return anomalies
            
        # Z-score 異常檢測
        for name, value, buffer in [
            ('voltage', point.voltage, self.voltage_buffer),
            ('current', point.current, self.current_buffer),
            ('power', point.power, self.power_buffer),
            ('resistance', point.resistance, self.resistance_buffer)
        ]:
            if len(buffer) > 5:
                data = np.array(buffer)
                mean = np.mean(data)
                std = np.std(data)
                
                if std > 0:  # 避免除零錯誤
                    z_score = abs(value - mean) / std
                    if z_score > std_threshold:
                        anomalies.append(f"{name}_anomaly")
                        
        return anomalies


class EnhancedDataLogger(QObject):
    """增強型數據記錄器"""
    
    # 信號定義
    data_saved = pyqtSignal(str)  # 數據保存完成
    statistics_updated = pyqtSignal(dict)  # 統計數據更新
    anomaly_detected = pyqtSignal(str, dict)  # 異常檢測
    storage_warning = pyqtSignal(str)  # 存儲警告
    
    def __init__(self, base_path: str = "data", 
                 auto_save_interval: int = 300,  # 5分鐘自動保存
                 max_memory_points: int = 10000):  # 內存最大數據點
        super().__init__()
        
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        self.auto_save_interval = auto_save_interval
        self.max_memory_points = max_memory_points
        
        # 當前會話
        self.current_session = None
        self.session_start_time = None
        
        # 數據存儲
        self.memory_buffer = deque(maxlen=max_memory_points)
        self.total_points = 0
        
        # 數據分析
        self.analyzer = DataAnalyzer()
        
        # 數據庫連接
        self.db_connection = None
        self.init_database()
        
        # 自動保存定時器
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save_data)
        
        # 線程鎖
        self.data_lock = threading.RLock()
        
        # 日誌
        self.logger = logging.getLogger(__name__)
        
    def init_database(self):
        """初始化SQLite數據庫"""
        db_path = self.base_path / "measurement_data.db"
        
        try:
            self.db_connection = sqlite3.connect(
                str(db_path), 
                check_same_thread=False,
                timeout=30.0
            )
            
            # 創建表
            cursor = self.db_connection.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    voltage_v REAL NOT NULL,
                    current_a REAL NOT NULL,
                    resistance_ohm REAL,
                    power_w REAL,
                    temperature_c REAL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_points INTEGER DEFAULT 0,
                    description TEXT,
                    instrument_config TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 創建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_session_timestamp 
                ON measurements(session_id, timestamp)
            ''')
            
            self.db_connection.commit()
            self.logger.info("數據庫初始化完成")
            
        except Exception as e:
            self.logger.error(f"數據庫初始化失敗: {e}")
            self.db_connection = None
    
    def start_session(self, session_name: str = None, 
                     description: str = "", 
                     instrument_config: Dict[str, Any] = None) -> str:
        """開始新的記錄會話"""
        
        if session_name is None:
            session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        self.current_session = session_name
        self.session_start_time = datetime.now()
        
        # 清空緩存
        with self.data_lock:
            self.memory_buffer.clear()
            self.total_points = 0
            
        # 記錄到數據庫
        if self.db_connection:
            try:
                cursor = self.db_connection.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO sessions 
                    (session_id, start_time, description, instrument_config)
                    VALUES (?, ?, ?, ?)
                ''', (
                    session_name,
                    self.session_start_time.isoformat(),
                    description,
                    json.dumps(instrument_config) if instrument_config else None
                ))
                self.db_connection.commit()
            except Exception as e:
                self.logger.error(f"會話記錄失敗: {e}")
        
        # 啟動自動保存
        if self.auto_save_interval > 0:
            self.auto_save_timer.start(self.auto_save_interval * 1000)
            
        self.logger.info(f"開始記錄會話: {session_name}")
        return session_name
    
    def log_measurement(self, voltage: float, current: float, 
                       resistance: float = None, power: float = None,
                       temperature: float = None,
                       metadata: Dict[str, Any] = None) -> MeasurementPoint:
        """記錄測量數據"""
        
        # 計算缺失值
        if resistance is None and current != 0:
            resistance = voltage / current
        if power is None:
            power = voltage * current
            
        # 創建數據點
        point = MeasurementPoint(
            timestamp=datetime.now(),
            voltage=voltage,
            current=current,
            resistance=resistance,
            power=power,
            temperature=temperature,
            metadata=metadata
        )
        
        with self.data_lock:
            # 添加到內存緩存
            self.memory_buffer.append(point)
            self.total_points += 1
            
            # 數據分析
            self.analyzer.add_point(point)
            
            # 異常檢測
            anomalies = self.analyzer.detect_anomalies(point)
            if anomalies:
                self.anomaly_detected.emit(
                    f"檢測到異常: {', '.join(anomalies)}", 
                    point.to_dict()
                )
        
        # 定期保存到數據庫
        if self.total_points % 100 == 0:  # 每100個點保存一次
            self.save_buffer_to_db()
            
        # 定期更新統計
        if self.total_points % 50 == 0:
            stats = self.analyzer.get_statistics()
            self.statistics_updated.emit(stats)
        
        # 內存管理警告
        if len(self.memory_buffer) >= self.max_memory_points * 0.9:
            self.storage_warning.emit("內存使用率過高，建議保存數據")
            
        return point
    
    def save_buffer_to_db(self):
        """將內存緩存保存到數據庫"""
        if not self.db_connection or not self.current_session:
            return
            
        with self.data_lock:
            if not self.memory_buffer:
                return
                
            try:
                cursor = self.db_connection.cursor()
                
                # 批量插入數據
                data_to_insert = []
                for point in self.memory_buffer:
                    data_to_insert.append((
                        self.current_session,
                        point.timestamp.isoformat(),
                        point.voltage,
                        point.current,
                        point.resistance,
                        point.power,
                        point.temperature,
                        json.dumps(point.metadata) if point.metadata else None
                    ))
                
                cursor.executemany('''
                    INSERT INTO measurements 
                    (session_id, timestamp, voltage_v, current_a, 
                     resistance_ohm, power_w, temperature_c, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', data_to_insert)
                
                self.db_connection.commit()
                self.logger.debug(f"保存 {len(data_to_insert)} 個數據點到數據庫")
                
            except Exception as e:
                self.logger.error(f"數據庫保存失敗: {e}")
    
    def auto_save_data(self):
        """自動保存數據"""
        try:
            self.save_buffer_to_db()
            
            # 更新會話統計
            if self.db_connection and self.current_session:
                cursor = self.db_connection.cursor()
                cursor.execute('''
                    UPDATE sessions SET total_points = ?, end_time = ?
                    WHERE session_id = ?
                ''', (
                    self.total_points,
                    datetime.now().isoformat(),
                    self.current_session
                ))
                self.db_connection.commit()
                
            self.data_saved.emit(f"自動保存完成 - {self.total_points} 個數據點")
            
        except Exception as e:
            self.logger.error(f"自動保存失敗: {e}")
    
    def export_session_data(self, format_type: str = "csv", 
                           session_id: str = None) -> str:
        """匯出會話數據"""
        if session_id is None:
            session_id = self.current_session
            
        if not session_id:
            raise ValueError("沒有指定的會話")
        
        # 從數據庫獲取數據
        if self.db_connection:
            query = '''
                SELECT timestamp, voltage_v, current_a, resistance_ohm, 
                       power_w, temperature_c, metadata
                FROM measurements 
                WHERE session_id = ? 
                ORDER BY timestamp
            '''
            df = pd.read_sql_query(query, self.db_connection, params=[session_id])
        else:
            # 使用內存數據
            data = [point.to_dict() for point in self.memory_buffer]
            df = pd.DataFrame(data)
        
        # 匯出文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type.lower() == "csv":
            filename = f"{session_id}_{timestamp}.csv"
            filepath = self.base_path / filename
            df.to_csv(filepath, index=False)
            
        elif format_type.lower() == "json":
            filename = f"{session_id}_{timestamp}.json"
            filepath = self.base_path / filename
            
            export_data = {
                'session_id': session_id,
                'export_time': datetime.now().isoformat(),
                'total_points': len(df),
                'data': df.to_dict('records')
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
                
        elif format_type.lower() == "xlsx":
            filename = f"{session_id}_{timestamp}.xlsx"
            filepath = self.base_path / filename
            df.to_excel(filepath, index=False)
            
        else:
            raise ValueError(f"不支援的匯出格式: {format_type}")
        
        self.logger.info(f"數據已匯出: {filepath}")
        return str(filepath)
    
    def get_session_statistics(self, session_id: str = None) -> Dict[str, Any]:
        """獲取會話統計數據"""
        if session_id is None:
            session_id = self.current_session
            
        stats = self.analyzer.get_statistics()
        
        # 添加會話信息
        stats['session_info'] = {
            'session_id': session_id,
            'start_time': self.session_start_time.isoformat() if self.session_start_time else None,
            'total_points': self.total_points,
            'duration_seconds': (datetime.now() - self.session_start_time).total_seconds() if self.session_start_time else 0
        }
        
        return stats
    
    def close_session(self):
        """結束當前會話"""
        if self.current_session:
            # 最後一次保存
            self.save_buffer_to_db()
            
            # 停止自動保存
            self.auto_save_timer.stop()
            
            # 更新會話結束時間
            if self.db_connection:
                try:
                    cursor = self.db_connection.cursor()
                    cursor.execute('''
                        UPDATE sessions SET end_time = ?, total_points = ?
                        WHERE session_id = ?
                    ''', (
                        datetime.now().isoformat(),
                        self.total_points,
                        self.current_session
                    ))
                    self.db_connection.commit()
                except Exception as e:
                    self.logger.error(f"會話結束記錄失敗: {e}")
            
            self.logger.info(f"會話結束: {self.current_session}, 總計 {self.total_points} 個數據點")
            self.current_session = None
    
    def cleanup(self):
        """清理資源"""
        self.close_session()
        
        if self.db_connection:
            self.db_connection.close()
            self.db_connection = None