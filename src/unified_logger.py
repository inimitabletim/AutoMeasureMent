#!/usr/bin/env python3
"""
統一日誌管理系統
提供整合的日誌記錄功能，支援檔案和控制台輸出
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Optional
from pathlib import Path

class UnifiedLogger:
    """統一日誌管理器"""
    
    _instance: Optional['UnifiedLogger'] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.setup_logger()
            UnifiedLogger._initialized = True
    
    def setup_logger(self):
        """設定日誌系統"""
        # 建立logs目錄
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # 設定主要日誌記錄器
        self.logger = logging.getLogger("MultiInstrumentControl")
        self.logger.setLevel(logging.DEBUG)
        
        # 避免重複添加處理器
        if self.logger.handlers:
            return
        
        # 建立格式器
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # 檔案處理器 - 使用輪轉日誌
        log_file = log_dir / f"multi_instrument_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # 控制台處理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # 添加處理器
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info("統一日誌系統已初始化")
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """
        獲取指定名稱的日誌記錄器
        
        Args:
            name: 日誌記錄器名稱，如果為None則返回主記錄器
            
        Returns:
            logging.Logger: 日誌記錄器
        """
        if name:
            return logging.getLogger(f"MultiInstrumentControl.{name}")
        return self.logger
    
    def log_instrument_command(self, instrument: str, command: str, response: str = None):
        """
        記錄儀器命令
        
        Args:
            instrument: 儀器名稱
            command: 發送的命令
            response: 接收的回應
        """
        logger = self.get_logger("InstrumentComm")
        if response:
            logger.debug(f"[{instrument}] CMD: {command} -> RSP: {response}")
        else:
            logger.debug(f"[{instrument}] CMD: {command}")
    
    def log_measurement_data(self, instrument: str, data: dict):
        """
        記錄測量數據
        
        Args:
            instrument: 儀器名稱
            data: 測量數據字典
        """
        logger = self.get_logger("Measurement")
        logger.info(f"[{instrument}] {data}")
    
    def log_connection_event(self, instrument: str, event: str, details: str = ""):
        """
        記錄連接事件
        
        Args:
            instrument: 儀器名稱
            event: 事件類型 (connected, disconnected, error)
            details: 事件詳情
        """
        logger = self.get_logger("Connection")
        if details:
            logger.info(f"[{instrument}] {event}: {details}")
        else:
            logger.info(f"[{instrument}] {event}")
    
    def log_error(self, component: str, error: str, exception: Exception = None):
        """
        記錄錯誤
        
        Args:
            component: 組件名稱
            error: 錯誤描述
            exception: 例外物件
        """
        logger = self.get_logger("Error")
        if exception:
            logger.error(f"[{component}] {error}: {str(exception)}")
            logger.exception(exception)
        else:
            logger.error(f"[{component}] {error}")
    
    def set_level(self, level: str):
        """
        設定日誌等級
        
        Args:
            level: 日誌等級 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        numeric_level = getattr(logging, level.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError(f'Invalid log level: {level}')
        
        self.logger.setLevel(numeric_level)
        for handler in self.logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.handlers.RotatingFileHandler):
                # 只調整控制台輸出等級
                handler.setLevel(numeric_level)

# 全域單例實例
unified_logger = UnifiedLogger()

# 便利函數
def get_logger(name: str = None) -> logging.Logger:
    """獲取日誌記錄器的便利函數"""
    return unified_logger.get_logger(name)

def log_instrument_command(instrument: str, command: str, response: str = None):
    """記錄儀器命令的便利函數"""
    unified_logger.log_instrument_command(instrument, command, response)

def log_measurement_data(instrument: str, data: dict):
    """記錄測量數據的便利函數"""
    unified_logger.log_measurement_data(instrument, data)

def log_connection_event(instrument: str, event: str, details: str = ""):
    """記錄連接事件的便利函數"""
    unified_logger.log_connection_event(instrument, event, details)

def log_error(component: str, error: str, exception: Exception = None):
    """記錄錯誤的便利函數"""
    unified_logger.log_error(component, error, exception)

if __name__ == "__main__":
    # 測試統一日誌系統
    logger = get_logger("Test")
    
    logger.info("測試統一日誌系統")
    log_instrument_command("Keithley2461", "SOUR:VOLT:LEV 3.3", "OK")
    log_measurement_data("Keithley2461", {"voltage": 3.3, "current": 0.001})
    log_connection_event("Keithley2461", "connected", "192.168.0.100:5025")
    log_error("TestComponent", "測試錯誤訊息")
    
    print("統一日誌系統測試完成，請查看 logs/ 目錄中的日誌檔案")