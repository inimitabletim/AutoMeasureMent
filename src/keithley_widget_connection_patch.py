#!/usr/bin/env python3
"""
Keithley Widget 連線功能升級補丁
將阻塞式連線升級為非阻塞式，解決UI凍結問題
"""

from PyQt6.QtWidgets import QGroupBox, QGridLayout, QLabel, QLineEdit
from PyQt6.QtCore import pyqtSignal

from widgets.connection_status_widget import ConnectionStatusWidget
from src.connection_worker import ConnectionStateManager


class EnhancedKeithleyConnectionMixin:
    """
    Keithley Widget 連線功能增強 Mixin
    為現有 widget 添加非阻塞式連線能力
    """
    
    # 添加連線狀態信號
    connection_changed = pyqtSignal(bool, str)  # (connected, info)
    
    def __init_enhanced_connection__(self):
        """初始化增強的連線功能"""
        self.connection_manager = ConnectionStateManager()
        self.keithley = None
        
    def create_enhanced_connection_group(self):
        """
        創建增強的設備連接群組
        替換原有的 create_connection_group 方法
        """
        group = QGroupBox("🔌 設備連接")
        layout = QGridLayout(group)
        
        # IP地址輸入
        layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit("192.168.0.100")
        self.ip_input.setPlaceholderText("例如: 192.168.0.100")
        layout.addWidget(self.ip_input, 0, 1)
        
        # 使用增強的連線狀態Widget
        self.connection_status_widget = ConnectionStatusWidget()
        layout.addWidget(self.connection_status_widget, 1, 0, 1, 2)
        
        # 連接信號
        self.connection_status_widget.connection_requested.connect(self._handle_connection_request)
        self.connection_status_widget.disconnection_requested.connect(self._handle_disconnection_request)
        self.connection_status_widget.connection_cancelled.connect(self._handle_connection_cancel)
        
        return group
        
    def _handle_connection_request(self):
        """處理連線請求"""
        ip_address = self.ip_input.text().strip()
        if not ip_address:
            self.connection_status_widget.set_connection_failed_state("請輸入IP地址")
            return
            
        # 驗證IP格式（簡單檢查）
        if not self._is_valid_ip(ip_address):
            self.connection_status_widget.set_connection_failed_state("IP地址格式不正確")
            return
            
        try:
            # 開始非阻塞連線
            connection_params = {
                'ip_address': ip_address,
                'port': 5025,
                'timeout': 5.0  # 5秒超時
            }
            
            worker = self.connection_manager.start_connection('keithley', connection_params)
            
            # 連接工作執行緒信號
            worker.connection_started.connect(self._on_connection_started)
            worker.connection_progress.connect(self._on_connection_progress)
            worker.connection_success.connect(self._on_connection_success)
            worker.connection_failed.connect(self._on_connection_failed)
            
            # 啟動工作執行緒
            worker.start()
            
        except RuntimeError as e:
            self.connection_status_widget.set_connection_failed_state(str(e))
            
    def _handle_disconnection_request(self):
        """處理斷線請求"""
        try:
            if self.keithley and self.keithley.connected:
                # 安全斷線：先關閉輸出
                if hasattr(self, 'measurement_worker') and self.measurement_worker:
                    self.measurement_worker.stop_measurement()
                    
                self.keithley.output_off()
                self.keithley.disconnect()
                
            self.keithley = None
            self.connection_status_widget.set_disconnected_state()
            
            # 更新UI狀態
            if hasattr(self, 'start_btn'):
                self.start_btn.setEnabled(False)
                
            # 發送信號通知父組件
            self.connection_changed.emit(False, "")
            
            self.log_message("✅ 已安全斷開設備連線")
            
        except Exception as e:
            self.log_message(f"❌ 斷線時發生錯誤: {e}")
            
    def _handle_connection_cancel(self):
        """處理連線取消"""
        self.connection_manager.cancel_connection()
        self.connection_status_widget.set_disconnected_state()
        self.log_message("⚠️ 用戶取消連線")
        
    def _on_connection_started(self):
        """連線開始回調"""
        self.connection_status_widget.set_connecting_state()
        self.log_message("🔄 開始連線儀器...")
        
    def _on_connection_progress(self, message: str):
        """連線進度回調"""
        self.connection_status_widget.update_connection_progress(message)
        self.log_message(f"🔄 {message}")
        
    def _on_connection_success(self, device_info: str):
        """連線成功回調"""
        # 獲取儀器實例
        worker = self.connection_manager.connection_worker
        if worker:
            self.keithley = worker.get_instrument()
            
        # 更新UI狀態
        self.connection_status_widget.set_connected_state(device_info.split('\n')[0] if device_info else "")
        
        if hasattr(self, 'start_btn'):
            self.start_btn.setEnabled(True)
            
        # 初始化數據記錄器
        self._initialize_data_logger()
        
        # 發送信號通知父組件
        self.connection_changed.emit(True, device_info)
        
        self.log_message(f"✅ 連線成功: {device_info}")
        
    def _on_connection_failed(self, error_message: str):
        """連線失敗回調"""
        self.connection_status_widget.set_connection_failed_state(error_message)
        self.keithley = None
        
        if hasattr(self, 'start_btn'):
            self.start_btn.setEnabled(False)
            
        # 發送信號通知父組件
        self.connection_changed.emit(False, "")
        
        self.log_message(f"❌ 連線失敗: {error_message}")
        
    def _initialize_data_logger(self):
        """初始化數據記錄器"""
        try:
            if hasattr(self, 'data_logger') and self.data_logger is None:
                from src.enhanced_data_system import EnhancedDataLogger
                self.data_logger = EnhancedDataLogger(
                    base_path="data",
                    auto_save_interval=300,  # 5分鐘自動保存
                    max_memory_points=5000   # 5000個數據點內存限制
                )
                
                # 連接數據系統信號
                if hasattr(self.data_logger, 'data_saved'):
                    self.data_logger.data_saved.connect(self.on_data_saved)
                if hasattr(self.data_logger, 'statistics_updated'):
                    self.data_logger.statistics_updated.connect(self.on_statistics_updated)
                # 其他信號連接...
                    
        except ImportError:
            self.log_message("⚠️ 增強型數據系統不可用，使用基本功能")
        except Exception as e:
            self.log_message(f"⚠️ 數據記錄器初始化警告: {e}")
            
    def _is_valid_ip(self, ip_address: str) -> bool:
        """檢查IP地址格式"""
        try:
            parts = ip_address.split('.')
            if len(parts) != 4:
                return False
                
            for part in parts:
                num = int(part)
                if not 0 <= num <= 255:
                    return False
                    
            return True
        except (ValueError, AttributeError):
            return False
            
    def disconnect_device(self):
        """外部斷線接口 - 保持向後相容性"""
        if hasattr(self, 'connection_status_widget'):
            self._handle_disconnection_request()
        else:
            # 舊版斷線邏輯
            if self.keithley and self.keithley.connected:
                self.keithley.disconnect()
            self.keithley = None


def patch_keithley_widget(widget_instance):
    """
    為現有的 Keithley Widget 實例應用連線功能補丁
    
    Args:
        widget_instance: 要升級的 ProfessionalKeithleyWidget 實例
    """
    
    # 添加 Mixin 方法到實例
    for method_name in dir(EnhancedKeithleyConnectionMixin):
        if not method_name.startswith('_') or method_name.startswith('__init_'):
            method = getattr(EnhancedKeithleyConnectionMixin, method_name)
            if callable(method):
                setattr(widget_instance, method_name, method.__get__(widget_instance))
    
    # 初始化增強功能
    widget_instance.__init_enhanced_connection__()
    
    # 替換連線群組
    if hasattr(widget_instance, 'connection_group'):
        # 移除舊的連線群組
        old_group = widget_instance.connection_group
        layout = old_group.parent().layout()
        
        if layout:
            # 創建新的連線群組
            new_group = widget_instance.create_enhanced_connection_group()
            
            # 在相同位置插入新群組
            index = layout.indexOf(old_group)
            if index >= 0:
                layout.insertWidget(index, new_group)
                layout.removeWidget(old_group)
                old_group.deleteLater()
                widget_instance.connection_group = new_group
                
    return widget_instance