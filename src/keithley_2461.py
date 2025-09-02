"""
Keithley 2461 SourceMeter控制模組
支援TCP/IP(LXI)連接進行SCPI命令控制
"""

import socket
import time
from typing import Optional, Tuple, List, Dict, Any
from src.instrument_base import SourceMeterBase
from src.unified_logger import get_logger, log_instrument_command, log_connection_event, log_error


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
        
        # 儀器狀態
        self.current_voltage = 0.0
        self.current_current = 0.0
        
        # 使用統一日誌系統
        self.logger = get_logger("Keithley2461")
        
    def connect(self, connection_params: Dict[str, Any] = None) -> bool:
        """
        連接到儀器 (使用Socket)
        
        Args:
            connection_params: 連接參數，可包含 'ip_address'
        
        Returns:
            bool: 連接成功返回True
        """
        # 從參數中獲取IP地址
        if connection_params and 'ip_address' in connection_params:
            self.ip_address = connection_params['ip_address']
            
        if not self.ip_address:
            self.logger.error("未設定IP地址")
            return False
            
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.ip_address, self.port))
            self.connected = True
            log_connection_event("Keithley2461", "connected", f"{self.ip_address}:{self.port}")
            
            # 確保儀器使用 SCPI 命令模式
            try:
                # 重置儀器並確保使用 SCPI 模式
                reset_cmd = "*RST\n"
                self.socket.send(reset_cmd.encode('utf-8'))
                time.sleep(1.0)  # 等待重置完成
                self.logger.info("儀器已重置")
                
                # 清除錯誤隊列
                self.socket.send("*CLS\n".encode('utf-8'))
                time.sleep(0.2)
                
            except Exception as e:
                self.logger.debug(f"初始化設定: {e}")
                
            # 驗證連接
            response = self.query("*IDN?")
            if "2461" in response:
                self.logger.info(f"儀器識別: {response.strip()}")
                
                # 檢查是否有錯誤
                errors = self.check_errors()
                if errors:
                    self.logger.warning(f"儀器連接後發現錯誤: {errors}")
                else:
                    self.logger.info("儀器連接成功，無錯誤")
                
                return True
            else:
                self.logger.warning(f"意外的儀器回應: {response}")
                
        except Exception as e:
            self.logger.error(f"Socket連接失敗: {e}")
            self.connected = False
            return False
            
        return self.connected
            
    def disconnect(self) -> None:
        """斷開儀器連接"""
        try:
            if self.socket:
                self.socket.close()
                self.socket = None
                
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
            if self.socket:
                command_bytes = (command + '\n').encode('utf-8')
                self.socket.send(command_bytes)
                self.logger.debug(f"發送命令: {command}")
            else:
                raise ConnectionError("Socket未連接")
                
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
            if self.socket:
                command_bytes = (command + '\n').encode('utf-8')
                self.socket.send(command_bytes)
                response = self.socket.recv(1024).decode('utf-8').strip()
                self.logger.debug(f"查詢: {command} -> {response}")
                return response
            else:
                raise ConnectionError("Socket未連接")
                
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
        self.send_command(f":SYST:BEEP {frequency}, {duration}")
        
    def check_errors(self) -> List[str]:
        """檢查儀器錯誤隊列"""
        errors = []
        try:
            while True:
                error = self.query(":SYST:ERR?")
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
            
        # Keithley 2461 的正確 SCPI 語法 - 使用完整格式
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
        同時測量電壓、電流、電阻和功率 - 優化版本
        
        Returns:
            Tuple[float, float, float, float]: (電壓, 電流, 電阻, 功率)
        """
        # 優化策略：直接查詢電壓和電流，避免冗餘的READ查詢
        # 因為READ?在當前配置下只返回單一值
        
        # 執行兩次必要的查詢
        voltage = self.measure_voltage()
        current = self.measure_current()
        
        # 計算衍生值
        if current != 0:
            resistance = voltage / current
        else:
            resistance = float('inf')  # 電流為 0 時電阻為無窮大
            
        power = voltage * current
        
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
            
        self.send_command(f":SENS:VOLT:NPLC {nplc}")
        self.send_command(f":SENS:CURR:NPLC {nplc}")
        self.logger.info(f"設定測量速度: {nplc} NPLC")
        
    def set_auto_range(self, enabled: bool = True) -> None:
        """
        設定自動範圍
        
        Args:
            enabled: True為開啟自動範圍，False為關閉
        """
        state = "ON" if enabled else "OFF"
        self.send_command(f":SENS:VOLT:RANG:AUTO {state}")
        self.send_command(f":SENS:CURR:RANG:AUTO {state}")
        self.send_command(f":SOUR:VOLT:RANG:AUTO {state}")
        self.send_command(f":SOUR:CURR:RANG:AUTO {state}")
        self.logger.info(f"自動範圍: {'開啟' if enabled else '關閉'}")
        
    def configure_measurement_display(self) -> None:
        """配置顯示器顯示測量值"""
        self.send_command(":DISP:WATC:CHAN1:STAT ON")
        self.send_command(":DISP:WATC:CHAN2:STAT ON") 
        self.send_command(":DISP:WATC:CHAN1:FUNC VOLT")
        self.send_command(":DISP:WATC:CHAN2:FUNC CURR")
        
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
        self.send_command(f":SENS:FUNC \"{scpi_func}\"")
        self.logger.info(f"設定測量功能為: {function}")
        
    def set_compliance(self, value: float, parameter: str) -> None:
        """設定限制值
        
        Args:
            value: 限制值
            parameter: 'voltage' 或 'current'
        """
        if parameter.lower() == 'voltage':
            self.send_command(f":SOUR:CURR:VLIM {value}")
            self.logger.info(f"設定電壓限制: {value}V")
        elif parameter.lower() == 'current':
            self.send_command(f":SOUR:VOLT:ILIM {value}")
            self.logger.info(f"設定電流限制: {value}A")
        else:
            raise ValueError(f"不支援的參數類型: {parameter}")
    
    # =================
    # 修正方法簽名以匹配基類
    # =================
    
    def _convert_unit_format(self, value_str: str) -> str:
        """
        將各種單位格式轉換為數值格式，Keithley 2461 SCPI 不接受單位後綴
        
        支援格式:
        - "500mV" -> "0.5" (毫伏轉為伏特)
        - "100uA" -> "0.0001" (微安轉為安培) 
        - "3.3V" -> "3.3" (伏特保持不變)
        - "100nA" -> "1e-07" (奈安轉為安培)
        
        Args:
            value_str: 輸入的值字串
            
        Returns:
            str: 轉換後的純數值格式
        """
        import re
        
        # 如果是純數字，直接返回
        try:
            float(value_str)
            return value_str
        except ValueError:
            pass
            
        # 分離數字和單位
        match = re.match(r'^([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)\s*([a-zA-Z]+)?$', value_str.strip())
        if not match:
            self.logger.warning(f"無法解析單位格式: {value_str}")
            return value_str
            
        number = float(match.group(1))
        unit = match.group(2) if match.group(2) else ""
        
        # 單位轉換係數表 (將所有單位轉換為基本單位的數值)
        unit_multipliers = {
            # 電壓單位 (轉換為伏特)
            'V': 1.0,           # 伏特
            'mV': 1e-3,         # 毫伏
            'uV': 1e-6,         # 微伏
            'nV': 1e-9,         # 奈伏
            'pV': 1e-12,        # 皮伏
            'kV': 1e3,          # 千伏
            'MV': 1e6,          # 兆伏
            
            # 電流單位 (轉換為安培)
            'A': 1.0,           # 安培
            'mA': 1e-3,         # 毫安
            'uA': 1e-6,         # 微安
            'nA': 1e-9,         # 奈安
            'pA': 1e-12,        # 皮安
            'kA': 1e3,          # 千安
            'MA': 1e6,          # 兆安
            
            # 已經是標準格式的單位符號
            'm': 1e-3,          # 毫
            'u': 1e-6,          # 微
            'n': 1e-9,          # 奈
            'p': 1e-12,         # 皮
            'k': 1e3,           # 千
            'M': 1e6,           # 兆
        }
        
        # 轉換為數值
        multiplier = unit_multipliers.get(unit, 1.0)
        result_value = number * multiplier
        
        # 格式化結果 (避免科學記號，但保持適當精度)
        if abs(result_value) >= 1e6 or (abs(result_value) < 1e-6 and result_value != 0):
            result = f"{result_value:.6e}"
        else:
            result = f"{result_value:.9g}"
        
        self.logger.debug(f"單位轉換: '{value_str}' -> '{result}'")
        return result
    
    def set_voltage(self, voltage, channel: int = 1, current_limit = 0.1) -> None:
        """
        設定電壓輸出 - 支援多種單位格式
        
        Args:
            voltage: 輸出電壓 (支援格式: "3.3", "3.3V", "500mV", "500m")
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
            current_limit: 電流限制 (支援格式: "0.1", "100mA", "100uA", "100u")
        """
        # 設定為電壓源模式
        self.set_source_function("VOLT")
        
        # 轉換單位格式
        if isinstance(voltage, str):
            voltage_str = self._convert_unit_format(voltage)
        else:
            voltage_str = str(voltage)
            
        if isinstance(current_limit, str):
            current_limit_str = self._convert_unit_format(current_limit)
        else:
            current_limit_str = str(current_limit)
        
        # 發送 SCPI 命令前先檢查錯誤隊列
        self.send_command("*CLS")  # 清除錯誤隊列
        
        # 發送命令
        # 使用完整的 SCPI 命令格式
        self.send_command(f":SOUR:VOLT:LEV {voltage_str}")
        self.send_command(f":SOUR:VOLT:ILIM {current_limit_str}")  # 使用正確的電流限制命令
        
        # 檢查是否有錯誤
        errors = self.check_errors()
        if errors:
            self.logger.error(f"設定電壓時發生錯誤: {errors}")
            raise RuntimeError(f"SCPI錯誤: {errors}")
        
        self.current_voltage = voltage
        self.logger.info(f"設定電壓: {voltage_str}, 電流限制: {current_limit_str}")
        
    def set_current(self, current, channel: int = 1, voltage_limit = 21.0) -> None:
        """
        設定電流輸出 - 支援多種單位格式
        
        Args:
            current: 輸出電流 (支援格式: "0.1", "100mA", "100uA", "100u")
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
            voltage_limit: 電壓限制 (支援格式: "21", "21V", "21000mV", "21000m")
        """
        # 設定為電流源模式
        self.set_source_function("CURR")
        
        # 轉換單位格式
        if isinstance(current, str):
            current_str = self._convert_unit_format(current)
        else:
            current_str = str(current)
            
        if isinstance(voltage_limit, str):
            voltage_limit_str = self._convert_unit_format(voltage_limit)
        else:
            voltage_limit_str = str(voltage_limit)
        
        # 發送 SCPI 命令前先檢查錯誤隊列
        self.send_command("*CLS")  # 清除錯誤隊列
        
        # 發送命令
        # 使用完整的 SCPI 命令格式
        self.send_command(f":SOUR:CURR:LEV {current_str}")
        self.send_command(f":SOUR:CURR:VLIM {voltage_limit_str}")  # 使用正確的電壓限制命令
        
        # 檢查是否有錯誤
        errors = self.check_errors()
        if errors:
            self.logger.error(f"設定電流時發生錯誤: {errors}")
            raise RuntimeError(f"SCPI錯誤: {errors}")
        
        self.current_current = current
        self.logger.info(f"設定電流: {current_str}, 電壓限制: {voltage_limit_str}")
        
    def output_on(self, channel: int = 1) -> None:
        """開啟輸出
        
        Args:
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
        """
        # 使用完整的 SCPI 命令格式以提高相容性
        self.send_command(":OUTP:STAT ON")
        self.logger.info("輸出已開啟")
        
    def output_off(self, channel: int = 1) -> None:
        """關閉輸出
        
        Args:
            channel: 通道號（Keithley 2461只有1個通道，此參數被忽略）
        """
        # 使用完整的 SCPI 命令格式以提高相容性
        self.send_command(":OUTP:STAT OFF")
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
        # 使用完整的 SCPI 命令格式
        response = self.query(":OUTP:STAT?")
        return bool(int(response))
        
    # =================
    # 2400系列相容流程
    # =================
    
    def run_2400_series_test(self, voltage_value: str = "10", current_limit: str = "10m") -> dict:
        """
        執行完整的2400系列測試流程
        自動化步驟：重置 → 設定電壓源 → 設定參數 → 開啟輸出 → 測量 → 關閉輸出
        
        Args:
            voltage_value: 電壓設定值（支援單位，如"10", "5V", "3.3"）
            current_limit: 電流限制值（支援單位，如"10m", "100mA", "0.01"）
            
        Returns:
            dict: 測試結果，包含測量值和執行狀態
        """
        if not self.connected:
            raise ConnectionError("儀器未連接，無法執行2400系列測試")
            
        test_result = {
            'success': False,
            'steps': [],
            'measurements': {},
            'errors': []
        }
        
        try:
            # 步驟1: 重置儀器 (*RST)
            self.logger.info("步驟1: 重置儀器 (*RST)")
            self.reset()
            test_result['steps'].append("✅ 重置儀器完成")
            
            # 步驟2: 設定為電壓源 (:SOUR:FUNC VOLT)
            self.logger.info("步驟2: 設定電壓源功能")
            self.set_source_function("VOLT")
            test_result['steps'].append("✅ 設定電壓源功能完成")
            
            # 步驟3: 設定固定模式 (:SOUR:VOLT:MODE FIXED)
            self.logger.info("步驟3: 設定固定電壓模式")
            self.send_command(":SOUR:VOLT:MODE FIXED")
            test_result['steps'].append("✅ 設定固定模式完成")
            
            # 步驟4: 設定電壓範圍 (:SOUR:VOLT:RANG 20)
            self.logger.info("步驟4: 設定電壓範圍為20V")
            self.send_command(":SOUR:VOLT:RANG 20")
            test_result['steps'].append("✅ 設定電壓範圍完成")
            
            # 步驟5: 設定電壓電平 (:SOUR:VOLT:LEV)
            self.logger.info(f"步驟5: 設定電壓電平 {voltage_value}")
            voltage_converted = self._convert_unit_format(voltage_value)
            self.send_command(f":SOUR:VOLT:LEV {voltage_converted}")
            test_result['steps'].append(f"✅ 設定電壓電平 {voltage_value} 完成")
            
            # 步驟6: 設定電流保護/限制 (:SENS:CURR:PROT)
            self.logger.info(f"步驟6: 設定電流保護 {current_limit}")
            current_converted = self._convert_unit_format(current_limit)
            self.send_command(f":SOUR:VOLT:ILIM {current_converted}")
            test_result['steps'].append(f"✅ 設定電流限制 {current_limit} 完成")
            
            # 步驟7: 設定測量功能 (2461預設即支援，跳過)
            self.logger.info("步驟7: 跳過測量功能設定 (2461預設支援電流測量)")
            # self.send_command(':SENS:FUNC:ON "CURR"')  # 此命令2461不需要
            test_result['steps'].append("✅ 測量功能使用預設值")
            
            # 步驟8: 設定電流測量範圍 (:SENS:CURR:RANG)
            self.logger.info("步驟8: 設定電流測量範圍")
            self.send_command(f":SENS:CURR:RANG {current_converted}")
            test_result['steps'].append("✅ 設定電流測量範圍完成")
            
            # 步驟9: 設定數據格式 (2461使用預設即可，跳過)
            self.logger.info("步驟9: 跳過數據格式設定 (2461預設支援)")
            # self.send_command(":FORM:ELEM CURR")  # 此命令2461不支援
            test_result['steps'].append("✅ 數據格式使用預設值")
            
            # 步驟10: 開啟輸出 (:OUTP ON)
            self.logger.info("步驟10: 開啟輸出")
            self.output_on()
            test_result['steps'].append("✅ 開啟輸出完成")
            
            # 等待穩定
            time.sleep(0.5)
            
            # 步驟11: 執行測量 (:READ?)
            self.logger.info("步驟11: 執行測量")
            voltage, current, resistance, power = self.measure_all()
            test_result['measurements'] = {
                'voltage': voltage,
                'current': current, 
                'resistance': resistance,
                'power': power
            }
            test_result['steps'].append("✅ 測量完成")
            
            # 步驟12: 關閉輸出 (:OUTP OFF)
            self.logger.info("步驟12: 關閉輸出")
            self.output_off()
            test_result['steps'].append("✅ 關閉輸出完成")
            
            # 檢查是否有錯誤
            errors = self.check_errors()
            if errors:
                test_result['errors'] = errors
                self.logger.warning(f"2400流程執行完成但有錯誤: {errors}")
            else:
                test_result['success'] = True
                self.logger.info("2400系列測試流程成功完成")
            
        except Exception as e:
            error_msg = f"2400流程執行失敗: {str(e)}"
            self.logger.error(error_msg)
            test_result['errors'].append(error_msg)
            
            # 確保輸出關閉
            try:
                self.output_off()
                test_result['steps'].append("⚠️ 安全關閉輸出")
            except:
                pass
                
        return test_result