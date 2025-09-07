# Morning TimeTree v1.0 — 設計書（修正版）

## 目的 / 方式
- 目的: 毎朝 06:00 JST に TimeTree の当日予定を自分の LINE に 1 通で通知
- 方式: サーバーレス（GitHub Actions のみ）
- 備考: TimeTree 公式エクスポート不可のため、外部ツールで ICS を生成 → 当日抽出 → LINE Notify 送信

## 実行/運用
- スケジュール: `cron: 0 21 * * *`（21:00 UTC = 06:00 JST）
- 許容遅延: GitHub Actions の特性上、±数分の遅延を許容
- 非アクティブ停止: リポジトリが長期間無活動だと停止し得る（既定挙動）。本ジョブは日次実行のため実害は小
- 重複防止: `concurrency: { group: morning-timetree, cancel-in-progress: true }`
- 手動実行: `workflow_dispatch` で `date` 入力により任意日でのリハーサルを可能に

## 依存
- Python 3.12
- ライブラリ: `icalendar`, `requests`（安定後にバージョン固定）
- 外部ツール: `timetree-exporter`（ICS 生成用。CLI 引数はバージョンにより差異あり）

## タイムゾーン / 当日抽出
- TZ: `Asia/Tokyo`（コード側は `zoneinfo` を使用）
- 当日範囲: `[今日 00:00 JST, 翌日 00:00 JST)`（終端は排他的）
- 正規化:
  - `date` 型 → その日の `00:00 JST`
  - `datetime`（naive）→ JST とみなす
  - `datetime`（tz 付き）→ JST へ変換
- 終日判定: 元の `DTSTART` が `date` 型の場合のみ終日扱い
- 包含条件（安全形）: `event_end > day_start && event_start < next_day_start`
- 表示用クリップ: `start = max(event_start, day_start)`, `end = min(event_end, next_day_start)`

## 表示フォーマット
- ヘッダ: `📅 本日の予定 yyyy/MM/dd(曜)`
- 並び順: 終日 → 時間指定（開始時刻昇順）
- 行:
  - 終日: `• 終日 タイトル`
  - 時間: `• HH:mm–HH:mm タイトル`
  - 場所: ある場合のみ ` ＠場所` を付加
- 予定なし: `🟢 予定はありません`
- 文字数制限: LINE Notify は 1000 文字上限 → 超過時は `…ほかN件` を付与して切り詰め

## エラー/再送
- 失敗時は Fail で終了（ログから調査）。自動再送は不要
- LINE 送信は 10 秒タイムアウト。4xx は即 Fail、5xx は再試行は行わない（必要なら将来追加）

## Secrets（GitHub Actions）
- `TIMETREE_EMAIL`, `TIMETREE_PASSWORD`, `TIMETREE_CALENDAR_CODE`, `LINE_TOKEN`
- Secrets 以外に平文で保持しない

## ファイル構成（最小）
```
. 
├─ .github/workflows/notify.yml
├─ notify.py
├─ requirements.txt
├─ DESIGN.md
└─ SECURITY.md
```

## 受け入れ基準
- 06:00 JST 前後に 1 日 1 回通知される
- JST の「今日」にかかるイベントのみ表示される（終日・跨ぎ含む）
- 終日/時間/場所が仕様通りに整形される
- 予定ゼロ時に「🟢 予定はありません」と表示される
- 1000 文字超でもエラーにならず適切に切り詰められる
- Secrets 以外に資格情報が露出しない

