# TimeTree予定通知システム SOW・設計書

## 1. プロジェクト概要

### 1.1 目的
TimeTreeの予定情報を自動取得し、LINE Notifyを通じてリアルタイムで通知するシステムを構築する。

### 1.2 スコープ
- TimeTreeからの予定データ自動取得
- 予定の変更・新規追加の検出
- LINE Notifyによる通知配信
- エラー処理・ログ管理
- 運用監視機能

### 1.3 成果物
- 実行可能なPythonアプリケーション
- 設定ファイル・環境変数テンプレート
- 運用手順書
- ログ監視ダッシュボード

## 2. システム要件

### 2.1 機能要件

#### 2.1.1 データ取得機能
- **F001**: TimeTree-Exporterを使用したICS形式での予定データ取得
- **F002**: 30分間隔での定期実行（設定可能）
- **F003**: データ取得失敗時のリトライ機能（最大3回）
- **F004**: 前回正常取得データのバックアップ保持

#### 2.1.2 変更検出機能
- **F005**: 予定の新規追加検出
- **F006**: 既存予定の変更検出（タイトル、時間、説明）
- **F007**: 予定削除の検出
- **F008**: ハッシュベースでの重複通知防止

#### 2.1.3 通知機能
- **F009**: LINE Notifyによる即時通知
- **F010**: 朝の定時通知（今日の予定一覧）
- **F011**: 予定開始前リマインダー（30分前、設定可能）
- **F012**: メッセージ長制限対応（1000文字以下に分割）

#### 2.1.4 運用管理機能
- **F013**: 実行ログの記録・ローテーション
- **F014**: エラー発生時の管理者通知
- **F015**: システムヘルスチェック機能
- **F016**: 設定ファイルによる動作制御

### 2.2 非機能要件

#### 2.2.1 性能要件
- **N001**: 予定データ処理時間: 10秒以内
- **N002**: LINE通知送信時間: 5秒以内
- **N003**: メモリ使用量: 100MB以内

#### 2.2.2 可用性要件
- **N004**: システム稼働率: 99.5%以上
- **N005**: エラー発生時の自動復旧機能
- **N006**: 24時間連続運用対応

#### 2.2.3 保守性要件
- **N007**: ログレベルによる出力制御
- **N008**: 設定変更時の動的リロード
- **N009**: モジュール化による保守性向上

## 3. システム設計

### 3.1 全体アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                   TimeTree通知システム                    │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐  │
│  │   Scheduler │───▶│  Data Sync   │───▶│  Notifier   │  │
│  │   (cron)    │    │   Manager    │    │  (LINE)     │  │
│  └─────────────┘    └──────────────┘    └─────────────┘  │
│                             │                            │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐  │
│  │   Logger    │◀───│  Event       │───▶│  Storage    │  │
│  │             │    │  Tracker     │    │  Manager    │  │
│  └─────────────┘    └──────────────┘    └─────────────┘  │
│                                                          │
│  ┌─────────────┐    ┌──────────────┐                     │
│  │   Health    │───▶│  Config      │                     │
│  │   Monitor   │    │  Manager     │                     │
│  └─────────────┘    └──────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

### 3.2 データフロー

```
TimeTree
    ↓ (TimeTree-Exporter)
ICSファイル
    ↓
ICSパーサー
    ↓
イベント抽出
    ↓
変更検出
    ↓
新規/変更あり？
    ↓ Yes          ↓ No
通知メッセージ生成    待機
    ↓               ↓
LINE Notify送信      ↓
    ↓               ↓
履歴更新            ↓
    ↓               ↓
ログ記録            ↓
    ↓_______________↓
次回実行待機
    ↓
(TimeTreeに戻る)
```

### 3.3 コンポーネント設計

#### 3.3.1 DataSyncManager
```python
class DataSyncManager:
    """TimeTreeデータ同期管理"""
    
    def __init__(self, config: Config):
        self.config = config
        self.exporter = TimeTreeExporter()
        self.validator = ICSValidator()
    
    async def fetch_latest_data(self) -> Path:
        """最新データの取得"""
    
    def validate_ics_data(self, file_path: Path) -> bool:
        """ICSデータの検証"""
    
    def backup_current_data(self, file_path: Path):
        """現在データのバックアップ"""
```

#### 3.3.2 EventTracker
```python
class EventTracker:
    """イベント変更追跡管理"""
    
    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.history = self.load_history()
    
    def detect_changes(self, events: List[Event]) -> List[Event]:
        """変更イベントの検出"""
    
    def update_history(self, events: List[Event]):
        """履歴の更新"""
    
    def generate_event_hash(self, event: Event) -> str:
        """イベントハッシュ生成"""
```

#### 3.3.3 NotificationManager
```python
class NotificationManager:
    """通知管理"""
    
    def __init__(self, line_token: str):
        self.line_notifier = LineNotifier(line_token)
        self.rate_limiter = RateLimiter()
    
    async def send_immediate_notification(self, events: List[Event]):
        """即時通知送信"""
    
    async def send_daily_summary(self, date: datetime):
        """日次サマリー送信"""
    
    async def send_reminder(self, event: Event):
        """リマインダー送信"""
```

### 3.4 データベース設計

#### 3.4.1 Event History Table
```sql
CREATE TABLE event_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uid TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    title TEXT,
    start_time DATETIME,
    end_time DATETIME,
    description TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    notification_sent BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 3.4.2 Notification Log Table
```sql
CREATE TABLE notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_uid TEXT,
    notification_type TEXT, -- 'immediate', 'daily', 'reminder'
    message TEXT,
    status TEXT, -- 'success', 'failed', 'retry'
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    retry_count INTEGER DEFAULT 0
);
```

## 4. 実装計画

### 4.1 開発フェーズ

#### Phase 1: 基盤構築 (Week 1-2)
- **Task 1.1**: プロジェクト構造セットアップ
- **Task 1.2**: 設定管理システム実装
- **Task 1.3**: ログ管理システム実装
- **Task 1.4**: データベースセットアップ

#### Phase 2: コア機能実装 (Week 3-4)
- **Task 2.1**: TimeTree-Exporter連携実装
- **Task 2.2**: ICSパーサー・イベント抽出機能
- **Task 2.3**: 変更検出ロジック実装
- **Task 2.4**: LINE Notify通知機能実装

#### Phase 3: 高度機能実装 (Week 5-6)
- **Task 3.1**: エラーハンドリング・リトライ機能
- **Task 3.2**: レート制限・バックオフ実装
- **Task 3.3**: ヘルスチェック・監視機能
- **Task 3.4**: 定時通知・リマインダー機能

#### Phase 4: テスト・運用準備 (Week 7-8)
- **Task 4.1**: 単体テスト・統合テスト
- **Task 4.2**: 性能テスト・負荷テスト
- **Task 4.3**: 運用手順書作成
- **Task 4.4**: デプロイ・運用開始

### 4.2 技術スタック

#### 4.2.1 開発環境
- **言語**: Python 3.9+
- **依存関係管理**: Poetry
- **データベース**: SQLite（開発）/ PostgreSQL（本番）
- **スケジューラー**: APScheduler
- **ログ**: structlog + loguru

#### 4.2.2 外部ライブラリ
```toml
[tool.poetry.dependencies]
python = "^3.9"
requests = "^2.31.0"
icalendar = "^5.0.10"
apscheduler = "^3.10.4"
sqlalchemy = "^2.0.21"
structlog = "^23.1.0"
loguru = "^0.7.2"
pydantic = "^2.4.2"
httpx = "^0.25.0"
```

## 5. 運用要件

### 5.1 デプロイ方法
- **開発環境**: ローカルマシン
- **本番環境**: VPS / AWS EC2
- **コンテナ化**: Docker + Docker Compose
- **プロセス管理**: systemd / supervisord

### 5.2 監視・アラート
- **システム監視**: Prometheus + Grafana
- **ログ監視**: ELK Stack（簡易版）
- **アラート通知**: LINE Notify（管理者向け）

### 5.3 バックアップ・災害復旧
- **データバックアップ**: 日次自動バックアップ
- **設定バックアップ**: Git管理
- **復旧手順**: 運用手順書に記載

## 6. リスク・課題

### 6.1 技術的リスク
- **TimeTree-Exporter依存**: メンテナンス停止リスク
- **TimeTree仕様変更**: スクレイピング失敗リスク
- **LINE Notify制限**: レート制限・サービス停止リスク

### 6.2 対応策
- **代替手段準備**: 複数の取得方法の実装
- **フォールバック機能**: 前回データでの継続運用
- **監視強化**: 異常検知の自動化

## 7. 成功指標

### 7.1 KPI
- **データ取得成功率**: 99.5%以上
- **通知送信成功率**: 99.9%以上
- **システム稼働率**: 99.5%以上
- **レスポンス時間**: 平均5秒以内

### 7.2 運用指標
- **エラー発生頻度**: 週1回以下
- **メンテナンス時間**: 月4時間以内
- **ログ監視対応時間**: 24時間以内

## 8. 実装ガイド・ポイント

### 8.1 Claude Code実装指示例

#### 8.1.1 初期セットアップ
```bash
# プロジェクト構造作成
claude-code "TimeTree通知システムのプロジェクト構造を作成。Poetry使用、Python3.9+、上記SOWの設計に基づく"

# 依存関係セットアップ  
claude-code "pyproject.tomlに必要な依存関係を追加。requests, icalendar, apscheduler, sqlalchemy, structlog, loguru, pydantic, httpxを含める"

# 基盤設定
claude-code "src/config/settings.py に設定管理クラス実装。環境変数読み込み、バリデーション、デフォルト値設定を含める"
```

#### 8.1.2 段階的実装指示
```bash
# Phase 1: 基盤構築
claude-code "ログ管理システム実装。RotatingFileHandler使用、JSON構造化ログ、レベル別出力制御"

claude-code "SQLiteデータベース初期化。event_history, notification_logテーブル作成、マイグレーション機能"

# Phase 2: コア機能
claude-code "DataSyncManagerクラス実装。TimeTree-Exporter実行、ICS検証、エラー処理、リトライ機能"

claude-code "EventTrackerクラス実装。ハッシュベース変更検出、履歴管理、重複防止"

claude-code "NotificationManagerクラス実装。LINE Notify送信、レート制限、メッセージ分割、リトライ"

# Phase 3: 高度機能
claude-code "HealthMonitorクラス実装。システム状態チェック、ファイル更新監視、管理者アラート"

claude-code "メインアプリケーション実装。APScheduler使用、定期実行、シグナルハンドリング"
```

### 8.2 重要実装ポイント

#### 8.2.1 外部プロセス実行（TimeTree-Exporter連携）
```python
# 実装時の注意点
async def run_timetree_exporter(self) -> Path:
    """
    重要ポイント:
    - subprocess.run()でタイムアウト設定必須
    - 標準出力・エラー出力の適切なキャプチャ
    - プロセス終了コードの確認
    - 一時ファイルの確実なクリーンアップ
    """
    cmd = ["timetree-exporter", "--output", "temp_export.ics"]
    result = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        timeout=60  # タイムアウト必須
    )
```

#### 8.2.2 LINE Notify レート制限対応
```python
# 実装時の注意点
class RateLimiter:
    """
    重要ポイント:
    - 1000回/時間の制限を考慮したバッファリング
    - 指数バックオフでのリトライ実装
    - トークンバケット方式の検討
    - 失敗したリクエストの永続化・再送
    """
    def __init__(self):
        self.requests_per_hour = 1000
        self.min_interval = 3.6  # 秒（安全マージン込み）
```

#### 8.2.3 SQLite マルチスレッド対応
```python
# 実装時の注意点
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite:///timetree_notifications.db",
    poolclass=StaticPool,
    pool_pre_ping=True,
    connect_args={
        "check_same_thread": False,  # マルチスレッド対応
        "timeout": 30  # ロックタイムアウト
    }
)
```

#### 8.2.4 設定の動的リロード
```python
# 実装時の注意点  
class ConfigManager:
    """
    重要ポイント:
    - ファイル変更監視（watchdog使用）
    - リロード時のバリデーション
    - 設定変更の影響範囲を最小化
    - ホットリロード中のエラー処理
    """
    def watch_config_file(self):
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
```

#### 8.2.5 エラーハンドリングパターン
```python
# 実装時の注意点
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(requests.RequestException)
)
async def robust_operation():
    """
    重要ポイント:
    - 一時的エラーと永続的エラーの区別
    - サーキットブレーカーパターンの適用
    - エラー詳細の構造化ログ出力
    - フォールバック処理の実装
    """
```

### 8.3 テスト実装指針

#### 8.3.1 単体テスト
```bash
# テストファースト実装
claude-code "EventTrackerのテストケース作成。モックデータ使用、境界値テスト、異常系テスト含む"

claude-code "NotificationManagerのテストケース作成。HTTP通信モック、レート制限テスト、リトライテスト含む"
```

#### 8.3.2 統合テスト
```bash
claude-code "エンドツーエンドテストシナリオ作成。ICS取得→変更検出→通知送信の全フロー"

claude-code "負荷テストスクリプト作成。大量イベント処理、同時リクエスト処理の検証"
```

### 8.4 デバッグ・トラブルシューティング

#### 8.4.1 開発時のログ設定
```python
# デバッグ時の推奨設定
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "{asctime} [{levelname:8}] {name}: {message}",
            "style": "{"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "detailed",
            "level": "DEBUG"  # 開発時はDEBUG
        }
    },
    "root": {
        "level": "DEBUG",
        "handlers": ["console"]
    }
}
```

#### 8.4.2 よくある問題と対処法
```python
# 実装時によくある問題
"""
1. ICSファイル文字エンコーディング問題
   → UTF-8での読み込み強制、BOM除去

2. タイムゾーン処理の不整合
   → pytzで明示的なタイムゾーン変換

3. LINE通知の文字数制限
   → 事前の文字数カウント、適切な分割処理

4. SQLiteのロック問題
   → 適切なトランザクション管理、タイムアウト設定

5. メモリリーク
   → 大きなICSファイルの段階的読み込み
"""
```

### 8.5 運用時の監視ポイント

#### 8.5.1 ヘルスチェック項目
```bash
claude-code "ヘルスチェック機能実装。以下をチェック：ICSファイル更新時刻、DB接続状態、LINE通知成功率、メモリ使用量"
```

#### 8.5.2 アラート条件
```python
# 監視・アラート設定例
ALERT_CONDITIONS = {
    "data_fetch_failure": "3回連続失敗",
    "notification_failure_rate": "1時間内に50%以上失敗",
    "disk_usage": "使用率90%超過", 
    "memory_usage": "100MB超過",
    "response_time": "平均10秒超過"
}
```

### 8.6 パフォーマンス最適化

#### 8.6.1 最適化ポイント
```bash
claude-code "パフォーマンス最適化実装：ICSパーサーの高速化、データベースインデックス、メモリ使用量削減"
```

#### 8.6.2 スケールアウト対応
```python
# 将来的な拡張を考慮した設計
"""
- Redis使用の分散ロック
- メッセージキュー（Celery）による非同期処理  
- データベースのレプリケーション対応
- ロードバランサー対応のヘルスチェックAPI
"""
```

---

**作成日**: 2025年8月23日  
**バージョン**: 1.1（実装ガイド追加）  
**承認者**: プロジェクトマネージャー