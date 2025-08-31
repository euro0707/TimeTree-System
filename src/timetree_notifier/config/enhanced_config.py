"""
強化設定管理システム - 設計書の「設定・運用」に基づく実装
階層化設定ファイルとセキュアな秘密情報管理
"""

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from cryptography.fernet import Fernet
import base64
import json
from ..utils.enhanced_logger import get_logger

logger = get_logger(__name__)


@dataclass
class DataAcquisitionConfig:
    """データ取得設定"""
    primary_method: str = "timetree_exporter"
    fallback_methods: List[str] = field(default_factory=lambda: ["direct_scraping", "cached_data"])
    retry_policy: Dict[str, Union[int, float]] = field(default_factory=lambda: {
        "max_attempts": 3,
        "backoff_multiplier": 2.0,
        "timeout_seconds": 300
    })
    cache: Dict[str, int] = field(default_factory=lambda: {
        "max_age_hours": 48,
        "cleanup_interval_hours": 24
    })


@dataclass
class DataProcessingConfig:
    """データ処理設定"""
    timezone: str = "Asia/Tokyo"
    encoding: Dict[str, bool] = field(default_factory=lambda: {
        "fix_garbled_text": True,
        "auto_detect_encoding": True
    })
    scheduler: Dict[str, Union[str, List[int]]] = field(default_factory=lambda: {
        "daily_notification_time": "06:00",
        "reminder_intervals": [15, 60]  # 15分前、1時間前
    })


@dataclass
class SyncLayerConfig:
    """同期層設定"""
    google_calendar: Dict[str, Union[str, bool, Dict]] = field(default_factory=lambda: {
        "enabled": True,
        "calendar_id": "primary",
        "sync_strategy": "one_way",  # one_way, two_way
        "conflict_resolution": {
            "strategy": "timetree_wins",
            "merge_policy": {
                "title": "timetree_priority",
                "description": "longer_text"
            }
        }
    })
    local_storage: Dict[str, Union[str, Dict]] = field(default_factory=lambda: {
        "database_url": "sqlite:///./data/events.db",
        "backup_settings": {
            "retention_days": 30,
            "compression": True
        }
    })


@dataclass
class NotificationChannelConfig:
    """通知チャンネル設定"""
    enabled: bool = True
    flex_message_enabled: bool = False
    voice_settings: Optional[Dict[str, str]] = None
    retry_policy: Dict[str, Union[int, float]] = field(default_factory=lambda: {
        "max_attempts": 3,
        "backoff_base": 2.0
    })


@dataclass
class NotificationLayerConfig:
    """通知層設定"""
    channels: Dict[str, NotificationChannelConfig] = field(default_factory=lambda: {
        "line": NotificationChannelConfig(
            enabled=True,
            flex_message_enabled=True
        ),
        "gas": NotificationChannelConfig(
            enabled=True,
            voice_settings={
                "voice_type": "standard",
                "speed": "1.0", 
                "language": "ja-JP"
            }
        )
    })
    delivery: Dict[str, Union[Dict, str]] = field(default_factory=lambda: {
        "retry_policy": {
            "max_attempts": 3,
            "backoff_base": 2.0
        },
        "rate_limits": {
            "line": "30/minute",
            "gas": "10/minute"
        }
    })


@dataclass
class SecurityConfig:
    """セキュリティ設定"""
    encryption_enabled: bool = True
    audit_logging: bool = True
    webhook_verification: bool = True
    token_rotation_days: int = 30


@dataclass
class AlertConfig:
    """アラート設定"""
    levels: Dict[str, Dict] = field(default_factory=lambda: {
        "info": {
            "channels": ["log"],
            "conditions": [
                "new_events_detected > 0",
                "successful_sync_completed"
            ]
        },
        "warning": {
            "channels": ["log", "slack"],
            "conditions": [
                "error_rate > 5%",
                "response_time > 30s",
                "fallback_method_used"
            ]
        },
        "critical": {
            "channels": ["log", "slack", "email", "sms"],
            "conditions": [
                "error_rate > 50%",
                "all_notification_channels_failed", 
                "data_corruption_detected"
            ]
        },
        "emergency": {
            "channels": ["log", "slack", "email", "sms", "phone_call"],
            "conditions": [
                "system_completely_down > 1h",
                "security_breach_detected"
            ]
        }
    })


@dataclass
class EnhancedConfig:
    """強化設定メインクラス"""
    # レイヤー別設定
    data_acquisition: DataAcquisitionConfig = field(default_factory=DataAcquisitionConfig)
    data_processing: DataProcessingConfig = field(default_factory=DataProcessingConfig)
    sync_layer: SyncLayerConfig = field(default_factory=SyncLayerConfig)
    notification_layer: NotificationLayerConfig = field(default_factory=NotificationLayerConfig)
    
    # システム設定
    security: SecurityConfig = field(default_factory=SecurityConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    
    # 一般設定
    debug: bool = False
    version: str = "3.0.0"
    environment: str = "development"  # development, staging, production


class SecurityManager:
    """セキュリティ管理クラス"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.encryption_key = encryption_key or self._get_or_create_key()
        self.cipher = Fernet(self.encryption_key.encode()) if self.encryption_key else None
    
    def _get_or_create_key(self) -> str:
        """暗号化キーの取得または生成"""
        # 環境変数から取得
        key = os.getenv('TIMETREE_ENCRYPTION_KEY')
        
        if not key:
            # 新しいキーを生成
            key = Fernet.generate_key().decode()
            logger.warning(
                "New encryption key generated. Store it securely!",
                key_preview=key[:8] + "...",
                operation="key_generation"
            )
        
        return key
    
    def encrypt_value(self, value: str) -> str:
        """値の暗号化"""
        if not self.cipher:
            return value
        
        try:
            encrypted = self.cipher.encrypt(value.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error("Encryption failed", error=e)
            return value
    
    def decrypt_value(self, encrypted_value: str) -> str:
        """値の復号化"""
        if not self.cipher:
            return encrypted_value
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_value.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error("Decryption failed", error=e)
            return encrypted_value


class ConfigManager:
    """設定管理メインクラス"""
    
    def __init__(self, 
                 config_dir: Union[str, Path] = "config",
                 secrets_dir: Union[str, Path] = "config/secrets"):
        
        self.config_dir = Path(config_dir)
        self.secrets_dir = Path(secrets_dir)
        self.security_manager = SecurityManager()
        
        # 設定ディレクトリの作成
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        
        # キャッシュされた設定
        self._config_cache: Optional[EnhancedConfig] = None
        self._secrets_cache: Dict[str, Any] = {}
    
    def load_config(self, reload: bool = False) -> EnhancedConfig:
        """設定の読み込み"""
        if self._config_cache and not reload:
            return self._config_cache
        
        try:
            # メイン設定ファイルの読み込み
            main_config = self._load_yaml_file(self.config_dir / "main.yaml")
            
            # レイヤー別設定ファイルの読み込み
            layer_configs = {
                'data_acquisition': self._load_yaml_file(self.config_dir / "data_acquisition.yaml"),
                'data_processing': self._load_yaml_file(self.config_dir / "data_processing.yaml"),
                'sync_layer': self._load_yaml_file(self.config_dir / "sync_layer.yaml"),
                'notification_layer': self._load_yaml_file(self.config_dir / "notification_layer.yaml")
            }
            
            # 設定の統合
            merged_config = self._merge_configs(main_config, layer_configs)
            
            # 環境変数によるオーバーライド
            merged_config = self._apply_env_overrides(merged_config)
            
            # 設定オブジェクトの作成
            self._config_cache = self._create_config_object(merged_config)
            
            logger.info(
                "Configuration loaded successfully",
                config_files=len(layer_configs) + 1,
                environment=self._config_cache.environment,
                version=self._config_cache.version,
                operation="config_load"
            )
            
            return self._config_cache
        
        except Exception as e:
            logger.error("Failed to load configuration", error=e)
            # フォールバック：デフォルト設定を使用
            self._config_cache = EnhancedConfig()
            return self._config_cache
    
    def load_secrets(self, reload: bool = False) -> Dict[str, Any]:
        """秘密情報の読み込み"""
        if self._secrets_cache and not reload:
            return self._secrets_cache
        
        try:
            # 環境変数から読み込み
            env_secrets = self._load_env_secrets()
            
            # .envファイルから読み込み
            env_file_secrets = self._load_env_file()
            
            # JSONファイルから読み込み
            json_secrets = self._load_json_secrets()
            
            # 統合（優先順位: 環境変数 > .env > JSON）
            self._secrets_cache = {
                **json_secrets,
                **env_file_secrets,
                **env_secrets
            }
            
            # 暗号化された値の復号化
            self._decrypt_secrets()
            
            logger.info(
                "Secrets loaded successfully",
                secret_count=len(self._secrets_cache),
                sources=["env", "env_file", "json"],
                operation="secrets_load"
            )
            
            return self._secrets_cache
        
        except Exception as e:
            logger.error("Failed to load secrets", error=e)
            return {}
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """YAMLファイルの読み込み"""
        if not file_path.exists():
            logger.debug(f"Config file not found: {file_path}")
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load YAML file: {file_path}", error=e)
            return {}
    
    def _load_env_secrets(self) -> Dict[str, str]:
        """環境変数からの秘密情報読み込み"""
        secret_keys = [
            'TIMETREE_EMAIL',
            'TIMETREE_PASSWORD', 
            'TIMETREE_CALENDAR_CODE',
            'LINE_CHANNEL_ACCESS_TOKEN',
            'LINE_USER_ID',
            'GOOGLE_CALENDAR_CREDS',
            'SLACK_WEBHOOK_URL',
            'DISCORD_WEBHOOK_URL',
            'ENCRYPTION_KEY'
        ]
        
        return {key: os.getenv(key) for key in secret_keys if os.getenv(key)}
    
    def _load_env_file(self) -> Dict[str, str]:
        """.envファイルからの読み込み"""
        env_file = self.secrets_dir / ".env"
        if not env_file.exists():
            return {}
        
        secrets = {}
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        secrets[key.strip()] = value.strip().strip('"\'')
        except Exception as e:
            logger.error(f"Failed to load .env file", error=e)
        
        return secrets
    
    def _load_json_secrets(self) -> Dict[str, Any]:
        """JSONファイルからの読み込み"""
        json_files = [
            "google_creds.json",
            "line_config.json", 
            "slack_config.json"
        ]
        
        secrets = {}
        for json_file in json_files:
            file_path = self.secrets_dir / json_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_secrets = json.load(f)
                        secrets.update(file_secrets)
                except Exception as e:
                    logger.error(f"Failed to load JSON file: {json_file}", error=e)
        
        return secrets
    
    def _decrypt_secrets(self):
        """暗号化された秘密情報の復号化"""
        encrypted_prefix = "encrypted:"
        
        for key, value in self._secrets_cache.items():
            if isinstance(value, str) and value.startswith(encrypted_prefix):
                encrypted_value = value[len(encrypted_prefix):]
                decrypted_value = self.security_manager.decrypt_value(encrypted_value)
                self._secrets_cache[key] = decrypted_value
    
    def _merge_configs(self, main_config: Dict, layer_configs: Dict) -> Dict:
        """設定の統合"""
        merged = main_config.copy()
        
        for layer_name, layer_config in layer_configs.items():
            if layer_config:
                merged[layer_name] = layer_config
        
        return merged
    
    def _apply_env_overrides(self, config: Dict) -> Dict:
        """環境変数によるオーバーライド"""
        env_overrides = {
            'TIMETREE_DEBUG': ('debug', lambda x: x.lower() in ['true', '1', 'yes']),
            'TIMETREE_ENVIRONMENT': ('environment', str),
            'TIMETREE_LOG_LEVEL': ('logging.level', str),
        }
        
        for env_key, (config_path, converter) in env_overrides.items():
            env_value = os.getenv(env_key)
            if env_value:
                try:
                    converted_value = converter(env_value)
                    self._set_nested_value(config, config_path, converted_value)
                except Exception as e:
                    logger.warning(f"Failed to apply env override {env_key}", error=e)
        
        return config
    
    def _set_nested_value(self, config: Dict, path: str, value: Any):
        """ネストされた設定値の設定"""
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _create_config_object(self, config_dict: Dict) -> EnhancedConfig:
        """設定辞書から設定オブジェクトを作成"""
        try:
            # DataClassの作成は複雑なので、まずは辞書として返す
            # TODO: より洗練された方法で DataClass に変換
            return EnhancedConfig(**config_dict)
        except Exception as e:
            logger.warning("Failed to create config object, using defaults", error=e)
            return EnhancedConfig()
    
    def save_config_template(self):
        """設定ファイルテンプレートの作成"""
        templates = {
            "main.yaml": {
                "version": "3.0.0",
                "environment": "development",
                "debug": False,
                "logging": {
                    "level": "INFO",
                    "file_path": "logs/timetree_notifier.log"
                }
            },
            "data_acquisition.yaml": {
                "primary_method": "timetree_exporter",
                "fallback_methods": ["direct_scraping", "cached_data"],
                "retry_policy": {
                    "max_attempts": 3,
                    "backoff_multiplier": 2.0,
                    "timeout_seconds": 300
                }
            },
            "notification_layer.yaml": {
                "channels": {
                    "line": {
                        "enabled": True,
                        "flex_message_enabled": True
                    },
                    "gas": {
                        "enabled": True,
                        "voice_settings": {
                            "voice_type": "standard",
                            "speed": "1.0",
                            "language": "ja-JP"
                        }
                    }
                }
            }
        }
        
        for filename, template in templates.items():
            file_path = self.config_dir / filename
            if not file_path.exists():
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        yaml.dump(template, f, default_flow_style=False, allow_unicode=True)
                    logger.info(f"Created config template: {filename}")
                except Exception as e:
                    logger.error(f"Failed to create template: {filename}", error=e)


# グローバルインスタンス
_global_config_manager: Optional[ConfigManager] = None


def get_config_manager(config_dir: Union[str, Path] = "config") -> ConfigManager:
    """グローバル設定マネージャーの取得"""
    global _global_config_manager
    
    if _global_config_manager is None:
        _global_config_manager = ConfigManager(config_dir)
    
    return _global_config_manager


def get_config(reload: bool = False) -> EnhancedConfig:
    """設定の取得"""
    return get_config_manager().load_config(reload)


def get_secrets(reload: bool = False) -> Dict[str, Any]:
    """秘密情報の取得"""
    return get_config_manager().load_secrets(reload)


# 使用例
if __name__ == "__main__":
    # 設定マネージャーのテスト
    config_manager = ConfigManager("test_config")
    
    # テンプレート作成
    config_manager.save_config_template()
    
    # 設定読み込み
    config = config_manager.load_config()
    secrets = config_manager.load_secrets()
    
    print("=== Configuration Test ===")
    print(f"Version: {config.version}")
    print(f"Environment: {config.environment}")
    print(f"Debug: {config.debug}")
    print(f"Secrets loaded: {len(secrets)} items")
    
    # セキュリティテスト
    security = SecurityManager()
    test_value = "sensitive_password_123"
    encrypted = security.encrypt_value(test_value)
    decrypted = security.decrypt_value(encrypted)
    
    print(f"\n=== Security Test ===")
    print(f"Original:  {test_value}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match:     {test_value == decrypted}")