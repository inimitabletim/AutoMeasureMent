#!/usr/bin/env python3
"""
預設配置設定
定義所有系統組件的預設值
"""

from typing import Dict, Any

DEFAULT_CONFIG: Dict[str, Any] = {
    # 儀器配置
    "instruments": {
        "keithley_2461": {
            "connection": {
                "default_ip": "192.168.0.100",
                "port": 5025,
                "timeout": 10.0,
                "connection_method": "visa",  # "visa" or "socket"
                "retry_attempts": 3,
                "retry_delay": 2.0
            },
            "measurement": {
                "auto_range": True,
                "measurement_speed": 0.1,
                "default_voltage_limit": 10.0,
                "default_current_limit": 0.1,
                "integration_time": "medium"
            },
            "safety": {
                "max_voltage": 200.0,
                "max_current": 7.0,
                "output_off_on_disconnect": True,
                "compliance_check": True
            }
        },
        
        "rigol_dp711": {
            "connection": {
                "default_baudrate": 9600,
                "timeout": 5.0,
                "scan_interval": 2000,  # ms
                "identification_timeout": 1.0
            },
            "measurement": {
                "measurement_interval": 1000,  # ms
                "auto_range": True
            },
            "safety": {
                "max_voltage": 30.0,
                "max_current": 5.0,
                "max_power": 150.0,
                "output_off_on_disconnect": True
            }
        }
    },
    
    # GUI配置
    "gui": {
        "theme": {
            "mode": "auto",  # "auto", "light", "dark"
            "custom_stylesheet": None
        },
        "window": {
            "default_width": 1400,
            "default_height": 900,
            "minimum_width": 1200,
            "minimum_height": 700,
            "remember_position": True,
            "center_on_start": True
        },
        "plotting": {
            "max_plot_points": 1000,
            "update_interval": 100,  # ms
            "auto_scale": True,
            "grid_enabled": True,
            "antialiasing": True
        },
        "measurements": {
            "display_precision": 6,
            "auto_start_continuous": False,
            "show_statistics": True
        }
    },
    
    # 數據管理配置
    "data": {
        "storage": {
            "default_format": "csv",  # "csv", "json", "sqlite"
            "auto_save": True,
            "auto_save_interval": 300,  # 秒
            "session_naming": "timestamp",  # "timestamp", "manual", "auto"
            "base_path": "data"
        },
        "export": {
            "include_metadata": True,
            "include_statistics": True,
            "compression": False,
            "decimal_places": 6
        },
        "buffer": {
            "real_time_buffer_size": 1000,
            "persistent_buffer_size": 10000,
            "cleanup_interval": 3600,  # 秒
            "memory_limit_mb": 100
        }
    },
    
    # 日誌配置
    "logging": {
        "level": "INFO",  # "DEBUG", "INFO", "WARNING", "ERROR"
        "file_logging": True,
        "console_logging": True,
        "log_rotation": {
            "max_file_size_mb": 10,
            "backup_count": 5
        },
        "formats": {
            "file": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "console": "%(levelname)s: %(message)s"
        }
    },
    
    # 性能配置
    "performance": {
        "worker_threads": {
            "measurement_priority": "normal",  # "low", "normal", "high"
            "connection_timeout": 10.0,
            "max_concurrent_workers": 5
        },
        "memory": {
            "garbage_collection_interval": 300,  # 秒
            "max_memory_usage_mb": 500,
            "warning_threshold_mb": 400
        },
        "ui": {
            "update_throttle_ms": 50,
            "plot_optimization": True,
            "lazy_loading": True
        }
    },
    
    # 安全配置
    "safety": {
        "emergency_stop": {
            "enabled": True,
            "confirmation_required": True,
            "auto_disconnect_on_error": True
        },
        "limits": {
            "enforce_instrument_limits": True,
            "warn_on_high_values": True,
            "automatic_compliance": True
        },
        "monitoring": {
            "connection_health_check": True,
            "health_check_interval": 30,  # 秒
            "auto_recovery": True
        }
    },
    
    # 開發配置
    "development": {
        "debug_mode": False,
        "mock_instruments": False,
        "test_data_generation": False,
        "performance_profiling": False
    }
}


# 配置驗證規則
CONFIG_VALIDATION_RULES = {
    "instruments.keithley_2461.connection.timeout": {
        "type": float,
        "min": 1.0,
        "max": 60.0
    },
    "instruments.keithley_2461.safety.max_voltage": {
        "type": float, 
        "min": 0.1,
        "max": 200.0
    },
    "instruments.rigol_dp711.connection.baudrate": {
        "type": int,
        "choices": [9600, 19200, 38400, 57600, 115200]
    },
    "gui.plotting.max_plot_points": {
        "type": int,
        "min": 100,
        "max": 10000
    },
    "data.buffer.real_time_buffer_size": {
        "type": int,
        "min": 50,
        "max": 5000
    }
}