# TimeTree通知システム - 改訂版MVP設計書

## 改訂日: 2025年8月27日
## 前回分析レポート: [timetree_sow_analysis_report_20250826.md](work-reports/timetree_sow_analysis_report_20250826.md)

## 1. 改訂背景・主要な変更点

### 1.1 前回設計の問題点（要約）
- **高リスク**: TimeTree-Exporterのスクレイピング依存
- **過度な複雑さ**: 7コンポーネントによる複雑なアーキテクチャ
- **非現実的要件**: 99.5%稼働率などの実現困難な性能要件
- **法的リスク**: スクレイピングによる利用規約違反の可能性

### 1.2 新設計のアプローチ
- **安全第一**: スクレイピング完全排除
- **シンプル化**: 最小限の機能で確実に動作
- **手動ベース**: ユーザーが手動でICSファイルを配置
- **段階的開発**: MVP → 拡張版 → フル機能版

## 2. 改訂版システム要件（MVP）

### 2.1 機能要件
- **F001**: 指定フォルダのICSファイル監視
- **F002**: ファイル変更時の自動検出
- **F003**: ICSファイルからのイベント抽出
- **F004**: LINE Notifyによる変更通知
- **F005**: 基本的なエラーハンドリング
- **F006**: シンプルなログ出力

### 2.2 非機能要件
- **N001**: ファイル監視レスポンス: 5秒以内
- **N002**: LINE通知送信: 10秒以内
- **N003**: メモリ使用量: 50MB以内
- **N004**: 24時間連続動作対応

## 3. 新アーキテクチャ設計

### 3.1 シンプル化されたシステム構成

```
┌────────────────────────────────────────┐
│        TimeTree通知システム（MVP）         │
├────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐     │
│  │File Watcher │───▶│ICS Parser   │     │
│  │  (監視)      │    │  (解析)      │     │
│  └─────────────┘    └─────────────┘     │
│         │                   │           │
│         ▼                   ▼           │
│  ┌─────────────┐    ┌─────────────┐     │
│  │   Logger    │◀───│  Notifier   │     │
│  │   (記録)     │    │  (LINE)     │     │
│  └─────────────┘    └─────────────┘     │
└────────────────────────────────────────┘
```

### 3.2 データフロー（簡素化）

```
手動ICSエクスポート（ユーザー操作）
    ↓
指定フォルダにファイル配置
    ↓
ファイル変更検出（自動）
    ↓
ICS内容解析
    ↓
前回データとの差分比較
    ↓
変更あり？
    ↓ Yes          ↓ No
LINE通知送信        待機
    ↓               ↓
履歴更新            ↓
    ↓               ↓
ログ記録            ↓
    ↓_______________↓
ファイル監視継続
```

### 3.3 MVP版コンポーネント設計

#### 3.3.1 FileWatcher（ファイル監視）
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ICSFileWatcher(FileSystemEventHandler):
    """ICSファイルの変更を監視"""
    
    def __init__(self, processor):
        self.processor = processor
        
    def on_modified(self, event):
        """ファイル変更時の処理"""
        if not event.is_directory and event.src_path.endswith('.ics'):
            self.processor.process_file_change(event.src_path)
```

#### 3.3.2 ICSProcessor（ICS処理）
```python
from icalendar import Calendar

class ICSProcessor:
    """ICSファイルの解析と変更検出"""
    
    def __init__(self, notifier):
        self.notifier = notifier
        self.last_events = {}
        
    def process_file_change(self, file_path: str):
        """ファイル変更の処理"""
        events = self.parse_ics_file(file_path)
        changes = self.detect_changes(events)
        if changes:
            self.notifier.send_notification(changes)
            
    def parse_ics_file(self, file_path: str) -> list:
        """ICSファイルからイベント抽出"""
        
    def detect_changes(self, events: list) -> list:
        """前回データとの変更検出"""
```

#### 3.3.3 LineNotifier（LINE通知）
```python
import requests

class LineNotifier:
    """LINE Notifyによる通知送信"""
    
    def __init__(self, token: str):
        self.token = token
        self.api_url = "https://notify-api.line.me/api/notify"
        
    def send_notification(self, changes: list):
        """変更内容をLINEに通知"""
        message = self.format_message(changes)
        self.send_line_message(message)
        
    def format_message(self, changes: list) -> str:
        """通知メッセージのフォーマット"""
        
    def send_line_message(self, message: str):
        """LINE APIへの送信"""
```

## 4. MVP実装計画

### 4.1 開発フェーズ（簡素化版）

#### Phase 1: 基盤構築 (3日)
- **Day 1**: プロジェクト構造セットアップ
- **Day 2**: 基本設定・ログ機能
- **Day 3**: ファイル監視機能実装

#### Phase 2: コア機能実装 (4日)
- **Day 4**: ICS解析機能
- **Day 5**: 変更検出ロジック
- **Day 6**: LINE通知機能
- **Day 7**: 統合テスト

#### Phase 3: 運用準備 (3日)
- **Day 8**: エラーハンドリング強化
- **Day 9**: ログ・設定調整
- **Day 10**: 運用手順書・デプロイ

### 4.2 技術スタック（簡素化）

```toml
[tool.poetry.dependencies]
python = "^3.9"
watchdog = "^3.0.0"      # ファイル監視
icalendar = "^5.0.0"     # ICS解析
requests = "^2.31.0"     # LINE通知
loguru = "^0.7.0"        # ログ（構造化不要）
pydantic = "^2.4.0"      # 設定管理
```

## 5. ユーザー操作フロー

### 5.1 初期セットアップ
1. システムを起動
2. 監視フォルダ（例: `./ics_files/`）を確認
3. LINE Notify トークンを設定

### 5.2 日常利用フロー
1. **TimeTreeからICSエクスポート**
   - TimeTree Web版またはアプリ
   - 「エクスポート」→「ICS形式」選択
   - ダウンロード

2. **ファイル配置**
   - ダウンロードしたICSファイルを監視フォルダに配置
   - ファイル名: `calendar.ics` （固定）

3. **自動処理**
   - システムが変更を自動検出
   - 前回データと比較
   - 変更があればLINE通知

### 5.3 通知内容例
```
📅 TimeTree予定が更新されました

🆕 新しい予定:
・2025/08/28 14:00-16:00
  「プロジェクトミーティング」

✏️ 変更された予定:
・2025/08/29 10:00-11:00
  「歯医者」→「歯医者（定期検診）」

更新時刻: 2025/08/27 09:30
```

## 6. 設定ファイル設計

### 6.1 config.yaml
```yaml
# TimeTree通知システム - MVP設定
app:
  name: "TimeTree Notifier MVP"
  version: "1.0.0"

monitoring:
  watch_directory: "./ics_files"
  file_pattern: "*.ics"
  check_interval: 1  # 秒

notification:
  line_notify_token: "${LINE_NOTIFY_TOKEN}"
  max_message_length: 1000

logging:
  level: "INFO"
  file: "./logs/app.log"
  max_size: "10MB"
  rotation: 5

storage:
  history_file: "./data/event_history.json"
  backup_count: 7
```

### 6.2 環境変数（.env）
```env
# LINE Notify設定
LINE_NOTIFY_TOKEN=your_line_notify_token_here

# ログレベル
LOG_LEVEL=INFO

# 監視ディレクトリ
WATCH_DIRECTORY=./ics_files
```

## 7. エラーハンドリング設計

### 7.1 主要なエラーパターン
```python
# エラー分類と対応
ERROR_PATTERNS = {
    # ファイル関連
    "file_not_found": "ICSファイルが見つかりません",
    "file_parse_error": "ICSファイルの形式が正しくありません",
    "file_permission": "ファイルアクセス権限がありません",
    
    # 通知関連
    "line_api_error": "LINE通知の送信に失敗しました",
    "line_token_invalid": "LINEトークンが無効です",
    "network_error": "ネットワーク接続に問題があります",
    
    # システム関連
    "memory_limit": "メモリ使用量が上限に達しました",
    "disk_full": "ディスク容量が不足しています"
}
```

### 7.2 リトライ戦略
```python
# シンプルなリトライ設定
RETRY_CONFIG = {
    "line_notify": {
        "max_attempts": 3,
        "delay": 5,  # 5秒間隔
        "backoff": "fixed"  # 指数バックオフなし
    },
    "file_operations": {
        "max_attempts": 2,
        "delay": 1
    }
}
```

## 8. 監視・運用方針

### 8.1 ヘルスチェック（簡素版）
```python
class SimpleHealthChecker:
    """基本的なシステム状態確認"""
    
    def check_system_health(self):
        checks = {
            "watch_directory_exists": self.check_directory(),
            "line_token_valid": self.check_line_token(),
            "disk_space": self.check_disk_space(),
            "memory_usage": self.check_memory()
        }
        return checks
```

### 8.2 ログ出力設計
```python
# ログレベル設定
LOG_LEVELS = {
    "DEBUG": "開発時のデバッグ情報",
    "INFO": "正常な動作情報（デフォルト）",
    "WARNING": "注意が必要な状況",
    "ERROR": "エラーが発生した状況"
}

# ログ出力例
"""
2025-08-27 10:30:15 | INFO  | File change detected: calendar.ics
2025-08-27 10:30:16 | INFO  | Found 3 new events, 1 modified event  
2025-08-27 10:30:17 | INFO  | LINE notification sent successfully
2025-08-27 10:30:17 | INFO  | Event history updated
"""
```

## 9. 拡張計画（将来版）

### 9.1 Phase 2拡張機能
- 複数ICSファイル対応
- 定時サマリー通知
- より詳細な変更内容表示
- Web UI追加

### 9.2 Phase 3拡張機能  
- Google Calendar連携
- Slack通知対応
- 予定のリマインダー機能
- 統計・ダッシュボード

## 10. 移行・導入計画

### 10.1 従来システムからの移行
現在のSOW設計を使用していない場合は、このMVP版から開始することを推奨。

### 10.2 段階的導入
1. **Week 1**: MVP版の開発・テスト
2. **Week 2**: 本運用開始・問題修正
3. **Week 3-4**: ユーザーフィードバック収集
4. **Week 5以降**: 拡張機能の検討・実装

## 11. 成功指標（現実的設定）

### 11.1 MVP版KPI
- **ファイル検出成功率**: 95%以上
- **通知送信成功率**: 90%以上  
- **システム稼働時間**: 週95%以上
- **レスポンス時間**: 平均10秒以内

### 11.2 運用指標
- **エラー発生頻度**: 週3回以下
- **手動介入回数**: 週1回以下
- **ユーザー満足度**: 80%以上

## まとめ

本改訂版設計は、前回のSOW分析で判明した重大なリスクを回避し、実現可能で安全なシステムを目指しています。

**主要な改善点:**
- ✅ スクレイピングリスク完全排除
- ✅ システム複雑さの大幅軽減
- ✅ 手動操作による確実な動作
- ✅ 段階的な機能拡張計画

**次のステップ:**
1. MVP版の実装開始
2. 基本動作の確認
3. ユーザーフィードバックに基づく改善
4. 拡張機能の段階的追加

この設計により、安全で確実に動作するTimeTree通知システムの構築が可能となります。