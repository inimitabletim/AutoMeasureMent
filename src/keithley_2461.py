"""
Keithley 2461 SourceMeter控制模組
支援TCP/IP(LXI)連接進行SCPI命令控制
"""

import socket
import time
import logging
from typing import Optional, Tuple, List, Dict, Any
import pyvisa
from src.instrument_base import SourceMeterBase


class Keithley2461(SourceMeterBase):
    """Keithley 2461 SourceMeter控制類"""
    
    def __init__(self, ip_address: str = None, port: int = 5025, timeout: float = 10.0):
        """
        初始化Keithley 2461控制器
        
        Args:
            ip_address: 儀器IP地址
            port: TCP端口 (預設5025)
            timeout: 通訊超時時間(秒)
        """
        super().__init__("Keithley 2461")
        self.ip_address = ip_address
        self.port = port
        self.timeout = timeout
        
        # 連接物件
        self.socket = None
        self.visa_rm = None
        self.instrument = None
        
        # 儀器狀態
        self.current_voltage = 0.0
        self.current_current = 0.0
        
    def connect_via_socket(self) -> bool:
        """
        使用Socket連接儀器
        
        Returns:
            bool: 連接成功返回True
        """
        if not self.ip_address:
            self.logger.error("未設定IP地址")
            return False
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip_address, self.port))
            self.connected = True
            self.logger.info(f"成功連接到 {self.ip_address}:{self.port}")
            
            # 切換到 SCPI 命令模式
            try:
                switch_cmd = ":SYST:LANG SCPI\n"
                self.socket.send(switch_cmd.encode('utf-8'))
                time.sleep(0.2)
                self.logger.info("已切換到SCPI命令模式")
            except Exception as e:
                self.logger.debug(f"SCPI模式切換: {e}")
                
            # 驗證連接
            response = self.query("*IDN?")
            if "2461" in response:
                self.logger.info(f"儀器識別: {response.strip()}")
                return True
            else:
                self.logger.warning(f"意外的儀器回應: {response}")
                
        except Exception as e:
            self.logger.error(f"Socket連接失敗: {e}")
            self.connected = False
            return False
            
        return self.connected
        
    def connect_via_visa(self) -> bool:
        """
        使用PyVISA連接儀器
        
        Returns:
            bool: 連接成功返回True
        """
        if not self.ip_address:
            self.logger.error("未設定IP地址")
            return False
            
        try:
            self.visa_rm = pyvisa.ResourceManager()
            # TCPIP連接字符串格式: TCPIP::host::port::SOCKET
            visa_address = f"TCPIP::{self.ip_address}::{self.port}::SOCKET"
            
            self.instrument = self.visa_rm.open_resource(visa_address)
            self.instrument.timeout = int(self.timeout * 1000)  # 轉換為毫秒
            self.instrument.read_termination = '\n'
            self.instrument.write_termination = '\n'
            
            self.connected = True
            self.logger.info(f"VISA成功連接到 {visa_address}")
            
            # 切換到 SCPI 命令模式
            try:
                self.instrument.write(":SYST:LANG SCPI")
                time.sleep(0.2)
                self.logger.info("已切換到SCPI命令模式")
            except Exception as e:
                self.logger.debug(f"SCPI模式切換: {e}")
                
            # 驗證連接
            response = self.query("*IDN?")
            if "2461" in response:
                self.logger.info(f"儀器識別: {response.strip()}")
                return True
            else:
                self.logger.warning(f"意外的儀器回應: {response}")
                
        except Exception as e:
            self.logger.error(f"VISA連接失敗: {e}")
            self.connected = False
            return False
            
        return self.connected
        
    def connect(self, connection_params: Dict[str, Any] = None, method: str = "visa") -> bool:
        """
        連接到儀器
        
        Args:
            connection_params: 連接參數 (可選，為了符合基類接口)
            method: 連接方法 ("visa" 或 "socket")
            
        Returns:
            bool: 連接成功返回True
        """
        # 如果提供了connection_params，從中提取IP地址
        if connection_params and 'ip_address' in connection_params:
            self.ip_address = connection_params['ip_address']
        if connection_params and 'method' in connection_params:
            method = connection_params['method']
            
        if method.lower() == "visa":
            return self.connect_via_visa()
        elif method.lower() == "socket":
            return self.connect_via_socket()
        else:
            self.logger.error(f"不支援的連接方法: {method}")
            return False
            
    def disconnect(self) -> None:
        """斷開儀器連接"""
        try:
            if self.socket:
                self.socket.close()
                self.socket = None
                
            if self.instrument:
                self.instrument.close()
                self.instrument = None
                
            if self.visa_rm:
                self.visa_rm.close()
                self.visa_rm = None
                
            self.connected = False
            self.logger.info("儀器已斷開連接")
            
        except Exception as e:
            self.logger.error(f"斷開連接時發生錯誤: {e}")
            
    def send_command(self, command: str) -> None:
        """
        發送SCPI命令（無回應）
        
        Args:
            command: SCPI命令字符串
        """
        if not self.connected:
            raise ConnectionError("儀器未連接")
            
        try:
            if self.instrument:  # VISA方式
                self.instrument.write(command)
            elif self.socket:    # Socket方式
                command_bytes = (command + '\n').encode('utf-8')
                self.socket.send(command_bytes)
                
            self.logger.debug(f"發送命令: {command}")
            
        except Exception as e:
            self.logger.error(f"發送命令失敗: {e}")
            raise
            
    def query(self, command: str) -> str:
        """
        查詢SCPI命令（有回應）
        
        Args:
            command: SCPI查詢命令
            
        Returns:
            str: 儀器回應
        """
        if not self.connected:
            raise ConnectionError("儀器未連接")
            
        try:
            if self.instrument:  # VISA方式
                response = self.instrument.query(command).strip()
            elif self.socket:    # Socket方式
                command_bytes = (command + '\n').encode('utf-8')
                self.socket.send(command_bytes)
                response = self.socket.recv(1024).decode('utf-8').strip()
                
            self.logger.debug(f"查詢: {command} -> {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"查詢命令失敗: {e}")
            raise
            
    def reset(self) -> None:
        """重置儀器到預設狀態"""
        self.send_command("*RST")
        time.sleep(1)  # 等待重置完成
        self.logger.info("儀器已重置")
        
    def get_identity(self) -> str:
        """獲取儀器識別信息"""
        return self.query("*IDN?")
        
    def beep(self, frequency: float = 2000, duration: float = 0.5) -> None:
        """
        儀器蜂鳴聲
        
        Args:
            frequency: 頻率 (Hz)
            duration: 持續時間 (秒)
        """
        self.send_command(f"SYST:BEEP {frequency}, {duration}")
        
    def check_errors(self) -> List[str]:
        """檢查儀器錯誤隊列"""
        errors = []
        try:
            while True:
                error = self.query("SYST:ERR?")
                if error.startswith("0,"):
                    break  # 無更多錯誤
                errors.append(error)
                if len(errors) > 20:  # 防止無限循環
                    break
        except:
            pass
        return errors
        
    def __enter__(self):
        """上下文管理器入口"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
        
    def __del__(self):
        """析構函數"""
        self.disconnect()
        
    # =================
    # 電壓/電流控制功能
    # =================
    
    def set_source_function(self, function: str) -> None:
        """
        設定輸出功能
        
        Args:
            function: "VOLT" (電壓源) 或 "CURR" (電流源)
        """
        if function.upper() not in ["VOLT", "CURR"]:
            raise ValueError("功能必須是 'VOLT' 或 'CURR'")
            
        # Keithley 2461 的正確 SCPI 語法
        if function.upper() == "VOLT":
            self.send_command(":SOUR:FUNC VOLT")
        else:
            self.send_command(":SOUR:FUNC CURR")
        self.logger.info(f"設定源功能為: {function.upper()}")
        
    # =================
    # 測量功能
    # =================
        
    def measure_resistance(self) -> float:
        """
        測量電阻
        
        Returns:
            float: 測量的電阻值 (Ω)
        """
        response = self.query(":MEAS:RES?")
        resistance = float(response)
        self.logger.debug(f"測量電阻: {resistance}Ω")
        return resistance
        
    def measure_power(self) -> float:
        """
        測量功率
        
        Returns:
            float: 測量的功率值 (W)
        """
        response = self.query(":MEAS:POW?")
        power = float(response)
        self.logger.debug(f"測量功率: {power}W")
        return power
        
    def measure_all(self) -> Tuple[float, float, float, float]:
        """
        同時測量電壓、電流、電阻和功率
        
        Returns:
            Tuple[float, float, float, float]: (電壓, 電流, 電阻, 功率)
        """
        # 使用一次查詢獲取所有數據以提高效率
        response = self.query(":READ?")
        values = [float(x) for x in response.split(',')]
        
        if len(values) >= 4:
            voltage, current, resistance, power = values[:4]
        else:
            # 備用方案：分別測量
            voltage = self.measure_voltage()
            current = self.measure_current()
            resistance = self.measure_resistance()  
            power = self.measure_power()
            
        self.logger.debug(f"全測量 - V:{voltage}V, I:{current}A, R:{resistance}Ω, P:{power}W")
        return voltage, current, resistance, power
        
    # =================
    # 配置功能
    # =================
    
    def set_measurement_speed(self, nplc: float = 1.0) -> None:
        """
        設定測量速度
        
        Args:
            nplc: Number of Power Line Cycles (0.01 - 10)
                 越小越快但精度較低
        """
        if not 0.01 <= nplc <= 10:
            raise ValueError("NPLC必須在0.01到10之間")
            
        self.send_command(f"SENS:VOLT:NPLC {nplc}")
        self.send_command(f"SENS:CURR:NPLC {nplc}")
        self.logger.info(f"設定測量速度: {nplc} NPLC")
        
    def set_auto_range(self, enabled: bool = True) -> None:
        """
        設定自動範圍
        
        Args:
            enabled: True為開啟自動範圍，False為關閉
        """
        state = "ON" if enabled else "OFF"
        self.send_command(f"SENS:VOLT:RANG:AUTO {state}")
        self.send_command(f"SENS:CURR:RANG:AUTO {state}")
        self.send_command(f"SOUR:VOLT:RANG:AUTO {state}")
        self.send_command(f"SOUR:CURR:RANG:AUTO {state}")
        self.logger.info(f"自動範圍: {'開啟' if enabled else '關閉'}")
        
    def configure_measurement_display(self) -> None:
        """配置顯示器顯示測量值"""
        self.send_command("DISP:WATC:CHAN1:STAT ON")
        self.send_command("DISP:WATC:CHAN2:STAT ON") 
        self.send_command("DISP:WATC:CHAN1:FUNC VOLT")
        self.send_command("DISP:WATC:CHAN2:FUNC CURR")
        
    # =================
    # 抽象方法實現
    # =================
    
    def is_connected(self) -> bool:
        """檢查儀器是否已連接"""
        return self.connected
        
    def set_measure_function(self, function: str) -> None:
        """設定測量功能
        
        Args:
            function: 'voltage', 'current', 'resistance', 'power'
        """
        function_map = {
            'voltage': 'VOLT',
            'current': 'CURR', 
            'resistance': 'RES',
            'power': 'POW'
        }
        
        if function.lower() not in function_map:
            raise ValueError(f"不支援的測量功能: {function}")
            
        scpi_func = function_map[function.lower()]
        self.send_command(f"SENS:FUNC \"{scpi_func}\"")
        self.logger.info(f"設定測量功能為: {function}")
        
    def set_compliance(self, value: float, parameter: str) -> None:
        """設定限制值
        
        Args:
            value: 限制值
            parameter: 'voltage' 或 'current'
        """
        if parameter.lower() == 'voltage':
            self.send_command(f"SOUR:CURR:VLIM {value}")
            self.logger.info(f"設定電壓限制: {value}V")
        elif parameter.lower() == 'current':
            self.send_command(f"SOUR:VOLT:ILIM {value}")
            self.logger.info(f"設定電流限制: {value}A")
        else:
            raise ValueError(f"不支援的參數類型: {parameter}")
    
    # =================
    # 修正方法簽名以匹配基類
    # =================
    
    def set_voltage(self, voltage: float, channel: int = 1, current_limit: float = 0.1) -> None:
        """
        設定電壓輸出
        
        Args:
            voltage: 輸出電壓 (V)
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
            current_limit: 電流限制 (A)
        """
        # 設定為電壓源模式
        self.set_source_function("VOLT")
        
        # 設定電壓值和電流限制 - 使用正確的 SCPI 格式
        self.send_command(f":SOUR:VOLT {voltage}")
        self.send_command(f":SOUR:VOLT:ILIM {current_limit}")
        
        self.current_voltage = voltage
        self.logger.info(f"設定電壓: {voltage}V, 電流限制: {current_limit}A")
        
    def set_current(self, current: float, channel: int = 1, voltage_limit: float = 21.0) -> None:
        """
        設定電流輸出
        
        Args:
            current: 輸出電流 (A)
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
            voltage_limit: 電壓限制 (V)
        """
        # 設定為電流源模式
        self.set_source_function("CURR")
        
        # 設定電流值和電壓限制 - 使用正確的 SCPI 格式
        self.send_command(f":SOUR:CURR {current}")
        self.send_command(f":SOUR:CURR:VLIM {voltage_limit}")
        
        self.current_current = current
        self.logger.info(f"設定電流: {current}A, 電壓限制: {voltage_limit}V")
        
    def output_on(self, channel: int = 1) -> None:
        """開啟輸出
        
        Args:
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
        """
        self.send_command(":OUTP ON")
        self.logger.info("輸出已開啟")
        
    def output_off(self, channel: int = 1) -> None:
        """關閉輸出
        
        Args:
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
        """
        self.send_command(":OUTP OFF")
        self.logger.info("輸出已關閉")
        
    def measure_voltage(self, channel: int = 1) -> float:
        """
        測量電壓
        
        Args:
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
            
        Returns:
            float: 測量的電壓值 (V)
        """
        response = self.query(":MEAS:VOLT?")
        voltage = float(response)
        self.logger.debug(f"測量電壓: {voltage}V")
        return voltage
        
    def measure_current(self, channel: int = 1) -> float:
        """
        測量電流
        
        Args:
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
            
        Returns:
            float: 測量的電流值 (A)
        """
        response = self.query(":MEAS:CURR?")
        current = float(response)
        self.logger.debug(f"測量電流: {current}A")
        return current
        
    def get_output_state(self, channel: int = 1) -> bool:
        """獲取輸出狀態
        
        Args:
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
        """
        response = self.query(":OUTP?")
        return bool(int(response))