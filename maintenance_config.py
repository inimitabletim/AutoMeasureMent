#!/usr/bin/env python3
"""
資料庫維護配置與自動化腳本
定期自動執行資料庫維護任務
"""

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False
    
import time
import logging
from datetime import datetime
from pathlib import Path
from src.database_maintenance import DatabaseMaintenance

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/maintenance.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MaintenanceScheduler:
    """資料庫維護排程器"""
    
    def __init__(self):
        """初始化排程器"""
        self.maintenance = DatabaseMaintenance()
        
        # 自定義維護策略
        self.maintenance.config.update({
            'max_db_size_mb': 50,        # 開發環境設置較小的限制
            'retention_days': 7,          # 保留7天的數據
            'archive_days': 3,            # 歸檔3天前的數據
            'cleanup_batch_size': 5000,   # 批次處理大小
            'vacuum_threshold_mb': 10,    # 10MB就觸發優化
            'auto_backup': True,          # 自動備份
            'compression': True           # 壓縮歸檔
        })
        
    def daily_maintenance(self):
        """每日維護任務"""
        logger.info("=" * 60)
        logger.info("開始執行每日維護任務")
        
        try:
            # 1. 獲取資料庫狀態
            info = self.maintenance.get_database_info()
            logger.info(f"資料庫大小: {info['size_mb']} MB")
            
            if 'measurements' in info['tables']:
                logger.info(f"測量記錄數: {info['tables']['measurements']['row_count']:,}")
            
            # 2. 執行自動維護
            result = self.maintenance.auto_maintain()
            
            # 3. 記錄結果
            for task in result['tasks']:
                task_name = task['task']
                task_result = task['result']
                
                if 'error' in task_result:
                    logger.error(f"{task_name}: {task_result['error']}")
                elif 'message' in task_result:
                    logger.info(f"{task_name}: {task_result['message']}")
                    
            if result['space_saved_mb'] > 0:
                logger.info(f"總共節省空間: {result['space_saved_mb']} MB")
                
        except Exception as e:
            logger.error(f"維護任務失敗: {e}")
            
        logger.info("每日維護任務完成")
        logger.info("=" * 60)
        
    def hourly_check(self):
        """每小時檢查"""
        try:
            info = self.maintenance.get_database_info()
            
            # 如果資料庫超過限制，立即執行清理
            if info['size_mb'] > self.maintenance.config['max_db_size_mb']:
                logger.warning(f"資料庫大小 {info['size_mb']} MB 超過限制，執行緊急清理")
                self.emergency_cleanup()
                
        except Exception as e:
            logger.error(f"小時檢查失敗: {e}")
            
    def emergency_cleanup(self):
        """緊急清理（開發環境用）"""
        logger.info("執行緊急清理...")
        
        try:
            # 只保留最新的5000條記錄
            from cleanup_test_data import cleanup_test_database
            cleanup_test_database(keep_recent_hours=0)  # 實際會保留10000條
            
        except Exception as e:
            logger.error(f"緊急清理失敗: {e}")
            
    def setup_schedule(self):
        """設置排程"""
        if not SCHEDULE_AVAILABLE:
            logger.warning("schedule 模組未安裝，排程功能不可用")
            logger.info("請執行: pip install schedule")
            return False
            
        # 每日凌晨2點執行維護
        schedule.every().day.at("02:00").do(self.daily_maintenance)
        
        # 每小時檢查一次
        schedule.every().hour.do(self.hourly_check)
        
        # 開發環境：每6小時執行一次維護
        if self.is_development():
            schedule.every(6).hours.do(self.daily_maintenance)
            
        logger.info("維護排程已設置")
        logger.info("- 每日維護: 02:00")
        logger.info("- 小時檢查: 每小時")
        
        if self.is_development():
            logger.info("- 開發環境: 每6小時額外維護")
            
    def is_development(self):
        """檢查是否為開發環境"""
        # 可以根據環境變數或其他條件判斷
        return True  # 目前設為開發環境
        
    def run(self):
        """運行排程器"""
        if not self.setup_schedule():
            logger.error("無法設置排程，請安裝 schedule 模組")
            return
            
        # 啟動時先執行一次檢查
        self.hourly_check()
        
        logger.info("維護排程器已啟動，按 Ctrl+C 停止")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分鐘檢查一次排程
                
        except KeyboardInterrupt:
            logger.info("維護排程器已停止")


# 手動執行維護的便捷函數
def quick_cleanup(keep_records=10000):
    """快速清理函數"""
    from cleanup_test_data import cleanup_test_database
    cleanup_test_database()
    

def show_status():
    """顯示資料庫狀態"""
    maintenance = DatabaseMaintenance()
    info = maintenance.get_database_info()
    
    print("\n" + "=" * 60)
    print("資料庫狀態報告")
    print("=" * 60)
    print(f"資料庫路徑: {info['path']}")
    print(f"檔案大小: {info['size_mb']} MB")
    
    if 'measurements' in info['tables']:
        table = info['tables']['measurements']
        print(f"測量記錄數: {table['row_count']:,}")
        
        if table['row_count'] > 0:
            print(f"最早記錄: {table['earliest']}")
            print(f"最新記錄: {table['latest']}")
            
    if 'daily_distribution' in info:
        print("\n最近數據分布:")
        for day in info['daily_distribution'][:7]:
            print(f"  {day['date']}: {day['count']:,} 條")
            
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "status":
            show_status()
            
        elif command == "cleanup":
            quick_cleanup()
            
        elif command == "schedule":
            scheduler = MaintenanceScheduler()
            scheduler.run()
            
        elif command == "once":
            scheduler = MaintenanceScheduler()
            scheduler.daily_maintenance()
            
        else:
            print("使用方法:")
            print("  python maintenance_config.py status    # 顯示狀態")
            print("  python maintenance_config.py cleanup   # 快速清理")
            print("  python maintenance_config.py once      # 執行一次維護")
            print("  python maintenance_config.py schedule  # 啟動排程器")
            
    else:
        # 預設顯示狀態
        show_status()