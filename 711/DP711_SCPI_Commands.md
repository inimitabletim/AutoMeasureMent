# Rigol DP711 SCPI 命令參考

## 基本資訊
- **型號**: Rigol DP711
- **類型**: 可程式化線性直流電源供應器
- **輸出**: 單通道 30V/5A, 最大功率 150W
- **通訊**: RS232 (需要 female-female 連接線)

## 基本 SCPI 指令

### 1. 系統識別
```scpi
*IDN?                   # 查詢儀器識別資訊
```

### 2. 快速設定（推薦）
```scpi
APPLy CH1,<voltage>,<current>   # 同時設定電壓和電流
# 範例：
APPLy CH1,12.5,2.0             # 設定 12.5V, 2.0A
APPLy CH1,5.0,1.0              # 設定 5.0V, 1.0A
```

### 3. 輸出控制
```scpi
OUTPut:STATe ON         # 開啟輸出
OUTPut:STATe OFF        # 關閉輸出
OUTPut ON               # 開啟輸出（簡寫）
OUTPut OFF              # 關閉輸出（簡寫）
OUTPut:STATe?           # 查詢輸出狀態
OUTPut?                 # 查詢輸出狀態（簡寫）
```

### 4. 電壓設定
```scpi
SOURce:VOLTage <value>  # 設定輸出電壓
SOURce:VOLTage?         # 查詢設定電壓
# 範例：
SOURce:VOLTage 12.5     # 設定 12.5V
```

### 5. 電流設定
```scpi
SOURce:CURRent <value>  # 設定輸出電流限制
SOURce:CURRent?         # 查詢設定電流
# 範例：
SOURce:CURRent 2.0      # 設定電流限制 2.0A
```

### 6. 測量指令
```scpi
MEASure:VOLTage?        # 測量實際輸出電壓
MEASure:CURRent?        # 測量實際輸出電流
MEASure:POWer?          # 測量輸出功率
MEASure:ALL?            # 測量所有參數（電壓,電流,功率）
```

## 通道選擇
DP711 為單通道設備，通道可表示為：
- `CH1` 或 `P30V`

## 典型操作序列

### 基本電源輸出
```scpi
*IDN?                   # 1. 確認設備連接
APPLy CH1,5.0,1.0      # 2. 設定 5V, 1A
OUTPut ON              # 3. 開啟輸出
MEASure:ALL?           # 4. 測量實際值
OUTPut OFF             # 5. 關閉輸出
```

### 漸進式設定
```scpi
SOURce:VOLTage 0       # 1. 先設定 0V
SOURce:CURRent 1.0     # 2. 設定電流限制
OUTPut ON              # 3. 開啟輸出
SOURce:VOLTage 12.0    # 4. 漸進調整到目標電壓
```

## 重要注意事項

1. **連接線**: 需要 female-female RS232 線（儘管設備有 male 接頭）
2. **指令結尾**: 所有指令以 `\n` 結尾
3. **不區分大小寫**: `VOLTAGE`, `voltage`, `Voltage` 都有效
4. **單位**: 預設單位為 V (伏特)、A (安培)、W (瓦特)
5. **參數範圍**: 
   - 電壓: 0-30V
   - 電流: 0-5A
   - 功率: 0-150W

## 錯誤處理
```scpi
SYSTem:ERRor?          # 查詢系統錯誤
SYSTem:ERRor:COUNt?    # 查詢錯誤計數
```

## 狀態查詢
```scpi
STATus:OPERation?      # 查詢操作狀態
STATus:QUEStionable?   # 查詢可疑狀態
```