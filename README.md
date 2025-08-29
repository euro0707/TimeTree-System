# TimeTree毎朝通知システム

毎朝6時にTimeTreeの予定をLINEで自動通知するシステム

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)](https://github.com/euro0707/TimeTree-System)

## 🌟 概要

TimeTreeの予定を毎朝自動でLINEに通知してくれるPythonアプリケーションです。
1日1回、安全にTimeTreeからデータを取得し、見やすい形で今日の予定をお知らせします。

## 🎯 主な機能

- ⏰ **毎朝6時に自動通知** - 今日の予定一覧をLINEに送信
- 📝 **予定なしも通知** - 予定がない日も「今日は予定なし」と通知
- 🔒 **完全自動化** - 環境変数による認証で対話的入力を完全排除
- 🎯 **正確な予定抽出** - 全ての予定を漏れなく取得（時刻指定・終日対応）
- ⏱️ **正確な時刻表示** - 時刻指定イベントと終日イベントを適切に区別表示
- ⚙️ **設定変更可能** - 通知時間・カレンダー・内容を設定ファイルで簡単変更
- 🛡️ **エラーハンドリング** - 通信失敗時も適切に対応・通知
- 📊 **詳細ログ** - 動作状況を記録、トラブル時も安心

## 📱 通知例

### 予定ありの場合
```
🌅 おはようございます！今日の予定

📅 2025年8月29日（木）

⏰ 今日の予定:
・14:00-15:00 避難訓練
・22:00-23:00 自転車整備
・終日 水の汲める場所はどこ
・終日 休み

今日も良い一日を！✨

---
TimeTree自動通知 | 06:19送信
```

### 予定なしの場合
```
🌅 おはようございます！

📅 2025年8月28日（水）

📝 今日は予定がありません
ゆっくりとした一日をお過ごしください！

今日も良い一日を！✨

---
TimeTree自動通知 | 06:00送信
```

## 🚀 クイックスタート

### 1. 事前準備

**必要なもの:**
- Python 3.9以上
- TimeTreeアカウント
- LINE Notifyトークン

### 2. リポジトリ取得・インストール

```bash
# リポジトリをクローン
git clone https://github.com/euro0707/TimeTree-System.git
cd TimeTree-System

# 依存関係をインストール
pip install -e .
```

### 3. LINE Messaging API設定

1. **LINE Developers Console**: https://developers.line.biz/
2. **新しいチャンネル作成** → **Messaging API**を選択
3. **チャンネル設定**で以下を取得:
   - **チャンネルアクセストークン**
   - **あなたのLINE User ID**
4. **Webhook設定**（任意）

### 4. 環境変数設定

`.env`ファイルを作成：
```bash
cp .env.example .env
```

`.env`ファイルを編集：
```env
# TimeTree認証情報
TIMETREE_EMAIL=your-email@example.com
TIMETREE_PASSWORD=your-secure-password

# LINE Messaging API設定  
LINE_CHANNEL_ACCESS_TOKEN=your-line-channel-access-token
LINE_USER_ID=your-line-user-id
```

### 5. 動作確認・実行

```bash
# 手動テスト実行（今すぐ通知送信）
python -m timetree_notifier.main --mode manual

# システム状態確認
python -m timetree_notifier.main --mode status

# 毎朝6時の自動実行開始
python -m timetree_notifier.main --mode daemon
```

## ⚙️ 設定カスタマイズ

### 通知時間の変更

`config.yaml`の`daily_summary.time`を編集：

```yaml
daily_summary:
  time: "07:30"  # 7時30分に変更
  time: "08:00"  # 8時に変更
  time: "05:30"  # 5時30分に変更
```

### 通知内容のカスタマイズ

```yaml
daily_summary:
  # 通知内容設定
  include_description: true    # 予定の説明を含める
  include_location: true       # 場所情報を含める
  max_events_display: 10       # 表示する予定数の上限
  
  # 予定なしの場合
  notify_when_no_events: true  # 予定なしの場合も通知
  no_events_message: "今日は予定がありません\nゆっくりとした一日をお過ごしください！"
```

### その他の設定

```yaml
# LINE通知設定
notification:
  max_message_length: 1000     # メッセージ最大長
  greeting: "🌅 おはようございます！今日の予定"
  closing: "今日も良い一日を！✨" 
  footer: "TimeTree自動通知"

# ログ設定
logging:
  level: "INFO"                # ログレベル
  file: "./logs/daily_notifier.log"
  max_size: "10MB"
  rotation: 7                  # ファイル保持数
```

## 📂 プロジェクト構造

```
TimeTree-System/
├── README.md                    # このファイル
├── config.yaml                 # メイン設定ファイル
├── pyproject.toml              # パッケージ設定
├── .env.example                # 環境変数テンプレート
├── .env                        # 環境変数（要作成）
├── .gitignore                  # Git除外設定
│
├── src/timetree_notifier/      # メインソースコード
│   ├── __init__.py
│   ├── main.py                 # メインアプリケーション
│   ├── config/                 # 設定管理
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── core/                   # コア機能
│   │   ├── __init__.py
│   │   ├── daily_notifier.py   # 毎朝通知機能
│   │   ├── scheduler.py        # スケジューラー
│   │   └── models.py           # データモデル
│   └── utils/                  # ユーティリティ
│       ├── __init__.py
│       └── logger.py           # ログ管理
│
├── docs/                       # ドキュメント
├── logs/                       # ログファイル（自動生成）
├── temp/                       # 一時ファイル（自動生成）
└── data/                       # バックアップファイル（自動生成）
```

## 🎮 使用方法

### デーモンモード（推奨）
```bash
python -m timetree_notifier.main --mode daemon
```
- バックグラウンドで実行
- 毎朝6時に自動通知
- `Ctrl+C`で停止

### 手動テストモード
```bash
python -m timetree_notifier.main --mode manual
```
- 即座に今日の予定を通知
- 動作確認・テスト用

### ステータス確認モード
```bash
python -m timetree_notifier.main --mode status
```
- システム状態を表示
- 設定内容・次回実行時刻の確認

### カスタム設定ファイル使用
```bash
python -m timetree_notifier.main --config custom_config.yaml --mode daemon
```

## 🔧 技術仕様

### 使用技術
- **Python**: 3.9+
- **TimeTree-Exporter**: 0.6.1 (TimeTreeデータ取得)
- **APScheduler**: 3.10.4+ (cron実行)
- **LINE Notify API**: 通知送信
- **icalendar**: 6.1.0+ (ICS解析)
- **loguru**: 0.7.2+ (ログ管理)
- **pydantic**: 2.4.2+ (設定検証)

### システム要件
- **OS**: Windows / macOS / Linux
- **メモリ**: 50MB以内
- **ディスク**: 100MB程度
- **ネットワーク**: インターネット接続必須

## 🛠️ トラブルシューティング

### よくあるエラーと対処法

#### エラー: `TimeTree-Exporter execution timeout`
**原因**: ネットワーク接続またはTimeTree認証の問題
**対処法**: 
1. インターネット接続を確認
2. `.env`ファイルのメールアドレス・パスワードを確認
3. TimeTreeにブラウザでログインできるか確認

#### エラー: `LINE通知の送信に失敗しました`
**原因**: LINE Notifyトークンの問題
**対処法**:
1. `.env`ファイルのトークンを確認
2. LINE Notifyのマイページでトークンの状態を確認
3. 必要に応じてトークンを再発行

#### 通知が届かない
**原因**: システムが停止しているか、設定ミス
**対処法**:
1. `--mode status`でシステム状態を確認
2. `logs/daily_notifier.log`でエラーログを確認
3. 手動テスト(`--mode manual`)で動作確認

#### 予定が表示されない
**原因**: TimeTreeのデータ取得失敗またはタイムゾーン設定
**対処法**:
1. TimeTreeに予定が正しく登録されているか確認
2. `config.yaml`のタイムゾーン設定を確認（`Asia/Tokyo`）
3. 手動でTimeTree-Exporterを実行して動作確認

### ログファイルの確認
```bash
# 最新のログを確認
tail -f logs/daily_notifier.log

# エラーのみ表示
grep "ERROR" logs/daily_notifier.log

# 特定日のログを確認
grep "2025-08-28" logs/daily_notifier.log
```

## 🔐 セキュリティ

### 認証情報の管理
- `.env`ファイルは絶対にGitにコミットしない
- `.env`ファイルのアクセス権限を適切に設定
- 定期的にパスワード・トークンを変更

### プライバシー保護
- ログファイルに機密情報は記録されません
- パスワード・トークンは自動でマスク処理されます

## 🤝 貢献・サポート

### 問題報告
- GitHubのIssuesで問題を報告してください
- ログファイルの内容も合わせて提供してください

### 機能要望
- GitHubのIssuesで機能要望を提出してください
- 具体的な使用ケースも説明してください

## 📄 ライセンス

MIT License - 詳細は[LICENSE](LICENSE)ファイルを参照

## 📊 更新履歴

### v2.2.0 (2025-08-29) 🎉
- 🔧 **完全自動化実現** - 対話的パスワード入力を完全排除
- 📊 **予定抽出の改善** - 全ての予定を正確に取得（4/4件対応）
- ⏱️ **時刻表示修正** - 時刻指定と終日イベントの正確な表示
- 🎯 **カレンダー選択最適化** - 実際の予定があるカレンダーへ自動切替
- 🕐 **タイムゾーン処理改善** - timezone-aware/naive datetime混在エラー解決
- 📱 **LINE Messaging API対応** - より安定した通知配信

### v2.1.0 (2025-08-27)
- ✨ 初回リリース
- ⏰ 毎朝6時の自動通知機能
- 🔒 TimeTree-Exporter統合
- 📱 LINE通知システム
- ⚙️ 設定管理システム
- 📝 包括的ドキュメント

---

**作成者**: TimeTree Auto Notifier Team  
**作成日**: 2025年8月27日  
**最終更新**: 2025年8月29日  
**バージョン**: 2.2.0  

💡 **Tip**: 毎朝の通知で一日をスムーズにスタートしましょう！
