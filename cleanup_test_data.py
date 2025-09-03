#!/usr/bin/env python3
"""
快速清理測試數據腳本
用於開發階段清理過多的測試數據
"""

import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path

def cleanup_test_database(db_path="data/measurement_data.db", keep_recent_hours=1):
    """
    清理測試資料庫，只保留最近N小時的數據
    
    Args:
        db_path: 資料庫路徑
        keep_recent_hours: 保留最近幾小時的數據
    """
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"資料庫不存在: {db_path}")
        return
        
    # 獲取初始大小
    initial_size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"初始資料庫大小: {initial_size_mb:.2f} MB")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 獲取總記錄數
        cursor.execute("SELECT COUNT(*) FROM measurements")
        total_records = cursor.fetchone()[0]
        print(f"總記錄數: {total_records:,}")
        
        # 計算保留時間點
        cutoff_time = datetime.now() - timedelta(hours=keep_recent_hours)
        print(f"將刪除 {cutoff_time} 之前的所有數據")
        
        # 方案1: 保留最新的10000條記錄
        print("\n執行清理策略: 保留最新的 10000 條記錄...")
        
        # 先獲取要保留的記錄ID範圍
        cursor.execute("""
            SELECT id FROM measurements 
            ORDER BY id DESC 
            LIMIT 10000
        """)
        keep_ids = cursor.fetchall()
        
        if keep_ids:
            min_keep_id = keep_ids[-1][0]
            
            # 刪除舊記錄
            cursor.execute("""
                DELETE FROM measurements 
                WHERE id < ?
            """, (min_keep_id,))
            
            deleted_count = cursor.rowcount
            print(f"已刪除 {deleted_count:,} 條記錄")
            
            # 提交更改
            conn.commit()
            
            # 清理已刪除的會話
            cursor.execute("""
                DELETE FROM sessions 
                WHERE session_id NOT IN (
                    SELECT DISTINCT session_id 
                    FROM measurements
                )
            """)
            deleted_sessions = cursor.rowcount
            print(f"已清理 {deleted_sessions} 個空會話")
            
            conn.commit()
            
            # 執行VACUUM優化
            print("\n執行 VACUUM 優化...")
            conn.execute("VACUUM")
            
            # 重建索引
            print("重建索引...")
            conn.execute("REINDEX")
            
        else:
            print("沒有找到任何記錄")
            
        # 獲取最終記錄數
        cursor.execute("SELECT COUNT(*) FROM measurements")
        final_records = cursor.fetchone()[0]
        print(f"\n最終記錄數: {final_records:,}")
        
    except Exception as e:
        print(f"錯誤: {e}")
        conn.rollback()
        
    finally:
        conn.close()
        
    # 獲取最終大小
    final_size_mb = db_path.stat().st_size / (1024 * 1024)
    saved_mb = initial_size_mb - final_size_mb
    
    print(f"\n清理完成!")
    print(f"最終資料庫大小: {final_size_mb:.2f} MB")
    print(f"節省空間: {saved_mb:.2f} MB ({saved_mb/initial_size_mb*100:.1f}%)")


def reset_test_database(db_path="data/measurement_data.db"):
    """
    完全重置測試資料庫（清空所有數據）
    
    Args:
        db_path: 資料庫路徑
    """
    response = input("警告: 這將刪除所有測試數據! 確定要繼續嗎? (yes/no): ")
    
    if response.lower() != 'yes':
        print("操作已取消")
        return
        
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"資料庫不存在: {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 清空所有表
        cursor.execute("DELETE FROM measurements")
        cursor.execute("DELETE FROM sessions")
        cursor.execute("DELETE FROM sqlite_sequence")  # 重置自增ID
        
        conn.commit()
        
        # VACUUM優化
        conn.execute("VACUUM")
        
        print("資料庫已重置")
        
    except Exception as e:
        print(f"錯誤: {e}")
        conn.rollback()
        
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        # 完全重置模式
        reset_test_database()
    else:
        # 正常清理模式
        cleanup_test_database()
        
        # 提供額外選項
        print("\n選項:")
        print("1. 執行更徹底的清理 (保留1000條)")
        print("2. 完全重置資料庫")
        print("3. 退出")
        
        choice = input("\n請選擇 (1-3): ")
        
        if choice == "1":
            # 修改清理邏輯保留更少記錄
            print("\n執行徹底清理...")
            db_path = Path("data/measurement_data.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM measurements 
                WHERE id NOT IN (
                    SELECT id FROM measurements 
                    ORDER BY id DESC 
                    LIMIT 1000
                )
            """)
            
            conn.commit()
            conn.execute("VACUUM")
            conn.close()
            
            final_size_mb = db_path.stat().st_size / (1024 * 1024)
            print(f"徹底清理完成! 最終大小: {final_size_mb:.2f} MB")
            
        elif choice == "2":
            reset_test_database()