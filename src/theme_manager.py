#!/usr/bin/env python3
"""
主題管理器 - 自動檢測並應用系統主題
支援 macOS, Windows, Linux 的深色/淺色模式切換
"""

import sys
import platform
import subprocess
from typing import Dict, Any
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QPalette


class ThemeManager(QObject):
    """主題管理器 - 處理系統主題檢測"""
    
    def __init__(self):
        super().__init__()
        self.current_theme = self.detect_system_theme()
        
    def detect_system_theme(self) -> str:
        """檢測系統主題模式
        
        Returns:
            str: 'dark' 或 'light'
        """
        system = platform.system()
        
        try:
            if system == "Darwin":  # macOS
                return self._detect_macos_theme()
            elif system == "Windows":
                return self._detect_windows_theme()
            elif system == "Linux":
                return self._detect_linux_theme()
            else:
                # 使用 Qt 的調色盤檢測
                return self._detect_qt_theme()
                
        except Exception:
            # 如果檢測失敗，預設使用淺色主題
            return "light"
            
    def _detect_macos_theme(self) -> str:
        """檢測 macOS 主題"""
        try:
            result = subprocess.run(
                ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0 and 'Dark' in result.stdout:
                return "dark"
            else:
                return "light"
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return self._detect_qt_theme()
            
    def _detect_windows_theme(self) -> str:
        """檢測 Windows 主題"""
        try:
            import winreg
            
            # 檢查 Windows 註冊表
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            )
            
            # AppsUseLightTheme: 0 = 深色, 1 = 淺色
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            
            return "light" if value == 1 else "dark"
            
        except (ImportError, OSError, FileNotFoundError):
            return self._detect_qt_theme()
            
    def _detect_linux_theme(self) -> str:
        """檢測 Linux 主題"""
        try:
            # 嘗試 GNOME/GTK 主題檢測
            result = subprocess.run(
                ['gsettings', 'get', 'org.gnome.desktop.interface', 'gtk-theme'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                theme_name = result.stdout.strip().lower()
                if 'dark' in theme_name or 'adwaita-dark' in theme_name:
                    return "dark"
                else:
                    return "light"
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        # 嘗試 KDE 主題檢測
        try:
            result = subprocess.run(
                ['kreadconfig5', '--group', 'General', '--key', 'ColorScheme'],
                capture_output=True,
                text=True,
                timeout=2
            )
            
            if result.returncode == 0:
                scheme = result.stdout.strip().lower()
                if 'dark' in scheme or 'breeze dark' in scheme:
                    return "dark"
                else:
                    return "light"
                    
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
            
        return self._detect_qt_theme()
        
    def _detect_qt_theme(self) -> str:
        """使用 Qt 調色盤檢測主題"""
        try:
            app = QApplication.instance()
            if app:
                palette = app.palette()
                window_color = palette.color(QPalette.ColorRole.Window)
                
                # 計算亮度 (0-255)
                brightness = (
                    window_color.red() * 0.299 +
                    window_color.green() * 0.587 +
                    window_color.blue() * 0.114
                )
                
                return "dark" if brightness < 128 else "light"
            else:
                return "light"
                
        except Exception:
            return "light"
            
    def get_current_theme(self) -> str:
        """獲取當前主題
        
        Returns:
            str: 'dark' 或 'light'
        """
        return self.current_theme


class ThemeStyleSheet:
    """主題樣式表管理器"""
    
    @staticmethod
    def get_stylesheet(theme: str) -> str:
        """獲取指定主題的樣式表
        
        Args:
            theme: 'dark' 或 'light'
            
        Returns:
            str: CSS 樣式表
        """
        if theme == "dark":
            return ThemeStyleSheet._get_dark_theme()
        else:
            return ThemeStyleSheet._get_light_theme()
            
    @staticmethod
    def _get_light_theme() -> str:
        """淺色主題樣式"""
        return """
            QMainWindow {
                background-color: #ffffff;
                color: #2c3e50;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 12px;
                background-color: #f8f9fa;
                color: #2c3e50;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #34495e;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel {
                color: #2c3e50;
                font-size: 15px;
            }
            QLineEdit {
                border: 2px solid #ecf0f1;
                border-radius: 4px;
                padding: 6px;
                background-color: #ffffff;
                color: #2c3e50;
                font-size: 15px;
                selection-background-color: #3498db;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background-color: #ffffff;
            }
            QDoubleSpinBox, QComboBox {
                border: 2px solid #ecf0f1;
                border-radius: 4px;
                padding: 6px;
                background-color: #ffffff;
                color: #2c3e50;
                font-size: 15px;
            }
            QDoubleSpinBox:focus, QComboBox:focus {
                border: 2px solid #3498db;
            }
            QCheckBox {
                color: #2c3e50;
                font-size: 15px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #bdc3c7;
                background-color: #ffffff;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #27ae60;
                background-color: #27ae60;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 15px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
            QTextEdit {
                border: 2px solid #ecf0f1;
                border-radius: 4px;
                background-color: #ffffff;
                color: #2c3e50;
                font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
                font-size: 14px;
                padding: 8px;
            }
            QStatusBar {
                background-color: #ecf0f1;
                color: #2c3e50;
                font-size: 14px;
                border-top: 1px solid #bdc3c7;
            }
        """
        
    @staticmethod
    def _get_dark_theme() -> str:
        """深色主題樣式"""
        return """
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 6px;
                margin-top: 1ex;
                padding-top: 12px;
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                color: #ffffff;
                font-size: 16px;
                font-weight: bold;
            }
            QLabel {
                color: #ffffff;
                font-size: 15px;
            }
            QLineEdit {
                border: 2px solid #555555;
                border-radius: 4px;
                padding: 6px;
                background-color: #404040;
                color: #ffffff;
                font-size: 15px;
                selection-background-color: #0078d4;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
                background-color: #404040;
            }
            QDoubleSpinBox, QComboBox {
                border: 2px solid #555555;
                border-radius: 4px;
                padding: 6px;
                background-color: #404040;
                color: #ffffff;
                font-size: 15px;
            }
            QDoubleSpinBox:focus, QComboBox:focus {
                border: 2px solid #0078d4;
            }
            QCheckBox {
                color: #ffffff;
                font-size: 15px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #777777;
                background-color: #404040;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #0078d4;
                background-color: #0078d4;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 10px 18px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 15px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #888888;
            }
            QTextEdit {
                border: 2px solid #555555;
                border-radius: 4px;
                background-color: #1e1e1e;
                color: #ffffff;
                font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
                font-size: 14px;
                padding: 8px;
            }
            QStatusBar {
                background-color: #404040;
                color: #ffffff;
                font-size: 14px;
                border-top: 1px solid #555555;
            }
        """
        
    @staticmethod
    def get_log_colors(theme: str) -> Dict[str, str]:
        """獲取日誌顏色配置
        
        Args:
            theme: 'dark' 或 'light'
            
        Returns:
            Dict[str, str]: 日誌級別對應的顏色
        """
        if theme == "dark":
            return {
                'DEBUG': '#888888',
                'INFO': '#ffffff',
                'WARNING': '#ffa500',
                'ERROR': '#ff6b6b',
                'CRITICAL': '#ff4757'
            }
        else:
            return {
                'DEBUG': '#6c757d',
                'INFO': '#212529',
                'WARNING': '#fd7e14',
                'ERROR': '#dc3545',
                'CRITICAL': '#721c24'
            }