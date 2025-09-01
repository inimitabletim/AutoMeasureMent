#!/usr/bin/env python3
"""
統一測量工作執行緒
使用策略模式支援連續測量、掃描測量等不同模式
"""

import time
import numpy as np
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base_worker import UnifiedWorkerBase, WorkerState


class MeasurementStrategy(ABC):
    """測量策略抽象基類"""
    
    @abstractmethod
    def setup(self, instrument, params: Dict[str, Any]) -> bool:
        """設置測量參數"""
        pass
        
    @abstractmethod
    def execute_single_measurement(self, instrument) -> Optional[Dict[str, Any]]:
        """執行單次測量"""
        pass
        
    @abstractmethod
    def should_continue(self) -> bool:
        """是否應該繼續測量"""
        pass
        
    @abstractmethod
    def get_progress(self) -> int:
        """獲取當前進度 (0-100)"""
        pass
        
    @abstractmethod
    def cleanup(self, instrument) -> None:
        """清理資源"""
        pass


class ContinuousMeasurementStrategy(MeasurementStrategy):
    """連續測量策略"""
    
    def __init__(self):
        self.interval_ms = 1000
        self.max_measurements = None  # 無限制
        self.current_count = 0
        
    def setup(self, instrument, params: Dict[str, Any]) -> bool:
        """設置連續測量參數"""
        self.interval_ms = params.get('interval_ms', 1000)
        self.max_measurements = params.get('max_measurements', None)
        self.current_count = 0
        return True
        
    def execute_single_measurement(self, instrument) -> Optional[Dict[str, Any]]:
        """執行單次測量"""
        try:
            if hasattr(instrument, 'measure_all'):
                v, i, r, p = instrument.measure_all()
                return {
                    'voltage': v,
                    'current': i, 
                    'resistance': r,
                    'power': p,
                    'measurement_type': 'continuous',
                    'sequence_number': self.current_count
                }
            else:
                # Rigol DP711 測量模式
                v = instrument.measure_voltage()
                i = instrument.measure_current()
                p = v * i
                return {
                    'voltage': v,
                    'current': i,
                    'power': p,
                    'measurement_type': 'continuous',
                    'sequence_number': self.current_count
                }
        except Exception as e:
            raise Exception(f"測量失敗: {e}")
            
    def should_continue(self) -> bool:
        """檢查是否應該繼續測量"""
        if self.max_measurements is None:
            return True
        return self.current_count < self.max_measurements
        
    def get_progress(self) -> int:
        """獲取測量進度"""
        if self.max_measurements is None:
            return -1  # 無限測量
        return min(100, int(self.current_count * 100 / self.max_measurements))
        
    def cleanup(self, instrument) -> None:
        """清理連續測量"""
        pass  # 連續測量不需要特殊清理


class SweepMeasurementStrategy(MeasurementStrategy):
    """掃描測量策略"""
    
    def __init__(self):
        self.start_value = 0
        self.stop_value = 0
        self.step_value = 0
        self.delay_ms = 100
        self.current_limit = 0.1
        self.voltage_points = []
        self.current_index = 0
        
    def setup(self, instrument, params: Dict[str, Any]) -> bool:
        """設置掃描測量參數"""
        try:
            self.start_value = params['start']
            self.stop_value = params['stop'] 
            self.step_value = params['step']
            self.delay_ms = params.get('delay', 100)
            self.current_limit = params.get('current_limit', 0.1)
            
            # 生成掃描點
            self.voltage_points = np.arange(
                self.start_value, 
                self.stop_value + self.step_value, 
                self.step_value
            ).tolist()
            self.current_index = 0
            
            # 設置儀器為電壓源模式
            if hasattr(instrument, 'set_source_function'):
                instrument.set_source_function("VOLT")
                
            return True
            
        except Exception as e:
            raise Exception(f"掃描參數設置失敗: {e}")
            
    def execute_single_measurement(self, instrument) -> Optional[Dict[str, Any]]:
        """執行掃描中的單次測量"""
        if self.current_index >= len(self.voltage_points):
            return None
            
        try:
            # 設置電壓
            voltage = self.voltage_points[self.current_index]
            if hasattr(instrument, 'set_voltage'):
                instrument.set_voltage(voltage, current_limit=self.current_limit)
                
            # 等待穩定
            time.sleep(self.delay_ms / 1000.0)
            
            # 測量
            if hasattr(instrument, 'measure_all'):
                v, i, r, p = instrument.measure_all()
            else:
                v = instrument.measure_voltage()
                i = instrument.measure_current()
                r = v / i if i != 0 else float('inf')
                p = v * i
                
            result = {
                'voltage': v,
                'current': i,
                'resistance': r, 
                'power': p,
                'measurement_type': 'sweep',
                'set_voltage': voltage,
                'point_number': self.current_index + 1,
                'total_points': len(self.voltage_points)
            }
            
            self.current_index += 1
            return result
            
        except Exception as e:
            raise Exception(f"掃描測量失敗: {e}")
            
    def should_continue(self) -> bool:
        """檢查掃描是否應該繼續"""
        return self.current_index < len(self.voltage_points)
        
    def get_progress(self) -> int:
        """獲取掃描進度"""
        if len(self.voltage_points) == 0:
            return 100
        return int(self.current_index * 100 / len(self.voltage_points))
        
    def cleanup(self, instrument) -> None:
        """清理掃描測量"""
        try:
            if hasattr(instrument, 'output_off'):
                instrument.output_off()
        except:
            pass


class MeasurementWorker(UnifiedWorkerBase):
    """統一測量工作執行緒
    
    使用策略模式支援不同的測量類型：
    - 連續測量
    - 掃描測量  
    - 單次測量
    """
    
    def __init__(self, instrument, strategy: MeasurementStrategy, params: Dict[str, Any]):
        """初始化測量Worker
        
        Args:
            instrument: 儀器實例
            strategy: 測量策略
            params: 測量參數
        """
        super().__init__(f"Measurement_{strategy.__class__.__name__}", instrument)
        self.strategy = strategy
        self.params = params
        
    def setup(self) -> bool:
        """設置測量Worker"""
        try:
            if not self.instrument or not self.instrument.is_connected():
                self._emit_error("instrument_error", "儀器未連接")
                return False
                
            return self.strategy.setup(self.instrument, self.params)
            
        except Exception as e:
            self._emit_error("setup_error", str(e))
            return False
            
    def execute_operation(self) -> bool:
        """執行測量操作"""
        try:
            if not self.strategy.should_continue():
                return False
                
            # 執行測量
            measurement_data = self.strategy.execute_single_measurement(self.instrument)
            
            if measurement_data:
                # 發送數據
                self._emit_data(measurement_data)
                
                # 更新進度
                progress = self.strategy.get_progress()
                if progress >= 0:
                    self._emit_progress(progress)
                    
                # 檢查延遲
                if isinstance(self.strategy, ContinuousMeasurementStrategy):
                    self.msleep(self.strategy.interval_ms)
                    
            return True
            
        except Exception as e:
            self._emit_error("measurement_error", str(e))
            return False
            
    def cleanup(self) -> None:
        """清理測量資源"""
        try:
            if self.strategy and self.instrument:
                self.strategy.cleanup(self.instrument)
        except Exception as e:
            self.logger.error(f"清理失敗: {e}")
            
    def pause_measurement(self):
        """暫停測量"""
        self.pause_work()
        
    def resume_measurement(self):
        """恢復測量"""
        self.resume_work()
        
    def stop_measurement(self):
        """停止測量"""
        self.stop_work()