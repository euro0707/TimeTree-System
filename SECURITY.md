# Morning TimeTree — セキュリティ指針（個人運用・修正版）

## 1. 資格情報の管理
- Secrets のみで保管（コード/ログに直書き禁止）
  - `TIMETREE_EMAIL`, `TIMETREE_PASSWORD`, `TIMETREE_CALENDAR_CODE`, `LINE_TOKEN`
- 可能なら通知専用の TimeTree アカウントを作成し、対象カレンダーのみ共有
- LINE Notify トークンは用途名を明記し、漏洩時は即 revoke（失効）可能に
- 半年に一度のローテーションを推奨

## 2. リポジトリ設定
- Private 推奨
- 外部 PR でワークフローが勝手に動かない既定設定を維持
- Secret scanning / Dependabot alerts を ON
- 必要に応じて Environments で Secrets へのアクセスを制限

## 3. GitHub Actions の堅牢化
- 最小権限: `permissions: contents: read`
- 競合抑止: `concurrency: { group: morning-timetree, cancel-in-progress: true }`
- `timeout-minutes` を設定（必要に応じて追加）
- 依存の安定後はバージョン固定（`requirements.txt` にピン留め）

## 4. データ露出の最小化
- ICS/JSON を Pages / Artifacts 等で公開しない
- ログに予定の詳細や Secrets を出力しない（`notify.py` は安全出力）
- 必要であれば `::add-mask::` で機微情報を明示的にマスク

## 5. インシデント対応
- LINE トークン漏洩: 即 revoke → 新トークンを Secrets に設定 → 再実行
- TimeTree アカウント情報漏洩: パスワード変更 + 共有カレンダー権限見直し
- Actions の実行履歴/直近コミット点検で不審挙動の有無を確認
