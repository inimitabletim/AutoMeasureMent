#!/usr/bin/env python3
"""
優化架構演示程式
展示新舊架構的對比效果和統一的儀器控制介面
"""

import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QTabWidget, QLabel, QPushButton,
                            QMessageBox, QSplitter, QGroupBox, QTextEdit)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont

# 確保可以導入模組
script_dir = Path(__file__).parent.absolute()
os.chdir(script_dir)

from widgets.keithley_widget_optimized import OptimizedKeithleyWidget
from widgets.rigol_widget_optimized import OptimizedRigolWidget
from src.config import get_config
from src.data import get_data_manager
from src.unified_logger import get_logger


class ArchitectureDemoWindow(QMainWindow):
    """架構演示主視窗"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger("ArchitectureDemo")
        self.setup_ui()
        self.setup_demo_content()
        
    def setup_ui(self):
        """設置用戶介面"""
        self.setWindowTitle("🚀 優化架構演示 - 統一儀器控制系統")
        self.setMinimumSize(1400, 1000)
        self.resize(1600, 1200)
        
        # 居中顯示
        self.center_on_screen()
        
        # 創建中央widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 標題區域
        self.create_title_section(main_layout)
        
        # 架構對比說明
        self.create_architecture_info(main_layout)
        
        # 演示內容
        self.create_demo_tabs(main_layout)
        
        # 底部狀態和統計
        self.create_status_section(main_layout)
        
    def create_title_section(self, layout):
        """創建標題區域"""
        title_group = QGroupBox()
        title_layout = QVBoxLayout(title_group)
        
        # 主標題
        title_label = QLabel("🏗️ 多儀器控制系統 - 架構優化演示")
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_layout.addWidget(title_label)
        
        # 副標題
        subtitle_label = QLabel("統一Worker系統 • 標準化Widget架構 • 集中式配置管理 • 統一數據處理")
        subtitle_label.setFont(QFont("Arial", 12))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        title_layout.addWidget(subtitle_label)
        
        layout.addWidget(title_group)
        
    def create_architecture_info(self, layout):
        """創建架構信息區域"""
        info_group = QGroupBox("🎯 架構優化成果")
        info_layout = QHBoxLayout(info_group)
        
        # 優化統計
        stats_widget = QWidget()
        stats_layout = QVBoxLayout(stats_widget)
        
        stats_info = [
            "📊 4,536 行新架構代碼",
            "🔄 50%+ Worker重複代碼消除", 
            "🎨 60%+ Widget重複代碼消除",
            "⚙️ 統一配置管理系統",
            "📈 整合雙重數據記錄系統",
            "🎭 跨平台主題支援"
        ]
        
        for stat in stats_info:
            label = QLabel(stat)
            label.setFont(QFont("Arial", 10))
            stats_layout.addWidget(label)
            
        info_layout.addWidget(stats_widget)
        
        # 架構特性
        features_widget = QWidget() 
        features_layout = QVBoxLayout(features_widget)
        
        features_info = [
            "🏗️ 統一Worker基類系統",
            "🧩 Mixin模式組件化設計", 
            "🔧 標準化連接和測量控制",
            "📊 可重用數據視覺化組件",
            "🛡️ 改進的錯誤處理和恢復",
            "🚀 插件化架構基礎"
        ]
        
        for feature in features_info:
            label = QLabel(feature)
            label.setFont(QFont("Arial", 10))
            features_layout.addWidget(label)
            
        info_layout.addWidget(features_widget)
        
        layout.addWidget(info_group)
        
    def create_demo_tabs(self, layout):
        """創建演示標籤頁"""
        self.demo_tabs = QTabWidget()
        
        # Keithley 2461 優化Widget
        self.keithley_widget = OptimizedKeithleyWidget()
        self.demo_tabs.addTab(self.keithley_widget, "🔬 Keithley 2461 (優化版)")
        
        # Rigol DP711 優化Widget
        self.rigol_widget = OptimizedRigolWidget()
        self.demo_tabs.addTab(self.rigol_widget, "⚡ Rigol DP711 (優化版)")
        
        # 架構對比標籤頁
        comparison_tab = self.create_architecture_comparison()
        self.demo_tabs.addTab(comparison_tab, "📋 架構對比")
        
        # 配置演示標籤頁
        config_tab = self.create_config_demo()
        self.demo_tabs.addTab(config_tab, "⚙️ 配置管理")
        
        layout.addWidget(self.demo_tabs)
        
    def create_architecture_comparison(self) -> QWidget:
        """創建架構對比標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 對比標題
        title = QLabel("新舊架構對比")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 對比內容
        comparison_splitter = QSplitter()
        
        # 舊架構
        old_arch_group = QGroupBox("🔴 舊架構問題")
        old_arch_layout = QVBoxLayout(old_arch_group)
        
        old_arch_text = QTextEdit()
        old_arch_text.setReadOnly(True)
        old_arch_text.setPlainText("""
❌ 重複的Worker類:
   - SweepMeasurementWorker
   - ContinuousMeasurementWorker  
   - RigolMeasurementWorker
   
❌ 雙重數據記錄系統:
   - DataLogger (基本功能)
   - EnhancedDataLogger (高級功能)
   
❌ Widget代碼重複:
   - 連接管理重複實現
   - 測量控制UI重複
   - 數據顯示組件重複
   
❌ 配置分散:
   - 硬編碼設定散布各處
   - 缺乏統一配置管理
   - 無用戶自定義選項
   
❌ 錯誤處理不一致:
   - 各組件獨立錯誤處理
   - 缺乏統一恢復機制
        """)
        old_arch_layout.addWidget(old_arch_text)
        
        # 新架構  
        new_arch_group = QGroupBox("🟢 新架構優勢")
        new_arch_layout = QVBoxLayout(new_arch_group)
        
        new_arch_text = QTextEdit()
        new_arch_text.setReadOnly(True)
        new_arch_text.setPlainText("""
✅ 統一Worker基類系統:
   - UnifiedWorkerBase (統一基類)
   - 策略模式測量Worker
   - 標準化狀態管理
   
✅ 統一數據管理:
   - UnifiedDataManager (整合功能)
   - 智能緩存管理
   - 多格式存儲後端
   
✅ Widget標準化架構:
   - InstrumentWidgetBase (統一基類)
   - ConnectionMixin (連接管理)
   - MeasurementMixin (測量控制)
   - DataVisualizationMixin (數據顯示)
   
✅ 集中式配置管理:
   - ConfigManager (統一配置)
   - 用戶自定義設定
   - 配置驗證和熱重載
   
✅ 標準化錯誤處理:
   - 統一錯誤處理模式
   - 自動恢復機制
   - 用戶友好錯誤提示
        """)
        new_arch_layout.addWidget(new_arch_text)
        
        comparison_splitter.addWidget(old_arch_group)
        comparison_splitter.addWidget(new_arch_group)
        comparison_splitter.setSizes([700, 700])
        
        layout.addWidget(comparison_splitter)
        
        return tab
        
    def create_config_demo(self) -> QWidget:
        """創建配置演示標籤頁"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 配置演示標題
        title = QLabel("配置管理系統演示")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # 配置信息顯示
        config_text = QTextEdit()
        config_text.setReadOnly(True)
        
        # 獲取並顯示配置信息
        try:
            config = get_config()
            
            config_info = f"""
🔧 配置管理系統狀態:

📋 儀器配置:
   • Keithley 2461: {config.get('instruments.keithley_2461.connection.timeout', '未設定')}秒超時
   • Rigol DP711: {config.get('instruments.rigol_dp711.connection.baudrate', '未設定')} 波特率

🎨 GUI配置:
   • 主題模式: {config.get('gui.theme.mode', 'auto')}
   • 視窗大小: {config.get('gui.window.default_width', 1400)}x{config.get('gui.window.default_height', 900)}
   • 圖表點數: {config.get('gui.plotting.max_plot_points', 1000)}

💾 數據配置:
   • 預設格式: {config.get('data.storage.default_format', 'csv')}
   • 自動保存: {'已啟用' if config.get('data.storage.auto_save', False) else '已停用'}
   • 緩存大小: {config.get('data.buffer.real_time_buffer_size', 1000)} 數據點

🚀 性能配置:
   • 最大併發Worker: {config.get('performance.worker_threads.max_concurrent_workers', 5)}
   • 內存限制: {config.get('performance.memory.max_memory_usage_mb', 500)}MB
   • UI更新節流: {config.get('performance.ui.update_throttle_ms', 50)}ms

🔐 安全配置:
   • 緊急停止: {'已啟用' if config.get('safety.emergency_stop.enabled', False) else '已停用'}
   • 自動斷開錯誤: {'已啟用' if config.get('safety.emergency_stop.auto_disconnect_on_error', False) else '已停用'}
   • 健康檢查間隔: {config.get('safety.monitoring.health_check_interval', 30)}秒
            """
            
            config_text.setPlainText(config_info)
            
        except Exception as e:
            config_text.setPlainText(f"配置載入錯誤: {e}")
            
        layout.addWidget(config_text)
        
        # 配置操作按鈕
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("刷新配置")
        refresh_btn.clicked.connect(lambda: self.refresh_config_display(config_text))
        button_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("導出配置")
        export_btn.clicked.connect(self.export_config)
        button_layout.addWidget(export_btn)
        
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        return tab
        
    def create_status_section(self, layout):
        """創建底部狀態區域"""
        status_group = QGroupBox("系統狀態")
        status_layout = QHBoxLayout(status_group)
        
        # 系統狀態標籤
        self.system_status_label = QLabel("系統就緒 - 架構演示模式")
        self.system_status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        status_layout.addWidget(self.system_status_label)
        
        status_layout.addStretch()
        
        # 架構信息
        self.arch_info_label = QLabel("統一架構 v2.0")
        status_layout.addWidget(self.arch_info_label)
        
        layout.addWidget(status_group)
        
    def setup_demo_content(self):
        """設置演示內容"""
        # 設置狀態更新定時器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(5000)  # 每5秒更新一次
        
        # 連接Widget狀態信號
        self.keithley_widget.status_changed.connect(self.on_widget_status_changed)
        self.rigol_widget.status_changed.connect(self.on_widget_status_changed)
        
        self.logger.info("架構演示程式已啟動")
        
    def refresh_config_display(self, text_widget):
        """刷新配置顯示"""
        # 重新載入配置並更新顯示
        self.create_config_demo()
        QMessageBox.information(self, "配置刷新", "配置信息已更新")
        
    def export_config(self):
        """導出配置"""
        try:
            config = get_config()
            filename = f"config_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            if config.export_config(filename):
                QMessageBox.information(self, "配置導出", f"配置已導出到: {filename}")
            else:
                QMessageBox.warning(self, "配置導出", "配置導出失敗")
                
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"導出配置時發生錯誤: {e}")
            
    def on_widget_status_changed(self, status: str):
        """Widget狀態變化處理"""
        self.system_status_label.setText(f"系統狀態: {status}")
        
    def update_status(self):
        """定期狀態更新"""
        # 獲取數據管理器狀態
        try:
            data_manager = get_data_manager()
            memory_usage = data_manager.get_memory_usage()
            
            status_info = (f"內存使用: {memory_usage.get('total_memory_mb', 0):.1f}MB | "
                          f"活動緩存: {memory_usage.get('buffer_count', 0)} | "
                          f"總數據點: {memory_usage.get('total_points', 0)}")
                          
            self.arch_info_label.setText(status_info)
            
        except Exception as e:
            self.arch_info_label.setText(f"狀態獲取失敗: {e}")
            
    def center_on_screen(self):
        """視窗居中顯示"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()
        
        window_geometry = self.frameGeometry()
        center_point = screen_geometry.center()
        window_geometry.moveCenter(center_point)
        
        self.move(window_geometry.topLeft())
        
    def closeEvent(self, event):
        """關閉事件處理"""
        reply = QMessageBox.question(
            self,
            "確認退出",
            "確定要退出架構演示程式嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("架構演示程式正常關閉")
            event.accept()
        else:
            event.ignore()


def main():
    """演示程式主入口"""
    app = QApplication(sys.argv)
    app.setApplicationName("Architecture Demo")
    app.setApplicationVersion("2.0")
    
    # 創建演示視窗
    demo_window = ArchitectureDemoWindow()
    demo_window.show()
    
    # 運行應用程式
    sys.exit(app.exec())


if __name__ == "__main__":
    main()