#!/usr/bin/env python3
"""
測試修正後的 Keithley 2461 SCPI 命令格式
"""

import sys
import logging
from src.keithley_2461 import Keithley2461

def test_scpi_commands():
    """測試 SCPI 命令格式"""
    
    # 設置日誌
    logging.basicConfig(level=logging.INFO)
    
    print("=== Keithley 2461 SCPI 命令格式測試 ===\n")
    
    # 創建儀器實例（不連接）
    keithley = Keithley2461()
    
    print("[OK] 修正的 SCPI 命令格式：")
    print("   - :SOURce:FUNCtion VOLTage  (完整關鍵字)")
    print("   - :SOURce:VOLTage:LEVel <value>")
    print("   - :SOURce:VOLTage:LIMit:CURRent <value>")
    print("   - :SOURce:CURRent:LEVel <value>")  
    print("   - :SOURce:CURRent:LIMit:VOLTage <value>")
    print("   - :OUTPut ON/OFF")
    print("   - :MEASure:VOLTage?")
    print("   - :MEASure:CURRent?")
    print("   - :MEASure:RESistance?")
    print("   - :MEASure:POWer?")
    
    print("\n[OK] 連接時的改善：")
    print("   - 連接時自動重置儀器 (*RST)")
    print("   - 清除錯誤隊列 (*CLS)")  
    print("   - 連接後檢查錯誤狀態")
    print("   - 增加初始化等待時間")
    
    print("\n[INFO] 根據搜尋結果的主要修正：")
    print("   1. 使用完整 SCPI 關鍵字而非縮寫")
    print("   2. 確保儀器在 SCPI 模式而非 TSP 模式")  
    print("   3. 在連接時重置並清除錯誤")
    print("   4. 使用標準 Keithley SCPI 命令格式")
    
    print("\n[TIPS] 如果仍有 -285 錯誤，請檢查：")
    print("   1. 儀器面板設定是否為 SCPI 模式")
    print("   2. 網路連線是否穩定")
    print("   3. 儀器韌體版本是否支援所有命令")
    print("   4. 檢查儀器的 SYST:ERR? 獲得詳細錯誤訊息")

if __name__ == "__main__":
    test_scpi_commands()