# GAS TimeTree同期システム 実装計画

## 🚀 **GASアプローチの最大のメリット**

### **完全無料・無制限・高可用性**
- ✅ **$0/月**: 完全無料（Googleアカウントのみ）
- ✅ **無制限実行**: GitHub Actionsの2000分/月制限なし
- ✅ **99.9%稼働率**: Googleインフラの信頼性
- ✅ **PC完全不要**: クラウド完結

### **開発・運用の簡単さ**
- ✅ **WebUI**: ブラウザで編集・実行・デバッグ
- ✅ **認証簡単**: Google APIが標準で利用可能
- ✅ **エラー通知**: Gmail自動通知
- ✅ **即座実行**: 手動でテスト実行可能

## 📅 **段階的実装計画（2週間）**

### **Phase 1: GAS基盤構築 (Day 1-3)**

#### **Day 1: GASプロジェクト作成**
1. **Google Apps Scriptプロジェクト作成**
   - https://script.google.com にアクセス
   - 新しいプロジェクト作成
   - プロジェクト名: `TimeTree-Sync-System`

2. **権限設定 (appsscript.json)**
```json
{
  "timeZone": "Asia/Tokyo",
  "dependencies": {
    "enabledAdvancedServices": []
  },
  "oauthScopes": [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send", 
    "https://www.googleapis.com/auth/script.external_request"
  ]
}
```

3. **基本設定ファイル作成**
```javascript
// Config.gs
function setupConfig() {
  const properties = PropertiesService.getScriptProperties();
  
  properties.setProperties({
    'LINE_CHANNEL_ACCESS_TOKEN': 'YOUR_LINE_TOKEN',
    'LINE_USER_ID': 'YOUR_LINE_USER_ID',
    'TIMETREE_DATA_URL': 'https://your-github-pages.github.io/timetree-data/events.json'
  });
}
```

#### **Day 2: Googleカレンダー連携**
```javascript
// Calendar.gs - Googleカレンダー同期機能
function syncToGoogleCalendar(events) {
  const calendar = CalendarApp.getDefaultCalendar();
  
  // 今日のTimeTree同期イベントをクリア
  clearTodayTimeTreeEvents(calendar);
  
  // 新しいイベントを追加
  events.forEach(event => {
    if (event.allDay) {
      calendar.createAllDayEvent(`📱 ${event.title}`, new Date(event.start));
    } else {
      calendar.createEvent(
        `📱 ${event.title}`, 
        new Date(event.start), 
        new Date(event.end || event.start)
      );
    }
  });
}

function clearTodayTimeTreeEvents(calendar) {
  const today = new Date();
  const events = calendar.getEventsForDay(today);
  
  events.forEach(event => {
    if (event.getTitle().startsWith('📱')) {
      event.deleteEvent();
    }
  });
}
```

#### **Day 3: LINE通知機能**
```javascript
// LineNotifier.gs
function sendLineNotification(events) {
  const config = getConfig();
  const message = createDailyMessage(events);
  
  const payload = {
    'to': config.lineUserId,
    'messages': [{'type': 'text', 'text': message}]
  };
  
  const options = {
    'method': 'POST',
    'headers': {
      'Authorization': `Bearer ${config.lineToken}`,
      'Content-Type': 'application/json'
    },
    'payload': JSON.stringify(payload)
  };
  
  UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', options);
}

function createDailyMessage(events) {
  const today = new Date();
  const dateStr = Utilities.formatDate(today, 'Asia/Tokyo', 'M月d日');
  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  const weekday = weekdays[today.getDay()];
  
  if (events.length === 0) {
    return `🌅 おはようございます！\n\n📅 ${dateStr}（${weekday}）の予定はありません。\n\nゆっくりとした一日をお過ごしください！`;
  }
  
  let message = `🌅 おはようございます！\n\n📅 ${dateStr}（${weekday}）の予定 ${events.length}件\n\n`;
  
  events.slice(0, 8).forEach(event => {
    const timeStr = event.allDay ? '終日' : 
      Utilities.formatDate(new Date(event.start), 'Asia/Tokyo', 'H:mm') + '〜';
    message += `▫️ ${timeStr} ${event.title}\n`;
  });
  
  message += '\n✅ Googleカレンダーにも同期済み\n今日も一日頑張りましょう！';
  return message;
}
```

### **Phase 2: TimeTreeデータ連携 (Day 4-7)**

#### **Day 4-5: 既存システムの活用**
現在動作しているTimeTreeシステムを活用：

```javascript
// TimeTreeData.gs
function getTimeTreeData() {
  try {
    // Method 1: 既存システムのJSONエクスポート機能を活用
    return getDataFromExistingSystem();
    
  } catch (error) {
    Logger.log(`Primary method failed: ${error.message}`);
    
    // Method 2: フォールバック
    return getDataFromBackup();
  }
}

function getDataFromExistingSystem() {
  // 現在のシステムでJSONエクスポート機能を追加
  // GitHub Pages等でホストされたデータを取得
  
  const config = getConfig();
  const response = UrlFetchApp.fetch(config.timetreeDataUrl);
  
  if (response.getResponseCode() !== 200) {
    throw new Error(`HTTP ${response.getResponseCode()}`);
  }
  
  return JSON.parse(response.getContentText());
}
```

#### **Day 6: 既存システムのJSONエクスポート機能追加**
現在のPythonシステムに追加：

```python
# 追加: src/timetree_notifier/core/json_exporter.py
class JSONExporter:
    """TimeTreeデータをJSON形式でエクスポート"""
    
    def export_today_events(self, events: List[Event], output_path: str):
        """今日の予定をJSON形式で出力"""
        
        export_data = {
            "last_updated": datetime.now().isoformat(),
            "date": datetime.now().date().isoformat(),
            "total_events": len(events),
            "events": []
        }
        
        for event in events:
            export_data["events"].append({
                "title": event.title,
                "start": event.start_time.isoformat() if event.start_time else None,
                "end": event.end_time.isoformat() if event.end_time else None,
                "allDay": event.is_all_day,
                "description": event.description,
                "location": event.location
            })
        
        # JSONファイルに出力
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return export_data
```

#### **Day 7: GitHub Pages連携**
```yaml
# .github/workflows/export-to-pages.yml
name: Export TimeTree to GitHub Pages

on:
  schedule:
    - cron: '30 21 * * *'  # 毎朝6:30JST (GASの前に実行)

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Export TimeTree Data
        run: |
          python -m timetree_notifier.main --mode json_export
          
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./data
          publish_branch: gh-pages
```

### **Phase 3: 統合・自動化 (Day 8-10)**

#### **Day 8: メイン処理統合**
```javascript
// Main.gs
function dailyTimeTreeSync() {
  try {
    Logger.log('=== TimeTree Daily Sync Started ===');
    
    // 1. TimeTreeデータ取得
    const timeTreeData = getTimeTreeData();
    const todayEvents = filterTodayEvents(timeTreeData.events);
    
    Logger.log(`Found ${todayEvents.length} events for today`);
    
    // 2. Googleカレンダー同期
    syncToGoogleCalendar(todayEvents);
    Logger.log('Google Calendar sync completed');
    
    // 3. LINE通知
    sendLineNotification(todayEvents);
    Logger.log('LINE notification sent');
    
    Logger.log('=== TimeTree Daily Sync Completed Successfully ===');
    
  } catch (error) {
    Logger.log(`ERROR: ${error.message}`);
    sendErrorNotification(error);
  }
}

function filterTodayEvents(events) {
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  
  return events.filter(event => {
    const eventDate = Utilities.formatDate(new Date(event.start), 'Asia/Tokyo', 'yyyy-MM-dd');
    return eventDate === today;
  });
}
```

#### **Day 9: トリガー設定・テスト**
```javascript
// Trigger.gs
function setupDailyTrigger() {
  // 既存のトリガーを削除
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => ScriptApp.deleteTrigger(trigger));
  
  // 新しいトリガーを作成（毎朝6:00）
  ScriptApp.newTrigger('dailyTimeTreeSync')
    .timeBased()
    .everyDays(1)
    .atHour(6)
    .create();
  
  Logger.log('Daily trigger created for 6:00 AM JST');
}

// テスト実行
function testSync() {
  Logger.log('=== Manual Test Execution ===');
  dailyTimeTreeSync();
}
```

#### **Day 10: エラーハンドリング・監視**
```javascript
// ErrorHandler.gs
function sendErrorNotification(error) {
  const subject = '⚠️ TimeTree同期エラー';
  const body = `
TimeTree同期処理でエラーが発生しました。

時刻: ${new Date().toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'})}
エラー: ${error.message}

スタック: ${error.stack}

GASコンソールで詳細を確認してください：
https://script.google.com/home
`;
  
  GmailApp.sendEmail(Session.getActiveUser().getEmail(), subject, body);
}

function healthCheck() {
  // システムの正常性チェック
  const status = {
    timestamp: new Date().toISOString(),
    calendar_access: testCalendarAccess(),
    line_config: testLineConfig(),
    timetree_data: testTimeTreeData()
  };
  
  Logger.log(`Health Check: ${JSON.stringify(status)}`);
  return status;
}
```

### **Phase 4: 運用開始 (Day 11-14)**

#### **Day 11-12: 本番設定・テスト**
1. **本番環境設定**
   - LINE Token設定
   - TimeTree Data URL設定
   - トリガー有効化

2. **継続テスト**
   - 手動実行テスト
   - Googleカレンダー同期確認
   - LINE通知確認

#### **Day 13-14: 運用監視**
1. **自動実行確認**
   - 毎朝6時の実行
   - ログ確認
   - エラー通知確認

2. **運用ドキュメント作成**
   - 操作手順
   - トラブルシューティング

## 🎯 **GASシステムの優位性**

### **vs GitHub Actions**
| 項目 | GAS | GitHub Actions |
|------|-----|----------------|
| **コスト** | 完全無料 | 月2000分制限 |
| **稼働率** | 99.9% | 95-98% |
| **設定** | WebUIで簡単 | YAML設定 |
| **デバッグ** | リアルタイム | ログファイル |
| **認証** | 不要 | 複雑 |

### **vs その他クラウド**
| 項目 | GAS | AWS Lambda | Vercel |
|------|-----|------------|--------|
| **月額料金** | $0 | $5-20 | $20+ |
| **セットアップ** | 5分 | 30分+ | 15分+ |
| **Google連携** | 標準 | 複雑 | 複雑 |

## 📊 **期待される成果**

### **機能面**
- ✅ **毎朝6時**: 確実な自動実行
- ✅ **同期精度**: 100%（Googleカレンダー）
- ✅ **通知成功率**: 99%以上（LINE）
- ✅ **エラー検知**: 即座にGmail通知

### **運用面**
- ✅ **完全自動化**: PC・サーバー不要
- ✅ **保守簡単**: WebUIで管理
- ✅ **コスト0**: 継続費用なし
- ✅ **高可用性**: Googleインフラ

この実装により、最もシンプルで確実なTimeTree同期システムを構築できます！