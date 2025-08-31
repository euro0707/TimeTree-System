"""
強化ログシステム - 設計書の「監視・アラート設計」に基づく実装
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum
import structlog
from collections import defaultdict


class LogLevel(Enum):
    """ログレベル定義"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class AlertLevel(Enum):
    """アラートレベル階層化"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricsCollector:
    """システムメトリクス収集"""
    
    def __init__(self):
        self.counters = defaultdict(int)
        self.gauges = {}
        self.histograms = defaultdict(list)
        self.start_time = datetime.now()
    
    def record_success(self, operation: str, duration: float):
        """成功メトリクス記録"""
        self.counters[f"{operation}_success"] += 1
        self.histograms[f"{operation}_duration"].append(duration)
    
    def record_error(self, operation: str, error_type: str):
        """エラーメトリクス記録"""
        self.counters[f"{operation}_error_{error_type}"] += 1
    
    def record_event(self, event_name: str, count: int = 1):
        """イベント記録"""
        self.counters[event_name] += count
    
    def set_gauge(self, name: str, value: float):
        """ゲージメトリクス設定"""
        self.gauges[name] = value
    
    def get_health_summary(self) -> dict:
        """システム健全性サマリー"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # 成功率計算
        total_operations = 0
        total_successes = 0
        
        for key, count in self.counters.items():
            if key.endswith('_success'):
                total_successes += count
                operation = key.replace('_success', '')
                # 対応するエラーカウントも含める
                for error_key in self.counters:
                    if error_key.startswith(f"{operation}_error"):
                        total_operations += self.counters[error_key]
        
        total_operations += total_successes
        success_rate = (total_successes / total_operations * 100) if total_operations > 0 else 100.0
        
        # 平均応答時間計算
        avg_response_times = {}
        for key, durations in self.histograms.items():
            if durations:
                avg_response_times[key] = sum(durations) / len(durations)
        
        return {
            'uptime_seconds': uptime,
            'success_rate_percent': success_rate,
            'total_operations': total_operations,
            'avg_response_times': avg_response_times,
            'error_rates_by_type': self._get_error_rates(),
            'last_health_check': datetime.now().isoformat(),
            'gauges': self.gauges.copy()
        }
    
    def _get_error_rates(self) -> Dict[str, float]:
        """エラー率をタイプ別に取得"""
        error_rates = {}
        total_ops_by_type = defaultdict(int)
        
        # 各操作の総数を計算
        for key, count in self.counters.items():
            if '_success' in key or '_error' in key:
                operation = key.split('_')[0]
                total_ops_by_type[operation] += count
        
        # エラー率を計算
        for key, count in self.counters.items():
            if '_error' in key:
                parts = key.split('_')
                operation = parts[0]
                error_type = '_'.join(parts[2:])  # operation_error_type
                
                if total_ops_by_type[operation] > 0:
                    error_rate = (count / total_ops_by_type[operation]) * 100
                    error_rates[f"{operation}_{error_type}"] = error_rate
        
        return error_rates


class EnhancedLogger:
    """強化ログシステム"""
    
    def __init__(self, 
                 name: str = "timetree_notifier",
                 log_level: LogLevel = LogLevel.INFO,
                 log_file: Optional[Path] = None,
                 metrics_enabled: bool = True):
        
        self.name = name
        self.log_level = log_level
        self.log_file = log_file
        self.metrics_enabled = metrics_enabled
        
        # メトリクス収集器
        self.metrics = MetricsCollector() if metrics_enabled else None
        
        # 構造化ログ設定
        self._setup_structured_logging()
        
        # 標準ログ設定
        self._setup_standard_logging()
        
        # アラート設定
        self.alert_config = self._load_alert_config()
    
    def _setup_structured_logging(self):
        """構造化ログの設定"""
        # タイムスタンプとレベルを追加するプロセッサー
        def add_timestamp(logger, method_name, event_dict):
            event_dict['timestamp'] = datetime.now().isoformat()
            event_dict['level'] = method_name.upper()
            event_dict['logger'] = logger.name
            return event_dict
        
        # JSON形式でフォーマット
        def json_formatter(logger, method_name, event_dict):
            return json.dumps(event_dict, ensure_ascii=False, default=str)
        
        # structlog設定
        structlog.configure(
            processors=[
                add_timestamp,
                structlog.processors.add_log_level,
                json_formatter,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, self.log_level.value)
            ),
            logger_factory=structlog.WriteLoggerFactory(),
            cache_logger_on_first_use=True,
        )
        
        self.structured_logger = structlog.get_logger(self.name)
    
    def _setup_standard_logging(self):
        """標準ログの設定"""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(getattr(logging, self.log_level.value))
        
        # フォーマッター
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # コンソールハンドラー
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # ファイルハンドラー（指定された場合）
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
    
    def _load_alert_config(self) -> Dict[AlertLevel, dict]:
        """アラート設定の読み込み"""
        return {
            AlertLevel.INFO: {
                "channels": ["log"],
                "conditions": [
                    "new_events_detected > 0",
                    "successful_sync_completed"
                ]
            },
            AlertLevel.WARNING: {
                "channels": ["log", "slack"],
                "conditions": [
                    "error_rate > 5%",
                    "response_time > 30s",
                    "fallback_method_used"
                ]
            },
            AlertLevel.CRITICAL: {
                "channels": ["log", "slack", "email", "sms"],
                "conditions": [
                    "error_rate > 50%",
                    "all_notification_channels_failed",
                    "data_corruption_detected"
                ]
            },
            AlertLevel.EMERGENCY: {
                "channels": ["log", "slack", "email", "sms", "phone_call"],
                "conditions": [
                    "system_completely_down > 1h",
                    "security_breach_detected"
                ]
            }
        }
    
    def info(self, message: str, **kwargs):
        """情報ログ"""
        self._log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """警告ログ"""
        self._log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """エラーログ"""
        if error:
            kwargs['error_type'] = error.__class__.__name__
            kwargs['error_message'] = str(error)
        self._log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """クリティカルログ"""
        self._log(LogLevel.CRITICAL, message, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """デバッグログ"""
        self._log(LogLevel.DEBUG, message, **kwargs)
    
    def _log(self, level: LogLevel, message: str, **kwargs):
        """内部ログ処理"""
        # メトリクス記録
        if self.metrics:
            if level in [LogLevel.ERROR, LogLevel.CRITICAL]:
                operation = kwargs.get('operation', 'unknown')
                error_type = kwargs.get('error_type', 'unknown')
                self.metrics.record_error(operation, error_type)
            
            # 成功メトリクスの記録（特定のキーワードがある場合）
            if 'success' in message.lower() or 'completed' in message.lower():
                operation = kwargs.get('operation', 'general')
                duration = kwargs.get('duration', 0.0)
                self.metrics.record_success(operation, duration)
        
        # 構造化ログ
        self.structured_logger.info(message, **kwargs)
        
        # 標準ログ
        log_method = getattr(self.logger, level.value.lower())
        if kwargs:
            message_with_context = f"{message} | Context: {json.dumps(kwargs, default=str)}"
        else:
            message_with_context = message
        log_method(message_with_context)
        
        # アラート判定
        self._check_alert_conditions(level, message, kwargs)
    
    def _check_alert_conditions(self, level: LogLevel, message: str, context: dict):
        """アラート条件のチェック"""
        # エラー率チェック
        if self.metrics and level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            health_summary = self.metrics.get_health_summary()
            success_rate = health_summary.get('success_rate_percent', 100.0)
            
            if success_rate < 50.0:
                self._trigger_alert(AlertLevel.CRITICAL, 
                                  f"Success rate dropped to {success_rate:.1f}%", 
                                  health_summary)
            elif success_rate < 95.0:
                self._trigger_alert(AlertLevel.WARNING, 
                                  f"Success rate at {success_rate:.1f}%", 
                                  health_summary)
        
        # 緊急キーワードチェック
        emergency_keywords = ['security breach', 'system down', 'complete failure']
        if any(keyword in message.lower() for keyword in emergency_keywords):
            self._trigger_alert(AlertLevel.EMERGENCY, message, context)
    
    def _trigger_alert(self, alert_level: AlertLevel, message: str, context: dict):
        """アラートトリガー"""
        alert_info = {
            'alert_level': alert_level.value,
            'message': message,
            'context': context,
            'timestamp': datetime.now().isoformat(),
            'system': self.name
        }
        
        # アラート設定に基づく通知チャンネル
        channels = self.alert_config[alert_level]['channels']
        
        self.critical(f"🚨 ALERT [{alert_level.value.upper()}]: {message}", 
                     alert_info=alert_info, alert_channels=channels)
        
        # TODO: 実際の通知送信実装
        # - Slack通知
        # - Email送信
        # - SMS送信
        # - 電話通知（緊急時）
    
    def log_operation_start(self, operation: str, **context) -> dict:
        """操作開始ログ"""
        start_time = datetime.now()
        operation_context = {
            'operation': operation,
            'start_time': start_time.isoformat(),
            'status': 'started',
            **context
        }
        
        self.info(f"Operation started: {operation}", **operation_context)
        return {'start_time': start_time, 'operation': operation, **context}
    
    def log_operation_end(self, operation_context: dict, success: bool = True, **additional_context):
        """操作終了ログ"""
        end_time = datetime.now()
        start_time = operation_context.get('start_time')
        operation = operation_context.get('operation')
        
        if start_time:
            duration = (end_time - start_time).total_seconds()
        else:
            duration = 0.0
        
        result_context = {
            **operation_context,
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'status': 'success' if success else 'failed',
            **additional_context
        }
        
        if success:
            self.info(f"Operation completed: {operation} ({duration:.2f}s)", 
                     **result_context)
        else:
            self.error(f"Operation failed: {operation} ({duration:.2f}s)", 
                      **result_context)
    
    def get_health_status(self) -> dict:
        """システム健全性ステータス取得"""
        if not self.metrics:
            return {"status": "metrics_disabled"}
        
        health_summary = self.metrics.get_health_summary()
        
        # 健全性判定
        success_rate = health_summary.get('success_rate_percent', 100.0)
        if success_rate >= 98.0:
            status = "healthy"
        elif success_rate >= 90.0:
            status = "warning"
        elif success_rate >= 70.0:
            status = "degraded"
        else:
            status = "critical"
        
        return {
            "overall_status": status,
            "timestamp": datetime.now().isoformat(),
            **health_summary
        }


# グローバルインスタンス
_global_logger: Optional[EnhancedLogger] = None


def get_logger(name: str = "timetree_notifier", 
               log_level: LogLevel = LogLevel.INFO,
               log_file: Optional[Path] = None) -> EnhancedLogger:
    """グローバルロガー取得"""
    global _global_logger
    
    if _global_logger is None:
        _global_logger = EnhancedLogger(name, log_level, log_file)
    
    return _global_logger


def setup_logging(config: dict = None):
    """ログ設定の初期化"""
    config = config or {}
    
    log_level = LogLevel(config.get('level', 'INFO'))
    log_file_path = config.get('file_path')
    log_file = Path(log_file_path) if log_file_path else None
    
    global _global_logger
    _global_logger = EnhancedLogger(
        name=config.get('name', 'timetree_notifier'),
        log_level=log_level,
        log_file=log_file,
        metrics_enabled=config.get('metrics_enabled', True)
    )
    
    return _global_logger


# 使用例
if __name__ == "__main__":
    # テスト用の設定
    logger = get_logger("test_logger", LogLevel.DEBUG, Path("logs/test.log"))
    
    # 操作ログのテスト
    op_context = logger.log_operation_start("data_sync", source="timetree", target="calendar")
    
    # 一般ログ
    logger.info("Starting data synchronization", operation="data_sync", records=100)
    logger.warning("Rate limit approaching", current_rate=80, max_rate=100)
    
    # エラーログ
    try:
        raise ConnectionError("Network timeout")
    except Exception as e:
        logger.error("Connection failed", error=e, operation="network_request")
    
    # 操作終了ログ
    logger.log_operation_end(op_context, success=True, records_processed=100)
    
    # 健全性チェック
    health = logger.get_health_status()
    print("Health Status:", json.dumps(health, indent=2, ensure_ascii=False))