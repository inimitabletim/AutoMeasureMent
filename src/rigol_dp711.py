#!/usr/bin/env python3
"""
Rigol DP711 可程式化線性直流電源供應器控制模組
支援 SCPI 指令通訊控制
"""

import logging
import time
from typing import Optional, Dict, Any, Tuple
import pyvisa
from src.instrument_base import PowerSupplyBase


class RigolDP711(PowerSupplyBase):
    """Rigol DP711 可程式化線性直流電源供應器控制類別"""
    
    def __init__(self, port: str = "COM1", baudrate: int = 9600):
        """初始化 Rigol DP711
        
        Args:
            port: 串口端口 (如 "COM1", "/dev/ttyUSB0")
            baudrate: 波特率 (預設 9600)
        """
        super().__init__("Rigol DP711")
        self.port = port
        self.baudrate = baudrate
        self.instrument = None
        self.resource_manager = None
        
        # 設備規格
        self.max_voltage = 30.0  # V
        self.max_current = 5.0   # A
        self.max_power = 150.0   # W
        
        self.logger.info(f"初始化 Rigol DP711 - 端口: {port}")
        
    def connect(self, connection_params: Optional[Dict[str, Any]] = None) -> bool:
        """連接到 Rigol DP711
        
        Args:
            connection_params: 連接參數 (可覆蓋初始設定)
            
        Returns:
            bool: 連接是否成功
        """
        try:
            # 更新連接參數（如果提供）
            if connection_params:
                self.port = connection_params.get('port', self.port)
                self.baudrate = connection_params.get('baudrate', self.baudrate)
            
            # 建立 VISA 資源管理器
            self.resource_manager = pyvisa.ResourceManager()
            
            # 嘗試連接設備
            resource_name = f"ASRL{self.port}::INSTR"
            self.instrument = self.resource_manager.open_resource(resource_name)
            
            # 設定串口參數
            self.instrument.baud_rate = self.baudrate
            self.instrument.data_bits = 8
            self.instrument.parity = pyvisa.constants.Parity.none
            self.instrument.stop_bits = pyvisa.constants.StopBits.one
            self.instrument.flow_control = pyvisa.constants.VI_ASRL_FLOW_NONE
            
            # 設定讀取終止符
            self.instrument.read_termination = '\n'
            self.instrument.write_termination = '\n'
            
            # 設定超時時間
            self.instrument.timeout = 5000  # 5 秒
            
            # 驗證連接
            identity = self.get_identity()
            if "DP711" in identity or "RIGOL" in identity.upper():
                self.connected = True
                self.logger.info(f"成功連接到設備: {identity}")
                
                # 初始化設備
                self._initialize_device()
                return True
            else:
                self.logger.error(f"設備識別失敗: {identity}")
                self.disconnect()
                return False
                
        except Exception as e:
            self.logger.error(f"連接失敗: {e}")
            self.disconnect()
            return False
            
    def disconnect(self) -> None:
        """斷開與設備的連接"""
        try:
            if self.instrument:
                # 安全關閉輸出
                try:
                    self.output_off()
                except:
                    pass
                
                # 關閉連接
                self.instrument.close()
                self.instrument = None
                
            if self.resource_manager:
                self.resource_manager.close()
                self.resource_manager = None
                
            self.connected = False
            self.logger.info("設備連接已斷開")
            
        except Exception as e:
            self.logger.error(f"斷開連接時發生錯誤: {e}")
            
    def _initialize_device(self) -> None:
        """初始化設備設定"""
        try:
            # 清除錯誤
            self._send_command("*CLS")
            time.sleep(0.1)
            
            # 設定預設狀態
            self.output_off()
            self.set_voltage(0.0)
            self.set_current(1.0)  # 預設電流限制 1A
            
            self.logger.info("設備初始化完成")
            
        except Exception as e:
            self.logger.error(f"設備初始化失敗: {e}")
            
    def _send_command(self, command: str) -> None:
        """發送 SCPI 指令
        
        Args:
            command: SCPI 指令
        """
        if not self.connected or not self.instrument:
            raise RuntimeError("設備未連接")
            
        try:
            self.instrument.write(command)
            self.logger.debug(f"發送指令: {command}")
            
        except Exception as e:
            self.logger.error(f"發送指令失敗: {command} - {e}")
            raise
            
    def _query_command(self, command: str) -> str:
        """查詢 SCPI 指令
        
        Args:
            command: SCPI 查詢指令
            
        Returns:
            str: 設備回應
        """
        if not self.connected or not self.instrument:
            raise RuntimeError("設備未連接")
            
        try:
            response = self.instrument.query(command).strip()
            self.logger.debug(f"查詢指令: {command} -> {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"查詢指令失敗: {command} - {e}")
            raise
            
    def reset(self) -> None:
        """重置設備到預設狀態"""
        try:
            self._send_command("*RST")
            time.sleep(1.0)  # 等待重置完成
            self._initialize_device()
            self.logger.info("設備已重置")
            
        except Exception as e:
            self.logger.error(f"重置設備失敗: {e}")
            
    def get_identity(self) -> str:
        """獲取設備識別資訊
        
        Returns:
            str: 設備識別字串
        """
        try:
            return self._query_command("*IDN?")
        except:
            return "Unknown"
            
    def is_connected(self) -> bool:
        """檢查設備是否已連接
        
        Returns:
            bool: 連接狀態
        """
        return self.connected and self.instrument is not None
        
    def set_voltage(self, voltage: float, channel: int = 1) -> None:
        """設定輸出電壓
        
        Args:
            voltage: 電壓值 (V)
            channel: 通道號 (DP711 只有一個通道)
        """
        if not 0 <= voltage <= self.max_voltage:
            raise ValueError(f"電壓值超出範圍: 0-{self.max_voltage}V")
            
        try:
            self._send_command(f"SOURce:VOLTage {voltage:.3f}")
            self.logger.info(f"設定電壓: {voltage:.3f}V")
            
        except Exception as e:
            self.logger.error(f"設定電壓失敗: {e}")
            raise
            
    def set_current(self, current: float, channel: int = 1) -> None:
        """設定輸出電流限制
        
        Args:
            current: 電流限制值 (A)
            channel: 通道號 (DP711 只有一個通道)
        """
        if not 0 <= current <= self.max_current:
            raise ValueError(f"電流值超出範圍: 0-{self.max_current}A")
            
        try:
            self._send_command(f"SOURce:CURRent {current:.3f}")
            self.logger.info(f"設定電流限制: {current:.3f}A")
            
        except Exception as e:
            self.logger.error(f"設定電流限制失敗: {e}")
            raise
            
    def apply_settings(self, voltage: float, current: float, channel: int = 1) -> None:
        """同時設定電壓和電流（建議使用此方法）
        
        Args:
            voltage: 電壓值 (V)
            current: 電流限制值 (A)
            channel: 通道號 (DP711 只有一個通道)
        """
        if not 0 <= voltage <= self.max_voltage:
            raise ValueError(f"電壓值超出範圍: 0-{self.max_voltage}V")
        if not 0 <= current <= self.max_current:
            raise ValueError(f"電流值超出範圍: 0-{self.max_current}A")
            
        try:
            self._send_command(f"APPLy CH1,{voltage:.3f},{current:.3f}")
            self.logger.info(f"應用設定: {voltage:.3f}V, {current:.3f}A")
            
        except Exception as e:
            self.logger.error(f"應用設定失敗: {e}")
            raise
            
    def output_on(self, channel: int = 1) -> None:
        """開啟輸出
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
        """
        try:
            self._send_command("OUTPut:STATe ON")
            self.logger.info("輸出已開啟")
            
        except Exception as e:
            self.logger.error(f"開啟輸出失敗: {e}")
            raise
            
    def output_off(self, channel: int = 1) -> None:
        """關閉輸出
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
        """
        try:
            self._send_command("OUTPut:STATe OFF")
            self.logger.info("輸出已關閉")
            
        except Exception as e:
            self.logger.error(f"關閉輸出失敗: {e}")
            raise
            
    def get_output_state(self, channel: int = 1) -> bool:
        """獲取輸出狀態
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
            
        Returns:
            bool: True 表示輸出開啟
        """
        try:
            response = self._query_command("OUTPut:STATe?")
            return response.upper() in ['1', 'ON']
            
        except Exception as e:
            self.logger.error(f"查詢輸出狀態失敗: {e}")
            return False
            
    def measure_voltage(self, channel: int = 1) -> float:
        """測量實際輸出電壓
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
            
        Returns:
            float: 電壓值 (V)
        """
        try:
            response = self._query_command("MEASure:VOLTage?")
            voltage = float(response)
            self.logger.debug(f"測量電壓: {voltage:.6f}V")
            return voltage
            
        except Exception as e:
            self.logger.error(f"測量電壓失敗: {e}")
            return 0.0
            
    def measure_current(self, channel: int = 1) -> float:
        """測量實際輸出電流
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
            
        Returns:
            float: 電流值 (A)
        """
        try:
            response = self._query_command("MEASure:CURRent?")
            current = float(response)
            self.logger.debug(f"測量電流: {current:.6f}A")
            return current
            
        except Exception as e:
            self.logger.error(f"測量電流失敗: {e}")
            return 0.0
            
    def measure_power(self, channel: int = 1) -> float:
        """測量輸出功率
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
            
        Returns:
            float: 功率值 (W)
        """
        try:
            response = self._query_command("MEASure:POWer?")
            power = float(response)
            self.logger.debug(f"測量功率: {power:.6f}W")
            return power
            
        except Exception as e:
            self.logger.error(f"測量功率失敗: {e}")
            return 0.0
            
    def measure_all(self, channel: int = 1) -> Tuple[float, float, float]:
        """測量所有參數
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
            
        Returns:
            Tuple[float, float, float]: (電壓, 電流, 功率)
        """
        try:
            response = self._query_command("MEASure:ALL?")
            values = [float(x.strip()) for x in response.split(',')]
            
            if len(values) >= 3:
                voltage, current, power = values[0], values[1], values[2]
                self.logger.debug(f"測量所有參數: {voltage:.6f}V, {current:.6f}A, {power:.6f}W")
                return voltage, current, power
            else:
                # 如果單一指令失敗，分別測量
                voltage = self.measure_voltage(channel)
                current = self.measure_current(channel)
                power = self.measure_power(channel)
                return voltage, current, power
                
        except Exception as e:
            self.logger.error(f"測量所有參數失敗: {e}")
            return 0.0, 0.0, 0.0
            
    def get_set_voltage(self, channel: int = 1) -> float:
        """獲取設定的電壓值
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
            
        Returns:
            float: 設定電壓值 (V)
        """
        try:
            response = self._query_command("SOURce:VOLTage?")
            return float(response)
            
        except Exception as e:
            self.logger.error(f"查詢設定電壓失敗: {e}")
            return 0.0
            
    def get_set_current(self, channel: int = 1) -> float:
        """獲取設定的電流限制值
        
        Args:
            channel: 通道號 (DP711 只有一個通道)
            
        Returns:
            float: 設定電流限制值 (A)
        """
        try:
            response = self._query_command("SOURce:CURRent?")
            return float(response)
            
        except Exception as e:
            self.logger.error(f"查詢設定電流失敗: {e}")
            return 0.0
            
    def check_errors(self) -> list:
        """檢查設備錯誤
        
        Returns:
            list: 錯誤訊息列表
        """
        errors = []
        try:
            while True:
                response = self._query_command("SYSTem:ERRor?")
                if response.startswith("0,"):
                    break  # 沒有更多錯誤
                errors.append(response)
                
                # 防止無限迴圈
                if len(errors) > 10:
                    break
                    
        except Exception as e:
            self.logger.error(f"檢查錯誤失敗: {e}")
            
        return errors