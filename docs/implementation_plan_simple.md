# TimeTree簡単同期システム 実装計画

## 🎯 **実装要件の整理**

### **現在の問題**
1. **予定認識エラー**: 文字化けにより予定が正しく表示されない
2. **TimeTree-Exporter問題**: 空のICSファイルが生成される
3. **同期機能なし**: Googleカレンダーとの連携がない

### **解決すべき課題**
1. ✅ **文字化け修正**: 「�A�I�L」→「アオキ」等の変換
2. ✅ **TimeTree取得の安定化**: エラー処理とフォールバック
3. ✅ **Googleカレンダー同期**: 毎朝の自動同期
4. ✅ **LINE通知改善**: 読みやすいメッセージフォーマット

## 📅 **実装スケジュール（2週間）**

### **Phase 1: 文字化け修正（Day 1-3）**

#### **Day 1: 文字化け分析と修正クラス作成**
```python
# 新規作成: src/timetree_notifier/core/encoding_fixer.py
class EncodingFixer:
    """TimeTreeデータの文字化け修正"""
    
    # 実際の文字化けパターン（今朝の通知から学習）
    GARBLED_PATTERNS = {
        "�A�I�L": "アオキ",
        "����": "買い物",
        "���X�g": "リスト",
        "�X�g": "スト",
        "�d�b": "電話",
        "���[�e�B���O": "ミーティング",
        # 運用しながら追加
    }
    
    def fix_event_text(self, text: str) -> str:
        """イベントテキストの文字化け修正"""
        if not text or '�' not in text:
            return text
            
        fixed_text = text
        for garbled, correct in self.GARBLED_PATTERNS.items():
            fixed_text = fixed_text.replace(garbled, correct)
        
        # パターンにない場合の対処
        if '�' in fixed_text:
            # ログに記録して学習データに追加
            self._log_unknown_pattern(text, fixed_text)
            # 暫定的に � を除去
            fixed_text = fixed_text.replace('�', '')
            
        return fixed_text
```

#### **Day 2: 既存コードに統合**
```python
# 修正: src/timetree_notifier/core/daily_notifier.py
from .encoding_fixer import EncodingFixer

class DailySummaryNotifier:
    def __init__(self, config: Config):
        self.config = config
        self.encoding_fixer = EncodingFixer()  # 追加
        # ... 既存コード
    
    def _parse_event_component(self, component, target_date: date) -> Optional[Event]:
        # 既存の処理後に文字化け修正を追加
        event = # ... 既存の処理
        
        if event:
            # 文字化け修正
            event.title = self.encoding_fixer.fix_event_text(event.title)
            event.description = self.encoding_fixer.fix_event_text(event.description)
            
        return event
```

#### **Day 3: テストと検証**
- 既存の文字化けパターンでテスト
- 新しいパターンの検出機能テスト
- ログ出力の確認

### **Phase 2: Googleカレンダー同期（Day 4-7）**

#### **Day 4: Google Calendar API設定**
```python
# 新規作成: src/timetree_notifier/integrations/google_calendar.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

class GoogleCalendarSync:
    def __init__(self, config):
        self.config = config
        self.service = self._build_service()
        
    def _build_service(self):
        """Google Calendar API サービス構築"""
        creds = Credentials.from_authorized_user_file(
            self.config.google_calendar.credentials_path
        )
        return build('calendar', 'v3', credentials=creds)
```

#### **Day 5: 同期機能実装**
```python
class GoogleCalendarSync:
    async def sync_daily_events(self, timetree_events: List[Event]):
        """今日のTimeTree予定をGoogleカレンダーに同期"""
        
        # 1. 既存のTimeTree同期イベントをクリア
        await self._clear_timetree_events()
        
        # 2. 新しいイベントを追加
        for event in timetree_events:
            google_event = self._convert_to_google_format(event)
            await self._insert_calendar_event(google_event)
    
    def _convert_to_google_format(self, timetree_event: Event) -> dict:
        """TimeTreeイベントをGoogle Calendar形式に変換"""
        return {
            'summary': f"📱 {timetree_event.title}",
            'description': f"TimeTreeから同期\n{timetree_event.description}",
            'start': self._format_datetime(timetree_event.start_time),
            'end': self._format_datetime(timetree_event.end_time or timetree_event.start_time),
        }
```

#### **Day 6: 既存システムとの統合**
```python
# 修正: src/timetree_notifier/core/daily_notifier.py
from ..integrations.google_calendar import GoogleCalendarSync

class DailySummaryNotifier:
    def __init__(self, config: Config):
        # ... 既存コード
        self.google_sync = GoogleCalendarSync(config)  # 追加
    
    async def send_daily_summary(self, target_date: Optional[date] = None) -> bool:
        # ... 既存の処理（TimeTree取得、文字化け修正）
        
        # Googleカレンダー同期を追加
        try:
            await self.google_sync.sync_daily_events(today_events)
            logger.info("Google Calendar sync completed")
        except Exception as e:
            logger.warning(f"Google Calendar sync failed: {e}")
            # 同期失敗してもLINE通知は続行
        
        # ... 既存のLINE通知処理
```

#### **Day 7: 認証とテスト**
- Google Calendar API認証設定
- 同期機能の動作テスト
- エラーハンドリングの確認

### **Phase 3: LINE通知改善（Day 8-10）**

#### **Day 8: メッセージフォーマット改善**
```python
# 修正: src/timetree_notifier/core/daily_notifier.py
def _generate_daily_summary(self, target_date: date, events: List[Event]) -> DailySummary:
    """改良された日次サマリー生成"""
    
    today_str = target_date.strftime('%m月%d日')
    weekday = ['月', '火', '水', '木', '金', '土', '日'][target_date.weekday()]
    
    if not events:
        message = f"""おはようございます！

📅 {today_str}（{weekday}）の予定はありません。

ゆっくりとした一日をお過ごしください！"""
    else:
        # 予定リストの生成
        event_lines = []
        for event in events[:8]:  # 最大8件表示
            time_str = self._format_event_time(event)
            event_lines.append(f"▫️ {time_str} {event.title}")
            
        events_text = '\n'.join(event_lines)
        
        if len(events) > 8:
            events_text += f"\n... 他{len(events) - 8}件"
            
        message = f"""おはようございます！

📅 {today_str}（{weekday}）の予定 {len(events)}件

{events_text}

✅ Googleカレンダーにも同期済み
今日も一日頑張りましょう！"""

    return DailySummary(
        date=target_date,
        events=events,
        total_events=len(events),
        message=message,
        generated_at=datetime.now()
    )

def _format_event_time(self, event: Event) -> str:
    """読みやすい時刻表示"""
    if event.is_all_day:
        return "終日"
    
    start = event.start_time.strftime('%H:%M')
    if event.end_time:
        end = event.end_time.strftime('%H:%M')
        if start != end:
            return f"{start}-{end}"
    return f"{start}〜"
```

#### **Day 9: エラー通知の改善**
```python
async def _send_error_notification(self, target_date: date, error_message: str) -> bool:
    """わかりやすいエラー通知"""
    
    error_emoji = "⚠️" if "timeout" in error_message.lower() else "❌"
    
    message = f"""{error_emoji} TimeTree取得エラー

📅 {target_date.strftime('%m月%d日')}の予定取得に失敗しました

🔍 エラー詳細:
{error_message[:200]}

📱 手動でTimeTreeアプリを確認してください
システムは次回自動で再試行します"""

    return await self.line_notifier.send_message(message)
```

#### **Day 10: 通知成功確認**
- メッセージの見た目確認
- 文字数制限チェック
- エラー通知のテスト

### **Phase 4: 自動化と運用（Day 11-14）**

#### **Day 11: GitHub Actions設定**
```yaml
# .github/workflows/timetree_daily_sync.yml
name: TimeTree Daily Sync

on:
  schedule:
    - cron: '0 21 * * *'  # 毎朝6時JST (21時UTC)
  workflow_dispatch:

jobs:
  daily-sync:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          
      - name: Run daily sync
        env:
          TIMETREE_EMAIL: ${{ secrets.TIMETREE_EMAIL }}
          TIMETREE_PASSWORD: ${{ secrets.TIMETREE_PASSWORD }}
          LINE_CHANNEL_ACCESS_TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
          LINE_USER_ID: ${{ secrets.LINE_USER_ID }}
          GOOGLE_CALENDAR_CREDENTIALS: ${{ secrets.GOOGLE_CALENDAR_CREDENTIALS }}
        run: |
          python -m timetree_notifier.main --mode daily
```

#### **Day 12: 設定ファイル整備**
```yaml
# config.yaml の更新
timetree:
  email: ${TIMETREE_EMAIL}
  password: ${TIMETREE_PASSWORD}
  calendar_code: "your_calendar_id"
  exporter:
    timeout: 300

google_calendar:
  enabled: true
  calendar_id: "primary"
  credentials_json: ${GOOGLE_CALENDAR_CREDENTIALS}

line_notification:
  channel_access_token: ${LINE_CHANNEL_ACCESS_TOKEN}
  user_id: ${LINE_USER_ID}
  
encoding:
  fix_garbled_text: true
  log_unknown_patterns: true

daily_summary:
  timezone: "Asia/Tokyo"
  max_events_display: 8
  include_google_sync_status: true
```

#### **Day 13: 本番テスト**
- 手動実行での動作確認
- すべてのエラーケースのテスト
- ログ出力の確認

#### **Day 14: 運用開始**
- GitHub Actions の本番実行開始
- 初回成功の確認
- 運用監視の設定

## 🧪 **テスト計画**

### **文字化け修正テスト**
```python
def test_encoding_fixer():
    fixer = EncodingFixer()
    
    # 既知パターンのテスト
    assert fixer.fix_event_text("�A�I�L����") == "アオキ買い物"
    assert fixer.fix_event_text("���[�e�B���O") == "ミーティング"
    
    # 正常テキストが変わらないことを確認
    assert fixer.fix_event_text("会議") == "会議"
```

### **Googleカレンダー同期テスト**
```python
async def test_google_sync():
    sync = GoogleCalendarSync(test_config)
    
    # テスト用イベント作成
    test_event = Event(
        title="テスト予定",
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(hours=1)
    )
    
    # 同期実行
    await sync.sync_daily_events([test_event])
    
    # Googleカレンダーで確認
    # （実装は手動確認でも可）
```

## 📊 **成功指標**

### **機能成功基準**
- **文字化け修正率**: 100%（既知パターン）
- **Google同期成功率**: 95%以上
- **LINE通知成功率**: 98%以上
- **自動実行成功率**: 95%以上

### **運用成功基準**
- **毎朝6時の確実な通知**: 7日連続成功
- **文字化けゼロ**: 新しいパターンの迅速な対応
- **同期の確認**: Googleカレンダーで予定確認可能

この実装計画により、2週間でシンプルかつ確実なTimeTree連携システムを構築できます。