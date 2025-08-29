# TimeTree通知システム - TimeTree-Exporter統合版設計書

## 改訂日: 2025年8月27日
## 設計方針: TimeTree-Exporterによる自動取得を採用

## 1. 設計変更の背景

### 1.1 ユーザー要求
- 手動操作を最小限にしたい
- TimeTree-Exporterを活用した自動取得を実現したい
- 定期的な予定同期を実現したい

### 1.2 TimeTree-Exporter調査結果
- **認証**: 環境変数による自動化対応
- **実行**: コマンドライン完全対応
- **出力**: ICS形式で各種カレンダーアプリ対応
- **制限**: アラート機能の不完全性（許容範囲内）

## 2. リスク軽減戦略

### 2.1 スクレイピング関連リスク対応
```python
# 多段階フォールバック戦略
FALLBACK_STRATEGY = {
    "primary": "TimeTree-Exporter自動実行",
    "secondary": "前回正常データの継続使用",
    "tertiary": "手動ICSファイル配置",
    "emergency": "エラー通知のみ"
}
```

### 2.2 エラー検出・回復機能
- **接続失敗**: 3回リトライ後、前回データ使用
- **認証エラー**: 管理者アラート + マニュアルモード切替
- **データ異常**: 検証失敗時、前回データ保持
- **レート制限**: 指数バックオフ + 実行間隔調整

## 3. システム設計（改訂版）

### 3.1 統合アーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│             TimeTree自動通知システム                      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐  │
│  │  Scheduler  │───▶│ Exporter     │───▶│ Validator   │  │
│  │  (定期実行)   │    │ Manager      │    │ (検証)       │  │
│  └─────────────┘    └──────────────┘    └─────────────┘  │
│                             │                   │        │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐  │
│  │ Fallback    │◀───│ Error        │───▶│ Change      │  │
│  │ Manager     │    │ Handler      │    │ Detector    │  │
│  └─────────────┘    └──────────────┘    └─────────────┘  │
│                                                 │        │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐  │
│  │   Logger    │◀───│ Notification │◀───│ Event       │  │
│  │             │    │ Manager      │    │ Parser      │  │
│  └─────────────┘    └──────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 データフロー（TimeTree-Exporter統合版）

```
定期実行トリガー（例：30分間隔）
    ↓
TimeTree-Exporter実行準備
    ↓
認証情報確認（環境変数）
    ↓
timetree-exporter -o temp.ics 実行
    ↓
実行結果判定
    ↓ 成功          ↓ 失敗
ICSファイル検証     エラー分類
    ↓ OK           ↓
前回データと比較    リトライ判定
    ↓              ↓ 継続リトライ
変更検出           フォールバック実行
    ↓ 変更あり      ↓ 停止
LINE通知生成       前回データ使用
    ↓              ↓
通知送信           管理者アラート
    ↓              ↓
履歴データ更新      ↓
    ↓______________↓
ログ記録・次回実行待機
```

## 4. 主要コンポーネント設計

### 4.1 ExporterManager（TimeTree-Exporter管理）

```python
import subprocess
import asyncio
from pathlib import Path

class ExporterManager:
    """TimeTree-Exporter実行管理"""
    
    def __init__(self, config):
        self.config = config
        self.output_path = Path(config.temp_ics_path)
        self.timeout = config.exporter_timeout
        
    async def execute_export(self) -> ExportResult:
        """TimeTree-Exporterの実行"""
        try:
            cmd = [
                "timetree-exporter", 
                "-o", str(self.output_path),
                "-e", self.config.timetree_email
            ]
            
            # 環境変数設定
            env = os.environ.copy()
            env.update({
                "TIMETREE_EMAIL": self.config.timetree_email,
                "TIMETREE_PASSWORD": self.config.timetree_password
            })
            
            # 非同期プロセス実行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                timeout=self.timeout
            )
            
            stdout, stderr = await process.communicate()
            
            return ExportResult(
                success=process.returncode == 0,
                output_file=self.output_path if process.returncode == 0 else None,
                error_message=stderr.decode() if process.returncode != 0 else None,
                execution_time=time.time() - start_time
            )
            
        except asyncio.TimeoutError:
            return ExportResult(
                success=False,
                error_message="TimeTree-Exporter execution timeout",
                error_type="timeout"
            )
        except Exception as e:
            return ExportResult(
                success=False,
                error_message=str(e),
                error_type="execution_error"
            )
```

### 4.2 ErrorHandler（エラー処理・フォールバック）

```python
class ErrorHandler:
    """エラー処理とフォールバック管理"""
    
    def __init__(self, fallback_manager, notifier):
        self.fallback = fallback_manager
        self.notifier = notifier
        self.error_counts = {}
        
    async def handle_export_error(self, error: ExportResult) -> HandlingResult:
        """エクスポートエラーの処理"""
        error_type = self.classify_error(error)
        
        if error_type == "authentication":
            # 認証エラー: 管理者通知 + マニュアルモード
            await self.notifier.send_admin_alert(
                "TimeTree認証エラーが発生しました。認証情報を確認してください。"
            )
            return HandlingResult(
                action="switch_to_manual",
                retry=False,
                use_fallback=True
            )
            
        elif error_type == "rate_limit":
            # レート制限: 実行間隔を延長
            return HandlingResult(
                action="extend_interval",
                retry=True,
                delay=self.calculate_backoff_delay()
            )
            
        elif error_type == "network":
            # ネットワークエラー: リトライ
            retry_count = self.error_counts.get("network", 0) + 1
            self.error_counts["network"] = retry_count
            
            if retry_count < 3:
                return HandlingResult(
                    action="retry",
                    retry=True,
                    delay=min(60 * retry_count, 300)  # 最大5分
                )
            else:
                # リトライ上限: フォールバック
                return HandlingResult(
                    action="use_fallback",
                    retry=False,
                    use_fallback=True
                )
                
        elif error_type == "parsing":
            # データ形式エラー: 前回データ使用
            return HandlingResult(
                action="use_previous_data",
                retry=False,
                use_fallback=True
            )
            
        else:
            # 不明エラー: デフォルトフォールバック
            return HandlingResult(
                action="default_fallback",
                retry=False,
                use_fallback=True
            )
```

### 4.3 FallbackManager（フォールバック管理）

```python
class FallbackManager:
    """フォールバック機能管理"""
    
    def __init__(self, config):
        self.config = config
        self.previous_data_path = Path(config.backup_data_path)
        self.manual_ics_path = Path(config.manual_ics_path)
        
    async def execute_fallback(self, strategy: str) -> FallbackResult:
        """フォールバック実行"""
        
        if strategy == "use_previous_data":
            # 前回正常データの使用
            if self.previous_data_path.exists():
                return FallbackResult(
                    success=True,
                    data_source="previous_backup",
                    ics_file=self.previous_data_path,
                    message="前回のデータを使用して継続します"
                )
                
        elif strategy == "check_manual_file":
            # 手動配置ファイルの確認
            if self.manual_ics_path.exists():
                # ファイルの新しさを確認
                modified_time = self.manual_ics_path.stat().st_mtime
                if time.time() - modified_time < 3600:  # 1時間以内
                    return FallbackResult(
                        success=True,
                        data_source="manual_file",
                        ics_file=self.manual_ics_path,
                        message="手動配置ファイルを検出しました"
                    )
                    
        elif strategy == "emergency_mode":
            # 緊急モード: エラー通知のみ
            return FallbackResult(
                success=False,
                data_source="none",
                message="すべてのデータ取得方法が失敗しました。手動での確認が必要です。"
            )
            
        return FallbackResult(
            success=False,
            data_source="none",
            message="フォールバック戦略の実行に失敗しました"
        )
```

## 5. 設定管理

### 5.1 config.yaml
```yaml
# TimeTree-Exporter統合版設定
app:
  name: "TimeTree Auto Notifier"
  version: "2.0.0"

timetree:
  # TimeTree認証情報（環境変数参照）
  email: "${TIMETREE_EMAIL}"
  password: "${TIMETREE_PASSWORD}"
  
  # TimeTree-Exporter設定
  exporter:
    timeout: 120  # 2分
    retry_count: 3
    retry_delay: 60  # 1分
    
scheduler:
  # 実行間隔（分）
  interval_minutes: 30
  # エラー時の間隔延長
  error_backoff_multiplier: 2
  max_interval_minutes: 240  # 4時間

paths:
  temp_ics: "./temp/timetree_export.ics"
  backup_data: "./data/backup.ics"
  manual_ics: "./manual/calendar.ics"
  logs: "./logs"

notification:
  line_notify_token: "${LINE_NOTIFY_TOKEN}"
  admin_line_token: "${ADMIN_LINE_NOTIFY_TOKEN}"  # 管理者用
  
  # 通知内容設定
  include_description: true
  max_message_length: 1000
  timezone: "Asia/Tokyo"

fallback:
  # フォールバック戦略の優先順位
  strategies:
    - "use_previous_data"
    - "check_manual_file"
    - "emergency_mode"
    
  # 前回データの有効期限（時間）
  previous_data_max_age: 24

error_handling:
  # エラー分類設定
  classification:
    authentication: ["login", "password", "credential"]
    rate_limit: ["rate", "limit", "too many"]
    network: ["network", "connection", "timeout"]
    parsing: ["parse", "format", "invalid"]
    
  # リトライ設定
  retry:
    max_attempts: 3
    backoff_base: 60  # 秒
    max_delay: 300    # 5分
```

### 5.2 環境変数設定（.env）
```env
# TimeTree認証情報
TIMETREE_EMAIL=your-email@example.com
TIMETREE_PASSWORD=your-secure-password

# LINE Notify設定
LINE_NOTIFY_TOKEN=your-line-notify-token
ADMIN_LINE_NOTIFY_TOKEN=admin-line-notify-token

# ログレベル
LOG_LEVEL=INFO

# デバッグモード
DEBUG_MODE=false
```

## 6. エラーパターンとハンドリング戦略

### 6.1 主要エラーパターンと対応

```python
ERROR_HANDLING_MAP = {
    # 認証関連エラー
    "authentication_failed": {
        "severity": "critical",
        "action": "admin_alert",
        "retry": False,
        "fallback": "switch_to_manual"
    },
    
    # ネットワーク関連エラー
    "network_timeout": {
        "severity": "warning", 
        "action": "retry",
        "retry": True,
        "max_retries": 3,
        "fallback": "use_previous_data"
    },
    
    # レート制限エラー
    "rate_limited": {
        "severity": "info",
        "action": "extend_interval",
        "retry": True,
        "delay": "exponential_backoff",
        "fallback": "use_previous_data"
    },
    
    # データ形式エラー
    "invalid_ics_format": {
        "severity": "warning",
        "action": "validate_and_repair",
        "retry": False,
        "fallback": "use_previous_data"
    },
    
    # TimeTreeサイト変更エラー
    "scraping_structure_changed": {
        "severity": "critical",
        "action": "admin_alert",
        "retry": False,
        "fallback": "emergency_mode"
    }
}
```

### 6.2 管理者アラート条件

```yaml
admin_alerts:
  conditions:
    - error_type: "authentication_failed"
      immediate: true
      
    - consecutive_failures: 5
      timeframe: "1 hour"
      
    - fallback_mode_duration: "6 hours"
    
    - manual_intervention_required: true
    
  notification_template: |
    🚨 TimeTree通知システム アラート
    
    エラー: {error_type}
    発生時刻: {timestamp}
    詳細: {error_details}
    
    現在の状態: {current_status}
    推奨アクション: {recommended_action}
```

## 7. 運用・監視機能

### 7.1 システム状態監視

```python
class SystemMonitor:
    """システム状態の監視"""
    
    def generate_status_report(self):
        """システム状態レポート生成"""
        return StatusReport(
            # TimeTree-Exporter関連
            exporter_status=self.check_exporter_availability(),
            last_successful_export=self.get_last_successful_export(),
            consecutive_failures=self.get_consecutive_failures(),
            
            # データ関連
            current_data_age=self.get_current_data_age(),
            backup_data_available=self.check_backup_availability(),
            manual_file_available=self.check_manual_file(),
            
            # 通知関連
            notification_success_rate=self.get_notification_stats(),
            last_notification=self.get_last_notification(),
            
            # システム関連
            memory_usage=self.get_memory_usage(),
            disk_usage=self.get_disk_usage(),
            uptime=self.get_uptime()
        )
```

### 7.2 定期ヘルスチェック

```python
async def daily_health_check():
    """日次ヘルスチェック"""
    checks = {
        "timetree_exporter_working": await test_exporter_execution(),
        "line_notify_working": await test_line_notification(),
        "backup_data_fresh": check_backup_data_freshness(),
        "disk_space_sufficient": check_disk_space(),
        "error_rate_acceptable": check_error_rate_last_24h()
    }
    
    if not all(checks.values()):
        await send_health_check_alert(checks)
    
    return checks
```

## 8. 実装スケジュール

### 8.1 Phase 1: 基盤構築（3日）
- Day 1: プロジェクト設定・TimeTree-Exporter統合テスト
- Day 2: エラーハンドリング・フォールバック基盤
- Day 3: 設定管理・ログシステム

### 8.2 Phase 2: コア機能（4日）
- Day 4: ExporterManager実装
- Day 5: 変更検出・通知システム
- Day 6: エラー分類・リトライ機能
- Day 7: フォールバック機能実装

### 8.3 Phase 3: 運用機能（3日）
- Day 8: 監視・ヘルスチェック機能
- Day 9: 管理者アラート・統合テスト
- Day 10: ドキュメント・デプロイ準備

## 9. セキュリティ考慮事項

### 9.1 認証情報の保護
```python
# セキュア設定例
SECURITY_CONFIG = {
    "env_file_permissions": "600",  # 読み取り専用
    "log_credential_masking": True,
    "password_in_memory_encryption": True,
    "process_isolation": True
}
```

### 9.2 ログの機密情報マスキング
```python
class SecureLogger:
    SENSITIVE_PATTERNS = [
        r'password[\'\"]*\s*[=:]\s*[\'\"]*([^\'\"\\s]+)',
        r'token[\'\"]*\s*[=:]\s*[\'\"]*([^\'\"\\s]+)',
        r'email[\'\"]*\s*[=:]\s*[\'\"]*([^\'\"\\s]+)'
    ]
    
    def mask_sensitive_data(self, message):
        for pattern in self.SENSITIVE_PATTERNS:
            message = re.sub(pattern, r'\1: [MASKED]', message)
        return message
```

## まとめ

TimeTree-Exporterを活用した自動取得システムで、以下の特徴を持つ実用的な設計が完成しました：

**主な特徴:**
- ✅ TimeTree-Exporter完全統合
- ✅ 多段階フォールバック機能
- ✅ 包括的エラーハンドリング
- ✅ 管理者アラート機能
- ✅ セキュアな認証情報管理

**リスク軽減策:**
- ✅ スクレイピング失敗時の自動フォールバック
- ✅ 前回データの自動バックアップ・復旧
- ✅ 手動ファイル配置への緊急切替
- ✅ 管理者への即時アラート

この設計により、TimeTree-Exporterの利点を活用しつつ、リスクを最小限に抑えた実用的なシステムが実現できます。