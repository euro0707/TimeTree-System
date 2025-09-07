# Morning TimeTree

毎朝 06:00 JST に TimeTree の当日予定を通知します。初期は LINE Notify を想定しつつ、LINE Messaging API にも対応しています。

## セットアップ

1) Secrets を設定（GitHub リポジトリ Settings → Secrets and variables → Actions）
- `TIMETREE_EMAIL`: TimeTree ログインメール
- `TIMETREE_PASSWORD`: TimeTree パスワード
- `TIMETREE_CALENDAR_CODE`: カレンダーURL末尾の英数字
- 通知方式（どちらか）
  - LINE Notify を使う場合: `LINE_TOKEN`
  - LINE Messaging API を使う場合: `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_USER_ID`

2) 内容確認（任意）
- ローカルに Python 3.12+ があれば、以下で整形結果のみ確認できます。
  ```bash
  pip install -r requirements.txt
  python notify.py --ics sample.ics --date 2025-09-07 --dry-run
  ```

3) GitHub Actions を実行
- 手動: Actions → "Morning TimeTree" → Run workflow（必要なら `date` 入力に `YYYY-MM-DD`）
- 定期: 毎日 06:00 JST（`cron: 0 21 * * *`）に自動通知
  - Secrets に `LINE_CHANNEL_ACCESS_TOKEN` と `LINE_USER_ID` が両方設定されていれば Messaging API を優先します

## 実装の要点
- タイムゾーン: `zoneinfo` で JST に正規化
- 当日抽出: `[今日00:00, 翌日00:00)`（排他的終端）。終日/跨ぎイベントに対応
- 表示: 終日 → 時間順。場所はあれば `＠場所`。予定なしは `🟢 予定はありません`
- 文字数: 1000 文字上限で切り詰め（`…ほかN件`）
- 安全性: Secrets のみ使用。ジョブ権限は `contents: read` 最小権限。ICSは後片付けで削除

## トラブルシュート
- `calendar.ics が生成されませんでした`:
  - `timetree-exporter` の CLI 名や引数が環境で異なる場合があります。ワークフローの Export ステップを実環境の `--help` に合わせて調整してください。
- 日本語や絵文字が文字化けする:
  - ローカル実行時は `-X utf8` を付けるか、`PYTHONUTF8=1` を設定してください。
- LINE Notify が使えない/終了している:
  - `LINE_CHANNEL_ACCESS_TOKEN` と `LINE_USER_ID` を設定すると Messaging API で送信します。
- 通知が来ない:
  - Actions 実行ログを確認。Secrets やスケジュールの有効性、権限設定を点検

## 参考
- 仕様とセキュリティの詳細は `DESIGN.md` / `SECURITY.md` を参照
