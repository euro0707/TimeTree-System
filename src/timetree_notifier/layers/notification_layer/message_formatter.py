"""
メッセージフォーマット最適化システム - 設計書の「Message Formatter」に基づく実装
各プラットフォーム最適化形式での通知メッセージ生成
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """メッセージタイプ"""
    DAILY_SUMMARY = "daily_summary"
    EVENT_ADDED = "event_added"
    EVENT_UPDATED = "event_updated"
    EVENT_REMINDER = "event_reminder"
    SYSTEM_ALERT = "system_alert"


class ChannelFormat(Enum):
    """チャンネル形式"""
    LINE_TEXT = "line_text"
    LINE_FLEX = "line_flex"
    SLACK_TEXT = "slack_text"
    SLACK_BLOCKS = "slack_blocks"
    DISCORD_TEXT = "discord_text"
    DISCORD_EMBED = "discord_embed"
    GAS_VOICE = "gas_voice"
    EMAIL_HTML = "email_html"


@dataclass
class EventData:
    """イベントデータ"""
    title: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    is_all_day: bool = False
    description: str = ""
    location: str = ""
    url: Optional[str] = None
    attendees: List[str] = field(default_factory=list)
    
    def format_time_range(self, format_type: str = "standard") -> str:
        """時刻範囲のフォーマット"""
        if self.is_all_day:
            return "終日"
        
        if not self.start_time:
            return "時刻未定"
        
        start_str = self.start_time.strftime("%H:%M")
        
        if self.end_time and self.end_time != self.start_time:
            end_str = self.end_time.strftime("%H:%M")
            if format_type == "voice":
                return f"{self.start_time.hour}時{self.start_time.minute if self.start_time.minute else ''}分から{self.end_time.hour}時{self.end_time.minute if self.end_time.minute else ''}分まで"
            else:
                return f"{start_str}-{end_str}"
        else:
            if format_type == "voice":
                return f"{self.start_time.hour}時{self.start_time.minute if self.start_time.minute else ''}分から"
            else:
                return f"{start_str}〜"


@dataclass
class MessageTemplate:
    """メッセージテンプレート"""
    channel_format: ChannelFormat
    message_type: MessageType
    template_data: Dict[str, Any]
    
    def render(self, context: Dict[str, Any]) -> Any:
        """テンプレートのレンダリング"""
        # 簡易テンプレートエンジン
        if isinstance(self.template_data, str):
            return self._render_string_template(self.template_data, context)
        elif isinstance(self.template_data, dict):
            return self._render_dict_template(self.template_data, context)
        elif isinstance(self.template_data, list):
            return self._render_list_template(self.template_data, context)
        else:
            return self.template_data
    
    def _render_string_template(self, template: str, context: Dict[str, Any]) -> str:
        """文字列テンプレートのレンダリング"""
        try:
            return template.format(**context)
        except KeyError as e:
            logger.warning(f"Template variable not found: {e}")
            return template
    
    def _render_dict_template(self, template: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """辞書テンプレートのレンダリング"""
        result = {}
        for key, value in template.items():
            if isinstance(value, str):
                result[key] = self._render_string_template(value, context)
            elif isinstance(value, dict):
                result[key] = self._render_dict_template(value, context)
            elif isinstance(value, list):
                result[key] = self._render_list_template(value, context)
            else:
                result[key] = value
        return result
    
    def _render_list_template(self, template: List[Any], context: Dict[str, Any]) -> List[Any]:
        """リストテンプレートのレンダリング"""
        result = []
        for item in template:
            if isinstance(item, str):
                result.append(self._render_string_template(item, context))
            elif isinstance(item, dict):
                result.append(self._render_dict_template(item, context))
            elif isinstance(item, list):
                result.append(self._render_list_template(item, context))
            else:
                result.append(item)
        return result


class MessageFormatter:
    """メッセージフォーマット最適化システム"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.templates: Dict[str, MessageTemplate] = {}
        self._load_default_templates()
    
    def _load_default_templates(self):
        """デフォルトテンプレートの読み込み"""
        
        # LINE テキスト形式 - 日次サマリー
        self.register_template(MessageTemplate(
            channel_format=ChannelFormat.LINE_TEXT,
            message_type=MessageType.DAILY_SUMMARY,
            template_data="🌅 おはようございます！\n\n📅 {date_str}（{weekday}）{events_summary}\n\n{events_list}{footer_message}"
        ))
        
        # LINE Flex Message形式 - 日次サマリー
        self.register_template(MessageTemplate(
            channel_format=ChannelFormat.LINE_FLEX,
            message_type=MessageType.DAILY_SUMMARY,
            template_data={
                "type": "flex",
                "altText": "{date_str}の予定 {event_count}件",
                "contents": {
                    "type": "bubble",
                    "header": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🌅 今日の予定",
                                "weight": "bold",
                                "size": "xl",
                                "color": "#1DB446"
                            },
                            {
                                "type": "text",
                                "text": "{date_str}（{weekday}）",
                                "size": "sm",
                                "color": "#666666",
                                "margin": "md"
                            }
                        ]
                    },
                    "body": {
                        "type": "box",
                        "layout": "vertical",
                        "contents": "{flex_event_list}"
                    },
                    "footer": {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": "✅ Googleカレンダーにも同期済み",
                                "size": "xs",
                                "color": "#888888"
                            }
                        ]
                    }
                }
            }
        ))
        
        # Slack Blocks形式 - 日次サマリー
        self.register_template(MessageTemplate(
            channel_format=ChannelFormat.SLACK_BLOCKS,
            message_type=MessageType.DAILY_SUMMARY,
            template_data={
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🌅 今日の予定 - {date_str}（{weekday}）"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "{events_summary}"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    "{slack_events_block}",
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "✅ *Googleカレンダーにも同期済み* | 📱 TimeTree Notifier v3.0"
                            }
                        ]
                    }
                ]
            }
        ))
        
        # Discord Embed形式 - 日次サマリー
        self.register_template(MessageTemplate(
            channel_format=ChannelFormat.DISCORD_EMBED,
            message_type=MessageType.DAILY_SUMMARY,
            template_data={
                "embeds": [
                    {
                        "title": "🌅 今日の予定",
                        "description": "{events_summary}",
                        "color": 3066993,  # Green
                        "fields": "{discord_event_fields}",
                        "footer": {
                            "text": "TimeTree Notifier v3.0 | Googleカレンダーと同期済み"
                        },
                        "timestamp": "{timestamp}"
                    }
                ]
            }
        ))
        
        # GAS 音声形式 - 日次サマリー
        self.register_template(MessageTemplate(
            channel_format=ChannelFormat.GAS_VOICE,
            message_type=MessageType.DAILY_SUMMARY,
            template_data="{date_voice}の予定は、{event_count_voice}です。{voice_events_list}今日も一日頑張りましょう。"
        ))
        
        # イベント追加通知
        self.register_template(MessageTemplate(
            channel_format=ChannelFormat.LINE_TEXT,
            message_type=MessageType.EVENT_ADDED,
            template_data="📅 新しい予定が追加されました\n\n⏰ {event_time}\n📝 {event_title}\n{event_details}"
        ))
    
    def register_template(self, template: MessageTemplate):
        """テンプレート登録"""
        key = f"{template.channel_format.value}_{template.message_type.value}"
        self.templates[key] = template
        logger.debug(f"Registered template: {key}")
    
    def format_daily_summary(self, events: List[EventData], target_date: date, 
                           channel_format: ChannelFormat) -> Any:
        """日次サマリーメッセージの作成"""
        
        # 基本的なコンテキスト作成
        context = self._create_daily_summary_context(events, target_date)
        
        # チャンネル形式別の特別処理
        if channel_format == ChannelFormat.LINE_FLEX:
            context.update(self._create_line_flex_context(events))
        elif channel_format == ChannelFormat.SLACK_BLOCKS:
            context.update(self._create_slack_blocks_context(events))
        elif channel_format == ChannelFormat.DISCORD_EMBED:
            context.update(self._create_discord_embed_context(events))
        elif channel_format == ChannelFormat.GAS_VOICE:
            context.update(self._create_gas_voice_context(events, target_date))
        
        return self._render_template(channel_format, MessageType.DAILY_SUMMARY, context)
    
    def _create_daily_summary_context(self, events: List[EventData], target_date: date) -> Dict[str, Any]:
        """日次サマリー基本コンテキスト"""
        weekdays = ['月', '火', '水', '木', '金', '土', '日']
        
        context = {
            'date_str': target_date.strftime('%m月%d日').lstrip('0'),
            'weekday': weekdays[target_date.weekday()],
            'event_count': len(events),
            'timestamp': datetime.now().isoformat()
        }
        
        if not events:
            context.update({
                'events_summary': 'の予定はありません。',
                'events_list': '',
                'footer_message': 'ゆっくりとした一日をお過ごしください！'
            })
        else:
            context.update({
                'events_summary': f'の予定 {len(events)}件',
                'events_list': self._create_text_events_list(events),
                'footer_message': '今日も一日頑張りましょう！'
            })
        
        return context
    
    def _create_text_events_list(self, events: List[EventData]) -> str:
        """テキスト形式のイベントリスト"""
        if not events:
            return ''
        
        lines = []
        for event in events[:8]:  # 最大8件
            time_str = event.format_time_range()
            lines.append(f"▫️ {time_str} {event.title}")
            if event.location:
                lines.append(f"   📍 {event.location}")
        
        if len(events) > 8:
            lines.append(f"\n... 他{len(events) - 8}件")
        
        return '\n' + '\n'.join(lines) + '\n'
    
    def _create_line_flex_context(self, events: List[EventData]) -> Dict[str, Any]:
        """LINE Flex Message用コンテキスト"""
        flex_events = []
        
        for event in events[:5]:  # Flexは最大5件
            time_str = event.format_time_range()
            
            event_box = {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": event.title,
                        "weight": "bold",
                        "size": "md",
                        "wrap": True
                    },
                    {
                        "type": "text", 
                        "text": f"⏰ {time_str}",
                        "size": "sm",
                        "color": "#666666"
                    }
                ],
                "margin": "md"
            }
            
            if event.location:
                event_box["contents"].append({
                    "type": "text",
                    "text": f"📍 {event.location}",
                    "size": "sm",
                    "color": "#888888"
                })
            
            flex_events.append(event_box)
        
        if not flex_events:
            flex_events = [{
                "type": "text",
                "text": "今日は予定がありません\nゆっくりお過ごしください 😊",
                "align": "center",
                "color": "#666666"
            }]
        
        return {"flex_event_list": flex_events}
    
    def _create_slack_blocks_context(self, events: List[EventData]) -> Dict[str, Any]:
        """Slack Blocks用コンテキスト"""
        if not events:
            events_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_今日は予定がありません。ゆっくりお過ごしください！_ 😊"
                }
            }
        else:
            events_text = []
            for event in events[:10]:
                time_str = event.format_time_range()
                location_part = f" | {event.location}" if event.location else ""
                events_text.append(f"• *{time_str}* {event.title}{location_part}")
            
            if len(events) > 10:
                events_text.append(f"_... 他{len(events) - 10}件_")
            
            events_block = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(events_text)
                }
            }
        
        return {"slack_events_block": events_block}
    
    def _create_discord_embed_context(self, events: List[EventData]) -> Dict[str, Any]:
        """Discord Embed用コンテキスト"""
        if not events:
            return {
                "discord_event_fields": [{
                    "name": "今日の予定",
                    "value": "予定はありません。ゆっくりお過ごしください！",
                    "inline": False
                }]
            }
        
        fields = []
        for i, event in enumerate(events[:10]):  # 最大10件
            time_str = event.format_time_range()
            
            field_value = time_str
            if event.location:
                field_value += f"\n📍 {event.location}"
            if event.description and len(event.description) < 100:
                field_value += f"\n💭 {event.description}"
            
            fields.append({
                "name": f"{i+1}. {event.title}",
                "value": field_value,
                "inline": True
            })
        
        if len(events) > 10:
            fields.append({
                "name": "その他",
                "value": f"他{len(events) - 10}件の予定があります",
                "inline": False
            })
        
        return {"discord_event_fields": fields}
    
    def _create_gas_voice_context(self, events: List[EventData], target_date: date) -> Dict[str, Any]:
        """GAS音声用コンテキスト"""
        date_voice = target_date.strftime('%-m月%-d日')
        
        if not events:
            return {
                'date_voice': date_voice,
                'event_count_voice': '予定はありません',
                'voice_events_list': 'ゆっくりとした一日をお過ごしください。'
            }
        
        # 件数の音声表現
        if len(events) == 1:
            event_count_voice = '1件です'
        else:
            event_count_voice = f'{len(events)}件です'
        
        # イベントリストの音声表現
        voice_list_parts = []
        for i, event in enumerate(events[:5]):  # 音声は最大5件
            order = ['1つ目', '2つ目', '3つ目', '4つ目', '5つ目'][i]
            time_voice = event.format_time_range('voice')
            voice_list_parts.append(f'{order}、{time_voice}、{event.title}。')
        
        if len(events) > 5:
            voice_list_parts.append(f'他{len(events) - 5}件の予定があります。')
        
        return {
            'date_voice': date_voice,
            'event_count_voice': event_count_voice,
            'voice_events_list': ''.join(voice_list_parts)
        }
    
    def format_event_notification(self, event: EventData, message_type: MessageType,
                                channel_format: ChannelFormat) -> Any:
        """個別イベント通知メッセージの作成"""
        
        context = {
            'event_title': event.title,
            'event_time': event.format_time_range(),
            'event_location': event.location or '場所未定',
            'event_description': event.description or '',
            'timestamp': datetime.now().isoformat()
        }
        
        # イベント詳細の構築
        details_parts = []
        if event.location:
            details_parts.append(f"📍 {event.location}")
        if event.description:
            details_parts.append(f"💭 {event.description[:100]}")
        
        context['event_details'] = '\n'.join(details_parts) if details_parts else ''
        
        return self._render_template(channel_format, message_type, context)
    
    def _render_template(self, channel_format: ChannelFormat, message_type: MessageType, 
                        context: Dict[str, Any]) -> Any:
        """テンプレートレンダリング"""
        key = f"{channel_format.value}_{message_type.value}"
        template = self.templates.get(key)
        
        if not template:
            logger.warning(f"Template not found: {key}")
            return f"Template not available for {channel_format.value} {message_type.value}"
        
        try:
            return template.render(context)
        except Exception as e:
            logger.error(f"Template rendering failed for {key}: {e}")
            return f"Template rendering error: {str(e)}"
    
    def get_available_formats(self, message_type: MessageType) -> List[ChannelFormat]:
        """利用可能なフォーマット取得"""
        available = []
        for key, template in self.templates.items():
            if template.message_type == message_type:
                available.append(template.channel_format)
        return available


# 使用例とテスト
if __name__ == "__main__":
    def test_message_formatter():
        """メッセージフォーマッターのテスト"""
        
        formatter = MessageFormatter()
        
        # テストデータ
        test_events = [
            EventData(
                title="定例会議",
                start_time=datetime(2025, 9, 1, 10, 0),
                end_time=datetime(2025, 9, 1, 11, 0),
                location="会議室A",
                description="週次の定例会議です"
            ),
            EventData(
                title="昼食",
                start_time=datetime(2025, 9, 1, 12, 0),
                is_all_day=False,
                location="レストラン"
            ),
            EventData(
                title="休暇",
                is_all_day=True,
                description="有給休暇"
            )
        ]
        
        target_date = date(2025, 9, 1)  # 月曜日
        
        print("=== Message Formatting Test ===")
        
        # LINE テキスト形式
        line_text = formatter.format_daily_summary(test_events, target_date, ChannelFormat.LINE_TEXT)
        print(f"\n📱 LINE Text:\n{line_text}")
        
        # Slack Blocks形式
        slack_blocks = formatter.format_daily_summary(test_events, target_date, ChannelFormat.SLACK_BLOCKS)
        print(f"\n💬 Slack Blocks:\n{json.dumps(slack_blocks, indent=2, ensure_ascii=False)}")
        
        # GAS 音声形式
        gas_voice = formatter.format_daily_summary(test_events, target_date, ChannelFormat.GAS_VOICE)
        print(f"\n🔊 GAS Voice:\n{gas_voice}")
        
        # 個別イベント通知
        event_notification = formatter.format_event_notification(
            test_events[0], MessageType.EVENT_ADDED, ChannelFormat.LINE_TEXT
        )
        print(f"\n📅 Event Added Notification:\n{event_notification}")
        
        # 利用可能フォーマット確認
        available_formats = formatter.get_available_formats(MessageType.DAILY_SUMMARY)
        print(f"\n📋 Available formats for daily summary: {[f.value for f in available_formats]}")
        
        print("\n✅ Message formatter test completed")
    
    # テスト実行
    test_message_formatter()