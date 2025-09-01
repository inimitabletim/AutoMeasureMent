"""
統一配置管理系統
集中管理所有應用程式設定
"""

from .config_manager import ConfigManager, get_config
from .default_settings import DEFAULT_CONFIG

__all__ = ['ConfigManager', 'get_config', 'DEFAULT_CONFIG']