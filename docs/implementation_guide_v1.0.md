# TimeTree-GAS統合システム 実装ガイド v1.0

## 🚀 **実装概要**

**1週間で完成**する段階的実装計画。既存システムを最大限活用し、リスクを最小化しながら確実に構築します。

## 📅 **詳細実装スケジュール**

### **Day 1-2: 既存システム改良**

#### **Day 1: JSONエクスポート機能実装**

**1. 新ファイル作成**
```bash
cd "C:\Users\skyeu\code\app\20250826_TimeTree-System"
mkdir -p src/timetree_notifier/core
touch src/timetree_notifier/core/json_exporter.py
```

**2. JSONエクスポートクラス実装**
```python
# src/timetree_notifier/core/json_exporter.py
import json
import logging
from datetime import datetime, date
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)

class JSONExporter:
    """GAS連携用JSONエクスポート機能"""
    
    def __init__(self, config):
        self.config = config
        self.output_path = Path("temp/timetree_events.json")
        
    def export_today_events(self, events: List) -> dict:
        """今日の予定をGAS用JSON形式でエクスポート"""
        
        export_data = {
            "metadata": {
                "exported_at": datetime.now().isoformat(),
                "date": date.today().isoformat(),
                "total_events": len(events),
                "system_version": "2.1-GAS",
                "export_source": "TimeTree-Python"
            },
            "events": []
        }
        
        # イベントデータの変換
        for event in events:
            try:
                event_data = {
                    "title": event.title or "無題",
                    "start": event.start_time.isoformat() if event.start_time else None,
                    "end": event.end_time.isoformat() if event.end_time else None,
                    "allDay": getattr(event, 'is_all_day', False),
                    "description": getattr(event, 'description', '') or "",
                    "location": getattr(event, 'location', '') or ""
                }
                export_data["events"].append(event_data)
            except Exception as e:
                logger.warning(f"Failed to export event {event}: {e}")
                continue
        
        # JSONファイル出力
        self._write_json_file(export_data)
        
        logger.info(f"Exported {len(export_data['events'])} events to {self.output_path}")
        return export_data
    
    def _write_json_file(self, data: dict):
        """JSONファイルを安全に書き込み"""
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 一時ファイルに書き込み後、rename（原子的操作）
            temp_path = self.output_path.with_suffix('.tmp')
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            temp_path.replace(self.output_path)
            
        except Exception as e:
            logger.error(f"Failed to write JSON file: {e}")
            raise
```

**3. 既存システム統合**
```python
# src/timetree_notifier/core/daily_notifier.py に追加
from .json_exporter import JSONExporter

class DailySummaryNotifier:
    def __init__(self, config: Config):
        # ... 既存の初期化コード
        self.json_exporter = JSONExporter(config)  # この行を追加
        
    async def send_daily_summary(self, target_date: Optional[date] = None) -> bool:
        """毎朝の予定サマリー送信（GAS連携対応版）"""
        try:
            # ... 既存のTimeTree取得処理
            
            # 今日の予定を抽出
            today_events = self._extract_today_events(export_result.output_file, target_date)
            
            # ★★★ GAS用JSONエクスポートを追加 ★★★
            try:
                self.json_exporter.export_today_events(today_events)
                logger.info("JSON export for GAS completed")
            except Exception as e:
                logger.warning(f"JSON export failed (non-critical): {e}")
            
            # 日次サマリー生成（既存処理）
            summary = self._generate_daily_summary(target_date, today_events)
            
            # LINE通知送信（既存処理 - フォールバック用として継続）
            result = await self.line_notifier.send_message(summary.message)
            
            if result.success:
                logger.info(f"Daily summary sent successfully for {target_date}")
                self._backup_ics_file(export_result.output_file)
            else:
                logger.error(f"Failed to send daily summary: {result.error_message}")
            
            return result.success
            
        except Exception as e:
            logger.error(f"Unexpected error in daily summary: {e}")
            return await self._send_error_notification(target_date, str(e))
```

#### **Day 2: Google Drive同期設定**

**1. Google Drive デスクトップアプリのインストール**
- https://www.google.com/drive/download/ からダウンロード
- インストール後、Googleアカウントでサインイン

**2. 同期フォルダ設定**
```
ローカルフォルダ: 
C:\Users\[username]\code\app\20250826_TimeTree-System\temp\

Google Drive フォルダ: 
/TimeTree-System/data/
```

**3. 同期確認テスト**
```bash
# テスト用ファイル作成
echo '{"test": "sync works"}' > temp/test_sync.json

# Google Driveで確認
# ブラウザで https://drive.google.com を開き、
# TimeTree-System/data/test_sync.json が同期されているか確認
```

### **Day 3-4: GAS実装**

#### **Day 3: GASプロジェクト作成と基本実装**

**1. GASプロジェクト作成**
1. https://script.google.com にアクセス
2. 「新しいプロジェクト」をクリック
3. プロジェクト名を `TimeTree-GAS-Integration` に変更

**2. 権限設定（appsscript.json）**
```json
{
  "timeZone": "Asia/Tokyo",
  "dependencies": {
    "enabledAdvancedServices": []
  },
  "oauthScopes": [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/script.external_request"
  ]
}
```

**3. Code.gs（メイン処理）作成**
```javascript
/**
 * TimeTree-GAS統合システム v1.0
 * メイン処理ファイル
 */

/**
 * 毎朝の自動実行関数
 */
function dailyTimeTreeSync() {
  const startTime = new Date();
  
  try {
    Logger.log('=== TimeTree-GAS Sync Started ===');
    Logger.log(`Execution time: ${startTime.toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'})}`);
    
    // 1. Google DriveからTimeTreeデータを取得
    const timeTreeData = getTimeTreeDataFromDrive();
    
    if (!timeTreeData || !timeTreeData.events || timeTreeData.events.length === 0) {
      Logger.log('No events found or data not available');
      sendNoEventsNotification();
      return;
    }
    
    // 2. 今日の予定のみフィルタ
    const todayEvents = filterTodayEvents(timeTreeData.events);
    Logger.log(`Found ${todayEvents.length} events for today`);
    
    // 3. Googleカレンダーに同期
    const syncResult = syncToGoogleCalendar(todayEvents);
    Logger.log(`Calendar sync: ${syncResult.successCount} success, ${syncResult.failCount} failed`);
    
    // 4. LINE通知送信
    const lineResult = sendGASLineNotification(todayEvents, timeTreeData.metadata);
    Logger.log(`LINE notification: ${lineResult.success ? 'SUCCESS' : 'FAILED'}`);
    
    // 5. 実行結果サマリー
    const executionTime = (new Date() - startTime) / 1000;
    Logger.log(`=== Completed in ${executionTime.toFixed(2)}s ===`);
    
  } catch (error) {
    Logger.log(`FATAL ERROR: ${error.message}`);
    Logger.log(`Stack trace: ${error.stack}`);
    sendErrorNotification(error);
  }
}

/**
 * Google DriveからTimeTreeデータを取得
 */
function getTimeTreeDataFromDrive() {
  try {
    Logger.log('Fetching TimeTree data from Google Drive...');
    
    // Google Drive上のファイルを検索
    const fileName = 'timetree_events.json';
    const files = DriveApp.getFilesByName(fileName);
    
    if (!files.hasNext()) {
      throw new Error(`File not found in Google Drive: ${fileName}`);
    }
    
    const file = files.next();
    Logger.log(`Found file: ${file.getName()}, Last modified: ${file.getLastUpdated()}`);
    
    // ファイル内容を取得
    const content = file.getBlob().getDataAsString('UTF-8');
    const data = JSON.parse(content);
    
    // データ構造の検証
    if (!data.metadata || !data.events || !Array.isArray(data.events)) {
      throw new Error('Invalid JSON structure');
    }
    
    // データの鮮度チェック
    const exportTime = new Date(data.metadata.exported_at);
    const now = new Date();
    const minutesDiff = (now - exportTime) / (1000 * 60);
    
    Logger.log(`Data exported ${minutesDiff.toFixed(0)} minutes ago`);
    
    if (minutesDiff > 360) { // 6時間
      Logger.log('WARNING: Data is more than 6 hours old');
    }
    
    // キャッシュに保存
    cacheTimeTreeData(data);
    
    return data;
    
  } catch (error) {
    Logger.log(`Failed to get TimeTree data from Drive: ${error.message}`);
    
    // フォールバック: キャッシュデータを使用
    Logger.log('Attempting to use cached data...');
    return getCachedTimeTreeData();
  }
}

/**
 * 今日の予定のみフィルタリング
 */
function filterTodayEvents(events) {
  const today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');
  Logger.log(`Filtering events for date: ${today}`);
  
  const todayEvents = events.filter(event => {
    if (!event.start) {
      Logger.log(`Skipping event without start time: ${event.title}`);
      return false;
    }
    
    try {
      const eventDate = Utilities.formatDate(new Date(event.start), 'Asia/Tokyo', 'yyyy-MM-dd');
      return eventDate === today;
    } catch (e) {
      Logger.log(`Invalid date format for event: ${event.title} - ${event.start}`);
      return false;
    }
  });
  
  Logger.log(`Filtered to ${todayEvents.length} events for today`);
  return todayEvents;
}
```

#### **Day 4: カレンダー同期とLINE通知実装**

**Code.gs に追加**
```javascript
/**
 * Googleカレンダー同期処理
 */
function syncToGoogleCalendar(events) {
  try {
    Logger.log('Starting Google Calendar sync...');
    
    const calendar = CalendarApp.getDefaultCalendar();
    
    // 既存のTimeTree同期イベントをクリア
    const deletedCount = clearTimeTreeEvents(calendar);
    Logger.log(`Cleared ${deletedCount} existing TimeTree events`);
    
    let successCount = 0;
    let failCount = 0;
    
    // 新しいイベントを作成
    events.forEach((event, index) => {
      try {
        Logger.log(`Creating event ${index + 1}/${events.length}: ${event.title}`);
        
        const calendarEvent = createCalendarEvent(calendar, event);
        Logger.log(`✓ Created: ${event.title}`);
        successCount++;
        
      } catch (error) {
        Logger.log(`✗ Failed to create ${event.title}: ${error.message}`);
        failCount++;
      }
    });
    
    const result = {
      success: failCount === 0,
      successCount: successCount,
      failCount: failCount
    };
    
    Logger.log(`Calendar sync completed: ${successCount} success, ${failCount} failed`);
    return result;
    
  } catch (error) {
    Logger.log(`Calendar sync failed: ${error.message}`);
    return { success: false, error: error.message, successCount: 0, failCount: events.length };
  }
}

/**
 * カレンダーイベント作成
 */
function createCalendarEvent(calendar, event) {
  const title = `📱 ${event.title}`;
  const description = `📱 TimeTreeから自動同期\n\n${event.description || ''}`;
  const options = {
    description: description,
    location: event.location || ''
  };
  
  if (event.allDay) {
    Logger.log(`Creating all-day event: ${title}`);
    return calendar.createAllDayEvent(title, new Date(event.start), options);
  } else {
    const startTime = new Date(event.start);
    let endTime;
    
    if (event.end) {
      endTime = new Date(event.end);
    } else {
      // 終了時刻がない場合は1時間後に設定
      endTime = new Date(startTime.getTime() + 60 * 60 * 1000);
    }
    
    Logger.log(`Creating timed event: ${title} (${startTime.toLocaleTimeString()} - ${endTime.toLocaleTimeString()})`);
    return calendar.createEvent(title, startTime, endTime, options);
  }
}

/**
 * 既存のTimeTree同期イベントをクリア
 */
function clearTimeTreeEvents(calendar) {
  const today = new Date();
  const startOfDay = new Date(today);
  startOfDay.setHours(0, 0, 0, 0);
  
  const endOfDay = new Date(today);
  endOfDay.setHours(23, 59, 59, 999);
  
  Logger.log(`Clearing TimeTree events for ${Utilities.formatDate(today, 'Asia/Tokyo', 'yyyy-MM-dd')}`);
  
  const events = calendar.getEvents(startOfDay, endOfDay);
  let deletedCount = 0;
  
  events.forEach(event => {
    if (event.getTitle().startsWith('📱')) {
      Logger.log(`Deleting: ${event.getTitle()}`);
      event.deleteEvent();
      deletedCount++;
    }
  });
  
  return deletedCount;
}

/**
 * GAS版LINE通知
 */
function sendGASLineNotification(events, metadata) {
  try {
    Logger.log('Sending LINE notification...');
    
    const config = getConfig();
    
    if (!config.lineToken || !config.lineUserId) {
      Logger.log('LINE configuration missing - skipping notification');
      return { success: false, reason: 'Missing LINE configuration' };
    }
    
    // メッセージ作成
    const message = createEnhancedDailyMessage(events, metadata);
    Logger.log(`Message length: ${message.length} characters`);
    
    // LINE API呼び出し
    const payload = {
      to: config.lineUserId,
      messages: [{
        type: 'text',
        text: message
      }]
    };
    
    const response = UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.lineToken}`
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    const responseCode = response.getResponseCode();
    Logger.log(`LINE API response: ${responseCode}`);
    
    if (responseCode === 200) {
      Logger.log('LINE notification sent successfully');
      return { success: true };
    } else {
      const errorText = response.getContentText();
      Logger.log(`LINE API error: ${errorText}`);
      throw new Error(`HTTP ${responseCode}: ${errorText}`);
    }
    
  } catch (error) {
    Logger.log(`LINE notification failed: ${error.message}`);
    return { success: false, error: error.message };
  }
}

/**
 * 拡張版日次メッセージ作成
 */
function createEnhancedDailyMessage(events, metadata) {
  const today = new Date();
  const dateStr = Utilities.formatDate(today, 'Asia/Tokyo', 'M月d日');
  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  const weekday = weekdays[today.getDay()];
  
  let message = `🌅 おはようございます！\n\n📅 ${dateStr}（${weekday}）`;
  
  if (events.length === 0) {
    message += 'の予定はありません。\n\nゆっくりとした一日をお過ごしください！';
  } else {
    message += `の予定 ${events.length}件\n\n`;
    
    // 予定リスト（最大8件表示）
    events.slice(0, 8).forEach((event, index) => {
      const timeStr = formatEventTimeString(event);
      message += `▫️ ${timeStr} ${event.title}\n`;
    });
    
    // 省略表示
    if (events.length > 8) {
      message += `\n... 他${events.length - 8}件`;
    }
    
    message += '\n✅ Googleカレンダーにも同期済み';
  }
  
  // システム情報追加
  if (metadata && metadata.exported_at) {
    const exportTime = new Date(metadata.exported_at);
    const timeStr = Utilities.formatDate(exportTime, 'Asia/Tokyo', 'HH:mm');
    message += `\n\n📡 ${timeStr}更新 | GAS-v1.0`;
  } else {
    message += '\n\n📡 GAS-v1.0';
  }
  
  return message;
}

/**
 * イベント時刻フォーマット
 */
function formatEventTimeString(event) {
  if (event.allDay) {
    return '終日';
  }
  
  try {
    const start = new Date(event.start);
    const startStr = Utilities.formatDate(start, 'Asia/Tokyo', 'H:mm');
    
    if (event.end) {
      const end = new Date(event.end);
      const endStr = Utilities.formatDate(end, 'Asia/Tokyo', 'H:mm');
      if (startStr !== endStr) {
        return `${startStr}-${endStr}`;
      }
    }
    
    return `${startStr}〜`;
  } catch (e) {
    return '時刻不明';
  }
}
```

### **Day 5-6: 設定・エラー処理・テスト**

#### **Day 5: 設定とエラー処理**

**Config.gs 作成**
```javascript
/**
 * 設定管理
 */
function getConfig() {
  const properties = PropertiesService.getScriptProperties();
  
  return {
    lineToken: properties.getProperty('LINE_CHANNEL_ACCESS_TOKEN'),
    lineUserId: properties.getProperty('LINE_USER_ID')
  };
}

/**
 * 初期設定（一度だけ実行）
 */
function setupConfig() {
  Logger.log('Setting up configuration...');
  
  const properties = PropertiesService.getScriptProperties();
  
  properties.setProperties({
    'LINE_CHANNEL_ACCESS_TOKEN': 'YOUR_LINE_CHANNEL_ACCESS_TOKEN_HERE',
    'LINE_USER_ID': 'YOUR_LINE_USER_ID_HERE'
  });
  
  Logger.log('Configuration setup completed');
  Logger.log('Please update the token and user ID with your actual values');
}

/**
 * 設定確認
 */
function checkConfig() {
  const config = getConfig();
  
  Logger.log('=== Configuration Check ===');
  Logger.log(`LINE Token: ${config.lineToken ? 'SET' : 'NOT SET'}`);
  Logger.log(`LINE User ID: ${config.lineUserId ? 'SET' : 'NOT SET'}`);
  
  if (!config.lineToken || !config.lineUserId) {
    Logger.log('⚠️ Please run setupConfig() and update your credentials');
    return false;
  }
  
  Logger.log('✅ Configuration is complete');
  return true;
}
```

**ErrorHandler.gs 作成**
```javascript
/**
 * エラー処理・通知
 */

/**
 * システムエラー通知
 */
function sendErrorNotification(error) {
  try {
    Logger.log('Sending error notification...');
    
    const subject = '⚠️ TimeTree-GAS システムエラー';
    const body = createErrorEmailBody(error);
    
    GmailApp.sendEmail(Session.getActiveUser().getEmail(), subject, body);
    Logger.log('Error notification sent via Gmail');
    
  } catch (gmailError) {
    Logger.log(`Failed to send error notification: ${gmailError.message}`);
    // フォールバック: コンソールに詳細出力
    Logger.log('=== ERROR DETAILS ===');
    Logger.log(`Error: ${error.message}`);
    Logger.log(`Stack: ${error.stack}`);
  }
}

/**
 * エラーメール本文作成
 */
function createErrorEmailBody(error) {
  const now = new Date();
  const timestamp = now.toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'});
  
  return `
TimeTree-GAS統合システムでエラーが発生しました。

■ エラー情報
時刻: ${timestamp}
エラー: ${error.message}

■ スタックトレース
${error.stack}

■ 対処方法
1. Google Driveで 'timetree_events.json' ファイルを確認
2. 既存のPythonシステムの動作状況を確認
3. GASコンソールで詳細ログを確認: https://script.google.com/home
4. LINE APIトークンの有効性を確認

■ システム情報
GAS Project: TimeTree-GAS-Integration
Version: v1.0
実行関数: dailyTimeTreeSync

自動復旧を試みますが、問題が継続する場合は手動で確認してください。
`;
}

/**
 * 予定がない場合の通知
 */
function sendNoEventsNotification() {
  Logger.log('Sending no-events notification...');
  
  const config = getConfig();
  
  if (!config.lineToken || !config.lineUserId) {
    Logger.log('Cannot send no-events notification: LINE config missing');
    return;
  }
  
  try {
    const message = createNoEventsMessage();
    
    const payload = {
      to: config.lineUserId,
      messages: [{ type: 'text', text: message }]
    };
    
    const response = UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.lineToken}`
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    if (response.getResponseCode() === 200) {
      Logger.log('No-events notification sent successfully');
    } else {
      Logger.log(`No-events notification failed: ${response.getContentText()}`);
    }
    
  } catch (error) {
    Logger.log(`Failed to send no-events notification: ${error.message}`);
  }
}

/**
 * 予定なしメッセージ作成
 */
function createNoEventsMessage() {
  const today = new Date();
  const dateStr = Utilities.formatDate(today, 'Asia/Tokyo', 'M月d日');
  const weekdays = ['日', '月', '火', '水', '木', '金', '土'];
  const weekday = weekdays[today.getDay()];
  
  return `🌅 おはようございます！\n\n📅 ${dateStr}（${weekday}）の予定はありません。\n\nゆっくりとした一日をお過ごしください！\n\n📡 GAS-v1.0`;
}

/**
 * キャッシュからのデータ取得
 */
function getCachedTimeTreeData() {
  try {
    Logger.log('Attempting to get cached TimeTree data...');
    
    const cache = CacheService.getScriptCache();
    const cachedData = cache.get('last_timetree_data');
    
    if (cachedData) {
      Logger.log('Using cached TimeTree data');
      const data = JSON.parse(cachedData);
      
      // キャッシュデータの時刻を確認
      const cacheTime = new Date(data.metadata.exported_at);
      const now = new Date();
      const hoursDiff = (now - cacheTime) / (1000 * 60 * 60);
      
      Logger.log(`Cached data is ${hoursDiff.toFixed(1)} hours old`);
      
      return data;
    } else {
      Logger.log('No cached data available');
    }
    
  } catch (error) {
    Logger.log(`Failed to get cached data: ${error.message}`);
  }
  
  // デフォルトの空データ
  return {
    metadata: {
      exported_at: new Date().toISOString(),
      date: Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd'),
      total_events: 0,
      system_version: "cache-fallback",
      export_source: "GAS-Cache"
    },
    events: []
  };
}

/**
 * データをキャッシュに保存
 */
function cacheTimeTreeData(data) {
  try {
    const cache = CacheService.getScriptCache();
    cache.put('last_timetree_data', JSON.stringify(data), 21600); // 6時間キャッシュ
    Logger.log('TimeTree data cached successfully');
    
  } catch (error) {
    Logger.log(`Failed to cache TimeTree data: ${error.message}`);
  }
}
```

#### **Day 6: 統合テストとトリガー設定**

**Test.gs 作成（テスト用）**
```javascript
/**
 * テスト用関数群
 */

/**
 * 手動テスト実行
 */
function testManualSync() {
  Logger.log('=== MANUAL TEST START ===');
  
  try {
    // 設定確認
    if (!checkConfig()) {
      Logger.log('Configuration check failed - please run setupConfig()');
      return;
    }
    
    // メイン処理実行
    dailyTimeTreeSync();
    
    Logger.log('=== MANUAL TEST COMPLETED ===');
    
  } catch (error) {
    Logger.log(`Test failed: ${error.message}`);
    Logger.log(`Stack: ${error.stack}`);
  }
}

/**
 * Google Drive接続テスト
 */
function testDriveConnection() {
  Logger.log('Testing Google Drive connection...');
  
  try {
    const fileName = 'timetree_events.json';
    const files = DriveApp.getFilesByName(fileName);
    
    if (files.hasNext()) {
      const file = files.next();
      Logger.log(`✅ Found file: ${file.getName()}`);
      Logger.log(`   Size: ${file.getSize()} bytes`);
      Logger.log(`   Last modified: ${file.getLastUpdated()}`);
      
      // ファイル内容の一部を確認
      const content = file.getBlob().getDataAsString('UTF-8');
      const data = JSON.parse(content);
      
      Logger.log(`   Events count: ${data.events ? data.events.length : 'N/A'}`);
      Logger.log(`   Export time: ${data.metadata ? data.metadata.exported_at : 'N/A'}`);
      
      return true;
    } else {
      Logger.log(`❌ File not found: ${fileName}`);
      Logger.log('Please check:');
      Logger.log('1. Google Drive sync is working');
      Logger.log('2. Python system has run and created the JSON file');
      Logger.log('3. File permissions are correct');
      return false;
    }
    
  } catch (error) {
    Logger.log(`Drive connection test failed: ${error.message}`);
    return false;
  }
}

/**
 * LINE通知テスト
 */
function testLineNotification() {
  Logger.log('Testing LINE notification...');
  
  const config = getConfig();
  
  if (!config.lineToken || !config.lineUserId) {
    Logger.log('❌ LINE configuration missing');
    return false;
  }
  
  const testMessage = `🧪 GASテスト通知\n\n時刻: ${new Date().toLocaleString('ja-JP', {timeZone: 'Asia/Tokyo'})}\n\nこの通知が届けば、GAS-LINE連携は正常に動作しています。`;
  
  try {
    const payload = {
      to: config.lineUserId,
      messages: [{ type: 'text', text: testMessage }]
    };
    
    const response = UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${config.lineToken}`
      },
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    });
    
    const responseCode = response.getResponseCode();
    
    if (responseCode === 200) {
      Logger.log('✅ LINE test notification sent successfully');
      return true;
    } else {
      Logger.log(`❌ LINE notification failed: HTTP ${responseCode}`);
      Logger.log(`Response: ${response.getContentText()}`);
      return false;
    }
    
  } catch (error) {
    Logger.log(`LINE test failed: ${error.message}`);
    return false;
  }
}

/**
 * 総合システムテスト
 */
function runSystemTest() {
  Logger.log('=== SYSTEM TEST START ===');
  
  const tests = [
    { name: 'Configuration Check', test: checkConfig },
    { name: 'Google Drive Connection', test: testDriveConnection },
    { name: 'LINE Notification', test: testLineNotification }
  ];
  
  let passed = 0;
  
  tests.forEach(({name, test}) => {
    Logger.log(`\n--- Testing: ${name} ---`);
    
    try {
      const result = test();
      if (result) {
        Logger.log(`✅ ${name}: PASSED`);
        passed++;
      } else {
        Logger.log(`❌ ${name}: FAILED`);
      }
    } catch (error) {
      Logger.log(`❌ ${name}: ERROR - ${error.message}`);
    }
  });
  
  Logger.log(`\n=== TEST RESULTS ===`);
  Logger.log(`Passed: ${passed}/${tests.length}`);
  
  if (passed === tests.length) {
    Logger.log('🎉 All tests passed! System is ready for deployment.');
  } else {
    Logger.log('⚠️ Some tests failed. Please fix issues before deployment.');
  }
}

/**
 * トリガー設定
 */
function setupDailyTrigger() {
  Logger.log('Setting up daily trigger...');
  
  try {
    // 既存のトリガーを削除
    const triggers = ScriptApp.getProjectTriggers();
    triggers.forEach(trigger => {
      if (trigger.getHandlerFunction() === 'dailyTimeTreeSync') {
        ScriptApp.deleteTrigger(trigger);
        Logger.log('Deleted existing trigger');
      }
    });
    
    // 新しいトリガーを作成（毎朝7時）
    const trigger = ScriptApp.newTrigger('dailyTimeTreeSync')
      .timeBased()
      .everyDays(1)
      .atHour(7)  // 7:00 AM JST
      .create();
    
    Logger.log(`✅ Daily trigger created: ${trigger.getUniqueId()}`);
    Logger.log('Function: dailyTimeTreeSync');
    Logger.log('Schedule: Every day at 7:00 AM JST');
    
  } catch (error) {
    Logger.log(`Failed to setup trigger: ${error.message}`);
  }
}
```

### **Day 7: 最終テストと運用開始**

**最終チェックリスト**
```
□ 1. 既存Pythonシステムが正常動作
□ 2. JSON出力ファイルが生成される
□ 3. Google Drive同期が機能
□ 4. GAS設定が完了
□ 5. LINE通知テストが成功
□ 6. Googleカレンダー同期テストが成功
□ 7. エラー処理テストが成功
□ 8. 日次トリガー設定完了
```

**最終テスト実行**
```javascript
// GASコンソールで実行
runSystemTest();        // 総合テスト
testManualSync();       // 手動同期テスト
setupDailyTrigger();    // 日次トリガー設定
```

これで1週間での実装が完了します！
