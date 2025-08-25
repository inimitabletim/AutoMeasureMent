# 多儀器控制系統

基於Python的多儀器控制系統，支援Keithley 2461 SourceMeter和Rigol DP711 Power Supply的統一控制介面。

## 主要功能

- ✅ **網路連接**: 支援TCP/IP(LXI)連接Keithley 2461
- ✅ **SCPI控制**: 完整的SCPI命令介面
- ✅ **電壓/電流控制**: 支援電壓源和電流源模式
- ✅ **測量功能**: 電壓、電流、電阻、功率測量
- ✅ **資料記錄**: CSV/JSON格式數據保存
- ✅ **自動配置**: 自動範圍、測量速度設定
- ✅ **圖形化界面**: PyQt6 GUI，實時數據顯示和圖表
- ✅ **多執行緒**: 背景測量，UI不卡頓
- ✅ **Rigol DP711**: 支援多設備同時連接(RS232/COM端口)

## 專案結構

```
code/
├── 2461/                    # Keithley 2461說明書和文檔
├── src/                     # 核心程式模組
│   ├── keithley_2461.py     # Keithley 2461控制類
│   ├── rigol_dp711.py       # Rigol DP711控制類
│   ├── port_manager.py      # COM端口自動檢測
│   ├── multi_device_manager.py # 多設備管理
│   ├── instrument_base.py   # 儀器抽象基礎類
│   ├── theme_manager.py     # 主題管理
│   └── data_logger.py       # 資料記錄模組
├── widgets/                 # GUI控制組件
│   ├── keithley_widget.py   # Keithley控制Widget
│   └── rigol_widget.py      # Rigol多設備控制Widget
├── main.py                  # 多儀器GUI主程式
├── gui_main.py              # 單一Keithley GUI(舊版)
├── gui_multi_instrument.py  # 多儀器GUI實現
├── test_keithley.py         # 功能測試腳本
├── requirements.txt         # Python依賴套件
└── README.md               # 專案說明
```

## 安裝依賴

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 啟動多儀器控制系統 (推薦)

```bash
python main.py
```

### 2. 啟動單一Keithley GUI (舊版)

```bash
python gui_main.py
```

### 3. 功能測試

```bash
python test_keithley.py
```

### 4. 程式範例

```python
from src.keithley_2461 import Keithley2461
from src.data_logger import DataLogger

# 連接設備
with Keithley2461(ip_address="192.168.0.100") as keithley:
    if keithley.connect("visa"):
        # 設定電壓源模式
        keithley.set_voltage(5.0, current_limit=0.1)
        keithley.output_on()
        
        # 測量
        voltage, current, resistance, power = keithley.measure_all()
        print(f"V={voltage}V, I={current}A, R={resistance}Ω, P={power}W")
        
        # 關閉輸出
        keithley.output_off()
```

## GUI功能特色

### 主要界面組件

1. **設備連接面板**
   - IP地址輸入
   - 一鍵連接/斷開功能
   - 連接狀態指示

2. **輸出控制面板**
   - 電壓源/電流源模式切換
   - 輸出值設定(電壓、電流、限制)
   - 輸出開關控制
   - 即時設定應用

3. **測量控制面板**
   - 單次測量功能
   - 自動連續測量
   - 測量間隔設定

4. **實時數據顯示**
   - 大字體數值顯示
   - 彩色標籤區分不同參數
   - 即時數據更新

5. **圖表顯示**
   - 實時電壓/電流曲線
   - 可縮放、拖動的互動圖表
   - 自動數據點管理(最新1000點)

6. **數據記錄功能**
   - 一鍵開啟/關閉記錄
   - 支援CSV/JSON格式保存
   - 數據統計和摘要生成

7. **系統日誌**
   - 即時操作記錄
   - 錯誤信息顯示
   - 自動滾動日誌視窗

### GUI優勢

- 🎯 **直觀操作**: 圖形化界面，無需記憶命令
- 📊 **實時監控**: 即時數據顯示和圖表更新
- 🔄 **多執行緒**: 背景測量不影響UI響應
- 💾 **數據管理**: 內建數據記錄和保存功能
- 🛡️ **錯誤處理**: 友好的錯誤提示和恢復機制

## 設備配置

### Keithley 2461設定
- 確保儀器連接到網路
- 記錄儀器IP地址
- 預設SCPI連接埠: 5025

### 支援的連接方式
1. **VISA**: 推薦方式，使用PyVISA庫
2. **Socket**: 直接TCP/IP連接

## API參考

### Keithley2461類

#### 連接控制
- `connect(method="visa")`: 連接設備
- `disconnect()`: 斷開連接
- `get_identity()`: 獲取設備資訊

#### 輸出控制
- `set_voltage(voltage, current_limit)`: 設定電壓源
- `set_current(current, voltage_limit)`: 設定電流源
- `output_on()`: 開啟輸出
- `output_off()`: 關閉輸出

#### 測量功能
- `measure_voltage()`: 測量電壓
- `measure_current()`: 測量電流
- `measure_resistance()`: 測量電阻
- `measure_power()`: 測量功率
- `measure_all()`: 同時測量所有參數

### DataLogger類

#### 記錄控制
- `start_session(name)`: 開始記錄會話
- `log_measurement(v, i, r, p)`: 記錄測量數據
- `save_session_csv()`: 保存為CSV
- `save_session_json()`: 保存為JSON

## 開發狀態

### 已完成功能 ✅
- [x] 專案基本結構
- [x] Keithley 2461網路連接
- [x] SCPI命令實現
- [x] 電壓/電流控制
- [x] 測量功能實現
- [x] 資料記錄系統
- [x] 完整測試套件

### 計劃功能 🔄
- [ ] 進階掃描功能
- [ ] 更多儀器支援
- [ ] 遠端監控介面
- [ ] 數據分析工具

## 測試

執行測試腳本驗證所有功能：

```bash
python test_keithley.py
```

測試項目包括：
- 設備連接測試
- SCPI命令測試
- 測量功能測試
- 資料記錄測試

## 故障排除

### 常見問題
1. **連接失敗**: 檢查IP地址和網路連接
2. **VISA錯誤**: 確認已安裝VISA運行時
3. **權限問題**: 確認網路埠5025可存取

### 日誌檢查
程式會生成 `instrument_control.log` 日誌文件，可查看詳細錯誤信息。

## 貢獻

歡迎提交問題報告和功能建議！

## 授權

此專案僅供學習和研究使用。