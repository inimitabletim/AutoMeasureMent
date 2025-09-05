#!/usr/bin/env python3
"""
測試查詢指令是否導致遠程指令錯誤
重點測試 GUI 系統中使用的查詢指令
"""

import sys
import time
from src.rigol_dp711 import RigolDP711

def test_query_commands():
    """測試各種查詢指令"""
    print("=== 測試 GUI 系統中的查詢指令 ===")
    
    query_commands = [
        ("SOURce:VOLTage?", "查詢設定電壓", "get_set_voltage"),
        ("SOURce:CURRent?", "查詢設定電流", "get_set_current"),
        ("OUTPut:STATe?", "查詢輸出狀態", "get_output_state"),
        ("MEASure:VOLTage?", "查詢測量電壓", "get_measured_voltage"),  
        ("MEASure:CURRent?", "查詢測量電流", "get_measured_current"),
        ("*IDN?", "查詢設備身份", "get_identity")
    ]
    
    try:
        rigol = RigolDP711("COM3")
        
        for i, (scpi_cmd, description, method_name) in enumerate(query_commands, 1):
            print(f"\n=== 測試 {i}: {description} ===")
            
            # 建立最小連接
            print("[INFO] 建立最小連接...")
            success = rigol.connect(minimal_mode=True)
            
            if not success:
                print("[ERROR] 連接失敗")
                return False
            
            print("[SUCCESS] 最小連接成功")
            input(f"確認設備面板正常，然後按 Enter 測試查詢指令: {scpi_cmd}")
            
            # 執行查詢指令
            print(f"[INFO] 執行查詢: {scpi_cmd}")
            try:
                if method_name == "get_set_voltage":
                    result = rigol.get_set_voltage()
                elif method_name == "get_set_current":
                    result = rigol.get_set_current()
                elif method_name == "get_output_state":
                    result = rigol.get_output_state()
                elif method_name == "get_measured_voltage":
                    result = rigol.get_measured_voltage()
                elif method_name == "get_measured_current":
                    result = rigol.get_measured_current()
                elif method_name == "get_identity":
                    result = rigol.get_identity()
                
                print(f"[SUCCESS] 查詢結果: {result}")
                
            except Exception as e:
                print(f"[ERROR] 查詢失敗: {str(e)}")
                rigol.disconnect()
                return scpi_cmd
            
            # 關鍵檢查
            response = input(f"\n[關鍵] 執行查詢 {scpi_cmd} 後:\n設備面板是否出現遠程指令錯誤？ (y/N): ")
            
            if response.lower() in ['y', 'yes']:
                print(f"\n🎯 [發現] 問題查詢指令: {scpi_cmd}")
                print(f"描述: {description}")
                print(f"方法: {method_name}")
                rigol.disconnect()
                return scpi_cmd
            else:
                print(f"[OK] {scpi_cmd} 沒有問題")
            
            rigol.disconnect()
            time.sleep(2)
        
        print("\n=== 所有查詢指令測試完成 ===")
        print("沒有發現單獨的問題查詢指令...")
        return "no_single_issue"
        
    except Exception as e:
        print(f"[ERROR] 測試失敗: {str(e)}")
        return False

def test_gui_sequence():
    """模擬 GUI 系統的完整指令序列"""
    print("\n=== 模擬 GUI 系統完整序列 ===")
    
    try:
        rigol = RigolDP711("COM3")
        
        # 建立連接（非最小模式，包含初始化）
        print("[INFO] 建立完整連接（包含初始化）...")
        success = rigol.connect(minimal_mode=False)
        
        if not success:
            print("[ERROR] 連接失敗")
            return False
        
        print("[SUCCESS] 連接和初始化完成")
        
        # 模擬 GUI 在連接成功後的查詢
        print("\n[INFO] 模擬 GUI 系統的後續查詢...")
        
        time.sleep(1)  # 給設備時間穩定
        
        print("[1] 查詢設定電壓...")
        voltage = rigol.get_set_voltage()
        print(f"    結果: {voltage}V")
        
        time.sleep(0.5)
        
        print("[2] 查詢設定電流...")
        current = rigol.get_set_current()
        print(f"    結果: {current}A")
        
        time.sleep(0.5)
        
        print("[3] 查詢輸出狀態...")
        output_state = rigol.get_output_state()
        print(f"    結果: {output_state}")
        
        print("\n[SUCCESS] 完整 GUI 序列執行完成")
        
        response = input("\n[最終檢查] 執行完整 GUI 序列後:\n設備面板是否出現遠程指令錯誤？ (y/N): ")
        
        rigol.disconnect()
        
        if response.lower() in ['y', 'yes']:
            print("\n🎯 [確認] GUI 完整序列導致遠程指令錯誤")
            print("問題可能是:")
            print("- 初始化 + 查詢的組合效應")
            print("- 指令時序問題")
            print("- 特定查詢指令在初始化後的問題")
            return "gui_sequence_issue"
        else:
            print("\n[意外] GUI 序列也沒有問題...")
            return "mystery"
            
    except Exception as e:
        print(f"[ERROR] GUI 序列測試失敗: {str(e)}")
        return False

if __name__ == "__main__":
    print("深度診斷：查詢指令對遠程指令錯誤的影響")
    print("=" * 50)
    
    # 階段1: 測試各個查詢指令
    result1 = test_query_commands()
    
    if result1 and result1 != "no_single_issue":
        print(f"\n🎯 發現問題查詢指令: {result1}")
    else:
        print("\n單個查詢指令都正常，測試完整序列...")
        
        # 階段2: 測試完整GUI序列
        result2 = test_gui_sequence()
        print(f"\n🎯 GUI序列測試結果: {result2}")
    
    print("\n=== 最終診斷 ===")
    print("這個測試將幫助我們確定:")
    print("1. 是否某個特定的查詢指令導致問題")
    print("2. 是否初始化+查詢的組合導致問題")
    print("3. 真正的問題根源在哪裡")
    
    sys.exit(0)