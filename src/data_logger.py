"""
資料記錄模組
用於記錄和保存測量數據
"""

import csv
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
import os
import logging


class DataLogger:
    """資料記錄器類"""
    
    def __init__(self, base_path: str = "data"):
        """
        初始化資料記錄器
        
        Args:
            base_path: 資料保存基礎路徑
        """
        self.base_path = base_path
        self.logger = logging.getLogger(__name__)
        
        # 建立資料目錄
        os.makedirs(base_path, exist_ok=True)
        
        # 當前記錄會話
        self.current_session = None
        self.session_data = []
        
    def start_session(self, session_name: str = None) -> str:
        """
        開始新的記錄會話
        
        Args:
            session_name: 會話名稱（可選）
            
        Returns:
            str: 會話ID
        """
        if session_name is None:
            session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        self.current_session = session_name
        self.session_data = []
        
        self.logger.info(f"開始記錄會話: {session_name}")
        return session_name
        
    def log_measurement(self, 
                       voltage: float, 
                       current: float, 
                       resistance: float = None, 
                       power: float = None,
                       timestamp: datetime = None,
                       metadata: Dict[str, Any] = None) -> None:
        """
        記錄一次測量數據
        
        Args:
            voltage: 電壓值 (V)
            current: 電流值 (A) 
            resistance: 電阻值 (Ω)
            power: 功率值 (W)
            timestamp: 時間戳
            metadata: 額外的元數據
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # 計算缺失的值
        if resistance is None and current != 0:
            resistance = voltage / current
        if power is None:
            power = voltage * current
            
        record = {
            'timestamp': timestamp.isoformat(),
            'voltage_v': voltage,
            'current_a': current,
            'resistance_ohm': resistance,
            'power_w': power
        }
        
        # 添加元數據
        if metadata:
            record.update(metadata)
            
        self.session_data.append(record)
        
        self.logger.debug(f"記錄測量: V={voltage:.6f}V, I={current:.6f}A, "
                         f"R={resistance:.2f}Ω, P={power:.6f}W")
        
    def save_session_csv(self, filename: str = None) -> str:
        """
        保存當前會話為CSV文件
        
        Args:
            filename: 文件名（可選）
            
        Returns:
            str: 保存的文件路徑
        """
        if not self.session_data:
            raise ValueError("沒有數據可以保存")
            
        if filename is None:
            filename = f"{self.current_session}.csv"
            
        filepath = os.path.join(self.base_path, filename)
        
        # 轉換為DataFrame並保存
        df = pd.DataFrame(self.session_data)
        df.to_csv(filepath, index=False)
        
        self.logger.info(f"會話數據已保存到: {filepath}")
        return filepath
        
    def save_session_json(self, filename: str = None) -> str:
        """
        保存當前會話為JSON文件
        
        Args:
            filename: 文件名（可選）
            
        Returns:
            str: 保存的文件路徑
        """
        if not self.session_data:
            raise ValueError("沒有數據可以保存")
            
        if filename is None:
            filename = f"{self.current_session}.json"
            
        filepath = os.path.join(self.base_path, filename)
        
        session_info = {
            'session_name': self.current_session,
            'start_time': self.session_data[0]['timestamp'] if self.session_data else None,
            'end_time': self.session_data[-1]['timestamp'] if self.session_data else None,
            'total_measurements': len(self.session_data),
            'data': self.session_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(session_info, f, indent=2, ensure_ascii=False)
            
        self.logger.info(f"會話數據已保存到: {filepath}")
        return filepath
        
    def load_session(self, filepath: str) -> List[Dict[str, Any]]:
        """
        從文件載入會話數據
        
        Args:
            filepath: 文件路徑
            
        Returns:
            List[Dict]: 載入的數據
        """
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
            data = df.to_dict('records')
        elif filepath.endswith('.json'):
            with open(filepath, 'r', encoding='utf-8') as f:
                session_info = json.load(f)
                data = session_info.get('data', [])
        else:
            raise ValueError("不支援的文件格式")
            
        self.logger.info(f"從 {filepath} 載入了 {len(data)} 筆記錄")
        return data
        
    def get_session_statistics(self) -> Dict[str, Any]:
        """
        獲取當前會話的統計信息
        
        Returns:
            Dict: 統計信息
        """
        if not self.session_data:
            return {}
            
        df = pd.DataFrame(self.session_data)
        
        stats = {
            'total_measurements': len(self.session_data),
            'duration_seconds': 0,
            'voltage_stats': {
                'min': float(df['voltage_v'].min()),
                'max': float(df['voltage_v'].max()),
                'mean': float(df['voltage_v'].mean()),
                'std': float(df['voltage_v'].std())
            },
            'current_stats': {
                'min': float(df['current_a'].min()),
                'max': float(df['current_a'].max()),
                'mean': float(df['current_a'].mean()),
                'std': float(df['current_a'].std())
            },
            'power_stats': {
                'min': float(df['power_w'].min()),
                'max': float(df['power_w'].max()),
                'mean': float(df['power_w'].mean()),
                'std': float(df['power_w'].std())
            }
        }
        
        # 計算持續時間
        if len(self.session_data) > 1:
            start_time = datetime.fromisoformat(self.session_data[0]['timestamp'])
            end_time = datetime.fromisoformat(self.session_data[-1]['timestamp'])
            stats['duration_seconds'] = (end_time - start_time).total_seconds()
            
        return stats
        
    def export_summary(self, filename: str = None) -> str:
        """
        匯出會話總結報告
        
        Args:
            filename: 文件名（可選）
            
        Returns:
            str: 報告文件路徑
        """
        if filename is None:
            filename = f"{self.current_session}_summary.txt"
            
        filepath = os.path.join(self.base_path, filename)
        stats = self.get_session_statistics()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"測量會話總結報告\n")
            f.write(f"=" * 50 + "\n\n")
            f.write(f"會話名稱: {self.current_session}\n")
            f.write(f"總測量次數: {stats.get('total_measurements', 0)}\n")
            f.write(f"測量時長: {stats.get('duration_seconds', 0):.2f} 秒\n\n")
            
            if 'voltage_stats' in stats:
                f.write(f"電壓統計 (V):\n")
                v_stats = stats['voltage_stats']
                f.write(f"  最小值: {v_stats['min']:.6f}\n")
                f.write(f"  最大值: {v_stats['max']:.6f}\n")
                f.write(f"  平均值: {v_stats['mean']:.6f}\n")
                f.write(f"  標準差: {v_stats['std']:.6f}\n\n")
                
            if 'current_stats' in stats:
                f.write(f"電流統計 (A):\n")
                i_stats = stats['current_stats']
                f.write(f"  最小值: {i_stats['min']:.6f}\n")
                f.write(f"  最大值: {i_stats['max']:.6f}\n")
                f.write(f"  平均值: {i_stats['mean']:.6f}\n")
                f.write(f"  標準差: {i_stats['std']:.6f}\n\n")
                
            if 'power_stats' in stats:
                f.write(f"功率統計 (W):\n")
                p_stats = stats['power_stats']
                f.write(f"  最小值: {p_stats['min']:.6f}\n")
                f.write(f"  最大值: {p_stats['max']:.6f}\n")
                f.write(f"  平均值: {p_stats['mean']:.6f}\n")
                f.write(f"  標準差: {p_stats['std']:.6f}\n\n")
                
        self.logger.info(f"總結報告已保存到: {filepath}")
        return filepath