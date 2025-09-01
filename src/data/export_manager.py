#!/usr/bin/env python3
"""
導出管理器
統一處理數據導出功能
"""

import csv
import json
import pandas as pd
from enum import Enum
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.unified_logger import get_logger


class ExportFormat(Enum):
    """導出格式"""
    CSV = "csv"
    JSON = "json" 
    EXCEL = "xlsx"
    PARQUET = "parquet"


class ExportManager:
    """導出管理器"""
    
    def __init__(self, base_path: str = "exports"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger("ExportManager")
        
    def export_data(self, data: List, format: ExportFormat, 
                   filename: Optional[str] = None) -> str:
        """導出數據
        
        Args:
            data: 要導出的數據列表
            format: 導出格式
            filename: 自定義檔案名
            
        Returns:
            str: 導出檔案路徑
        """
        if not data:
            raise ValueError("沒有數據可導出")
            
        # 生成檔案名
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"export_{timestamp}.{format.value}"
            
        filepath = self.base_path / filename
        
        # 根據格式調用對應的導出方法
        export_methods = {
            ExportFormat.CSV: self._export_csv,
            ExportFormat.JSON: self._export_json,
            ExportFormat.EXCEL: self._export_excel,
            ExportFormat.PARQUET: self._export_parquet
        }
        
        if format not in export_methods:
            raise ValueError(f"不支援的導出格式: {format}")
            
        try:
            export_methods[format](data, filepath)
            self.logger.info(f"數據已導出: {filepath} ({len(data)} 個數據點)")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"導出失敗: {e}")
            raise
            
    def _export_csv(self, data: List, filepath: Path):
        """導出為CSV格式"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            if hasattr(data[0], 'to_dict'):
                # MeasurementPoint對象
                first_dict = data[0].to_dict()
            else:
                # 已經是字典
                first_dict = data[0]
                
            writer = csv.DictWriter(f, fieldnames=first_dict.keys())
            writer.writeheader()
            
            for item in data:
                if hasattr(item, 'to_dict'):
                    writer.writerow(item.to_dict())
                else:
                    writer.writerow(item)
                    
    def _export_json(self, data: List, filepath: Path):
        """導出為JSON格式"""
        export_data = []
        
        for item in data:
            if hasattr(item, 'to_dict'):
                export_data.append(item.to_dict())
            else:
                export_data.append(item)
                
        output = {
            'export_info': {
                'created_at': datetime.now().isoformat(),
                'data_count': len(data),
                'format': 'json'
            },
            'data': export_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            
    def _export_excel(self, data: List, filepath: Path):
        """導出為Excel格式"""
        try:
            import openpyxl
        except ImportError:
            raise ImportError("需要安裝 openpyxl 來支援Excel導出")
            
        # 轉換為DataFrame
        df_data = []
        for item in data:
            if hasattr(item, 'to_dict'):
                df_data.append(item.to_dict())
            else:
                df_data.append(item)
                
        df = pd.DataFrame(df_data)
        df.to_excel(filepath, index=False, engine='openpyxl')
        
    def _export_parquet(self, data: List, filepath: Path):
        """導出為Parquet格式（高效壓縮）"""
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            raise ImportError("需要安裝 pyarrow 來支援Parquet導出")
            
        # 轉換為DataFrame
        df_data = []
        for item in data:
            if hasattr(item, 'to_dict'):
                df_data.append(item.to_dict())
            else:
                df_data.append(item)
                
        df = pd.DataFrame(df_data)
        table = pa.Table.from_pandas(df)
        pq.write_table(table, filepath)