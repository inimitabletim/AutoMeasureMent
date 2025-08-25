#!/usr/bin/env python3
"""
儀器控制基類
提供所有儀器的共同介面
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
import logging

class InstrumentBase(ABC):
    """儀器控制抽象基類"""
    
    def __init__(self, name: str = "Unknown Instrument"):
        """初始化儀器基類
        
        Args:
            name: 儀器名稱
        """
        self.name = name
        self.connected = False
        self.connection = None
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def connect(self, connection_params: Dict[str, Any]) -> bool:
        """連接到儀器
        
        Args:
            connection_params: 連接參數（如 IP、串口等）
            
        Returns:
            bool: 連接是否成功
        """
        pass
        
    @abstractmethod
    def disconnect(self) -> None:
        """斷開儀器連接"""
        pass
        
    @abstractmethod
    def reset(self) -> None:
        """重置儀器到預設狀態"""
        pass
        
    @abstractmethod
    def get_identity(self) -> str:
        """獲取儀器識別信息"""
        pass
        
    @abstractmethod
    def is_connected(self) -> bool:
        """檢查儀器是否已連接"""
        return self.connected
        
    def __enter__(self):
        """進入上下文管理器"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        if self.connected:
            self.disconnect()
            

class PowerSupplyBase(InstrumentBase):
    """電源供應器基類"""
    
    @abstractmethod
    def set_voltage(self, voltage: float, channel: int = 1) -> None:
        """設定輸出電壓
        
        Args:
            voltage: 電壓值 (V)
            channel: 通道號
        """
        pass
        
    @abstractmethod
    def set_current(self, current: float, channel: int = 1) -> None:
        """設定輸出電流
        
        Args:
            current: 電流值 (A)
            channel: 通道號
        """
        pass
        
    @abstractmethod
    def output_on(self, channel: int = 1) -> None:
        """開啟輸出
        
        Args:
            channel: 通道號
        """
        pass
        
    @abstractmethod
    def output_off(self, channel: int = 1) -> None:
        """關閉輸出
        
        Args:
            channel: 通道號
        """
        pass
        
    @abstractmethod
    def measure_voltage(self, channel: int = 1) -> float:
        """測量電壓
        
        Args:
            channel: 通道號
            
        Returns:
            float: 電壓值 (V)
        """
        pass
        
    @abstractmethod
    def measure_current(self, channel: int = 1) -> float:
        """測量電流
        
        Args:
            channel: 通道號
            
        Returns:
            float: 電流值 (A)
        """
        pass
        
    @abstractmethod
    def get_output_state(self, channel: int = 1) -> bool:
        """獲取輸出狀態
        
        Args:
            channel: 通道號
            
        Returns:
            bool: True 表示輸出開啟
        """
        pass


class SourceMeterBase(PowerSupplyBase):
    """源表基類（如 Keithley 2461）"""
    
    @abstractmethod
    def set_source_function(self, function: str) -> None:
        """設定源功能
        
        Args:
            function: 'voltage' 或 'current'
        """
        pass
        
    @abstractmethod
    def set_measure_function(self, function: str) -> None:
        """設定測量功能
        
        Args:
            function: 'voltage', 'current', 'resistance', 'power'
        """
        pass
        
    @abstractmethod
    def measure_all(self) -> Tuple[float, float, float, float]:
        """測量所有參數
        
        Returns:
            Tuple: (電壓, 電流, 電阻, 功率)
        """
        pass
        
    @abstractmethod
    def set_compliance(self, value: float, parameter: str) -> None:
        """設定限制值
        
        Args:
            value: 限制值
            parameter: 'voltage' 或 'current'
        """
        pass


class InstrumentManager:
    """儀器管理器 - 管理多個儀器"""
    
    def __init__(self):
        """初始化儀器管理器"""
        self.instruments: Dict[str, InstrumentBase] = {}
        self.logger = logging.getLogger(__name__)
        
    def add_instrument(self, name: str, instrument: InstrumentBase) -> None:
        """添加儀器
        
        Args:
            name: 儀器識別名稱
            instrument: 儀器實例
        """
        self.instruments[name] = instrument
        self.logger.info(f"已添加儀器: {name}")
        
    def remove_instrument(self, name: str) -> None:
        """移除儀器
        
        Args:
            name: 儀器識別名稱
        """
        if name in self.instruments:
            instrument = self.instruments[name]
            if instrument.is_connected():
                instrument.disconnect()
            del self.instruments[name]
            self.logger.info(f"已移除儀器: {name}")
            
    def get_instrument(self, name: str) -> Optional[InstrumentBase]:
        """獲取儀器
        
        Args:
            name: 儀器識別名稱
            
        Returns:
            Optional[InstrumentBase]: 儀器實例或 None
        """
        return self.instruments.get(name)
        
    def list_instruments(self) -> list:
        """列出所有儀器
        
        Returns:
            list: 儀器名稱列表
        """
        return list(self.instruments.keys())
        
    def disconnect_all(self) -> None:
        """斷開所有儀器連接"""
        for name, instrument in self.instruments.items():
            if instrument.is_connected():
                instrument.disconnect()
                self.logger.info(f"已斷開儀器: {name}")