#!/usr/bin/env python3
"""
Keithley 2461測試腳本
用於測試連接和基本功能
"""

import logging
import time
from src.keithley_2461 import Keithley2461
from src.data_logger import DataLogger

def setup_logging():
    """設定測試日誌"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def test_connection(ip_address: str):
    """測試連接功能"""
    print("=== 測試連接功能 ===")
    
    with Keithley2461(ip_address=ip_address) as keithley:
        # 測試VISA連接
        print("測試VISA連接...")
        if keithley.connect("visa"):
            print("✓ VISA連接成功")
            
            # 獲取設備信息
            identity = keithley.get_identity()
            print(f"設備識別: {identity}")
            
            # 測試基本命令
            print("測試基本SCPI命令...")
            keithley.beep(1000, 0.2)
            print("✓ 蜂鳴器測試完成")
            
            # 檢查錯誤
            errors = keithley.check_errors()
            if errors:
                print(f"發現錯誤: {errors}")
            else:
                print("✓ 無錯誤")
                
            return True
        else:
            print("✗ 連接失敗")
            return False

def test_measurement_functions(ip_address: str):
    """測試測量功能"""
    print("\n=== 測試測量功能 ===")
    
    with Keithley2461(ip_address=ip_address) as keithley:
        if not keithley.connect("visa"):
            print("✗ 無法連接到設備")
            return False
            
        try:
            # 重置設備
            keithley.reset()
            time.sleep(2)
            
            # 設定基本配置
            keithley.set_auto_range(True)
            keithley.set_measurement_speed(0.1)  # 快速測量
            
            # 測試電壓源模式
            print("測試電壓源模式...")
            keithley.set_voltage(1.0, current_limit=0.01)  # 1V, 10mA限制
            keithley.output_on()
            
            time.sleep(0.5)  # 等待穩定
            
            # 測量所有參數
            voltage, current, resistance, power = keithley.measure_all()
            print(f"測量結果: V={voltage:.6f}V, I={current:.6f}A, "
                  f"R={resistance:.2f}Ω, P={power:.6f}W")
            
            # 關閉輸出
            keithley.output_off()
            
            print("✓ 電壓源測試完成")
            
            # 測試電流源模式
            print("測試電流源模式...")
            keithley.set_current(0.001, voltage_limit=10.0)  # 1mA, 10V限制
            keithley.output_on()
            
            time.sleep(0.5)  # 等待穩定
            
            # 再次測量
            voltage, current, resistance, power = keithley.measure_all()
            print(f"測量結果: V={voltage:.6f}V, I={current:.6f}A, "
                  f"R={resistance:.2f}Ω, P={power:.6f}W")
            
            # 關閉輸出
            keithley.output_off()
            
            print("✓ 電流源測試完成")
            return True
            
        except Exception as e:
            print(f"✗ 測量功能測試失敗: {e}")
            keithley.output_off()  # 確保輸出關閉
            return False

def test_data_logging(ip_address: str):
    """測試資料記錄功能"""
    print("\n=== 測試資料記錄功能 ===")
    
    # 初始化資料記錄器
    logger = DataLogger(base_path="test_data")
    session_name = logger.start_session("keithley_test")
    
    with Keithley2461(ip_address=ip_address) as keithley:
        if not keithley.connect("visa"):
            print("✗ 無法連接到設備")
            return False
            
        try:
            # 設定測試條件
            keithley.reset()
            time.sleep(1)
            
            keithley.set_auto_range(True)
            keithley.set_measurement_speed(0.1)
            
            # 進行一系列測量
            print("開始記錄測量數據...")
            
            test_voltages = [0.5, 1.0, 1.5, 2.0, 2.5]
            
            for voltage in test_voltages:
                keithley.set_voltage(voltage, current_limit=0.01)
                keithley.output_on()
                
                time.sleep(0.5)  # 等待穩定
                
                # 測量並記錄
                v, i, r, p = keithley.measure_all()
                logger.log_measurement(v, i, r, p, metadata={
                    'set_voltage': voltage,
                    'test_type': 'voltage_sweep'
                })
                
                print(f"記錄點 - 設定:{voltage}V, 測量:{v:.3f}V, {i:.6f}A")
                
                keithley.output_off()
                time.sleep(0.2)
            
            # 保存數據
            csv_file = logger.save_session_csv()
            json_file = logger.save_session_json()
            summary_file = logger.export_summary()
            
            print(f"✓ 數據已保存到:")
            print(f"  CSV: {csv_file}")
            print(f"  JSON: {json_file}")
            print(f"  摘要: {summary_file}")
            
            # 顯示統計信息
            stats = logger.get_session_statistics()
            print(f"✓ 記錄了 {stats['total_measurements']} 筆數據")
            
            return True
            
        except Exception as e:
            print(f"✗ 資料記錄測試失敗: {e}")
            keithley.output_off()
            return False

def main():
    """主測試函數"""
    setup_logging()
    
    print("Keithley 2461 功能測試")
    print("=" * 50)
    
    # 獲取IP地址
    ip_address = input("請輸入Keithley 2461的IP地址: ").strip()
    if not ip_address:
        print("錯誤: 必須提供IP地址")
        return
        
    # 執行測試
    test_results = []
    
    try:
        # 測試連接
        test_results.append(("連接測試", test_connection(ip_address)))
        
        # 測試測量功能
        test_results.append(("測量功能測試", test_measurement_functions(ip_address)))
        
        # 測試資料記錄
        test_results.append(("資料記錄測試", test_data_logging(ip_address)))
        
    except KeyboardInterrupt:
        print("\n測試被用戶中斷")
        
    # 顯示測試結果摘要
    print("\n" + "=" * 50)
    print("測試結果摘要:")
    
    all_passed = True
    for test_name, result in test_results:
        status = "✓ 通過" if result else "✗ 失敗"
        print(f"  {test_name}: {status}")
        if not result:
            all_passed = False
            
    if all_passed:
        print("\n🎉 所有測試通過！")
    else:
        print("\n⚠️  部分測試失敗，請檢查錯誤信息")

if __name__ == "__main__":
    main()