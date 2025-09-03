#!/usr/bin/env python3
"""
儀器Widget基類
提供所有儀器控制Widget的標準化架構
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, 
                            QLabel, QPushButton, QMessageBox, QSplitter)
from PyQt6.QtCore import pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from src.config import get_config
from src.data import get_data_manager, MeasurementPoint
from src.workers import UnifiedWorkerBase
from src.unified_logger import get_logger
from .connection_mixin import ConnectionMixin
from .measurement_mixin import MeasurementMixin
from .data_visualization_mixin import DataVisualizationMixin


class InstrumentWidgetBase(QWidget, ConnectionMixin, MeasurementMixin, DataVisualizationMixin):
    """儀器控制Widget標準化基類
    
    提供所有儀器Widget的通用功能：
    - 標準化連接管理
    - 統一測量控制
    - 標準數據視覺化
    - 主題支援
    - 配置管理
    """
    
    # 標準信號
    connection_changed = pyqtSignal(bool, str)  # connected, info
    measurement_data = pyqtSignal(dict)         # measurement data
    error_occurred = pyqtSignal(str, str)       # error_type, message
    status_changed = pyqtSignal(str)            # status message
    theme_changed = pyqtSignal(str)             # theme name
    
    def __init__(self, instrument_type: str, instrument=None, parent=None):
        """初始化儀器Widget基類
        
        Args:
            instrument_type: 儀器類型標識 (如 'keithley_2461')
            instrument: 儀器實例 (可選)
            parent: 父Widget
        """
        super().__init__(parent)
        
        # 基礎屬性
        self.instrument_type = instrument_type
        self.instrument = instrument
        self.logger = get_logger(f"Widget.{instrument_type}")
        
        # 獲取配置和數據管理器
        self.config = get_config()
        self.data_manager = get_data_manager()
        
        # Widget狀態
        self.is_connected = False
        self.measurement_active = False
        self.current_theme = "light"
        
        # Worker管理
        self.active_workers: List[UnifiedWorkerBase] = []
        
        # 狀態定時器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self._update_status)
        
        # 設置UI
        self._setup_base_ui()
        self._setup_instrument_ui()
        
        # 註冊數據管理
        self.data_manager.register_instrument(self.instrument_type)
        
        # 連接信號
        self._connect_signals()
        
        # 應用配置
        self._apply_config()
        
    def _setup_base_ui(self):
        """設置基礎UI結構"""
        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(10)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 頂部狀態欄
        self._create_status_bar()
        
        # 主要內容區域 - 使用分割器
        self.content_splitter = QSplitter()
        self.main_layout.addWidget(self.content_splitter)
        
        # 左側控制面板
        self.control_panel = QWidget()
        self.control_layout = QVBoxLayout(self.control_panel)
        
        # 標準連接面板 (由ConnectionMixin提供)
        self.connection_group = self.create_connection_panel()
        self.control_layout.addWidget(self.connection_group)
        
        # 標準測量面板 (由MeasurementMixin提供)  
        self.measurement_group = self.create_measurement_panel()
        self.control_layout.addWidget(self.measurement_group)
        
        # 儀器特定控制面板 (子類實現)
        self.instrument_controls = QGroupBox("儀器控制")
        self.instrument_controls_layout = QVBoxLayout(self.instrument_controls)
        self.control_layout.addWidget(self.instrument_controls)
        
        # 右側數據視覺化面板 (由DataVisualizationMixin提供)
        self.visualization_panel = self.create_visualization_panel()
        
        # 添加到分割器
        self.content_splitter.addWidget(self.control_panel)
        self.content_splitter.addWidget(self.visualization_panel)
        
        # 設置分割器比例 (1:2)
        self.content_splitter.setSizes([400, 800])
        
        # 底部狀態和日誌區域
        self._create_bottom_panel()
        
    def _create_status_bar(self):
        """創建頂部狀態欄"""
        self.status_bar = QGroupBox()
        status_layout = QHBoxLayout(self.status_bar)
        
        # 儀器名稱標籤
        self.instrument_label = QLabel(f"{self.instrument_type.upper()}")
        self.instrument_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        status_layout.addWidget(self.instrument_label)
        
        # 連接狀態指示
        self.connection_status = QLabel("🔴 未連接")
        self.connection_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
        status_layout.addWidget(self.connection_status)
        
        # 測量狀態指示
        self.measurement_status = QLabel("⏸️ 待機")
        status_layout.addWidget(self.measurement_status)
        
        # 彈性空間
        status_layout.addStretch()
        
        # 主題切換按鈕
        self.theme_btn = QPushButton("🌙")
        self.theme_btn.setMaximumWidth(40)
        self.theme_btn.clicked.connect(self._toggle_theme)
        status_layout.addWidget(self.theme_btn)
        
        self.main_layout.addWidget(self.status_bar)
        
    def _create_bottom_panel(self):
        """創建底部面板"""
        self.bottom_panel = QGroupBox("狀態信息")
        bottom_layout = QHBoxLayout(self.bottom_panel)
        
        # 狀態消息標籤
        self.status_message = QLabel("準備就緒")
        bottom_layout.addWidget(self.status_message)
        
        # 彈性空間
        bottom_layout.addStretch()
        
        # 數據統計
        self.data_stats = QLabel("數據點: 0")
        bottom_layout.addWidget(self.data_stats)
        
        self.main_layout.addWidget(self.bottom_panel)
        
    @abstractmethod
    def _setup_instrument_ui(self):
        """設置儀器特定的UI組件 - 子類必須實現"""
        pass
        
    @abstractmethod
    def get_connection_params(self) -> Dict[str, Any]:
        """獲取連接參數 - 子類必須實現"""
        pass
        
    @abstractmethod
    def create_instrument_controls(self) -> QWidget:
        """創建儀器特定控制組件 - 子類必須實現"""
        pass
        
    def _connect_signals(self):
        """連接標準信號"""
        # 連接狀態變化
        self.connection_changed.connect(self._on_connection_changed)
        
        # 測量數據
        self.measurement_data.connect(self._on_measurement_data)
        
        # 錯誤處理
        self.error_occurred.connect(self._on_error)
        
        # 狀態更新
        self.status_changed.connect(self._on_status_changed)
        
    def _apply_config(self):
        """應用配置設置"""
        # 獲取儀器配置
        instrument_config = self.config.get_instrument_config(self.instrument_type)
        
        # 應用GUI配置
        gui_config = self.config.get_gui_config()
        
        # 設置主題
        theme_mode = gui_config.get('theme', {}).get('mode', 'auto')
        if theme_mode == 'auto':
            from src.theme_manager import ThemeManager
            theme_manager = ThemeManager()
            self.current_theme = theme_manager.get_current_theme()
        else:
            self.current_theme = theme_mode
            
        self.set_theme(self.current_theme)
        
    def connect_instrument(self):
        """連接儀器 - 使用新的Worker系統"""
        if self.is_connected or not self.instrument:
            return
            
        # 使用統一的連接Worker
        from src.workers import ConnectionWorker
        
        connection_params = self.get_connection_params()
        worker = ConnectionWorker(self.instrument, connection_params)
        
        # 連接信號
        worker.connection_success.connect(self._on_connection_success)
        worker.connection_failed.connect(self._on_connection_failed)
        worker.progress_updated.connect(self._on_connection_progress)
        
        # 開始連接
        self.add_worker(worker)
        worker.start_work()
        
        self.status_changed.emit("正在連接...")
        
    def disconnect_instrument(self):
        """斷開儀器連接"""
        if not self.is_connected or not self.instrument:
            return
            
        try:
            # 停止所有測量
            self.stop_measurement()
            
            # 斷開儀器
            if hasattr(self.instrument, 'disconnect'):
                self.instrument.disconnect()
                
            self.is_connected = False
            self.connection_changed.emit(False, "已斷開連接")
            self.status_changed.emit("已斷開連接")
            
        except Exception as e:
            self.error_occurred.emit("disconnect_error", str(e))
            
    def start_measurement(self):
        """開始測量 - 使用新的Worker系統"""
        if not self.is_connected or self.measurement_active:
            return
            
        # 由子類實現具體的測量邏輯
        measurement_worker = self._create_measurement_worker()
        if measurement_worker:
            self.logger.info(f"開始啟動測量Worker: {measurement_worker.worker_name}")
            
            # 連接信號
            measurement_worker.data_ready.connect(self._on_measurement_ready)
            measurement_worker.error_occurred.connect(self._on_measurement_error)
            
            self.add_worker(measurement_worker)
            measurement_worker.start_work()
            
            self.measurement_active = True
            self.logger.info(f"測量Worker已啟動，measurement_active = {self.measurement_active}")
        else:
            self.logger.error("無法創建測量Worker")
            self.status_changed.emit("測量進行中...")
            
    def stop_measurement(self):
        """停止測量"""
        if not self.measurement_active:
            return
            
        # 停止所有測量Worker
        for worker in self.active_workers[:]:
            if hasattr(worker, 'measurement') or 'Measurement' in worker.__class__.__name__:
                worker.stop_work()
                self.remove_worker(worker)
                
        self.measurement_active = False
        self.status_changed.emit("測量已停止")
        
    @abstractmethod
    def _create_measurement_worker(self) -> Optional[UnifiedWorkerBase]:
        """創建測量Worker - 子類實現"""
        pass
        
    def add_worker(self, worker: UnifiedWorkerBase):
        """添加Worker到管理列表"""
        self.active_workers.append(worker)
        worker.finished.connect(lambda: self.remove_worker(worker))
        
    def remove_worker(self, worker: UnifiedWorkerBase):
        """從管理列表移除Worker"""
        if worker in self.active_workers:
            self.active_workers.remove(worker)
            
    def set_theme(self, theme: str):
        """設置主題"""
        self.current_theme = theme
        
        # 應用主題樣式 (由子類具體實現)
        self._apply_theme_styles()
        
        # 更新主題按鈕
        if theme == "dark":
            self.theme_btn.setText("☀️")
        else:
            self.theme_btn.setText("🌙")
            
        self.theme_changed.emit(theme)
        
    def _apply_theme_styles(self):
        """應用主題樣式 - 子類可以覆蓋"""
        from src.theme_manager import ThemeStyleSheet
        stylesheet = ThemeStyleSheet.get_stylesheet(self.current_theme)
        self.setStyleSheet(stylesheet)
        
    def _toggle_theme(self):
        """切換主題"""
        new_theme = "dark" if self.current_theme == "light" else "light"
        self.set_theme(new_theme)
        
    # 事件處理方法
    def _on_connection_changed(self, connected: bool, info: str):
        """連接狀態變化處理"""
        self.is_connected = connected
        if connected:
            self.connection_status.setText("🟢 已連接")
            self.connection_status.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.connection_status.setText("🔴 未連接")
            self.connection_status.setStyleSheet("color: #e74c3c; font-weight: bold;")
            
    def _on_connection_success(self, instrument_name: str, connection_info: Dict[str, Any]):
        """連接成功處理"""
        self.connection_changed.emit(True, connection_info.get('identity', '已連接'))
        
    def _on_connection_failed(self, error_type: str, error_message: str):
        """連接失敗處理"""
        self.error_occurred.emit(error_type, error_message)
        
    def _on_connection_progress(self, progress: int):
        """連接進度更新"""
        self.status_changed.emit(f"連接中... {progress}%")
        
    def _on_measurement_data(self, data: Dict[str, Any]):
        """測量數據處理"""
        # 處理時間戳：如果是字串則轉換為datetime物件
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            from datetime import datetime
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            from datetime import datetime
            timestamp = datetime.now()
            
        # 創建MeasurementPoint並添加到數據管理器
        point = MeasurementPoint(
            timestamp=timestamp,
            instrument_id=self.instrument_type,
            voltage=data.get('voltage', 0),
            current=data.get('current', 0),
            resistance=data.get('resistance'),
            power=data.get('power'),
            metadata=data.get('metadata')
        )
        
        self.data_manager.add_measurement(point)
        
        # 更新可視化 (由DataVisualizationMixin處理)
        self.update_visualization(point)
        
    def _on_measurement_ready(self, data: Dict[str, Any]):
        """測量數據準備就緒"""
        self.measurement_data.emit(data)
        
    def _on_measurement_error(self, error_type: str, error_message: str):
        """測量錯誤處理"""
        self.error_occurred.emit(error_type, error_message)
        self.stop_measurement()
        
    def _on_error(self, error_type: str, error_message: str):
        """錯誤處理"""
        self.logger.error(f"{error_type}: {error_message}")
        
        # 顯示用戶友好的錯誤消息
        error_dialog = QMessageBox(self)
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.setWindowTitle("錯誤")
        error_dialog.setText(f"操作失敗: {error_message}")
        error_dialog.exec()
        
        self.status_changed.emit(f"錯誤: {error_message}")
        
    def _on_status_changed(self, status: str):
        """狀態變化處理"""
        self.status_message.setText(status)
        
    def _update_status(self):
        """定期狀態更新"""
        # 更新數據統計
        if self.data_manager:
            recent_data = self.data_manager.get_real_time_data(self.instrument_type, 1)
            total_count = len(self.data_manager.get_real_time_data(self.instrument_type, 10000))
            self.data_stats.setText(f"數據點: {total_count}")
            
    def closeEvent(self, event):
        """關閉事件處理"""
        # 停止所有Worker
        for worker in self.active_workers[:]:
            worker.stop_work()
            
        # 斷開儀器連接
        if self.is_connected:
            self.disconnect_instrument()
            
        # 停止定時器
        self.status_timer.stop()
        
        super().closeEvent(event)