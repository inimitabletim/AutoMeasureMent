#!/usr/bin/env python3
"""
Keithley 2461 儀器控制系統 - GUI主程式
"""

import sys
import os
from pathlib import Path

def check_dependencies():
    """檢查必要依賴套件"""
    missing_deps = []
    
    try:
        import PyQt6
    except ImportError:
        missing_deps.append('PyQt6')
        
    try:
        import pyqtgraph
    except ImportError:
        missing_deps.append('pyqtgraph')
        
    try:
        import pyvisa
    except ImportError:
        missing_deps.append('pyvisa')
        
    if missing_deps:
        try:
            print("❌ 缺少必要依賴套件:")
        except:
            print("[ERROR] 缺少必要依賴套件:")
        for dep in missing_deps:
            print(f"  - {dep}")
        print("\n請執行以下命令安裝:")
        print("pip install -r requirements.txt")
        
        # 不使用 tkinter 避免與 PyQt6 衝突
        # 只顯示控制台訊息
            
        return False
        
    return True

def main():
    """主程式入口 - 啟動GUI"""
    try:
        print("🚀 啟動 Keithley 2461 控制系統...")
    except UnicodeEncodeError:
        print("[START] 啟動 Keithley 2461 控制系統...")
    
    # 設定工作目錄
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)
    
    # 檢查依賴
    if not check_dependencies():
        sys.exit(1)
        
    try:
        # 設定環境變數
        os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
        
        # 啟動多儀器GUI
        from gui_multi_instrument import main as multi_gui_main
        multi_gui_main()
        
    except ImportError as e:
        try:
            print(f"❌ 匯入模組錯誤: {e}")
        except:
            print(f"[ERROR] 匯入模組錯誤: {e}")
        print("請確認:")
        print("1. 所有依賴套件已正確安裝")
        print("2. src 資料夾中的模組檔案存在")
        print("3. Python 環境配置正確")
            
        sys.exit(1)
        
    except KeyboardInterrupt:
        try:
            print("\n👋 程式被用戶中斷")
        except:
            print("\n[EXIT] 程式被用戶中斷")
        sys.exit(0)
        
    except Exception as e:
        try:
            print(f"❌ 啟動GUI時發生錯誤: {e}")
        except:
            print(f"[ERROR] 啟動GUI時發生錯誤: {e}")
        print("請檢查:")
        print("1. Python 版本是否 >= 3.8")
        print("2. 依賴套件是否完整")
        print("3. 檔案權限是否正確")
        print("4. 顯示環境是否正確配置")
            
        try:
            print("\n🔧 排除建議:")
        except:
            print("\n[INFO] 排除建議:")
        print("1. 檢查是否已安裝所有依賴: pip install -r requirements.txt")
        print("2. 檢查 Python 版本是否 >= 3.8")
        print("3. 檢查顯示環境是否正確")
        print("4. 查看 instrument_control.log 檔案了解詳細錯誤")
        sys.exit(1)
    
if __name__ == "__main__":
    main()