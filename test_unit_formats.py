#!/usr/bin/env python3
"""
測試 Keithley 2461 各種單位格式輸入
驗證單位轉換功能是否正常運作
"""

import sys
import time
from src.keithley_2461 import Keithley2461


def print_separator(title):
    """打印分隔線"""
    print(f"\n{'='*60}")
    print(f" {title}")
    print('='*60)


def test_unit_conversion():
    """測試單位轉換函數"""
    print_separator("測試單位轉換函數")
    
    # 創建 Keithley 實例（不連接）
    keithley = Keithley2461()
    
    test_cases = [
        # (輸入, 預期輸出, 描述)
        ("500mV", "500m", "毫伏轉換"),
        ("500.00000mV", "500.00000m", "高精度毫伏"),
        ("100uA", "100u", "微安轉換"),
        ("100.0uA", "100.0u", "微安帶小數點"),
        ("3.3V", "3.3", "伏特不需後綴"),
        ("3.3", "3.3", "純數字"),
        ("10nA", "10n", "奈安轉換"),
        ("1.5mA", "1.5m", "毫安轉換"),
        ("5kV", "5k", "千伏轉換"),
        ("100m", "100m", "已經是標準格式"),
        ("50u", "50u", "已經是微單位"),
    ]
    
    print("\n單位轉換測試結果:")
    print("-" * 50)
    
    for input_val, expected, description in test_cases:
        result = keithley._convert_unit_format(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} {description:<20} | 輸入: {input_val:<15} | 輸出: {result:<15} | 預期: {expected}")
        
        if result != expected:
            print(f"   ⚠️  轉換錯誤！")


def test_live_instrument(ip_address):
    """測試實際儀器連接（需要實際硬體）"""
    print_separator(f"測試實際儀器連接 - IP: {ip_address}")
    
    try:
        keithley = Keithley2461(ip_address=ip_address)
        
        # 連接儀器
        print("\n正在連接儀器...")
        if not keithley.connect():
            print("❌ 無法連接到儀器")
            return
            
        print("✅ 儀器連接成功")
        
        # 獲取儀器識別信息
        idn = keithley.get_identity()
        print(f"儀器識別: {idn}")
        
        # 測試各種單位格式設定
        print_separator("測試不同單位格式設定")
        
        test_configurations = [
            # (電壓, 電流限制, 描述)
            ("500mV", "100uA", "測試 mV 和 uA 格式"),
            ("500m", "100u", "測試標準 SCPI 格式"),
            ("3.3V", "100uA", "測試 V 和 uA 格式"),
            ("3.3", "0.0001", "測試純數字格式"),
            ("1000mV", "1mA", "測試 1V 用 mV 表示"),
            ("0.5", "100u", "測試混合格式"),
        ]
        
        for voltage, current_limit, description in test_configurations:
            print(f"\n測試: {description}")
            print(f"  設定電壓: {voltage}, 電流限制: {current_limit}")
            
            try:
                # 清除錯誤隊列
                keithley.send_command("*CLS")
                
                # 設定電壓和電流限制
                keithley.set_voltage(voltage, current_limit=current_limit)
                
                # 檢查錯誤
                errors = keithley.check_errors()
                if errors:
                    print(f"  ❌ SCPI錯誤: {errors}")
                else:
                    print(f"  ✅ 設定成功，無錯誤")
                    
                    # 讀取實際設定值
                    actual_voltage = keithley.query("SOUR:VOLT:LEV?")
                    actual_current_limit = keithley.query("SOUR:VOLT:ILIM?")
                    print(f"     實際電壓: {actual_voltage}")
                    print(f"     實際電流限制: {actual_current_limit}")
                    
            except Exception as e:
                print(f"  ❌ 執行錯誤: {e}")
            
            time.sleep(0.5)  # 給儀器一點時間處理
        
        # 斷開連接
        print("\n斷開儀器連接...")
        keithley.disconnect()
        print("✅ 測試完成")
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")


def main():
    """主函數"""
    print("="*60)
    print(" Keithley 2461 單位格式測試工具")
    print("="*60)
    
    # 首先測試單位轉換函數
    test_unit_conversion()
    
    # 詢問是否要測試實際儀器
    print("\n" + "="*60)
    response = input("\n是否要測試實際儀器連接？(y/n): ")
    
    if response.lower() == 'y':
        # 獲取IP地址
        ip = input("請輸入 Keithley 2461 的 IP 地址 (預設: 192.168.1.100): ").strip()
        if not ip:
            ip = "192.168.1.100"
        
        test_live_instrument(ip)
    else:
        print("\n跳過實際儀器測試")
    
    print("\n" + "="*60)
    print(" 測試結束")
    print("="*60)


if __name__ == "__main__":
    main()