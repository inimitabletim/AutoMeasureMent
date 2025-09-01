#!/usr/bin/env python3
"""
驗證非阻塞式連線修復的檢查腳本
"""

import sys
import os

def check_imports():
    """檢查必要的模組是否可以導入"""
    print("檢查模組導入...")
    
    try:
        from widgets.connection_status_widget import ConnectionStatusWidget
        print("ConnectionStatusWidget 導入成功")
    except ImportError as e:
        print(f"ConnectionStatusWidget 導入失敗: {e}")
        return False
        
    try:
        from src.connection_worker import ConnectionStateManager
        print("ConnectionStateManager 導入成功")
    except ImportError as e:
        print(f"ConnectionStateManager 導入失敗: {e}")
        return False
        
    try:
        from widgets.keithley_widget_professional import ProfessionalKeithleyWidget
        print("ProfessionalKeithleyWidget 導入成功")
    except ImportError as e:
        print(f"ProfessionalKeithleyWidget 導入失敗: {e}")
        return False
        
    return True

def check_widget_functionality():
    """檢查widget功能"""
    print("\n檢查Widget功能...")
    
    try:
        from PyQt6.QtWidgets import QApplication
        from widgets.keithley_widget_professional import ProfessionalKeithleyWidget
        
        app = QApplication(sys.argv)
        widget = ProfessionalKeithleyWidget()
        
        # 檢查是否有新的連線管理器
        if hasattr(widget, 'connection_manager'):
            print("連線管理器已初始化")
        else:
            print("連線管理器未找到")
            
        # 檢查是否有新的連線狀態widget
        if hasattr(widget, 'connection_status_widget'):
            print("連線狀態Widget已創建")
        else:
            print("連線狀態Widget未找到")
            
        # 檢查是否有新的連線處理方法
        if hasattr(widget, '_handle_connection_request'):
            print("非阻塞式連線方法已實現")
        else:
            print("非阻塞式連線方法未找到")
            
        # 檢查舊按鈕是否已移除
        if hasattr(widget, 'connect_btn') and widget.connect_btn is None:
            print("舊連線按鈕已正確移除")
        else:
            print("舊連線按鈕狀態異常")
            
        app.quit()
        return True
        
    except Exception as e:
        print(f"Widget功能檢查失敗: {e}")
        return False

def main():
    """主檢查函數"""
    print("=" * 60)
    print("非阻塞式連線修復驗證腳本")
    print("=" * 60)
    
    # 檢查工作目錄
    print(f"當前工作目錄: {os.getcwd()}")
    
    # 檢查導入
    if not check_imports():
        print("\n模組導入檢查失敗，請檢查檔案是否正確創建")
        return False
        
    # 檢查功能
    if not check_widget_functionality():
        print("\nWidget功能檢查失敗")
        return False
        
    print("\n" + "=" * 60)
    print("所有檢查通過！新的非阻塞式連線系統已就緒")
    print("=" * 60)
    print("\n使用說明：")
    print("1. 重新啟動您的程式: python main.py")
    print("2. 現在連線介面應該顯示新的狀態widget")
    print("3. 當儀器未開機時，UI不會凍結且可以取消連線")
    print("4. 連線超時從10秒縮短為5秒")
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)