#!/usr/bin/env python3
"""
資料庫維護工具
用於管理測量數據庫的大小、清理舊數據、歸檔重要數據
"""

import sqlite3
import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseMaintenance:
    """資料庫維護管理器"""
    
    def __init__(self, db_path: str = "data/measurement_data.db"):
        """
        初始化資料庫維護工具
        
        Args:
            db_path: 資料庫文件路徑
        """
        self.db_path = Path(db_path)
        self.archive_dir = self.db_path.parent / "archives"
        self.archive_dir.mkdir(exist_ok=True)
        
        # 維護策略配置
        self.config = {
            'max_db_size_mb': 100,           # 最大資料庫大小 (MB)
            'retention_days': 30,             # 資料保留天數
            'archive_days': 7,                # 歸檔超過此天數的資料
            'cleanup_batch_size': 10000,      # 清理批次大小
            'vacuum_threshold_mb': 50,        # 觸發VACUUM的閾值 (MB)
            'auto_backup': True,              # 自動備份
            'compression': True               # 歸檔壓縮
        }
        
    def get_database_info(self) -> Dict:
        """獲取資料庫信息"""
        if not self.db_path.exists():
            return {'exists': False, 'message': '資料庫文件不存在'}
            
        # 文件大小
        size_bytes = self.db_path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        
        # 連接資料庫獲取詳細信息
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        info = {
            'exists': True,
            'path': str(self.db_path),
            'size_bytes': size_bytes,
            'size_mb': round(size_mb, 2),
            'tables': {}
        }
        
        try:
            # 獲取所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table_name in tables:
                table_name = table_name[0]
                
                # 獲取記錄數
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                # 獲取最早和最新記錄時間
                time_info = {}
                if table_name == 'measurements':
                    cursor.execute(f"""
                        SELECT MIN(timestamp), MAX(timestamp) 
                        FROM {table_name}
                    """)
                    min_time, max_time = cursor.fetchone()
                    time_info = {
                        'earliest': min_time,
                        'latest': max_time
                    }
                
                info['tables'][table_name] = {
                    'row_count': row_count,
                    **time_info
                }
                
            # 分析資料分布
            if 'measurements' in info['tables'] and info['tables']['measurements']['row_count'] > 0:
                cursor.execute("""
                    SELECT 
                        DATE(timestamp) as date,
                        COUNT(*) as count
                    FROM measurements
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                    LIMIT 30
                """)
                daily_counts = cursor.fetchall()
                info['daily_distribution'] = [
                    {'date': date, 'count': count} for date, count in daily_counts
                ]
                
        except Exception as e:
            logger.error(f"獲取資料庫信息失敗: {e}")
            info['error'] = str(e)
            
        finally:
            conn.close()
            
        return info
        
    def cleanup_old_data(self, days: Optional[int] = None, dry_run: bool = False) -> Dict:
        """
        清理舊數據
        
        Args:
            days: 保留最近幾天的數據 (None使用預設值)
            dry_run: 是否僅預覽不實際刪除
            
        Returns:
            清理結果
        """
        retention_days = days or self.config['retention_days']
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        result = {
            'cutoff_date': cutoff_date.isoformat(),
            'retention_days': retention_days,
            'dry_run': dry_run,
            'deleted_count': 0,
            'space_freed_mb': 0
        }
        
        try:
            # 計算將要刪除的記錄數
            cursor.execute("""
                SELECT COUNT(*) FROM measurements 
                WHERE timestamp < ?
            """, (cutoff_date.isoformat(),))
            
            delete_count = cursor.fetchone()[0]
            result['deleted_count'] = delete_count
            
            if delete_count == 0:
                result['message'] = '沒有需要清理的舊數據'
                return result
                
            if not dry_run:
                # 執行刪除
                cursor.execute("""
                    DELETE FROM measurements 
                    WHERE timestamp < ?
                """, (cutoff_date.isoformat(),))
                
                conn.commit()
                
                # 執行VACUUM優化資料庫
                initial_size = self.db_path.stat().st_size
                conn.execute("VACUUM")
                final_size = self.db_path.stat().st_size
                
                result['space_freed_mb'] = round((initial_size - final_size) / (1024 * 1024), 2)
                result['message'] = f'成功刪除 {delete_count} 條記錄，釋放 {result["space_freed_mb"]} MB 空間'
            else:
                # 估算空間
                avg_record_size = self.db_path.stat().st_size / max(cursor.execute("SELECT COUNT(*) FROM measurements").fetchone()[0], 1)
                estimated_freed = (delete_count * avg_record_size) / (1024 * 1024)
                result['estimated_space_freed_mb'] = round(estimated_freed, 2)
                result['message'] = f'預覽模式：將刪除 {delete_count} 條記錄，預計釋放 {result["estimated_space_freed_mb"]} MB 空間'
                
        except Exception as e:
            logger.error(f"清理數據失敗: {e}")
            result['error'] = str(e)
            
        finally:
            conn.close()
            
        return result
        
    def archive_data(self, days: Optional[int] = None, compress: bool = True) -> Dict:
        """
        歸檔舊數據到CSV文件
        
        Args:
            days: 歸檔超過此天數的數據
            compress: 是否壓縮歸檔文件
            
        Returns:
            歸檔結果
        """
        archive_days = days or self.config['archive_days']
        cutoff_date = datetime.now() - timedelta(days=archive_days)
        
        result = {
            'archive_days': archive_days,
            'cutoff_date': cutoff_date.isoformat(),
            'archived_count': 0,
            'archive_file': None
        }
        
        try:
            # 讀取需要歸檔的數據
            conn = sqlite3.connect(self.db_path)
            
            query = """
                SELECT * FROM measurements 
                WHERE timestamp < ?
                ORDER BY timestamp
            """
            
            df = pd.read_sql_query(query, conn, params=[cutoff_date.isoformat()])
            
            if df.empty:
                result['message'] = '沒有需要歸檔的數據'
                return result
                
            # 生成歸檔文件名
            archive_filename = f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            archive_path = self.archive_dir / f"{archive_filename}.csv"
            
            # 保存到CSV
            df.to_csv(archive_path, index=False)
            result['archived_count'] = len(df)
            
            # 壓縮
            if compress:
                import gzip
                compressed_path = self.archive_dir / f"{archive_filename}.csv.gz"
                
                with open(archive_path, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                        
                # 刪除原始CSV
                archive_path.unlink()
                result['archive_file'] = str(compressed_path)
                result['compressed'] = True
            else:
                result['archive_file'] = str(archive_path)
                result['compressed'] = False
                
            result['message'] = f'成功歸檔 {result["archived_count"]} 條記錄到 {result["archive_file"]}'
            
        except Exception as e:
            logger.error(f"歸檔數據失敗: {e}")
            result['error'] = str(e)
            
        finally:
            if 'conn' in locals():
                conn.close()
                
        return result
        
    def optimize_database(self) -> Dict:
        """
        優化資料庫性能
        
        Returns:
            優化結果
        """
        result = {
            'optimizations': [],
            'initial_size_mb': 0,
            'final_size_mb': 0
        }
        
        try:
            initial_size = self.db_path.stat().st_size
            result['initial_size_mb'] = round(initial_size / (1024 * 1024), 2)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. 重建索引
            cursor.execute("REINDEX")
            result['optimizations'].append('重建索引完成')
            
            # 2. 分析表統計信息
            cursor.execute("ANALYZE")
            result['optimizations'].append('更新統計信息完成')
            
            # 3. VACUUM 壓縮資料庫
            conn.execute("VACUUM")
            result['optimizations'].append('VACUUM壓縮完成')
            
            conn.close()
            
            final_size = self.db_path.stat().st_size
            result['final_size_mb'] = round(final_size / (1024 * 1024), 2)
            result['space_saved_mb'] = round((initial_size - final_size) / (1024 * 1024), 2)
            result['message'] = f'優化完成，節省 {result["space_saved_mb"]} MB 空間'
            
        except Exception as e:
            logger.error(f"優化資料庫失敗: {e}")
            result['error'] = str(e)
            
        return result
        
    def backup_database(self, backup_name: Optional[str] = None) -> Dict:
        """
        備份資料庫
        
        Args:
            backup_name: 備份文件名 (不含擴展名)
            
        Returns:
            備份結果
        """
        if not backup_name:
            backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
        backup_path = self.archive_dir / f"{backup_name}.db"
        
        result = {
            'backup_name': backup_name,
            'backup_path': str(backup_path)
        }
        
        try:
            shutil.copy2(self.db_path, backup_path)
            result['size_mb'] = round(backup_path.stat().st_size / (1024 * 1024), 2)
            result['message'] = f'資料庫備份成功: {backup_path}'
            
        except Exception as e:
            logger.error(f"備份資料庫失敗: {e}")
            result['error'] = str(e)
            
        return result
        
    def auto_maintain(self) -> Dict:
        """
        自動維護流程
        根據配置自動執行維護任務
        
        Returns:
            維護結果
        """
        results = {
            'timestamp': datetime.now().isoformat(),
            'tasks': []
        }
        
        # 1. 檢查資料庫大小
        info = self.get_database_info()
        results['initial_size_mb'] = info['size_mb']
        
        # 2. 如果超過大小限制，執行清理
        if info['size_mb'] > self.config['max_db_size_mb']:
            logger.info(f"資料庫大小 {info['size_mb']} MB 超過限制 {self.config['max_db_size_mb']} MB，開始清理...")
            
            # 先歸檔
            if self.config['archive_days'] > 0:
                archive_result = self.archive_data()
                results['tasks'].append({
                    'task': 'archive',
                    'result': archive_result
                })
            
            # 再清理
            cleanup_result = self.cleanup_old_data()
            results['tasks'].append({
                'task': 'cleanup',
                'result': cleanup_result
            })
            
        # 3. 優化資料庫
        if info['size_mb'] > self.config['vacuum_threshold_mb']:
            optimize_result = self.optimize_database()
            results['tasks'].append({
                'task': 'optimize',
                'result': optimize_result
            })
            
        # 4. 自動備份
        if self.config['auto_backup']:
            backup_result = self.backup_database()
            results['tasks'].append({
                'task': 'backup',
                'result': backup_result
            })
            
        # 5. 最終狀態
        final_info = self.get_database_info()
        results['final_size_mb'] = final_info['size_mb']
        results['space_saved_mb'] = round(results['initial_size_mb'] - results['final_size_mb'], 2)
        
        return results


# 命令行介面
def main():
    """命令行介面"""
    import argparse
    
    parser = argparse.ArgumentParser(description='資料庫維護工具')
    parser.add_argument('--db', default='data/measurement_data.db', help='資料庫路徑')
    
    subparsers = parser.add_subparsers(dest='command', help='維護命令')
    
    # info 命令
    subparsers.add_parser('info', help='顯示資料庫信息')
    
    # cleanup 命令
    cleanup_parser = subparsers.add_parser('cleanup', help='清理舊數據')
    cleanup_parser.add_argument('--days', type=int, help='保留天數')
    cleanup_parser.add_argument('--dry-run', action='store_true', help='預覽模式')
    
    # archive 命令
    archive_parser = subparsers.add_parser('archive', help='歸檔數據')
    archive_parser.add_argument('--days', type=int, help='歸檔天數')
    archive_parser.add_argument('--no-compress', action='store_true', help='不壓縮')
    
    # optimize 命令
    subparsers.add_parser('optimize', help='優化資料庫')
    
    # backup 命令
    backup_parser = subparsers.add_parser('backup', help='備份資料庫')
    backup_parser.add_argument('--name', help='備份名稱')
    
    # auto 命令
    subparsers.add_parser('auto', help='自動維護')
    
    args = parser.parse_args()
    
    # 初始化維護工具
    maintenance = DatabaseMaintenance(args.db)
    
    # 執行命令
    if args.command == 'info':
        result = maintenance.get_database_info()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == 'cleanup':
        result = maintenance.cleanup_old_data(args.days, args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == 'archive':
        result = maintenance.archive_data(args.days, not args.no_compress)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == 'optimize':
        result = maintenance.optimize_database()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == 'backup':
        result = maintenance.backup_database(args.name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == 'auto':
        result = maintenance.auto_maintain()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    else:
        parser.print_help()


if __name__ == '__main__':
    main()