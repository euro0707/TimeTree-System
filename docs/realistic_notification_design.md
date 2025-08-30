# 通知システム現実的設計

## 🎯 設計原則
1. **段階的実装**: 複雑な機能は後回し
2. **既存活用**: 動作実績のある技術を優先
3. **コスト効率**: 無料枠内での運用

## 📱 Phase 1: 基本通知 (即実装可能)

### LINE通知 (既存改良)
```python
class EnhancedLINENotifier:
    """既存のLINE通知を改良"""
    
    def format_daily_summary(self, events: List[Event]) -> dict:
        """Flex Message形式で視覚的に改善"""
        
        if not events:
            return self._create_no_events_message()
            
        # 文字化け修正済みのイベント表示
        bubble_contents = []
        for event in events[:5]:  # 最大5件表示
            bubble_contents.append({
                "type": "box",
                "layout": "horizontal", 
                "contents": [
                    {
                        "type": "text",
                        "text": self._format_time(event),
                        "size": "sm",
                        "color": "#666666",
                        "flex": 2
                    },
                    {
                        "type": "text", 
                        "text": event.title,
                        "wrap": True,
                        "flex": 5
                    }
                ]
            })
        
        return {
            "type": "flex",
            "altText": f"今日の予定 {len(events)}件",
            "contents": {
                "type": "bubble",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [{
                        "type": "text",
                        "text": f"📅 {datetime.now().strftime('%m月%d日')}の予定",
                        "weight": "bold",
                        "size": "lg"
                    }]
                },
                "body": {
                    "type": "box", 
                    "layout": "vertical",
                    "contents": bubble_contents
                }
            }
        }
```

### 文字化け修正 (Priority High)
```python
class EncodingFixer:
    """TimeTreeスクレイピング時の文字化け修正"""
    
    GARBLED_PATTERNS = {
        # 実際の文字化けパターンをマッピング
        "�A�I�L": "アオキ",
        "�X�g": "スト", 
        "����": "買い物",
        "���X�g": "リスト"
    }
    
    def fix_garbled_text(self, text: str) -> str:
        """文字化け修正処理"""
        if not text or '�' not in text:
            return text
            
        fixed_text = text
        for garbled, correct in self.GARBLED_PATTERNS.items():
            fixed_text = fixed_text.replace(garbled, correct)
            
        return fixed_text
    
    def detect_encoding_issue(self, text: str) -> bool:
        """文字化けを検知"""
        return '�' in text or len([c for c in text if ord(c) > 1000]) == 0
```

## 🔊 Phase 2: 音声通知 (段階的実装)

### Option 1: IFTTT Webhook (推奨)
```python
class IFTTTVoiceNotifier:
    """最もシンプルな音声通知実装"""
    
    def __init__(self, webhook_key: str):
        self.webhook_url = f"https://maker.ifttt.com/trigger/{{event}}/with/key/{webhook_key}"
    
    async def send_daily_voice_summary(self, events: List[Event]):
        """毎朝の音声要約送信"""
        
        # 音声読み上げ用テキスト生成
        voice_text = self._create_voice_summary(events)
        
        # IFTTT Webhook送信
        payload = {
            "value1": voice_text,
            "value2": len(events),
            "value3": datetime.now().strftime("%m月%d日")
        }
        
        async with aiohttp.ClientSession() as session:
            await session.post(
                self.webhook_url.format(event="daily_summary"),
                json=payload
            )
    
    def _create_voice_summary(self, events: List[Event]) -> str:
        """音声読み上げ最適化"""
        
        if not events:
            return "今日の予定はありません。"
            
        date_str = datetime.now().strftime("%m月%d日")
        event_count = len(events)
        
        # 最初の3件のみ詳細読み上げ
        summaries = []
        for i, event in enumerate(events[:3], 1):
            time_str = self._voice_time_format(event)
            summaries.append(f"{i}つ目、{time_str}、{event.title}")
        
        detail_text = "、".join(summaries)
        
        if event_count > 3:
            additional = f"、他{event_count - 3}件"
        else:
            additional = ""
            
        return f"{date_str}の予定は、{event_count}件です。{detail_text}{additional}。以上です。"
    
    def _voice_time_format(self, event: Event) -> str:
        """音声用時刻フォーマット"""
        if event.is_all_day:
            return "終日"
        return event.start_datetime.strftime("%H時%M分から")
```

### IFTTT設定手順
```yaml
IFTTT Applet設定:
  Trigger: 
    Service: Webhooks
    Event: daily_summary
  Action:
    Service: Google Assistant 
    Action: Say a phrase
    設定: "{{Value1}}"  # voice_textが読み上げられる
```

### Option 2: Google Calendar通知 (Alternative)
```python
class GoogleCalendarVoiceNotifier:
    """Google Calendarの標準通知機能を活用"""
    
    async def setup_voice_reminders(self, events: List[Event]):
        """イベントごとに音声リマインダーを設定"""
        
        service = build('calendar', 'v3', credentials=self.creds)
        
        for event in events:
            # 音声通知用の特別なイベントを作成
            voice_event = {
                'summary': f"🔔 {event.title}",
                'start': {
                    'dateTime': event.start_datetime.isoformat(),
                    'timeZone': 'Asia/Tokyo',
                },
                'end': {
                    'dateTime': (event.start_datetime + timedelta(minutes=1)).isoformat(),
                    'timeZone': 'Asia/Tokyo',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 0},  # Google Assistant連携
                    ],
                },
            }
            
            service.events().insert(
                calendarId='primary', 
                body=voice_event
            ).execute()
```

## 📊 Phase 3: 拡張通知 (将来実装)

### Slack通知
```python
class SlackNotifier:
    async def send_team_summary(self, events: List[Event]):
        """チーム向けスケジュール共有"""
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text", 
                    "text": f"📅 {datetime.now().strftime('%m/%d')}のスケジュール"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        for event in events:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{event.title}*\n{self._format_time(event)}"
                }
            })
        
        await self.slack_client.chat_postMessage(
            channel="#schedule",
            blocks=blocks
        )
```

## 🎯 実装優先度

### High Priority (即実装)
1. ✅ 文字化け修正機能
2. ✅ LINE Flex Message改良
3. ✅ 基本エラーハンドリング

### Medium Priority (1-2週間後)
1. 🔄 IFTTT音声通知
2. 🔄 GitHub Actions完全自動化
3. 🔄 JSON Storage実装

### Low Priority (必要に応じて)
1. 📋 Slack/Discord拡張
2. 📋 高度な音声制御
3. 📋 WebUI Dashboard

## 💰 コスト試算

| サービス | 月額コスト | 使用量 |
|----------|------------|---------|
| **GitHub Actions** | 無料 | <2000分/月 |
| **IFTTT Pro** | $3.99 | 無制限Applet |
| **Google Calendar API** | 無料 | <100万リクエスト/月 |
| **LINE Messaging API** | 無料 | <1000メッセージ/月 |
| **合計** | **~$4/月** | **十分な余裕** |

この設計により、現実的で持続可能な通知システムを段階的に構築可能。