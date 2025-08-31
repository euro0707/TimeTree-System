"""
マルチチャンネル配信システム - 設計書の「Multi-Channel Dispatcher」に基づく実装
複数通知チャンネルへの非同期並行配信・優先度・リトライ・レート制限管理
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class NotificationPriority(Enum):
    """通知優先度"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class NotificationStatus(Enum):
    """通知配信ステータス"""
    PENDING = "pending"
    SENDING = "sending"
    SUCCESS = "success"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    RETRY = "retry"


@dataclass
class NotificationMessage:
    """通知メッセージ"""
    id: str
    content: str
    title: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[str] = field(default_factory=list)
    scheduled_time: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def should_retry(self) -> bool:
        return self.retry_count < self.max_retries


@dataclass
class ChannelDeliveryResult:
    """チャンネル配信結果"""
    channel: str
    message_id: str
    status: NotificationStatus
    attempt_time: datetime
    processing_time: float
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    def is_successful(self) -> bool:
        return self.status == NotificationStatus.SUCCESS


@dataclass
class NotificationResult:
    """通知配信結果サマリー"""
    message_id: str
    total_channels: int
    successful_channels: int
    failed_channels: int
    rate_limited_channels: int
    total_processing_time: float
    channel_results: List[ChannelDeliveryResult]
    
    def success_rate(self) -> float:
        return (self.successful_channels / self.total_channels * 100) if self.total_channels > 0 else 0.0
    
    def summary(self) -> str:
        return f"Delivery: {self.successful_channels}/{self.total_channels} channels ({self.success_rate():.1f}%)"


class RateLimiter:
    """レート制限管理"""
    
    def __init__(self, max_requests: int, time_window: int):
        self.max_requests = max_requests
        self.time_window = time_window  # seconds
        self.requests = []
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """レート制限チェック・許可取得"""
        async with self._lock:
            now = time.time()
            
            # 古いリクエスト記録を削除
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            # レート制限チェック
            if len(self.requests) >= self.max_requests:
                return False
            
            # リクエスト記録
            self.requests.append(now)
            return True
    
    async def wait_for_availability(self) -> float:
        """次に利用可能になるまでの待機時間を取得"""
        if not self.requests:
            return 0.0
        
        oldest_request = min(self.requests)
        wait_time = self.time_window - (time.time() - oldest_request)
        return max(0.0, wait_time)


class NotificationChannel(ABC):
    """通知チャンネル抽象基底クラス"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.rate_limiter = self._create_rate_limiter()
        
        # 統計情報
        self.total_sent = 0
        self.total_success = 0
        self.total_failed = 0
        self.total_rate_limited = 0
    
    def _create_rate_limiter(self) -> Optional[RateLimiter]:
        """レート制限器の作成"""
        rate_limit = self.config.get('rate_limit')
        if not rate_limit:
            return None
        
        # "30/minute", "100/hour" 形式のパース
        try:
            count, period = rate_limit.split('/')
            count = int(count)
            
            if period == 'second':
                time_window = 1
            elif period == 'minute':
                time_window = 60
            elif period == 'hour':
                time_window = 3600
            else:
                time_window = 60  # デフォルト
            
            return RateLimiter(count, time_window)
        except:
            logger.warning(f"Invalid rate limit format: {rate_limit}")
            return None
    
    @abstractmethod
    async def send_message(self, message: NotificationMessage) -> ChannelDeliveryResult:
        """メッセージ送信（サブクラスで実装）"""
        pass
    
    async def send_with_rate_limit(self, message: NotificationMessage) -> ChannelDeliveryResult:
        """レート制限を考慮した送信"""
        start_time = time.time()
        
        # レート制限チェック
        if self.rate_limiter:
            if not await self.rate_limiter.acquire():
                # レート制限に引っかかった場合
                self.total_rate_limited += 1
                
                return ChannelDeliveryResult(
                    channel=self.name,
                    message_id=message.id,
                    status=NotificationStatus.RATE_LIMITED,
                    attempt_time=datetime.now(),
                    processing_time=time.time() - start_time,
                    error_message="Rate limit exceeded"
                )
        
        # 実際の送信処理
        try:
            result = await self.send_message(message)
            
            # 統計更新
            self.total_sent += 1
            if result.is_successful():
                self.total_success += 1
            else:
                self.total_failed += 1
            
            return result
            
        except Exception as e:
            self.total_sent += 1
            self.total_failed += 1
            
            return ChannelDeliveryResult(
                channel=self.name,
                message_id=message.id,
                status=NotificationStatus.FAILED,
                attempt_time=datetime.now(),
                processing_time=time.time() - start_time,
                error_message=str(e)
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """チャンネル統計情報"""
        total = self.total_sent
        return {
            "channel": self.name,
            "total_sent": total,
            "successful": self.total_success,
            "failed": self.total_failed,
            "rate_limited": self.total_rate_limited,
            "success_rate": (self.total_success / total * 100) if total > 0 else 0.0
        }


class MockNotificationChannel(NotificationChannel):
    """テスト用モック通知チャンネル"""
    
    async def send_message(self, message: NotificationMessage) -> ChannelDeliveryResult:
        """模擬送信（テスト用）"""
        start_time = time.time()
        
        # 模擬処理時間
        await asyncio.sleep(0.1)
        
        # 成功/失敗をランダムに決定（テスト用）
        import random
        success = random.random() > 0.1  # 90%成功率
        
        return ChannelDeliveryResult(
            channel=self.name,
            message_id=message.id,
            status=NotificationStatus.SUCCESS if success else NotificationStatus.FAILED,
            attempt_time=datetime.now(),
            processing_time=time.time() - start_time,
            response_data={"mock": True, "sent": success},
            error_message=None if success else "Mock failure"
        )


class NotificationDispatcher:
    """マルチチャンネル通知配信システム"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.channels: Dict[str, NotificationChannel] = {}
        self.retry_policy = config.get('retry_policy', {})
        self.max_concurrent = config.get('max_concurrent_deliveries', 10)
        
        # メッセージキュー
        self.pending_queue: asyncio.Queue = asyncio.Queue()
        self.retry_queue: asyncio.Queue = asyncio.Queue()
        
        # バックグラウンドタスク管理
        self.background_tasks: Set[asyncio.Task] = set()
        self.is_running = False
        
        # 統計情報
        self.total_messages = 0
        self.total_deliveries = 0
        self.successful_deliveries = 0
        self.failed_deliveries = 0
    
    def register_channel(self, channel: NotificationChannel):
        """通知チャンネルの登録"""
        self.channels[channel.name] = channel
        logger.info(f"Registered notification channel: {channel.name}")
    
    async def dispatch_notification(self, message: NotificationMessage) -> NotificationResult:
        """通知配信（単発）"""
        start_time = time.time()
        
        # 対象チャンネルの決定
        target_channels = self._determine_target_channels(message)
        
        if not target_channels:
            logger.warning(f"No valid channels for message {message.id}")
            return NotificationResult(
                message_id=message.id,
                total_channels=0,
                successful_channels=0,
                failed_channels=0,
                rate_limited_channels=0,
                total_processing_time=time.time() - start_time,
                channel_results=[]
            )
        
        logger.info(f"Dispatching message {message.id} to {len(target_channels)} channels")
        
        # 並行配信実行
        channel_results = await self._dispatch_to_channels(message, target_channels)
        
        # 結果集計
        successful = sum(1 for r in channel_results if r.is_successful())
        failed = sum(1 for r in channel_results if r.status == NotificationStatus.FAILED)
        rate_limited = sum(1 for r in channel_results if r.status == NotificationStatus.RATE_LIMITED)
        
        # 統計更新
        self.total_messages += 1
        self.total_deliveries += len(channel_results)
        self.successful_deliveries += successful
        self.failed_deliveries += failed
        
        result = NotificationResult(
            message_id=message.id,
            total_channels=len(target_channels),
            successful_channels=successful,
            failed_channels=failed,
            rate_limited_channels=rate_limited,
            total_processing_time=time.time() - start_time,
            channel_results=channel_results
        )
        
        logger.info(f"Dispatch completed: {result.summary()}")
        
        # 失敗したメッセージのリトライ処理
        await self._handle_failed_deliveries(message, channel_results)
        
        return result
    
    def _determine_target_channels(self, message: NotificationMessage) -> List[str]:
        """配信対象チャンネルの決定"""
        if message.channels:
            # メッセージで指定されたチャンネル
            valid_channels = [ch for ch in message.channels if ch in self.channels]
        else:
            # 全チャンネル
            valid_channels = list(self.channels.keys())
        
        # 優先度による絞り込み
        if message.priority == NotificationPriority.URGENT:
            # 緊急時は全チャンネル
            pass
        elif message.priority == NotificationPriority.LOW:
            # 低優先度は主要チャンネルのみ
            primary_channels = self.config.get('primary_channels', ['line'])
            valid_channels = [ch for ch in valid_channels if ch in primary_channels]
        
        return valid_channels
    
    async def _dispatch_to_channels(self, message: NotificationMessage, 
                                  target_channels: List[str]) -> List[ChannelDeliveryResult]:
        """チャンネルへの並行配信"""
        
        # セマフォで同時実行数を制限
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def send_to_channel(channel_name: str) -> ChannelDeliveryResult:
            async with semaphore:
                channel = self.channels[channel_name]
                return await channel.send_with_rate_limit(message)
        
        # 全チャンネルに並行送信
        tasks = [send_to_channel(ch) for ch in target_channels]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 例外処理
        channel_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                channel_results.append(ChannelDeliveryResult(
                    channel=target_channels[i],
                    message_id=message.id,
                    status=NotificationStatus.FAILED,
                    attempt_time=datetime.now(),
                    processing_time=0.0,
                    error_message=str(result)
                ))
            else:
                channel_results.append(result)
        
        return channel_results
    
    async def _handle_failed_deliveries(self, message: NotificationMessage, 
                                      results: List[ChannelDeliveryResult]):
        """失敗した配信のリトライ処理"""
        if not message.should_retry():
            return
        
        failed_channels = [
            r.channel for r in results 
            if r.status in [NotificationStatus.FAILED, NotificationStatus.RATE_LIMITED]
        ]
        
        if not failed_channels:
            return
        
        # リトライ用メッセージ作成
        retry_message = NotificationMessage(
            id=f"{message.id}_retry_{message.retry_count + 1}",
            content=message.content,
            title=message.title,
            priority=message.priority,
            channels=failed_channels,
            retry_count=message.retry_count + 1,
            max_retries=message.max_retries,
            metadata={**message.metadata, "original_id": message.id}
        )
        
        # リトライキューに追加
        await self.retry_queue.put(retry_message)
        logger.info(f"Queued retry for message {message.id}: {len(failed_channels)} channels")
    
    async def start_background_processing(self):
        """バックグラウンド処理開始"""
        if self.is_running:
            return
        
        self.is_running = True
        
        # リトライ処理タスク
        retry_task = asyncio.create_task(self._retry_processor())
        self.background_tasks.add(retry_task)
        
        logger.info("Background notification processing started")
    
    async def stop_background_processing(self):
        """バックグラウンド処理停止"""
        self.is_running = False
        
        # 実行中タスクの停止
        for task in self.background_tasks:
            task.cancel()
        
        await asyncio.gather(*self.background_tasks, return_exceptions=True)
        self.background_tasks.clear()
        
        logger.info("Background notification processing stopped")
    
    async def _retry_processor(self):
        """リトライ処理ワーカー"""
        while self.is_running:
            try:
                # リトライキューから取得（タイムアウト付き）
                retry_message = await asyncio.wait_for(
                    self.retry_queue.get(), timeout=1.0
                )
                
                # 指数バックオフで待機
                backoff_base = self.retry_policy.get('backoff_base', 2.0)
                wait_time = backoff_base ** retry_message.retry_count
                
                logger.info(f"Waiting {wait_time}s before retry for {retry_message.id}")
                await asyncio.sleep(wait_time)
                
                # リトライ実行
                await self.dispatch_notification(retry_message)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in retry processor: {e}")
                await asyncio.sleep(5)  # エラー時は5秒待機
    
    def get_statistics(self) -> Dict[str, Any]:
        """配信システム統計情報"""
        channel_stats = {name: ch.get_statistics() for name, ch in self.channels.items()}
        
        return {
            "dispatcher": {
                "total_messages": self.total_messages,
                "total_deliveries": self.total_deliveries,
                "successful_deliveries": self.successful_deliveries,
                "failed_deliveries": self.failed_deliveries,
                "overall_success_rate": (self.successful_deliveries / self.total_deliveries * 100) 
                    if self.total_deliveries > 0 else 0.0,
                "channels_registered": len(self.channels),
                "background_processing": self.is_running
            },
            "channels": channel_stats
        }


# 使用例とテスト
if __name__ == "__main__":
    async def test_multi_channel_dispatcher():
        """マルチチャンネル配信システムのテスト"""
        
        # テスト設定
        config = {
            'max_concurrent_deliveries': 5,
            'retry_policy': {
                'backoff_base': 1.5,
                'max_retries': 2
            },
            'primary_channels': ['line', 'slack']
        }
        
        dispatcher = NotificationDispatcher(config)
        
        # テスト用チャンネル登録
        line_channel = MockNotificationChannel('line', {'rate_limit': '10/minute'})
        slack_channel = MockNotificationChannel('slack', {'rate_limit': '30/minute'})
        gas_channel = MockNotificationChannel('gas', {'rate_limit': '5/minute'})
        
        dispatcher.register_channel(line_channel)
        dispatcher.register_channel(slack_channel)
        dispatcher.register_channel(gas_channel)
        
        # バックグラウンド処理開始
        await dispatcher.start_background_processing()
        
        # テストメッセージ
        test_message = NotificationMessage(
            id="test_001",
            content="テスト通知メッセージです",
            title="テスト通知",
            priority=NotificationPriority.NORMAL,
            channels=['line', 'slack'],
            max_retries=2
        )
        
        # 配信実行
        result = await dispatcher.dispatch_notification(test_message)
        print(f"Dispatch result: {result.summary()}")
        
        # 詳細結果
        for channel_result in result.channel_results:
            print(f"  {channel_result.channel}: {channel_result.status.value} "
                  f"({channel_result.processing_time:.2f}s)")
        
        # 複数メッセージのテスト
        messages = [
            NotificationMessage(id=f"bulk_{i}", content=f"一括配信テスト {i+1}",
                               priority=NotificationPriority.LOW)
            for i in range(5)
        ]
        
        # 並行配信テスト
        bulk_tasks = [dispatcher.dispatch_notification(msg) for msg in messages]
        bulk_results = await asyncio.gather(*bulk_tasks)
        
        successful_bulk = sum(1 for r in bulk_results if r.successful_channels > 0)
        print(f"Bulk dispatch: {successful_bulk}/{len(bulk_results)} successful")
        
        # 少し待ってからリトライ処理確認
        await asyncio.sleep(2)
        
        # 統計情報
        stats = dispatcher.get_statistics()
        print("Statistics:")
        print(f"  Dispatcher: {stats['dispatcher']}")
        for channel, channel_stats in stats['channels'].items():
            print(f"  {channel}: {channel_stats}")
        
        # バックグラウンド処理停止
        await dispatcher.stop_background_processing()
        
        print("✅ Multi-channel dispatcher test completed")
    
    # テスト実行
    asyncio.run(test_multi_channel_dispatcher())