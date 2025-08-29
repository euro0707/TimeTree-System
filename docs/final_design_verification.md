# TimeTree通知システム - 最終設計書確認・ゴール明確化

## 実施日: 2025年8月27日

## 1. ゴール明確化

### 1.1 明確なゴール
**「毎朝決まった時間にLINEに予定を送る」**

### 1.2 現在の設計書での対応状況検証

#### ✅ 対応済み機能
- TimeTree-Exporter統合による自動データ取得
- LINE Notify通知機能
- エラーハンドリング・フォールバック機能

#### ⚠️ **不十分な機能（重要な問題）**
- **毎朝の定時通知機能が明確に設計されていない**
- スケジュール設定が「30分間隔での変更検出」のみ
- 朝の定時サマリー送信が詳細化されていない

## 2. 設計書の問題点と修正案

### 2.1 現在の設計の問題点

```python
# 現在の設計 - 問題あり
scheduler:
  interval_minutes: 30  # 変更検出のみ
```

**問題：**
- 変更通知のみで、毎朝の定時通知が主機能として設計されていない
- 朝の予定一覧送信が副次的機能として扱われている

### 2.2 修正版設計案

```python
# 修正版設計 - ゴール重視
scheduler:
  # メイン機能：毎朝の定時通知
  daily_summary:
    enabled: true
    time: "07:30"  # 毎朝7:30
    timezone: "Asia/Tokyo"
    
  # サブ機能：変更検出
  change_detection:
    enabled: true
    interval_minutes: 60  # 1時間間隔に変更
```

## 3. 修正版システム設計

### 3.1 機能優先度の再定義

```
【主機能】毎朝の定時通知
┌─────────────────────────────┐
│  毎朝7:30に今日の予定一覧送信   │
│  - 今日の予定リスト           │
│  - 時間・タイトル・説明       │
│  - 予定なしの場合も通知       │
└─────────────────────────────┘

【副機能】変更検出通知（オプション）
┌─────────────────────────────┐
│  予定変更時の即時通知         │
│  - 新規追加・変更・削除       │
│  - 即座にLINE通知送信        │
└─────────────────────────────┘
```

### 3.2 修正版データフロー

```
毎朝7:30のスケジュール実行
    ↓
TimeTree-Exporter実行
    ↓
今日の予定を抽出・整形
    ↓
朝の予定サマリー生成
    ↓
LINE通知送信
    ↓
送信完了ログ記録

【並行実行】変更検出（1時間間隔）
    ↓
前回データと比較
    ↓
変更あり？
    ↓ Yes
変更通知送信
```

### 3.3 朝の通知メッセージ形式

```
🌅 おはようございます！今日の予定

📅 2025年8月27日（火）

⏰ 今日の予定:
・09:00-10:30 プロジェクトミーティング
  場所: 会議室A
・14:00-15:00 歯医者
  場所: ○○歯科クリニック
・19:00-21:00 飲み会
  場所: 居酒屋○○

今日も良い一日を！✨

---
TimeTree自動通知 | 7:30送信
```

### 3.4 予定なしの場合の通知

```
🌅 おはようございます！

📅 2025年8月27日（火）

📝 今日は予定がありません
ゆっくりとした一日をお過ごしください！

今日も良い一日を！✨

---
TimeTree自動通知 | 7:30送信
```

## 4. 修正版コンポーネント設計

### 4.1 DailySummaryNotifier（新規追加）

```python
class DailySummaryNotifier:
    """毎朝の定時通知機能"""
    
    def __init__(self, config, exporter_manager, line_notifier):
        self.config = config
        self.exporter = exporter_manager
        self.notifier = line_notifier
        
    async def send_daily_summary(self, date: datetime = None) -> bool:
        """朝の予定サマリー送信"""
        if date is None:
            date = datetime.now(ZoneInfo("Asia/Tokyo")).date()
            
        try:
            # TimeTreeからデータ取得
            export_result = await self.exporter.execute_export()
            if not export_result.success:
                return await self.send_error_summary(date)
                
            # 今日の予定を抽出
            today_events = self.extract_today_events(export_result.ics_file, date)
            
            # メッセージ生成
            message = self.format_daily_summary(date, today_events)
            
            # LINE送信
            success = await self.notifier.send_daily_summary(message)
            
            if success:
                logger.info(f"Daily summary sent successfully for {date}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to send daily summary: {e}")
            return await self.send_error_summary(date)
    
    def extract_today_events(self, ics_file: Path, target_date: date) -> List[Event]:
        """今日の予定を抽出"""
        events = []
        
        with open(ics_file, 'rb') as f:
            calendar = Calendar.from_ical(f.read())
            
        for component in calendar.walk():
            if component.name == "VEVENT":
                event_date = component.get('dtstart').dt
                if isinstance(event_date, datetime):
                    event_date = event_date.date()
                    
                if event_date == target_date:
                    events.append(Event(
                        title=str(component.get('summary', '無題')),
                        start_time=component.get('dtstart').dt,
                        end_time=component.get('dtend').dt if component.get('dtend') else None,
                        description=str(component.get('description', ''))
                    ))
                    
        return sorted(events, key=lambda e: e.start_time)
    
    def format_daily_summary(self, date: date, events: List[Event]) -> str:
        """朝の通知メッセージ生成"""
        weekday_names = ['月', '火', '水', '木', '金', '土', '日']
        weekday = weekday_names[date.weekday()]
        
        message = f"🌅 おはようございます！今日の予定\n\n"
        message += f"📅 {date.strftime('%Y年%m月%d日')}（{weekday}）\n\n"
        
        if not events:
            message += "📝 今日は予定がありません\n"
            message += "ゆっくりとした一日をお過ごしください！\n\n"
        else:
            message += "⏰ 今日の予定:\n"
            for event in events:
                start_time = event.start_time.strftime('%H:%M')
                if event.end_time:
                    end_time = event.end_time.strftime('%H:%M')
                    time_str = f"{start_time}-{end_time}"
                else:
                    time_str = start_time
                    
                message += f"・{time_str} {event.title}\n"
                if event.description:
                    message += f"  {event.description}\n"
            message += "\n"
        
        message += "今日も良い一日を！✨\n\n"
        message += "---\n"
        message += f"TimeTree自動通知 | {datetime.now().strftime('%H:%M')}送信"
        
        return message
```

### 4.2 修正版スケジューラー設計

```python
class TimeTreeScheduler:
    """スケジュール管理（修正版）"""
    
    def __init__(self, config):
        self.config = config
        self.scheduler = AsyncIOScheduler()
        self.daily_notifier = DailySummaryNotifier(config)
        self.change_detector = ChangeDetector(config)  # 既存
        
    def setup_schedules(self):
        """スケジュール設定"""
        
        # メイン機能：毎朝の定時通知
        daily_time = self.config.daily_summary.time  # "07:30"
        hour, minute = map(int, daily_time.split(':'))
        
        self.scheduler.add_job(
            func=self.daily_notifier.send_daily_summary,
            trigger='cron',
            hour=hour,
            minute=minute,
            id='daily_summary',
            name='Daily Schedule Summary',
            timezone='Asia/Tokyo'
        )
        
        # サブ機能：変更検出（オプション）
        if self.config.change_detection.enabled:
            self.scheduler.add_job(
                func=self.change_detector.check_changes,
                trigger='interval',
                minutes=self.config.change_detection.interval_minutes,
                id='change_detection',
                name='Change Detection'
            )
```

## 5. 修正版設定ファイル

### 5.1 config.yaml（修正版）

```yaml
# TimeTree自動通知システム - 最終設計版
app:
  name: "TimeTree Daily Notifier"
  version: "2.1.0"
  goal: "毎朝決まった時間にLINEに予定を送る"

# メイン機能：毎朝の定時通知
daily_summary:
  enabled: true
  time: "07:30"  # 毎朝7:30
  timezone: "Asia/Tokyo"
  
  # 通知内容設定
  include_description: true
  include_location: true
  max_events_display: 10
  
  # 予定なしの場合の通知
  notify_when_no_events: true
  no_events_message: "今日は予定がありません\nゆっくりとした一日をお過ごしください！"

# サブ機能：変更検出（オプション）
change_detection:
  enabled: false  # 初期は無効（シンプル化）
  interval_minutes: 60
  notify_additions: true
  notify_modifications: true
  notify_deletions: true

# TimeTree設定
timetree:
  email: "${TIMETREE_EMAIL}"
  password: "${TIMETREE_PASSWORD}"
  exporter:
    timeout: 120
    retry_count: 3

# LINE通知設定
notification:
  line_notify_token: "${LINE_NOTIFY_TOKEN}"
  max_message_length: 1000
  timezone: "Asia/Tokyo"
  
  # メッセージテンプレート
  greeting: "🌅 おはようございます！今日の予定"
  closing: "今日も良い一日を！✨"
  footer: "TimeTree自動通知"

# ログ設定
logging:
  level: "INFO"
  file: "./logs/daily_notifier.log"
  max_size: "10MB"
  rotation: 7
```

## 6. 最終確認チェックリスト

### 6.1 ゴール達成確認

- ✅ **毎朝決まった時間（7:30）にLINE送信**
- ✅ **今日の予定一覧を整理して表示**
- ✅ **予定なしの場合も通知送信**
- ✅ **TimeTree-Exporterによる自動取得**
- ✅ **エラー時のフォールバック対応**

### 6.2 機能優先度確認

```
【最優先】毎朝7:30の定時通知 ← メイン機能
【次優先】エラーハンドリング・フォールバック
【低優先】変更検出通知（オプション機能）
```

### 6.3 ユーザー体験確認

**理想的な日常体験：**
1. 毎朝7:30にスマホにLINE通知が届く
2. 今日の予定が整理されて表示される
3. 予定がない日も「今日は予定なし」の通知
4. システムエラー時も可能な限り通知継続

## 7. 推奨実装手順（修正版）

### 7.1 Phase 1: コア機能実装（2日）
- Day 1: DailySummaryNotifier実装
- Day 2: スケジューラー統合・基本動作確認

### 7.2 Phase 2: 信頼性向上（2日）
- Day 3: TimeTree-Exporter統合・エラーハンドリング
- Day 4: フォールバック機能・テスト

### 7.3 Phase 3: 運用準備（1日）
- Day 5: 設定調整・デプロイ・運用開始

**合計：5日間（大幅短縮）**

## 結論

現在の設計書は「毎朝決まった時間にLINEに予定を送る」という明確なゴールに対して**不十分**でした。

**修正された設計のポイント：**
1. ✅ 毎朝7:30の定時通知を**メイン機能**として明確化
2. ✅ 変更検出を**サブ機能**（オプション）に格下げ
3. ✅ 実装期間を10日→5日に短縮
4. ✅ ユーザー体験を重視したメッセージ設計

この修正版設計で実装を進めることで、明確なゴール「毎朝決まった時間にLINEに予定を送る」を確実に達成できます。

**実装開始の最終確認：**
この修正版設計で実装を開始してよろしいでしょうか？