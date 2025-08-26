#!/usr/bin/env python3
"""
帶單位前綴的輸入框 Widget
支援 m, u, n, k, M 等前綴單位的輸入和顯示
"""

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLineEdit, QComboBox, 
                            QLabel, QCompleter)
from PyQt6.QtCore import pyqtSignal, QStringListModel
from PyQt6.QtGui import QValidator, QRegularExpressionValidator
from PyQt6.QtCore import QRegularExpression
from typing import Optional
from src.unit_converter import UnitConverter

class UnitInputWidget(QWidget):
    """帶單位前綴的數值輸入 Widget"""
    
    # 當值改變時發出信號 (基本單位值)
    valueChanged = pyqtSignal(float)
    
    def __init__(self, unit_symbol: str = "V", default_prefix: str = "", 
                 precision: int = 6, parent=None):
        """
        初始化單位輸入框 - 簡化版，UI控制操作順序
        
        Args:
            unit_symbol: 單位符號 (V, A, Ω, W)
            default_prefix: 預設前綴  
            precision: 顯示精度
            parent: 父控件
        """
        super().__init__(parent)
        self.unit_symbol = unit_symbol
        self.default_prefix = default_prefix
        self.precision = precision
        self.current_base_value = 0.0
        
        self.setup_ui()
        
    def setup_ui(self):
        """設置用戶介面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        
        # 數值輸入框 - 現在可以隨時輸入
        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText("輸入數值")
        self.value_edit.setText("0")  # 預設值
        
        # 設定輸入驗證器 - 允許數字、小數點、負號
        number_regex = QRegularExpression(r'^-?\d*\.?\d*$')
        validator = QRegularExpressionValidator(number_regex)
        self.value_edit.setValidator(validator)
        
        # 連接信號
        self.value_edit.textChanged.connect(self.on_value_changed)
        self.value_edit.editingFinished.connect(self.on_editing_finished)
        
        layout.addWidget(self.value_edit, 1)
        
        # 前綴選擇下拉框 - 簡化範圍 (k到n)
        self.prefix_combo = QComboBox()
        self.prefix_combo.addItems([
            f"k{self.unit_symbol}",  # kilo
            f"{self.unit_symbol}",   # 基本單位
            f"m{self.unit_symbol}",  # milli
            f"µ{self.unit_symbol}",  # micro
            f"n{self.unit_symbol}",  # nano
        ])
        
        # 預設選擇基本單位
        default_index = 1  # 基本單位位置
        if self.default_prefix:
            # 如果有指定預設前綴，嘗試找到它
            target_text = f"{self.default_prefix}{self.unit_symbol}"
            index = self.prefix_combo.findText(target_text)
            if index >= 0:
                default_index = index
        self.prefix_combo.setCurrentIndex(default_index)
        
        self.prefix_combo.currentTextChanged.connect(self.on_prefix_changed)
        
        layout.addWidget(self.prefix_combo)
        
    def on_value_changed(self, text: str):
        """數值改變時的處理 - 簡化版"""
        try:
            if text.strip() == "" or text.strip() == "-":
                return
                
            number_value = float(text)
            prefix = self.get_current_prefix()
            
            # 轉換為基本單位
            if prefix in UnitConverter.PREFIXES:
                self.current_base_value = number_value * UnitConverter.PREFIXES[prefix]
                self.valueChanged.emit(self.current_base_value)
            
        except ValueError:
            # 無效輸入，忽略
            pass
    
    def on_editing_finished(self):
        """編輯完成時的處理 - 格式化顯示"""
        try:
            if self.value_edit.text().strip() == "":
                self.value_edit.setText("0.000000")
                return
                
            number_value = float(self.value_edit.text())
            formatted = f"{number_value:.{self.precision}f}"
            self.value_edit.setText(formatted)
            
        except ValueError:
            self.value_edit.setText("0.000000")
    
    def on_prefix_changed(self, prefix_text: str):
        """前綴改變時的處理 - 超簡化版，無順序限制"""
        # 現在只是字串拼接，不需要任何特殊處理
        # 只需要觸發信號更新，讓外部知道單位改變了
        current_text = self.value_edit.text()
        if current_text:
            self.on_value_changed(current_text)
    
    def get_current_prefix(self) -> str:
        """獲取當前選擇的前綴 - SCPI格式"""
        prefix_text = self.prefix_combo.currentText()
        
        if not prefix_text:
            return ""
            
        # 移除單位符號，獲取前綴
        prefix = prefix_text.replace(self.unit_symbol, "")
        
        # 轉換µ為u (SCPI使用u代表micro)
        if prefix == "µ":
            prefix = "u"
            
        return prefix
    
    def set_value_and_prefix(self, value: float, prefix: str = ""):
        """
        設定值和前綴
        
        Args:
            value: 數值
            prefix: 前綴
        """
        # 設定前綴
        prefix_text = f"{prefix}{self.unit_symbol}"
        index = self.prefix_combo.findText(prefix_text)
        if index >= 0:
            self.prefix_combo.setCurrentIndex(index)
        
        # 設定數值
        self.value_edit.setText(f"{value:.{self.precision}f}")
        
        # 計算基本單位值
        if prefix in UnitConverter.PREFIXES:
            self.current_base_value = value * UnitConverter.PREFIXES[prefix]
            self.valueChanged.emit(self.current_base_value)
    
    def set_base_value(self, base_value: float):
        """
        設定基本單位值 - 簡化版，解決9.999999顯示問題
        
        Args:
            base_value: 基本單位的數值
        """
        self.current_base_value = base_value
        current_prefix = self.get_current_prefix()
        
        # 如果沒有選擇有效單位，不更新顯示
        if not current_prefix or current_prefix == "":
            return
        
        # 計算顯示值並修正浮點數精度問題
        if current_prefix in UnitConverter.PREFIXES:
            display_value = base_value / UnitConverter.PREFIXES[current_prefix]
            # 使用較高精度計算，然後格式化顯示
            if abs(display_value) < 1e-12:
                formatted_value = "0"
            else:
                # 先四捨五入到合理精度，再格式化
                rounded_value = round(display_value, self.precision)
                formatted_value = f"{rounded_value:g}"  # 使用g格式自動選擇最佳顯示
            self.value_edit.setText(formatted_value)
    
    def get_base_value(self) -> float:
        """獲取基本單位值"""
        return self.current_base_value
    
    def get_display_text(self) -> str:
        """獲取顯示文字"""
        return f"{self.value_edit.text()} {self.prefix_combo.currentText()}"
    
    def set_enabled(self, enabled: bool):
        """設定啟用狀態"""
        super().setEnabled(enabled)
        self.value_edit.setEnabled(enabled)
        self.prefix_combo.setEnabled(enabled)


class UnitDisplayWidget(QWidget):
    """單位顯示 Widget (只讀)"""
    
    def __init__(self, unit_symbol: str = "V", precision: int = 6, parent=None):
        """
        初始化單位顯示框
        
        Args:
            unit_symbol: 單位符號
            precision: 顯示精度
            parent: 父控件
        """
        super().__init__(parent)
        self.unit_symbol = unit_symbol
        self.precision = precision
        self.current_value = 0.0
        
        self.setup_ui()
        
    def setup_ui(self):
        """設置用戶介面"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.display_label = QLabel("0.000000 V")
        self.display_label.setStyleSheet("QLabel { background-color: white; padding: 5px; border: 1px solid #ccc; }")
        layout.addWidget(self.display_label)
        
    def set_value(self, value: float):
        """
        設定要顯示的值
        
        Args:
            value: 基本單位的數值
        """
        self.current_value = value
        
        # 處理無窮大
        if value == float('inf') or abs(value) > 1e9:
            self.display_label.setText(f"∞ {self.unit_symbol}")
            return
        
        # 使用UnitConverter自動選擇最佳前綴
        formatted = UnitConverter.format_value_with_unit(
            value, self.unit_symbol, precision=self.precision)
        
        self.display_label.setText(formatted)
    
    def get_value(self) -> float:
        """獲取當前值"""
        return self.current_value


if __name__ == "__main__":
    # 測試程式
    import sys
    from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
    
    app = QApplication(sys.argv)
    
    window = QWidget()
    layout = QVBoxLayout(window)
    
    # 電壓輸入
    voltage_input = UnitInputWidget("V", "m", 3)
    voltage_input.valueChanged.connect(lambda v: print(f"電壓: {v} V"))
    layout.addWidget(QLabel("電壓輸入:"))
    layout.addWidget(voltage_input)
    
    # 電流顯示
    current_display = UnitDisplayWidget("A", 6)
    layout.addWidget(QLabel("電流顯示:"))
    layout.addWidget(current_display)
    
    # 測試數據
    current_display.set_value(0.001234)  # 1.234mA
    
    window.show()
    sys.exit(app.exec())