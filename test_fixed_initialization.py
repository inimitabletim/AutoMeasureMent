#!/usr/bin/env python3
"""
測試修復後的 Rigol DP711 初始化
驗證移除 *CLS 指令後是否解決遠程指令錯誤
"""

import sys
import time
from src.rigol_dp711 import RigolDP711

def test_fixed_initialization():
    """測試修復後的完整初始化流程"""
    print("=== 測試修復後的 Rigol DP711 初始化 ===")
    
    try:
        rigol = RigolDP711("COM3")
        print("[INFO] 創建 Rigol DP711 實例成功")
        
        print("\n=== 測試修復後的完整連接 ===")
        print("[INFO] 嘗試完整連接（包含初始化）...")
        print("[INFO] 修改內容: 移除了導致錯誤的 *CLS 指令")
        
        # 完整連接（非最小模式）
        start_time = time.time()
        success = rigol.connect(minimal_mode=False)
        connect_time = time.time() - start_time
        
        if success:
            print(f"[SUCCESS] 完整連接成功！(耗時: {connect_time:.3f}秒)")
            print(f"[INFO] 設備身份: {rigol.get_identity()}")
            print(f"[INFO] 連接狀態: {rigol.is_connected()}")
            
            # 測試基本功能
            print("\n=== 測試基本功能 ===")
            try:
                # 測試狀態查詢
                output_state = rigol.get_output_state()
                print(f"[INFO] 輸出狀態: {output_state}")
                
                voltage = rigol.get_voltage()
                print(f"[INFO] 當前電壓: {voltage}V")
                
                current_limit = rigol.get_current_limit()
                print(f"[INFO] 電流限制: {current_limit}A")
                
                print("[SUCCESS] 所有基本功能測試通過")
                
            except Exception as e:
                print(f"[WARNING] 部分功能測試失敗: {e}")
            
            print("\n=== 關鍵檢查點 ===")
            print("請檢查 Rigol DP711 設備面板:")
            print("✓ 是否不再顯示 '遠程指令錯誤'？")
            print("✓ 設備是否工作正常？") 
            print("✓ 所有功能是否可用？")
            
            response = input("\n設備面板是否正常，無任何錯誤顯示？ (Y/n): ")
            
            rigol.disconnect()
            print("[SUCCESS] 連接已斷開")
            
            if response.lower() not in ['n', 'no']:
                print("\n🎉 修復成功！")
                return True
            else:
                print("\n❌ 仍有問題需要進一步調查")
                return False
                
        else:
            print("[ERROR] 完整連接失敗")
            return False
            
    except Exception as e:
        print(f"[ERROR] 測試失敗: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_multiple_connections():
    """測試多次連接的穩定性"""
    print("\n=== 測試連接穩定性 ===")
    
    try:
        rigol = RigolDP711("COM3")
        success_count = 0
        
        for i in range(5):
            print(f"\n第 {i+1} 次連接測試:")
            
            start_time = time.time()
            success = rigol.connect(minimal_mode=False)  # 完整初始化
            connect_time = time.time() - start_time
            
            if success:
                print(f"[SUCCESS] 連接成功 (耗時: {connect_time:.3f}秒)")
                success_count += 1
                
                # 短暫測試
                try:
                    identity = rigol.get_identity()
                    print(f"[INFO] 設備回應正常")
                except:
                    print("[WARNING] 設備回應異常")
                
                rigol.disconnect()
                print("[INFO] 已斷開")
            else:
                print("[ERROR] 連接失敗")
                
            time.sleep(1)  # 連接間隔
        
        print(f"\n=== 穩定性測試結果 ===")
        print(f"成功率: {success_count}/5 ({success_count*20}%)")
        
        return success_count == 5
        
    except Exception as e:
        print(f"[ERROR] 穩定性測試失敗: {str(e)}")
        return False

if __name__ == "__main__":
    print("開始測試修復後的初始化系統...")
    
    # 主要修復測試
    main_success = test_fixed_initialization()
    
    if main_success:
        # 穩定性測試
        stability_success = test_multiple_connections()
        
        if stability_success:
            print("\n🎉 完全修復成功！")
            print("✓ 遠程指令錯誤已解決")
            print("✓ 初始化流程穩定")
            print("✓ 設備功能正常")
            print("\n系統現在可以正常使用了！")
        else:
            print("\n⚠️ 基本修復成功，但穩定性需要改善")
    else:
        print("\n❌ 修復不完整，需要進一步調查")
    
    sys.exit(0 if main_success else 1)