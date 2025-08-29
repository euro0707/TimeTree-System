"""設定管理クラス"""

import os
import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv


class DailySummaryConfig(BaseModel):
    """毎朝通知設定"""
    enabled: bool = True
    time: str = "07:30"  # HH:MM format
    timezone: str = "Asia/Tokyo"
    include_description: bool = True
    include_location: bool = True
    max_events_display: int = 10
    notify_when_no_events: bool = True
    no_events_message: str = "今日は予定がありません\nゆっくりとした一日をお過ごしください！"
    
    @validator('time')
    def validate_time_format(cls, v):
        """時間フォーマットの検証"""
        try:
            parts = v.split(':')
            if len(parts) != 2:
                raise ValueError('時間は HH:MM 形式で入力してください')
            hour, minute = map(int, parts)
            if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                raise ValueError('有効な時間を入力してください (00:00-23:59)')
            return v
        except Exception as e:
            raise ValueError(f'無効な時間フォーマット: {v}. 例: "07:30"') from e


class TimeTreeConfig(BaseModel):
    """TimeTree設定"""
    email: str = Field(..., description="TimeTreeのメールアドレス")
    password: str = Field(..., description="TimeTreeのパスワード")
    calendar_code: str = Field(..., description="使用するTimeTreeカレンダーのコード")
    
    class ExporterConfig(BaseModel):
        timeout: int = 120
        retry_count: int = 3
        retry_delay: int = 30
    
    exporter: ExporterConfig = ExporterConfig()


class NotificationConfig(BaseModel):
    """LINE通知設定"""
    line_channel_access_token: str = Field(..., description="LINE Messaging API チャンネルアクセストークン")
    line_user_id: str = Field(..., description="送信先のLINE User ID")
    max_message_length: int = 1000
    greeting: str = "🌅 おはようございます！今日の予定"
    closing: str = "今日も良い一日を！✨"
    footer: str = "TimeTree自動通知"


class LoggingConfig(BaseModel):
    """ログ設定"""
    level: str = "INFO"
    file: str = "./logs/daily_notifier.log"
    max_size: str = "10MB"
    rotation: int = 7


class PathsConfig(BaseModel):
    """パス設定"""
    temp_ics: str = "./temp/timetree_export.ics"
    backup_data: str = "./data/backup.ics"
    logs: str = "./logs"


class Config(BaseModel):
    """メイン設定クラス"""
    daily_summary: DailySummaryConfig = DailySummaryConfig()
    timetree: TimeTreeConfig
    notification: NotificationConfig
    logging: LoggingConfig = LoggingConfig()
    paths: PathsConfig = PathsConfig()
    
    @classmethod
    def load_from_file(cls, config_path: str = "config.yaml") -> "Config":
        """設定ファイルから読み込み"""
        
        # 環境変数をロード
        load_dotenv()
        
        # config.yamlを読み込み
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {config_path}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        # 環境変数の置換
        config_data = cls._substitute_env_vars(config_data)
        
        return cls(**config_data)
    
    @staticmethod
    def _substitute_env_vars(data):
        """環境変数の置換処理"""
        if isinstance(data, dict):
            return {key: Config._substitute_env_vars(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [Config._substitute_env_vars(item) for item in data]
        elif isinstance(data, str) and data.startswith('${') and data.endswith('}'):
            env_var = data[2:-1]
            return os.getenv(env_var, data)
        else:
            return data
    
    def ensure_directories(self):
        """必要なディレクトリを作成"""
        dirs_to_create = [
            Path(self.paths.temp_ics).parent,
            Path(self.paths.backup_data).parent,
            Path(self.paths.logs)
        ]
        
        for dir_path in dirs_to_create:
            dir_path.mkdir(parents=True, exist_ok=True)