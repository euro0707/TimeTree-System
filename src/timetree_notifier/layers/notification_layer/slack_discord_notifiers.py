"""
Slack/Discord通知システム - 設計書の「Slack/Discord連携」に基づく実装
リッチメッセージ・インタラクティブ要素対応
"""

import asyncio
import aiohttp
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import logging

from .multi_channel_dispatcher import NotificationChannel, ChannelDeliveryResult, NotificationStatus
from .message_formatter import MessageFormatter, ChannelFormat, MessageType

logger = logging.getLogger(__name__)


class SlackMessageType(Enum):
    """Slackメッセージタイプ"""
    TEXT = "text"
    BLOCKS = "blocks"
    ATTACHMENTS = "attachments"


class DiscordMessageType(Enum):
    """Discordメッセージタイプ"""
    TEXT = "text"
    EMBED = "embed"
    COMPONENTS = "components"


@dataclass
class SlackConfig:
    """Slack設定"""
    webhook_url: str
    channel: Optional[str] = None
    username: str = "TimeTree Notifier"
    icon_emoji: str = ":calendar:"
    thread_ts: Optional[str] = None
    
    def validate(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith('https://hooks.slack.com/'))


@dataclass
class DiscordConfig:
    """Discord設定"""
    webhook_url: str
    username: str = "TimeTree Notifier"
    avatar_url: Optional[str] = None
    tts: bool = False
    
    def validate(self) -> bool:
        return bool(self.webhook_url and 'discord.com' in self.webhook_url)


class SlackNotifier(NotificationChannel):
    """Slack通知システム"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.slack_config = SlackConfig(**config.get('slack_settings', {}))
        self.message_formatter = MessageFormatter()
        self.default_message_type = SlackMessageType(config.get('message_type', 'blocks'))
        
        if not self.slack_config.validate():
            raise ValueError("Invalid Slack configuration")
    
    async def send_message(self, message) -> ChannelDeliveryResult:
        """Slackメッセージ送信"""
        start_time = datetime.now()
        
        try:
            # メッセージ形式の決定
            if hasattr(message, 'metadata') and 'slack_format' in message.metadata:
                message_format = SlackMessageType(message.metadata['slack_format'])
            else:
                message_format = self.default_message_type
            
            # Slack用ペイロード作成
            payload = await self._create_slack_payload(message, message_format)
            
            # Webhook送信
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.slack_config.webhook_url,
                    json=payload,
                    timeout=30
                ) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        return ChannelDeliveryResult(
                            channel=self.name,
                            message_id=getattr(message, 'id', 'unknown'),
                            status=NotificationStatus.SUCCESS,
                            attempt_time=start_time,
                            processing_time=(datetime.now() - start_time).total_seconds(),
                            response_data={"response": response_text}
                        )
                    else:
                        raise Exception(f"Slack API returned {response.status}: {response_text}")
        
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            return ChannelDeliveryResult(
                channel=self.name,
                message_id=getattr(message, 'id', 'unknown'),
                status=NotificationStatus.FAILED,
                attempt_time=start_time,
                processing_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    async def _create_slack_payload(self, message, message_format: SlackMessageType) -> Dict[str, Any]:
        """Slack用ペイロード作成"""
        
        base_payload = {
            "username": self.slack_config.username,
            "icon_emoji": self.slack_config.icon_emoji
        }
        
        if self.slack_config.channel:
            base_payload["channel"] = self.slack_config.channel
        
        if self.slack_config.thread_ts:
            base_payload["thread_ts"] = self.slack_config.thread_ts
        
        # メッセージタイプ別処理
        if message_format == SlackMessageType.BLOCKS:
            # Slack Blocks形式（リッチメッセージ）
            if hasattr(message, 'metadata') and 'events' in message.metadata:
                # 日次サマリーの場合
                events_data = message.metadata['events']
                target_date = message.metadata.get('target_date', datetime.now().date())
                
                blocks_message = self.message_formatter.format_daily_summary(
                    events_data, target_date, ChannelFormat.SLACK_BLOCKS
                )
                
                base_payload.update(blocks_message)
                base_payload["text"] = f"📅 {target_date}の予定"  # フォールバック用
                
            else:
                # 通常メッセージをBlocks形式に変換
                blocks_payload = self._create_simple_blocks(message)
                base_payload.update(blocks_payload)
        
        elif message_format == SlackMessageType.ATTACHMENTS:
            # Attachments形式（レガシー）
            attachments = self._create_slack_attachments(message)
            base_payload["attachments"] = attachments
            base_payload["text"] = getattr(message, 'title', 'TimeTree通知')
        
        else:
            # シンプルテキスト形式
            base_payload["text"] = getattr(message, 'content', str(message))
        
        return base_payload
    
    def _create_simple_blocks(self, message) -> Dict[str, Any]:
        """シンプルなBlocks形式メッセージ"""
        title = getattr(message, 'title', 'TimeTree通知')
        content = getattr(message, 'content', str(message))
        
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": content
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"📱 TimeTree Notifier v3.0 | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        }
                    ]
                }
            ]
        }
    
    def _create_slack_attachments(self, message) -> List[Dict[str, Any]]:
        """Slack Attachments作成"""
        title = getattr(message, 'title', 'TimeTree通知')
        content = getattr(message, 'content', str(message))
        
        attachment = {
            "color": "good",  # green
            "title": title,
            "text": content,
            "footer": "TimeTree Notifier v3.0",
            "ts": int(datetime.now().timestamp())
        }
        
        # 優先度による色分け
        if hasattr(message, 'priority'):
            priority = message.priority
            if priority.value >= 4:  # URGENT
                attachment["color"] = "danger"  # red
            elif priority.value >= 3:  # HIGH  
                attachment["color"] = "warning"  # yellow
            else:
                attachment["color"] = "good"  # green
        
        return [attachment]
    
    async def send_daily_summary(self, events_data: List[Any], target_date) -> ChannelDeliveryResult:
        """日次サマリー専用送信"""
        
        # メッセージオブジェクト作成
        from .multi_channel_dispatcher import NotificationMessage, NotificationPriority
        
        message = NotificationMessage(
            id=f"slack_daily_{target_date.strftime('%Y%m%d')}",
            content="",  # Blocksで構築するため空
            title=f"📅 {target_date}の予定",
            priority=NotificationPriority.NORMAL,
            metadata={
                'events': events_data,
                'target_date': target_date,
                'slack_format': 'blocks'
            }
        )
        
        return await self.send_message(message)


class DiscordNotifier(NotificationChannel):
    """Discord通知システム"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.discord_config = DiscordConfig(**config.get('discord_settings', {}))
        self.message_formatter = MessageFormatter()
        self.default_message_type = DiscordMessageType(config.get('message_type', 'embed'))
        
        if not self.discord_config.validate():
            raise ValueError("Invalid Discord configuration")
    
    async def send_message(self, message) -> ChannelDeliveryResult:
        """Discordメッセージ送信"""
        start_time = datetime.now()
        
        try:
            # メッセージ形式の決定
            if hasattr(message, 'metadata') and 'discord_format' in message.metadata:
                message_format = DiscordMessageType(message.metadata['discord_format'])
            else:
                message_format = self.default_message_type
            
            # Discord用ペイロード作成
            payload = await self._create_discord_payload(message, message_format)
            
            # Webhook送信
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.discord_config.webhook_url,
                    json=payload,
                    timeout=30
                ) as response:
                    response_text = await response.text()
                    
                    if response.status in [200, 204]:
                        return ChannelDeliveryResult(
                            channel=self.name,
                            message_id=getattr(message, 'id', 'unknown'),
                            status=NotificationStatus.SUCCESS,
                            attempt_time=start_time,
                            processing_time=(datetime.now() - start_time).total_seconds(),
                            response_data={"response": response_text}
                        )
                    else:
                        raise Exception(f"Discord API returned {response.status}: {response_text}")
        
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return ChannelDeliveryResult(
                channel=self.name,
                message_id=getattr(message, 'id', 'unknown'),
                status=NotificationStatus.FAILED,
                attempt_time=start_time,
                processing_time=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    async def _create_discord_payload(self, message, message_format: DiscordMessageType) -> Dict[str, Any]:
        """Discord用ペイロード作成"""
        
        base_payload = {
            "username": self.discord_config.username,
            "tts": self.discord_config.tts
        }
        
        if self.discord_config.avatar_url:
            base_payload["avatar_url"] = self.discord_config.avatar_url
        
        # メッセージタイプ別処理
        if message_format == DiscordMessageType.EMBED:
            # Discord Embed形式（リッチメッセージ）
            if hasattr(message, 'metadata') and 'events' in message.metadata:
                # 日次サマリーの場合
                events_data = message.metadata['events']
                target_date = message.metadata.get('target_date', datetime.now().date())
                
                embed_message = self.message_formatter.format_daily_summary(
                    events_data, target_date, ChannelFormat.DISCORD_EMBED
                )
                
                base_payload.update(embed_message)
                
            else:
                # 通常メッセージをEmbed形式に変換
                embed = self._create_simple_embed(message)
                base_payload["embeds"] = [embed]
        
        elif message_format == DiscordMessageType.COMPONENTS:
            # インタラクティブコンポーネント付き（将来拡張用）
            base_payload["content"] = getattr(message, 'content', str(message))
            base_payload["components"] = self._create_discord_components(message)
        
        else:
            # シンプルテキスト形式
            base_payload["content"] = getattr(message, 'content', str(message))
        
        return base_payload
    
    def _create_simple_embed(self, message) -> Dict[str, Any]:
        """シンプルなEmbed形式メッセージ"""
        title = getattr(message, 'title', 'TimeTree通知')
        content = getattr(message, 'content', str(message))
        
        embed = {
            "title": title,
            "description": content,
            "color": 3066993,  # Green
            "footer": {
                "text": "TimeTree Notifier v3.0"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 優先度による色分け
        if hasattr(message, 'priority'):
            priority = message.priority
            if priority.value >= 4:  # URGENT
                embed["color"] = 15158332  # Red
            elif priority.value >= 3:  # HIGH
                embed["color"] = 15105570  # Orange
            elif priority.value >= 2:  # NORMAL
                embed["color"] = 3447003   # Blue
            else:
                embed["color"] = 10197915  # Gray
        
        return embed
    
    def _create_discord_components(self, message) -> List[Dict[str, Any]]:
        """Discordコンポーネント作成（将来拡張用）"""
        # インタラクティブボタンなどの実装
        return [
            {
                "type": 1,  # Action Row
                "components": [
                    {
                        "type": 2,  # Button
                        "style": 5,  # Link
                        "label": "TimeTreeで確認",
                        "url": "https://timetree.com/"
                    }
                ]
            }
        ]
    
    async def send_daily_summary(self, events_data: List[Any], target_date) -> ChannelDeliveryResult:
        """日次サマリー専用送信"""
        
        from .multi_channel_dispatcher import NotificationMessage, NotificationPriority
        
        message = NotificationMessage(
            id=f"discord_daily_{target_date.strftime('%Y%m%d')}",
            content="",
            title=f"🌅 {target_date}の予定",
            priority=NotificationPriority.NORMAL,
            metadata={
                'events': events_data,
                'target_date': target_date,
                'discord_format': 'embed'
            }
        )
        
        return await self.send_message(message)


# 統合通知クラス
class SlackDiscordManager:
    """Slack/Discord通知統合管理"""
    
    def __init__(self, slack_config: Optional[Dict[str, Any]] = None,
                 discord_config: Optional[Dict[str, Any]] = None):
        
        self.notifiers = {}
        
        if slack_config and slack_config.get('enabled', False):
            try:
                self.notifiers['slack'] = SlackNotifier('slack', slack_config)
                logger.info("Slack notifier initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Slack notifier: {e}")
        
        if discord_config and discord_config.get('enabled', False):
            try:
                self.notifiers['discord'] = DiscordNotifier('discord', discord_config)
                logger.info("Discord notifier initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Discord notifier: {e}")
    
    async def broadcast_daily_summary(self, events_data: List[Any], target_date) -> Dict[str, ChannelDeliveryResult]:
        """日次サマリーの一斉配信"""
        results = {}
        
        tasks = []
        for name, notifier in self.notifiers.items():
            tasks.append(notifier.send_daily_summary(events_data, target_date))
        
        if tasks:
            delivery_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(delivery_results):
                notifier_name = list(self.notifiers.keys())[i]
                if isinstance(result, Exception):
                    logger.error(f"Failed to send to {notifier_name}: {result}")
                else:
                    results[notifier_name] = result
        
        return results
    
    def get_statistics(self) -> Dict[str, Any]:
        """統計情報取得"""
        stats = {}
        for name, notifier in self.notifiers.items():
            stats[name] = notifier.get_statistics()
        
        return {
            "slack_discord_manager": {
                "active_notifiers": list(self.notifiers.keys()),
                "total_notifiers": len(self.notifiers)
            },
            "notifiers": stats
        }


# 使用例とテスト
if __name__ == "__main__":
    async def test_slack_discord_notifiers():
        """Slack/Discord通知システムのテスト"""
        
        # テスト設定（実際のWebhook URLは設定しない）
        slack_config = {
            'enabled': False,  # テストのため無効化
            'slack_settings': {
                'webhook_url': 'https://hooks.slack.com/services/TEST/TEST/TEST',
                'channel': '#timeree-notifications',
                'username': 'TimeTree Bot',
                'icon_emoji': ':calendar:'
            },
            'message_type': 'blocks',
            'rate_limit': '10/minute'
        }
        
        discord_config = {
            'enabled': False,  # テストのため無効化
            'discord_settings': {
                'webhook_url': 'https://discord.com/api/webhooks/TEST/TEST',
                'username': 'TimeTree Bot'
            },
            'message_type': 'embed',
            'rate_limit': '15/minute'
        }
        
        print("=== Slack/Discord Notifiers Test ===")
        
        # 設定検証テスト
        if slack_config['enabled']:
            try:
                slack_notifier = SlackNotifier('slack', slack_config)
                print("✅ Slack notifier initialized")
            except Exception as e:
                print(f"❌ Slack notifier failed: {e}")
        
        if discord_config['enabled']:
            try:
                discord_notifier = DiscordNotifier('discord', discord_config)
                print("✅ Discord notifier initialized")
            except Exception as e:
                print(f"❌ Discord notifier failed: {e}")
        
        # 統合マネージャーテスト
        manager = SlackDiscordManager(slack_config, discord_config)
        
        # テスト用イベントデータ
        from .message_formatter import EventData
        from datetime import date
        
        test_events = [
            EventData(title="テスト会議", start_time=datetime(2025, 9, 1, 10, 0)),
            EventData(title="昼食会", start_time=datetime(2025, 9, 1, 12, 0))
        ]
        
        # メッセージフォーマットテスト
        formatter = MessageFormatter()
        
        slack_message = formatter.format_daily_summary(
            test_events, date(2025, 9, 1), ChannelFormat.SLACK_BLOCKS
        )
        print(f"\n📱 Slack Blocks Format:")
        print(json.dumps(slack_message, indent=2, ensure_ascii=False))
        
        discord_message = formatter.format_daily_summary(
            test_events, date(2025, 9, 1), ChannelFormat.DISCORD_EMBED
        )
        print(f"\n🎮 Discord Embed Format:")
        print(json.dumps(discord_message, indent=2, ensure_ascii=False))
        
        # 統計情報
        stats = manager.get_statistics()
        print(f"\n📊 Manager Statistics:")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        print("\n✅ Slack/Discord notifiers test completed")
        print("Note: Actual webhook sending was disabled for testing")
    
    # テスト実行
    asyncio.run(test_slack_discord_notifiers())