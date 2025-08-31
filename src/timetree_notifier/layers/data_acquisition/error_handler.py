"""
エラーハンドリング強化システム
設計書の「エラーハンドリング詳細」に基づく実装
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Type, Optional, Any
import hmac
import hashlib

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """エラータイプ分類"""
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    DATA_PARSING_ERROR = "data_parsing_error"
    TIMETREE_ACCESS_ERROR = "timetree_access_error"
    GOOGLE_CALENDAR_ERROR = "google_calendar_error"
    UNKNOWN_ERROR = "unknown_error"


class RecoveryResult(Enum):
    """復旧結果"""
    RETRY = "retry"
    FALLBACK = "fallback"
    ESCALATE = "escalate"
    SKIP = "skip"


@dataclass
class ErrorStrategy:
    """エラー対応戦略設定"""
    retry_attempts: int
    backoff_multiplier: float
    fallback: Optional[str] = None
    alert_threshold: int = 1
    escalation: Optional[str] = None
    wait_strategy: str = "exponential"


class ErrorHandler:
    """エラーハンドリング・自動復旧システム"""
    
    # エラータイプ別の対応戦略
    STRATEGIES: Dict[ErrorType, ErrorStrategy] = {
        ErrorType.NETWORK_ERROR: ErrorStrategy(
            retry_attempts=3,
            backoff_multiplier=2.0,
            fallback='use_cached_data',
            alert_threshold=3
        ),
        ErrorType.AUTHENTICATION_ERROR: ErrorStrategy(
            retry_attempts=1,
            backoff_multiplier=1.0,
            fallback='skip_source',
            alert_threshold=1,
            escalation='immediate'
        ),
        ErrorType.RATE_LIMIT_ERROR: ErrorStrategy(
            retry_attempts=5,
            backoff_multiplier=4.0,
            wait_strategy='exponential',
            alert_threshold=10
        ),
        ErrorType.DATA_PARSING_ERROR: ErrorStrategy(
            retry_attempts=2,
            backoff_multiplier=1.5,
            fallback='use_fallback_parser',
            alert_threshold=5
        ),
        ErrorType.TIMETREE_ACCESS_ERROR: ErrorStrategy(
            retry_attempts=3,
            backoff_multiplier=2.0,
            fallback='use_fallback_method',
            alert_threshold=2
        ),
        ErrorType.GOOGLE_CALENDAR_ERROR: ErrorStrategy(
            retry_attempts=3,
            backoff_multiplier=2.0,
            alert_threshold=3
        )
    }
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.error_counts: Dict[ErrorType, int] = {}
        self.recovery_manager = RecoveryManager(self.config)
    
    def classify_error(self, error: Exception) -> ErrorType:
        """エラーを分類してタイプを返す"""
        error_name = error.__class__.__name__
        error_message = str(error).lower()
        
        # ネットワーク関連エラー
        if any(keyword in error_message for keyword in ['connection', 'timeout', 'network']):
            return ErrorType.NETWORK_ERROR
        
        # 認証エラー  
        if any(keyword in error_message for keyword in ['unauthorized', '401', 'authentication', 'login']):
            return ErrorType.AUTHENTICATION_ERROR
        
        # レート制限エラー
        if any(keyword in error_message for keyword in ['rate limit', '429', 'too many requests']):
            return ErrorType.RATE_LIMIT_ERROR
        
        # データパースエラー
        if any(keyword in error_message for keyword in ['parse', 'json', 'xml', 'format']):
            return ErrorType.DATA_PARSING_ERROR
        
        # TimeTree特有のエラー
        if 'timetree' in error_message:
            return ErrorType.TIMETREE_ACCESS_ERROR
        
        # Google Calendar関連エラー
        if 'calendar' in error_message or 'google' in error_message:
            return ErrorType.GOOGLE_CALENDAR_ERROR
        
        return ErrorType.UNKNOWN_ERROR
    
    async def handle_error(self, error: Exception, context: dict = None) -> RecoveryResult:
        """エラーハンドリングとリカバリ実行"""
        error_type = self.classify_error(error)
        strategy = self.STRATEGIES.get(error_type, self.STRATEGIES[ErrorType.UNKNOWN_ERROR])
        
        # エラーカウント更新
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        logger.error(f"Error classified as {error_type.value}: {error}")
        logger.info(f"Error count for {error_type.value}: {self.error_counts[error_type]}")
        
        # アラート閾値チェック
        if self.error_counts[error_type] >= strategy.alert_threshold:
            await self._send_alert(error_type, error, self.error_counts[error_type])
        
        # 復旧処理を試行
        recovery_result = await self.recovery_manager.attempt_recovery(error, context or {})
        
        # エスカレーション判定
        if (strategy.escalation == 'immediate' or 
            recovery_result == RecoveryResult.ESCALATE):
            await self._escalate_error(error_type, error, context)
        
        return recovery_result
    
    async def _send_alert(self, error_type: ErrorType, error: Exception, count: int):
        """エラーアラート送信"""
        alert_message = f"""
⚠️ エラー多発警告

エラータイプ: {error_type.value}
発生回数: {count}
最新エラー: {error}
時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.warning(alert_message)
        # TODO: 実際のアラート送信実装 (Slack, Email等)
    
    async def _escalate_error(self, error_type: ErrorType, error: Exception, context: dict):
        """エラーエスカレーション"""
        escalation_message = f"""
🚨 緊急エラーエスカレーション

エラータイプ: {error_type.value}
エラー内容: {error}
コンテキスト: {context}
時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

即座に対応が必要です。
"""
        logger.critical(escalation_message)
        # TODO: 緊急通知実装 (電話, SMS等)


class RecoveryManager:
    """自動復旧機能"""
    
    def __init__(self, config: dict):
        self.config = config
    
    async def attempt_recovery(self, error: Exception, context: dict) -> RecoveryResult:
        """エラータイプに応じた自動復旧"""
        
        if isinstance(error, Exception):
            error_message = str(error).lower()
            
            # TimeTreeアクセスエラーの復旧
            if 'timetree' in error_message:
                return await self._recover_timetree_access(error, context)
            
            # Google Calendarエラーの復旧
            elif 'calendar' in error_message or 'google' in error_message:
                return await self._recover_google_calendar(error, context)
            
            # ネットワークエラーの復旧
            elif any(keyword in error_message for keyword in ['connection', 'timeout', 'network']):
                return await self._recover_network_error(error, context)
        
        return RecoveryResult.ESCALATE
    
    async def _recover_timetree_access(self, error: Exception, context: dict) -> RecoveryResult:
        """TimeTreeアクセスエラーの復旧処理"""
        try:
            # 1. 認証情報の更新を試行
            if await self._refresh_credentials():
                logger.info("TimeTree credentials refreshed, retrying...")
                return RecoveryResult.RETRY
            
            # 2. フォールバック方式に切り替え
            logger.info("Switching to fallback TimeTree access method")
            return RecoveryResult.FALLBACK
            
        except Exception as recovery_error:
            logger.error(f"Recovery attempt failed: {recovery_error}")
            return RecoveryResult.ESCALATE
    
    async def _recover_google_calendar(self, error: Exception, context: dict) -> RecoveryResult:
        """Google Calendarエラーの復旧処理"""
        error_message = str(error).lower()
        
        # Google API制限の場合は待機
        if 'rate limit' in error_message or '429' in error_message:
            # retry-afterヘッダーがあれば使用、なければデフォルト待機
            retry_after = getattr(error, 'retry_after', 60)
            logger.info(f"Rate limited, waiting {retry_after} seconds...")
            await asyncio.sleep(retry_after)
            return RecoveryResult.RETRY
        
        # 認証エラーの場合
        if 'unauthorized' in error_message or '401' in error_message:
            if await self._refresh_google_credentials():
                return RecoveryResult.RETRY
        
        return RecoveryResult.ESCALATE
    
    async def _recover_network_error(self, error: Exception, context: dict) -> RecoveryResult:
        """ネットワークエラーの復旧処理"""
        # 短時間待機してリトライ
        await asyncio.sleep(5)
        return RecoveryResult.RETRY
    
    async def _refresh_credentials(self) -> bool:
        """認証情報の更新"""
        try:
            # TODO: 実際の認証情報更新処理
            logger.info("Attempting to refresh TimeTree credentials...")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh credentials: {e}")
            return False
    
    async def _refresh_google_credentials(self) -> bool:
        """Google認証情報の更新"""
        try:
            # TODO: 実際のGoogle認証更新処理
            logger.info("Attempting to refresh Google credentials...")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh Google credentials: {e}")
            return False


# 使用例とテスト用コード
if __name__ == "__main__":
    async def test_error_handler():
        handler = ErrorHandler()
        
        # テスト用エラー
        test_errors = [
            ConnectionError("Network connection failed"),
            ValueError("Authentication failed"),
            Exception("Rate limit exceeded (429)"),
            ValueError("JSON parsing error")
        ]
        
        for error in test_errors:
            result = await handler.handle_error(error)
            print(f"Error: {error} -> Recovery: {result}")
    
    asyncio.run(test_error_handler())