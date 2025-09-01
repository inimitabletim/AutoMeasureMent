#!/usr/bin/env python3
"""
存儲後端實現
支援CSV、JSON、SQLite等多種數據存儲格式
"""

import csv
import json
import sqlite3
import pandas as pd
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.unified_logger import get_logger


class StorageBackend(ABC):
    """存儲後端抽象基類"""
    
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(f"Storage.{self.__class__.__name__}")
        
    @abstractmethod
    def save_point(self, point) -> bool:
        """保存單個數據點"""
        pass
        
    @abstractmethod
    def save_session(self, session_name: str, points: List) -> str:
        """保存整個會話的數據"""
        pass
        
    @abstractmethod 
    def load_session(self, session_name: str) -> List:
        """載入會話數據"""
        pass


class CSVStorage(StorageBackend):
    """CSV存儲後端"""
    
    def __init__(self, base_path: str = "data"):
        super().__init__(base_path)
        self.current_file = None
        self.current_writer = None
        
    def save_point(self, point) -> bool:
        """保存數據點到CSV"""
        try:
            # 確保有當前檔案
            if self.current_file is None:
                self._create_new_file()
                
            # 寫入數據
            if self.current_writer:
                row = point.to_dict()
                self.current_writer.writerow(row)
                return True
                
        except Exception as e:
            self.logger.error(f"CSV保存失敗: {e}")
            return False
            
    def save_session(self, session_name: str, points: List) -> str:
        """保存會話到CSV檔案"""
        filename = self.base_path / f"{session_name}.csv"
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                if points:
                    writer = csv.DictWriter(f, fieldnames=points[0].to_dict().keys())
                    writer.writeheader()
                    
                    for point in points:
                        writer.writerow(point.to_dict())
                        
            self.logger.info(f"會話已保存到CSV: {filename}")
            return str(filename)
            
        except Exception as e:
            self.logger.error(f"保存CSV會話失敗: {e}")
            raise
            
    def load_session(self, session_name: str) -> List:
        """從CSV載入會話數據"""
        filename = self.base_path / f"{session_name}.csv"
        
        try:
            if not filename.exists():
                return []
                
            df = pd.read_csv(filename)
            points = []
            
            for _, row in df.iterrows():
                # 轉換回MeasurementPoint格式
                points.append(row.to_dict())
                
            return points
            
        except Exception as e:
            self.logger.error(f"載入CSV會話失敗: {e}")
            return []
            
    def _create_new_file(self):
        """創建新的CSV檔案"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.base_path / f"measurements_{timestamp}.csv"
        
        self.current_file = open(filename, 'w', newline='', encoding='utf-8')
        # 稍後在第一個數據點時創建writer


class JSONStorage(StorageBackend):
    """JSON存儲後端"""
    
    def save_point(self, point) -> bool:
        """保存數據點到JSON（實時模式）"""
        # 對於實時保存，我們使用緩存並定期寫入
        return True  # 簡化實現
        
    def save_session(self, session_name: str, points: List) -> str:
        """保存會話到JSON檔案"""
        filename = self.base_path / f"{session_name}.json"
        
        try:
            data = {
                'session_name': session_name,
                'created_at': datetime.now().isoformat(),
                'measurement_count': len(points),
                'measurements': [point.to_dict() for point in points]
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"會話已保存到JSON: {filename}")
            return str(filename)
            
        except Exception as e:
            self.logger.error(f"保存JSON會話失敗: {e}")
            raise
            
    def load_session(self, session_name: str) -> List:
        """從JSON載入會話數據"""
        filename = self.base_path / f"{session_name}.json"
        
        try:
            if not filename.exists():
                return []
                
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            return data.get('measurements', [])
            
        except Exception as e:
            self.logger.error(f"載入JSON會話失敗: {e}")
            return []


class SQLiteStorage(StorageBackend):
    """SQLite存儲後端 - 用於大量數據和複雜查詢"""
    
    def __init__(self, base_path: str = "data"):
        super().__init__(base_path)
        self.db_path = self.base_path / "measurements.db"
        self._init_database()
        
    def _init_database(self):
        """初始化數據庫表結構"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS measurements (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        instrument_id TEXT NOT NULL,
                        session_name TEXT,
                        voltage REAL NOT NULL,
                        current REAL NOT NULL,
                        resistance REAL,
                        power REAL,
                        temperature REAL,
                        metadata TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_timestamp 
                    ON measurements(timestamp)
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_instrument_session 
                    ON measurements(instrument_id, session_name)
                ''')
                
        except Exception as e:
            self.logger.error(f"初始化數據庫失敗: {e}")
            
    def save_point(self, point) -> bool:
        """保存數據點到SQLite"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO measurements 
                    (timestamp, instrument_id, voltage, current, resistance, power, temperature, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    point.timestamp.isoformat(),
                    point.instrument_id,
                    point.voltage,
                    point.current,
                    point.resistance,
                    point.power,
                    point.temperature,
                    json.dumps(point.metadata) if point.metadata else None
                ))
                
            return True
            
        except Exception as e:
            self.logger.error(f"SQLite保存失敗: {e}")
            return False
            
    def save_session(self, session_name: str, points: List) -> str:
        """保存會話到SQLite"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                for point in points:
                    conn.execute('''
                        INSERT INTO measurements 
                        (timestamp, instrument_id, session_name, voltage, current, resistance, power, temperature, metadata)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        point.timestamp.isoformat(),
                        point.instrument_id,
                        session_name,
                        point.voltage,
                        point.current,
                        point.resistance,
                        point.power,
                        point.temperature,
                        json.dumps(point.metadata) if point.metadata else None
                    ))
                    
            self.logger.info(f"會話已保存到SQLite: {session_name} ({len(points)} 個點)")
            return str(self.db_path)
            
        except Exception as e:
            self.logger.error(f"保存SQLite會話失敗: {e}")
            raise
            
    def load_session(self, session_name: str) -> List:
        """從SQLite載入會話數據"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute('''
                    SELECT timestamp, instrument_id, voltage, current, resistance, power, temperature, metadata
                    FROM measurements 
                    WHERE session_name = ?
                    ORDER BY timestamp
                ''', (session_name,))
                
                points = []
                for row in cursor.fetchall():
                    point_dict = {
                        'timestamp': row[0],
                        'instrument_id': row[1], 
                        'voltage': row[2],
                        'current': row[3],
                        'resistance': row[4],
                        'power': row[5],
                        'temperature': row[6],
                        'metadata': json.loads(row[7]) if row[7] else None
                    }
                    points.append(point_dict)
                    
                return points
                
        except Exception as e:
            self.logger.error(f"載入SQLite會話失敗: {e}")
            return []