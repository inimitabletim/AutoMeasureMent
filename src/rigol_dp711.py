#!/usr/bin/env python3
"""
Rigol DP711 可程式化線性直流電源供應器控制模組
支援 SCPI 指令通訊控制
"""

import logging
import time
from datetime import datetime
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
            
            # 嘗試連接設備 - 修正端口名稱格式
            port_number = self.port.replace('COM', '') if 'COM' in self.port else self.port
            resource_name = f"ASRL{port_number}::INSTR"
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
            
            # 驗證連接 - 直接查詢而不依賴連接狀態
            try:
                identity = self.instrument.query("*IDN?").strip()
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
                self.logger.error(f"設備識別查詢失敗: {e}")
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
            
    # ================================
    # 專業化功能增強 (基於官方DP700程式設計指南)
    # ================================
    
    def save_memory_state(self, memory_number: int) -> bool:
        """保存當前設定到記憶體
        
        Args:
            memory_number: 記憶體編號 (1-5)
            
        Returns:
            bool: 保存是否成功
        """
        if not 1 <= memory_number <= 5:
            raise ValueError("記憶體編號必須在1-5之間")
            
        try:
            self._send_command(f"*SAV {memory_number}")
            self.logger.info(f"設定已保存到記憶體 {memory_number}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存記憶體狀態失敗: {e}")
            return False
            
    def recall_memory_state(self, memory_number: int) -> bool:
        """從記憶體載入設定
        
        Args:
            memory_number: 記憶體編號 (1-5)
            
        Returns:
            bool: 載入是否成功
        """
        if not 1 <= memory_number <= 5:
            raise ValueError("記憶體編號必須在1-5之間")
            
        try:
            self._send_command(f"*RCL {memory_number}")
            self.logger.info(f"已從記憶體 {memory_number} 載入設定")
            return True
            
        except Exception as e:
            self.logger.error(f"載入記憶體狀態失敗: {e}")
            return False
            
    def get_memory_catalog(self) -> Dict[int, Dict[str, Any]]:
        """獲取記憶體內容目錄
        
        Returns:
            Dict: 記憶體編號對應的設定內容
        """
        memory_catalog = {}
        
        for mem_num in range(1, 6):
            try:
                # 臨時保存當前狀態
                current_voltage = self.get_set_voltage()
                current_current = self.get_set_current()
                
                # 載入記憶體狀態
                if self.recall_memory_state(mem_num):
                    # 讀取記憶體中的設定
                    mem_voltage = self.get_set_voltage()
                    mem_current = self.get_set_current()
                    
                    memory_catalog[mem_num] = {
                        'voltage': mem_voltage,
                        'current': mem_current,
                        'timestamp': datetime.now().isoformat()
                    }
                    
                # 恢復原始狀態
                self.set_voltage(current_voltage)
                self.set_current(current_current)
                
            except Exception as e:
                self.logger.warning(f"讀取記憶體 {mem_num} 失敗: {e}")
                memory_catalog[mem_num] = {
                    'voltage': 0.0,
                    'current': 0.0,
                    'timestamp': None,
                    'error': str(e)
                }
                
        return memory_catalog
        
    def set_track_mode(self, mode: str) -> bool:
        """設定輸出追蹤模式
        
        Args:
            mode: 追蹤模式 ('INDEP'=獨立, 'SER'=串聯, 'PARA'=並聯)
            
        Returns:
            bool: 設定是否成功
        """
        valid_modes = ['INDEP', 'SER', 'PARA']
        mode = mode.upper()
        
        if mode not in valid_modes:
            raise ValueError(f"無效的追蹤模式: {mode}，有效值: {valid_modes}")
            
        try:
            self._send_command(f"OUTPut:TRACk {mode}")
            self.logger.info(f"追蹤模式已設定為: {mode}")
            return True
            
        except Exception as e:
            self.logger.error(f"設定追蹤模式失敗: {e}")
            return False
            
    def get_track_mode(self) -> str:
        """獲取當前追蹤模式
        
        Returns:
            str: 當前追蹤模式
        """
        try:
            response = self._query_command("OUTPut:TRACk?")
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"查詢追蹤模式失敗: {e}")
            return "UNKNOWN"
            
    def get_protection_status(self) -> Dict[str, Any]:
        """獲取詳細保護狀態
        
        Returns:
            Dict: 保護狀態詳細資訊
        """
        protection_status = {
            'ovp_triggered': False,
            'ocp_triggered': False,
            'otp_triggered': False,  # 過溫保護
            'unregulated': False,    # 調節失效
            'protection_clear': True,
            'raw_status': 0
        }
        
        try:
            # 查詢可疑狀態寄存器
            status_response = self._query_command("STATus:QUEStionable:CONDition?")
            status_value = int(float(status_response))
            protection_status['raw_status'] = status_value
            
            # 解析狀態位 (基於SCPI標準)
            protection_status['ovp_triggered'] = bool(status_value & 0x01)    # Bit 0
            protection_status['ocp_triggered'] = bool(status_value & 0x02)    # Bit 1  
            protection_status['otp_triggered'] = bool(status_value & 0x10)    # Bit 4
            protection_status['unregulated'] = bool(status_value & 0x08)      # Bit 3
            
            # 整體保護狀態
            protection_status['protection_clear'] = status_value == 0
            
            self.logger.debug(f"保護狀態: {protection_status}")
            
        except Exception as e:
            self.logger.error(f"查詢保護狀態失敗: {e}")
            protection_status['error'] = str(e)
            
        return protection_status
        
    def clear_protection(self) -> bool:
        """清除保護狀態
        
        Returns:
            bool: 清除是否成功
        """
        try:
            self._send_command("OUTPut:PROTection:CLEar")
            self.logger.info("保護狀態已清除")
            return True
            
        except Exception as e:
            self.logger.error(f"清除保護狀態失敗: {e}")
            return False
            
    def set_ovp_level(self, voltage: float) -> bool:
        """設定過壓保護電壓
        
        Args:
            voltage: 過壓保護電壓 (V)
            
        Returns:
            bool: 設定是否成功
        """
        if not 0.1 <= voltage <= 33.0:
            raise ValueError("過壓保護電壓必須在0.1V-33.0V之間")
            
        try:
            self._send_command(f"SOURce:VOLTage:PROTection:LEVel {voltage:.3f}")
            self.logger.info(f"過壓保護設定為: {voltage:.3f}V")
            return True
            
        except Exception as e:
            self.logger.error(f"設定過壓保護失敗: {e}")
            return False
            
    def set_ocp_level(self, current: float) -> bool:
        """設定過流保護電流
        
        Args:
            current: 過流保護電流 (A)
            
        Returns:
            bool: 設定是否成功
        """
        if not 0.01 <= current <= 5.5:
            raise ValueError("過流保護電流必須在0.01A-5.5A之間")
            
        try:
            self._send_command(f"SOURce:CURRent:PROTection:LEVel {current:.3f}")
            self.logger.info(f"過流保護設定為: {current:.3f}A")
            return True
            
        except Exception as e:
            self.logger.error(f"設定過流保護失敗: {e}")
            return False
            
    def get_ovp_level(self) -> float:
        """獲取過壓保護電壓設定
        
        Returns:
            float: 過壓保護電壓 (V)
        """
        try:
            response = self._query_command("SOURce:VOLTage:PROTection:LEVel?")
            return float(response)
            
        except Exception as e:
            self.logger.error(f"查詢過壓保護電壓失敗: {e}")
            return 0.0
            
    def get_ocp_level(self) -> float:
        """獲取過流保護電流設定
        
        Returns:
            float: 過流保護電流 (A)
        """
        try:
            response = self._query_command("SOURce:CURRent:PROTection:LEVel?")
            return float(response)
            
        except Exception as e:
            self.logger.error(f"查詢過流保護電流失敗: {e}")
            return 0.0
            
    def enable_ovp(self, enable: bool = True) -> bool:
        """啟用/停用過壓保護
        
        Args:
            enable: True=啟用, False=停用
            
        Returns:
            bool: 設定是否成功
        """
        try:
            state = "ON" if enable else "OFF"
            self._send_command(f"SOURce:VOLTage:PROTection:STATe {state}")
            self.logger.info(f"過壓保護已{'啟用' if enable else '停用'}")
            return True
            
        except Exception as e:
            self.logger.error(f"設定過壓保護狀態失敗: {e}")
            return False
            
    def enable_ocp(self, enable: bool = True) -> bool:
        """啟用/停用過流保護
        
        Args:
            enable: True=啟用, False=停用
            
        Returns:
            bool: 設定是否成功
        """
        try:
            state = "ON" if enable else "OFF"
            self._send_command(f"SOURce:CURRent:PROTection:STATe {state}")
            self.logger.info(f"過流保護已{'啟用' if enable else '停用'}")
            return True
            
        except Exception as e:
            self.logger.error(f"設定過流保護狀態失敗: {e}")
            return False
            
    def get_device_temperature(self) -> float:
        """獲取設備內部溫度
        
        Returns:
            float: 內部溫度 (攝氏度)
        """
        try:
            response = self._query_command("SYSTem:TEMPerature?")
            temperature = float(response)
            self.logger.debug(f"設備溫度: {temperature:.1f}°C")
            return temperature
            
        except Exception as e:
            self.logger.warning(f"查詢設備溫度失敗: {e}")
            return 0.0
            
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """獲取設備綜合狀態報告
        
        Returns:
            Dict: 完整的設備狀態資訊
        """
        status = {
            'timestamp': datetime.now().isoformat(),
            'connection': {
                'connected': self.is_connected(),
                'identity': self.get_identity(),
            },
            'output': {
                'state': self.get_output_state(),
                'voltage_set': self.get_set_voltage(),
                'current_set': self.get_set_current(),
                'voltage_measured': 0.0,
                'current_measured': 0.0,
                'power_measured': 0.0,
            },
            'protection': self.get_protection_status(),
            'tracking': {
                'mode': self.get_track_mode()
            },
            'environment': {
                'temperature': self.get_device_temperature()
            },
            'errors': self.check_errors()
        }
        
        # 如果輸出開啟，測量實際值
        if status['output']['state']:
            try:
                v, i, p = self.measure_all()
                status['output']['voltage_measured'] = v
                status['output']['current_measured'] = i  
                status['output']['power_measured'] = p
            except:
                pass
                
        return status