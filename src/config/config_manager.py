#!/usr/bin/env python3
"""
配置管理器
處理應用程式配置的加載、保存、驗證和更新
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from copy import deepcopy
from .default_settings import DEFAULT_CONFIG, CONFIG_VALIDATION_RULES
from src.unified_logger import get_logger


class ConfigValidationError(Exception):
    """配置驗證錯誤"""
    pass


class ConfigManager:
    """應用程式配置管理器"""
    
    def __init__(self, config_file: str = "config/user_settings.json"):
        """初始化配置管理器
        
        Args:
            config_file: 用戶配置檔案路徑
        """
        self.config_file = Path(config_file)
        self.logger = get_logger("ConfigManager")
        
        # 載入配置
        self._config = self._load_config()
        
        # 確保配置目錄存在
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self) -> Dict[str, Any]:
        """載入配置
        
        Returns:
            Dict: 合併後的配置
        """
        # 從預設配置開始
        config = deepcopy(DEFAULT_CONFIG)
        
        # 如果用戶配置存在，則覆蓋預設值
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    config = self._merge_configs(config, user_config)
                    self.logger.info(f"已載入用戶配置: {self.config_file}")
            except Exception as e:
                self.logger.error(f"載入用戶配置失敗: {e}, 使用預設配置")
                
        return config
        
    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """深度合併配置字典
        
        Args:
            base: 基礎配置
            override: 覆蓋配置
            
        Returns:
            Dict: 合併後的配置
        """
        result = deepcopy(base)
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def get(self, path: str, default: Any = None) -> Any:
        """獲取配置值
        
        Args:
            path: 配置路徑，如 "instruments.keithley_2461.connection.timeout"
            default: 預設值
            
        Returns:
            Any: 配置值
        """
        try:
            keys = path.split('.')
            value = self._config
            
            for key in keys:
                value = value[key]
                
            return value
            
        except (KeyError, TypeError):
            self.logger.debug(f"配置路徑不存在: {path}, 返回預設值: {default}")
            return default
            
    def set(self, path: str, value: Any, save: bool = True) -> bool:
        """設置配置值
        
        Args:
            path: 配置路徑
            value: 新值
            save: 是否立即保存到檔案
            
        Returns:
            bool: 設置是否成功
        """
        try:
            # 驗證新值
            if not self._validate_config_value(path, value):
                return False
                
            # 設置值
            keys = path.split('.')
            config_ref = self._config
            
            # 導航到父級
            for key in keys[:-1]:
                if key not in config_ref:
                    config_ref[key] = {}
                config_ref = config_ref[key]
                
            # 設置最終值
            config_ref[keys[-1]] = value
            
            self.logger.info(f"配置已更新: {path} = {value}")
            
            # 保存配置
            if save:
                self.save_config()
                
            return True
            
        except Exception as e:
            self.logger.error(f"設置配置失敗: {path} = {value}, 錯誤: {e}")
            return False
            
    def _validate_config_value(self, path: str, value: Any) -> bool:
        """驗證配置值
        
        Args:
            path: 配置路徑
            value: 要驗證的值
            
        Returns:
            bool: 驗證是否通過
        """
        if path not in CONFIG_VALIDATION_RULES:
            return True  # 沒有驗證規則的配置直接通過
            
        rules = CONFIG_VALIDATION_RULES[path]
        
        try:
            # 類型檢查
            if 'type' in rules:
                expected_type = rules['type']
                if not isinstance(value, expected_type):
                    raise ConfigValidationError(f"類型錯誤: 期望 {expected_type.__name__}, 實際 {type(value).__name__}")
                    
            # 範圍檢查
            if 'min' in rules and value < rules['min']:
                raise ConfigValidationError(f"值太小: {value} < {rules['min']}")
                
            if 'max' in rules and value > rules['max']:
                raise ConfigValidationError(f"值太大: {value} > {rules['max']}")
                
            # 選項檢查
            if 'choices' in rules and value not in rules['choices']:
                raise ConfigValidationError(f"無效選項: {value}, 可選: {rules['choices']}")
                
            return True
            
        except ConfigValidationError as e:
            self.logger.error(f"配置驗證失敗 {path}: {e}")
            return False
            
    def save_config(self) -> bool:
        """保存配置到檔案
        
        Returns:
            bool: 保存是否成功
        """
        try:
            # 只保存與預設配置不同的部分
            user_config = self._get_user_overrides()
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(user_config, f, indent=2, ensure_ascii=False)
                
            self.logger.info(f"配置已保存到: {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存配置失敗: {e}")
            return False
            
    def _get_user_overrides(self) -> Dict[str, Any]:
        """獲取用戶自定義的配置（與預設不同的部分）
        
        Returns:
            Dict: 用戶覆蓋的配置
        """
        def find_differences(current: Dict, default: Dict, path: str = "") -> Dict:
            differences = {}
            
            for key, value in current.items():
                current_path = f"{path}.{key}" if path else key
                
                if key not in default:
                    differences[key] = value
                elif isinstance(value, dict) and isinstance(default[key], dict):
                    sub_diff = find_differences(value, default[key], current_path)
                    if sub_diff:
                        differences[key] = sub_diff
                elif value != default[key]:
                    differences[key] = value
                    
            return differences
            
        return find_differences(self._config, DEFAULT_CONFIG)
        
    def reset_to_defaults(self, section: Optional[str] = None) -> bool:
        """重置配置到預設值
        
        Args:
            section: 要重置的配置段，None表示重置全部
            
        Returns:
            bool: 重置是否成功
        """
        try:
            if section is None:
                self._config = deepcopy(DEFAULT_CONFIG)
                self.logger.info("所有配置已重置為預設值")
            else:
                if section in DEFAULT_CONFIG:
                    self._config[section] = deepcopy(DEFAULT_CONFIG[section])
                    self.logger.info(f"配置段 '{section}' 已重置為預設值")
                else:
                    self.logger.warning(f"配置段 '{section}' 不存在")
                    return False
                    
            self.save_config()
            return True
            
        except Exception as e:
            self.logger.error(f"重置配置失敗: {e}")
            return False
            
    def get_instrument_config(self, instrument_type: str) -> Dict[str, Any]:
        """獲取特定儀器的配置
        
        Args:
            instrument_type: 儀器類型 (如 "keithley_2461")
            
        Returns:
            Dict: 儀器配置
        """
        return self.get(f"instruments.{instrument_type}", {})
        
    def get_gui_config(self, section: str = None) -> Dict[str, Any]:
        """獲取GUI配置
        
        Args:
            section: 具體的GUI配置段
            
        Returns:
            Dict: GUI配置
        """
        if section:
            return self.get(f"gui.{section}", {})
        return self.get("gui", {})
        
    def get_data_config(self, section: str = None) -> Dict[str, Any]:
        """獲取數據配置
        
        Args:
            section: 具體的數據配置段
            
        Returns:
            Dict: 數據配置
        """
        if section:
            return self.get(f"data.{section}", {})
        return self.get("data", {})
        
    def export_config(self, filepath: str) -> bool:
        """導出當前配置
        
        Args:
            filepath: 導出檔案路徑
            
        Returns:
            bool: 導出是否成功
        """
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            self.logger.info(f"配置已導出到: {filepath}")
            return True
        except Exception as e:
            self.logger.error(f"導出配置失敗: {e}")
            return False
            
    def import_config(self, filepath: str) -> bool:
        """導入配置
        
        Args:
            filepath: 配置檔案路徑
            
        Returns:
            bool: 導入是否成功
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
                
            # 驗證並合併配置
            self._config = self._merge_configs(DEFAULT_CONFIG, imported_config)
            self.save_config()
            self.logger.info(f"配置已從 {filepath} 導入")
            return True
            
        except Exception as e:
            self.logger.error(f"導入配置失敗: {e}")
            return False


# 全局配置管理器實例
_config_manager = None

def get_config() -> ConfigManager:
    """獲取全局配置管理器實例
    
    Returns:
        ConfigManager: 配置管理器實例
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager