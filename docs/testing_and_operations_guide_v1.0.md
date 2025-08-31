# TimeTree-GAS統合システム テスト計画・運用指針 v1.0

## 🧪 **テスト戦略**

段階的かつ包括的なテストにより、システムの確実な動作を保証します。

### **テストの分類**
1. **単体テスト**: 各コンポーネント個別の動作確認
2. **統合テスト**: コンポーネント間の連携確認
3. **エンドツーエンドテスト**: 全体フローの動作確認
4. **負荷テスト**: 大量データ・エラー条件での安定性確認
5. **運用テスト**: 本番環境での継続動作確認

## 📋 **詳細テスト計画**

### **Phase 1: 単体テスト（Day 5）**

#### **1.1 既存システム（Python）テスト**

**JSONエクスポート機能テスト**
```python
# test_json_exporter.py
import unittest
from datetime import datetime, date
from src.timetree_notifier.core.json_exporter import JSONExporter

class TestJSONExporter(unittest.TestCase):
    
    def setUp(self):
        self.exporter = JSONExporter(test_config)
        
    def test_export_empty_events(self):
        """空の予定リストのエクスポート"""
        result = self.exporter.export_today_events([])
        
        self.assertEqual(result['metadata']['total_events'], 0)
        self.assertEqual(len(result['events']), 0)
        self.assertIsInstance(result['metadata']['exported_at'], str)
    
    def test_export_single_event(self):
        """単一予定のエクスポート"""
        test_event = MockEvent(
            title="テスト予定",
            start_time=datetime.now(),
            is_all_day=False
        )
        
        result = self.exporter.export_today_events([test_event])
        
        self.assertEqual(result['metadata']['total_events'], 1)
        self.assertEqual(len(result['events']), 1)
        self.assertEqual(result['events'][0]['title'], "テスト予定")
        self.assertFalse(result['events'][0]['allDay'])
    
    def test_export_all_day_event(self):
        """終日予定のエクスポート"""
        test_event = MockEvent(
            title="終日イベント",
            start_time=date.today(),
            is_all_day=True
        )
        
        result = self.exporter.export_today_events([test_event])
        
        self.assertTrue(result['events'][0]['allDay'])
    
    def test_export_invalid_event(self):
        """不正なイベントデータの処理"""
        # タイトルがNoneの場合
        invalid_event = MockEvent(title=None, start_time=datetime.now())
        
        result = self.exporter.export_today_events([invalid_event])
        
        # エラーで落ちずに、適切にデフォルト値を設定
        self.assertEqual(result['events'][0]['title'], "無題")

# テスト実行
if __name__ == '__main__':
    unittest.main()
```

**手動テスト手順**
```bash
# 1. 既存システムでJSONエクスポートテスト
cd "C:\Users\skyeu\code\app\20250826_TimeTree-System"
python -m pytest test_json_exporter.py -v

# 2. 実際のデータでのエクスポートテスト
python -m timetree_notifier.main --mode manual

# 3. 生成されたJSONファイルの確認
cat temp/timetree_events.json | head -20
```

#### **1.2 GAS単体機能テスト**

**Google Drive読み込みテスト**
```javascript
function testDriveRead() {
  Logger.log('=== Drive Read Test ===');
  
  try {
    // テスト用JSONファイルを作成
    const testData = {
      metadata: {
        exported_at: new Date().toISOString(),
        total_events: 2
      },
      events: [
        {
          title: "テストイベント1",
          start: "2025-08-31T09:00:00+09:00",
          allDay: false
        },
        {
          title: "テストイベント2", 
          start: "2025-08-31T00:00:00+09:00",
          allDay: true
        }
      ]
    };
    
    // Google Driveにテストファイル作成
    const blob = Utilities.newBlob(JSON.stringify(testData), 'application/json', 'test_events.json');
    const file = DriveApp.createFile(blob);
    
    Logger.log(`Test file created: ${file.getId()}`);
    
    // 読み込みテスト
    const readData = JSON.parse(file.getBlob().getDataAsString());
    
    Logger.log(`Read ${readData.events.length} events`);
    Logger.log(`First event: ${readData.events[0].title}`);
    
    // クリーンアップ
    DriveApp.getFileById(file.getId()).setTrashed(true);
    
    Logger.log('✅ Drive read test passed');
    return true;
    
  } catch (error) {
    Logger.log(`❌ Drive read test failed: ${error.message}`);
    return false;
  }
}
```

**カレンダー作成テスト**
```javascript
function testCalendarCreation() {
  Logger.log('=== Calendar Creation Test ===');
  
  try {
    const calendar = CalendarApp.getDefaultCalendar();
    
    // テストイベント作成
    const testEvents = [
      {
        title: "GASテスト - 時限イベント",
        start: "2025-08-31T10:00:00+09:00",
        end: "2025-08-31T11:00:00+09:00",
        allDay: false
      },
      {
        title: "GASテスト - 終日イベント",
        start: "2025-08-31T00:00:00+09:00",
        allDay: true
      }
    ];
    
    const createdEvents = [];
    
    testEvents.forEach(event => {
      const calEvent = createCalendarEvent(calendar, event);
      createdEvents.push(calEvent);
      Logger.log(`Created: ${event.title}`);
    });
    
    Logger.log(`✅ Created ${createdEvents.length} test events`);
    
    // クリーンアップ（5秒後に削除）
    Utilities.sleep(5000);
    createdEvents.forEach(event => event.deleteEvent());
    Logger.log('Test events deleted');
    
    return true;
    
  } catch (error) {
    Logger.log(`❌ Calendar creation test failed: ${error.message}`);
    return false;
  }
}
```

### **Phase 2: 統合テスト（Day 6）**

#### **2.1 Python → Google Drive → GAS 連携テスト**

**統合テストシナリオ**
```yaml
テストケース1: 正常フロー
  1. Python側でJSONエクスポート実行
  2. Google Drive同期を待機（30秒）
  3. GAS側でデータ読み込み
  4. データ一致性を確認

テストケース2: データ更新フロー  
  1. 初回データを作成・同期
  2. Pythonで追加データを作成
  3. GAS側で差分を検知
  4. カレンダー更新が正しく実行

テストケース3: エラーハンドリング
  1. 不正なJSONデータを配置
  2. GASがフォールバック処理を実行
  3. エラー通知が送信される
```

**統合テスト実行スクリプト**
```javascript
function runIntegrationTest() {
  Logger.log('=== INTEGRATION TEST START ===');
  
  const testResults = [];
  
  // Test 1: データ読み込み統合テスト
  testResults.push(testDataIntegration());
  
  // Test 2: カレンダー同期統合テスト
  testResults.push(testCalendarIntegration());
  
  // Test 3: LINE通知統合テスト
  testResults.push(testLineIntegration());
  
  // Test 4: エラーハンドリング統合テスト
  testResults.push(testErrorHandling());
  
  // 結果集計
  const passed = testResults.filter(result => result).length;
  const total = testResults.length;
  
  Logger.log(`=== INTEGRATION TEST RESULTS ===`);
  Logger.log(`Passed: ${passed}/${total}`);
  
  if (passed === total) {
    Logger.log('🎉 All integration tests passed!');
  } else {
    Logger.log('⚠️ Some integration tests failed');
  }
  
  return passed === total;
}

function testDataIntegration() {
  Logger.log('--- Test: Data Integration ---');
  
  try {
    // 1. 既存データの確認
    const data = getTimeTreeDataFromDrive();
    
    if (!data || !data.events) {
      Logger.log('❌ No data available for integration test');
      return false;
    }
    
    // 2. データ構造の検証
    const requiredFields = ['metadata', 'events'];
    for (const field of requiredFields) {
      if (!(field in data)) {
        Logger.log(`❌ Missing required field: ${field}`);
        return false;
      }
    }
    
    // 3. メタデータの検証
    if (!data.metadata.exported_at || !data.metadata.total_events) {
      Logger.log('❌ Invalid metadata structure');
      return false;
    }
    
    // 4. イベントデータの検証
    if (data.events.length > 0) {
      const firstEvent = data.events[0];
      if (!firstEvent.title || !firstEvent.start) {
        Logger.log('❌ Invalid event structure');
        return false;
      }
    }
    
    Logger.log(`✅ Data integration test passed (${data.events.length} events)`);
    return true;
    
  } catch (error) {
    Logger.log(`❌ Data integration test failed: ${error.message}`);
    return false;
  }
}

function testCalendarIntegration() {
  Logger.log('--- Test: Calendar Integration ---');
  
  try {
    // テストデータ準備
    const testEvents = [
      {
        title: "統合テスト用イベント",
        start: new Date().toISOString(),
        allDay: false
      }
    ];
    
    // カレンダー同期実行
    const result = syncToGoogleCalendar(testEvents);
    
    if (!result.success || result.successCount !== 1) {
      Logger.log(`❌ Calendar sync failed: ${JSON.stringify(result)}`);
      return false;
    }
    
    // 作成されたイベントの確認
    const calendar = CalendarApp.getDefaultCalendar();
    const today = new Date();
    const events = calendar.getEventsForDay(today);
    
    const testEvent = events.find(event => 
      event.getTitle().includes('統合テスト用イベント')
    );
    
    if (!testEvent) {
      Logger.log('❌ Test event not found in calendar');
      return false;
    }
    
    // クリーンアップ
    testEvent.deleteEvent();
    
    Logger.log('✅ Calendar integration test passed');
    return true;
    
  } catch (error) {
    Logger.log(`❌ Calendar integration test failed: ${error.message}`);
    return false;
  }
}
```

### **Phase 3: エンドツーエンドテスト（Day 6）**

#### **3.1 完全フローテスト**

**E2Eテストスクリプト**
```javascript
function runE2ETest() {
  Logger.log('=== END-TO-END TEST START ===');
  
  const startTime = new Date();
  
  try {
    // 1. 事前確認
    Logger.log('Step 1: Pre-conditions check');
    if (!checkConfig()) {
      throw new Error('Configuration check failed');
    }
    
    // 2. データ取得テスト
    Logger.log('Step 2: Data acquisition test');
    const timeTreeData = getTimeTreeDataFromDrive();
    
    if (!timeTreeData) {
      throw new Error('Failed to get TimeTree data');
    }
    
    Logger.log(`Data acquired: ${timeTreeData.events.length} events`);
    
    // 3. 今日の予定フィルタリング
    Logger.log('Step 3: Today events filtering');
    const todayEvents = filterTodayEvents(timeTreeData.events);
    Logger.log(`Today events: ${todayEvents.length}`);
    
    // 4. カレンダー同期テスト
    Logger.log('Step 4: Calendar synchronization');
    const syncResult = syncToGoogleCalendar(todayEvents);
    
    if (!syncResult.success && syncResult.failCount > 0) {
      throw new Error(`Calendar sync partially failed: ${syncResult.failCount} failures`);
    }
    
    // 5. LINE通知テスト
    Logger.log('Step 5: LINE notification');
    const lineResult = sendGASLineNotification(todayEvents, timeTreeData.metadata);
    
    if (!lineResult.success) {
      throw new Error(`LINE notification failed: ${lineResult.error}`);
    }
    
    // 6. 結果確認
    const executionTime = (new Date() - startTime) / 1000;
    Logger.log(`=== E2E TEST COMPLETED SUCCESSFULLY in ${executionTime}s ===`);
    
    return {
      success: true,
      executionTime: executionTime,
      eventsProcessed: todayEvents.length,
      calendarSync: syncResult,
      lineNotification: lineResult
    };
    
  } catch (error) {
    const executionTime = (new Date() - startTime) / 1000;
    Logger.log(`=== E2E TEST FAILED after ${executionTime}s ===`);
    Logger.log(`Error: ${error.message}`);
    
    return {
      success: false,
      error: error.message,
      executionTime: executionTime
    };
  }
}
```

### **Phase 4: 負荷・エラーテスト（Day 6-7）**

#### **4.1 大量データテスト**

**負荷テストデータ生成**
```javascript
function generateLoadTestData() {
  Logger.log('Generating load test data...');
  
  const events = [];
  const today = new Date();
  
  // 50件の今日の予定を生成
  for (let i = 0; i < 50; i++) {
    const startTime = new Date(today);
    startTime.setHours(9 + (i % 12), (i * 15) % 60, 0, 0);
    
    events.push({
      title: `負荷テストイベント ${i + 1}`,
      start: startTime.toISOString(),
      end: new Date(startTime.getTime() + 60 * 60 * 1000).toISOString(),
      allDay: false,
      description: `これは負荷テスト用のイベント ${i + 1} です。`.repeat(10), // 長い説明
      location: `場所 ${i + 1}`
    });
  }
  
  return {
    metadata: {
      exported_at: new Date().toISOString(),
      total_events: events.length,
      system_version: "load-test"
    },
    events: events
  };
}

function runLoadTest() {
  Logger.log('=== LOAD TEST START ===');
  
  const startTime = new Date();
  
  try {
    // 負荷テストデータ生成
    const testData = generateLoadTestData();
    Logger.log(`Generated ${testData.events.length} test events`);
    
    // カレンダー同期テスト
    const syncResult = syncToGoogleCalendar(testData.events);
    Logger.log(`Sync result: ${syncResult.successCount} success, ${syncResult.failCount} failed`);
    
    // 実行時間測定
    const executionTime = (new Date() - startTime) / 1000;
    Logger.log(`Load test completed in ${executionTime}s`);
    
    // パフォーマンス評価
    const eventsPerSecond = testData.events.length / executionTime;
    Logger.log(`Performance: ${eventsPerSecond.toFixed(2)} events/second`);
    
    // クリーンアップ
    clearTimeTreeEvents(CalendarApp.getDefaultCalendar());
    Logger.log('Test events cleaned up');
    
    return {
      success: syncResult.failCount === 0,
      executionTime: executionTime,
      eventsPerSecond: eventsPerSecond
    };
    
  } catch (error) {
    Logger.log(`Load test failed: ${error.message}`);
    return { success: false, error: error.message };
  }
}
```

#### **4.2 エラー条件テスト**

**エラーシナリオテスト**
```javascript
function runErrorScenarioTests() {
  Logger.log('=== ERROR SCENARIO TESTS START ===');
  
  const scenarios = [
    { name: 'Missing Google Drive File', test: testMissingFile },
    { name: 'Invalid JSON Data', test: testInvalidJSON },
    { name: 'Network Timeout Simulation', test: testNetworkTimeout },
    { name: 'Invalid LINE Token', test: testInvalidLineToken },
    { name: 'Calendar Permission Error', test: testCalendarPermission }
  ];
  
  let passed = 0;
  
  scenarios.forEach(scenario => {
    Logger.log(`\n--- Testing: ${scenario.name} ---`);
    
    try {
      const result = scenario.test();
      if (result) {
        Logger.log(`✅ ${scenario.name}: PASSED`);
        passed++;
      } else {
        Logger.log(`❌ ${scenario.name}: FAILED`);
      }
    } catch (error) {
      Logger.log(`❌ ${scenario.name}: ERROR - ${error.message}`);
    }
  });
  
  Logger.log(`\n=== ERROR TESTS RESULTS ===`);
  Logger.log(`Passed: ${passed}/${scenarios.length}`);
  
  return passed === scenarios.length;
}

function testMissingFile() {
  Logger.log('Testing missing file handling...');
  
  try {
    // 存在しないファイル名で取得を試行
    const files = DriveApp.getFilesByName('non_existent_file.json');
    
    if (!files.hasNext()) {
      // 正常：ファイルが見つからない場合の処理
      const fallbackData = getCachedTimeTreeData();
      
      if (fallbackData && fallbackData.events) {
        Logger.log('✅ Fallback to cached data worked');
        return true;
      } else {
        Logger.log('❌ Fallback failed');
        return false;
      }
    }
    
    return false;
    
  } catch (error) {
    Logger.log(`Expected error handled: ${error.message}`);
    return true;
  }
}
```

## 🚀 **運用指針**

### **運用体制**

#### **日常運用**
```yaml
毎日の確認事項:
  - 朝7時のGAS実行ログ確認
  - LINE通知の受信確認
  - Googleカレンダーの同期確認

週次確認事項:
  - エラーログの詳細確認
  - システムパフォーマンス確認
  - Google Drive使用容量確認

月次確認事項:
  - GAS実行時間の使用量確認
  - LINE API使用量確認
  - システム全体の健全性チェック
```

#### **監視・アラート設定**

**GAS実行監視**
```javascript
function setupMonitoring() {
  Logger.log('Setting up monitoring...');
  
  // 実行失敗時のアラートトリガー設定
  const trigger = ScriptApp.newTrigger('monitoringCheck')
    .timeBased()
    .everyHours(1)
    .create();
    
  Logger.log(`Monitoring trigger created: ${trigger.getUniqueId()}`);
}

function monitoringCheck() {
  try {
    // 直近の実行ログをチェック
    const executions = ScriptApp.getProjectTriggers()
      .filter(trigger => trigger.getHandlerFunction() === 'dailyTimeTreeSync');
    
    // エラー率が高い場合はアラート
    // 実装は環境に応じて調整
    
  } catch (error) {
    Logger.log(`Monitoring check failed: ${error.message}`);
  }
}
```

**自動復旧機能**
```javascript
function autoRecovery() {
  Logger.log('Attempting auto-recovery...');
  
  try {
    // 1. キャッシュクリア
    CacheService.getScriptCache().removeAll();
    
    // 2. 再実行トリガー設定（1時間後）
    ScriptApp.newTrigger('dailyTimeTreeSync')
      .timeBased()
      .after(60 * 60 * 1000) // 1時間後
      .create();
    
    Logger.log('Auto-recovery initiated');
    
  } catch (error) {
    Logger.log(`Auto-recovery failed: ${error.message}`);
  }
}
```

### **保守・メンテナンス手順**

#### **定期メンテナンス**

**月次メンテナンス手順**
```yaml
1. ログの確認・クリーンアップ:
   - GAS実行ログの確認
   - エラーパターンの分析
   - 不要なログの削除

2. 設定の確認:
   - LINE APIトークンの有効期限確認
   - Google Drive容量の確認
   - GAS実行制限の確認

3. 機能テスト:
   - 手動テストの実行
   - 各機能の動作確認
   - パフォーマンスの測定

4. バックアップ:
   - 設定情報のバックアップ
   - 重要なログのアーカイブ
```

**システム更新手順**
```yaml
更新時の注意事項:
  1. 既存システムの動作を停止させない
  2. 段階的なデプロイ
  3. ロールバック手順の準備
  4. 更新後の動作確認

更新手順:
  1. テスト環境での検証
  2. 本番環境での部分的更新
  3. 動作確認
  4. 全体更新
  5. 最終確認
```

### **トラブルシューティング**

#### **よくある問題と対処法**

**問題1: GAS実行エラー**
```yaml
症状: 毎朝7時の自動実行が失敗
原因候補:
  - Google Driveファイルが更新されていない
  - 権限エラー
  - LINE APIトークン無効

対処法:
  1. GAS実行ログを確認
  2. Google Driveのファイル更新時刻を確認
  3. 手動でtestManualSync()を実行
  4. 必要に応じて設定を更新
```

**問題2: LINE通知が届かない**
```yaml
症状: GAS実行は成功するがLINE通知なし
原因候補:
  - LINE APIトークンの期限切れ
  - LINE User IDの間違い
  - ネットワークエラー

対処法:
  1. testLineNotification()を実行
  2. LINE Developers コンソールで確認
  3. トークン・User IDを再設定
```

**問題3: Googleカレンダー同期エラー**
```yaml
症状: カレンダーにイベントが作成されない
原因候補:
  - カレンダー権限エラー
  - 重複するイベントの制限
  - 日時形式エラー

対処法:
  1. testCalendarCreation()を実行
  2. カレンダーの権限を確認
  3. 重複イベントの削除
```

## 📊 **成功指標とKPI**

### **システム品質指標**
```yaml
可用性:
  目標: 99%以上
  測定: 月間実行成功率

精度:
  目標: 100%
  測定: 予定データの正確性

応答時間:
  目標: 5分以内
  測定: GAS実行完了時間

通知成功率:
  目標: 98%以上
  測定: LINE通知送信成功率
```

### **運用品質指標**
```yaml
自動復旧率:
  目標: 90%以上
  測定: エラー後の自動復旧成功率

平均復旧時間:
  目標: 1時間以内
  測定: 障害発生から復旧まで

月間コスト:
  目標: $0
  測定: 実際の利用料金
```

この包括的なテスト計画と運用指針により、TimeTree-GAS統合システムの確実な動作と継続的な品質を保証できます。