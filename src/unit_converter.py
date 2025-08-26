#!/usr/bin/env python3
"""
單位轉換工具
支援電壓、電流的前綴單位轉換 (m, u, n, k, M 等)
"""

import re
from typing import Tuple, Union

class UnitConverter:
    """單位前綴轉換器"""
    
    # 單位前綴對應的倍數
    PREFIXES = {
        'T': 1e12,   # Tera
        'G': 1e9,    # Giga  
        'M': 1e6,    # Mega
        'k': 1e3,    # Kilo
        '': 1.0,     # 基本單位
        'm': 1e-3,   # Milli
        'μ': 1e-6,   # Micro
        'n': 1e-9,   # Nano
        'p': 1e-12,  # Pico
        'f': 1e-15,  # Femto
    }
    
    # 反向查找 - 從倍數找前綴
    REVERSE_PREFIXES = {v: k for k, v in PREFIXES.items() if k != 'μ'}  # 避免重複
    
    @classmethod
    def parse_value_with_unit(cls, text: str) -> Tuple[float, str]:
        """
        解析帶單位的數值字串
        
        Args:
            text: 輸入字串，如 "3.3V", "100mA", "1.2k", "50u"
            
        Returns:
            Tuple[float, str]: (基本單位數值, 原始前綴)
        """
        # 移除空白字符
        text = text.strip()
        
        # 正則表達式匹配數值和單位
        # 支援: 3.3V, 100mA, 1.2k, 50u, 2.5mV 等格式
        pattern = r'^(-?\d*\.?\d+)([TGMkmuμnpf]?)([VAΩWΩv]*)$'
        match = re.match(pattern, text, re.IGNORECASE)
        
        if not match:
            # 嘗試純數字
            try:
                return float(text), ''
            except ValueError:
                raise ValueError(f"無法解析數值: {text}")
        
        number_str = match.group(1)
        prefix = match.group(2)
        # unit = match.group(3)  # 暫不使用單位部分
        
        try:
            number = float(number_str)
        except ValueError:
            raise ValueError(f"無效的數值: {number_str}")
        
        # 轉換為基本單位
        if prefix in cls.PREFIXES:
            base_value = number * cls.PREFIXES[prefix]
            return base_value, prefix
        else:
            raise ValueError(f"不支援的單位前綴: {prefix}")
    
    @classmethod
    def format_value_with_unit(cls, value: float, unit: str = '', 
                             target_prefix: str = None, precision: int = 6) -> str:
        """
        格式化數值為帶前綴的字串
        
        Args:
            value: 基本單位的數值
            unit: 單位符號 (V, A, Ω, W)
            target_prefix: 目標前綴，若為None則自動選擇最佳前綴
            precision: 精度位數
            
        Returns:
            str: 格式化後的字串
        """
        if value == 0:
            return f"0.000000 {unit}"
        
        # 如果指定了目標前綴
        if target_prefix is not None:
            if target_prefix in cls.PREFIXES:
                scaled_value = value / cls.PREFIXES[target_prefix]
                return f"{scaled_value:.{precision}f} {target_prefix}{unit}"
            else:
                raise ValueError(f"不支援的前綴: {target_prefix}")
        
        # 自動選擇最佳前綴
        abs_value = abs(value)
        
        # 選擇最適合的前綴
        best_prefix = ''
        best_scale = 1.0
        
        for prefix, scale in sorted(cls.PREFIXES.items(), key=lambda x: x[1], reverse=True):
            if prefix == 'μ':  # 跳過μ，使用u
                continue
            scaled = abs_value / scale
            if scaled >= 1.0 and scaled < 1000.0:
                best_prefix = prefix
                best_scale = scale
                break
        
        scaled_value = value / best_scale
        return f"{scaled_value:.{precision}f} {best_prefix}{unit}"
    
    @classmethod
    def convert_to_base_unit(cls, text: str) -> float:
        """
        將帶前綴的字串轉換為基本單位數值
        
        Args:
            text: 輸入字串
            
        Returns:
            float: 基本單位數值
        """
        value, _ = cls.parse_value_with_unit(text)
        return value
    
    @classmethod
    def get_prefix_multipliers(cls) -> dict:
        """獲取所有前綴及其倍數"""
        return cls.PREFIXES.copy()
    
    @classmethod
    def validate_input(cls, text: str) -> bool:
        """
        驗證輸入是否為有效的數值格式
        
        Args:
            text: 待驗證的字串
            
        Returns:
            bool: 是否有效
        """
        try:
            cls.parse_value_with_unit(text)
            return True
        except ValueError:
            return False


if __name__ == "__main__":
    # 測試示例
    converter = UnitConverter()
    
    test_cases = [
        "3.3V",
        "100mA", 
        "1.2k",
        "50u",
        "2.5mV",
        "1.5nA",
        "2.2MΩ"
    ]
    
    print("單位轉換測試:")
    for case in test_cases:
        try:
            value, prefix = converter.parse_value_with_unit(case)
            formatted = converter.format_value_with_unit(value, "V")
            print(f"{case:8s} -> {value:12.9f} -> {formatted}")
        except ValueError as e:
            print(f"{case:8s} -> 錯誤: {e}")