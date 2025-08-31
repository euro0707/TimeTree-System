# TimeTree Notifier v3.0 - セキュリティセットアップガイド

## 🔐 **GitHub Secrets 設定**

### **必須シークレット一覧**

GitHub リポジトリの Settings > Secrets and variables > Actions で以下を設定：

#### **TimeTree 認証情報**
```
TIMETREE_EMAIL=your_timetree_email@example.com
TIMETREE_PASSWORD=your_secure_password
TIMETREE_CALENDAR_CODE=jUDDi-7ww775
```

#### **LINE Messaging API**
```
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_USER_ID=your_line_user_id
```

#### **Google APIs**
```
GOOGLE_CREDENTIALS={"type":"service_account","project_id":"..."}
GOOGLE_CALENDAR_ID=primary
```

#### **GAS (Google Apps Script)**
```
GAS_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
GAS_PROJECT_ID_STAGING=your_staging_gas_project_id
GAS_PROJECT_ID_PRODUCTION=your_production_gas_project_id
CLASP_CREDENTIALS={"access_token":"...","refresh_token":"..."}
```

#### **Slack Integration**
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
SLACK_ERROR_WEBHOOK=https://hooks.slack.com/services/T.../B.../...
```

#### **Discord Integration**
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/.../...
```

## 🛡️ **セキュリティベストプラクティス**

### **1. 認証情報の保護**
- ❌ **絶対にしないこと**: パスワードやトークンをコードに直接記述
- ✅ **推奨**: GitHub Secretsまたは暗号化された環境変数を使用
- ✅ **推奨**: 定期的な認証情報のローテーション

### **2. アクセス権限の最小化**
```yaml
# Google Calendar API権限例
scopes:
  - https://www.googleapis.com/auth/calendar.events
  # ❌ https://www.googleapis.com/auth/calendar (フルアクセスは避ける)
```

### **3. ネットワークセキュリティ**
- すべての外部API呼び出しはHTTPS
- Webhook URLの適切な検証
- レート制限とタイムアウト設定

### **4. データ保護**
- 個人情報の最小限の保存
- ログからの機密情報除外
- 一時ファイルの自動削除

## 🔧 **セットアップ手順**

### **Step 1: Google Cloud Setup**
```bash
# Google Cloud Console で新しいプロジェクト作成
gcloud projects create timetree-notifier-v3

# 必要なAPIの有効化
gcloud services enable calendar-json.googleapis.com
gcloud services enable texttospeech.googleapis.com

# サービスアカウント作成
gcloud iam service-accounts create timetree-sync-sa \
  --display-name="TimeTree Sync Service Account"

# 権限付与
gcloud projects add-iam-policy-binding timetree-notifier-v3 \
  --member="serviceAccount:timetree-sync-sa@timetree-notifier-v3.iam.gserviceaccount.com" \
  --role="roles/calendar.eventsEditor"

# 認証キー作成
gcloud iam service-accounts keys create credentials.json \
  --iam-account=timetree-sync-sa@timetree-notifier-v3.iam.gserviceaccount.com
```

### **Step 2: LINE Messaging API Setup**
1. [LINE Developers Console](https://developers.line.biz/) でChannelを作成
2. Channel Access Tokenを取得
3. Webhook URLを設定: `https://your-domain.com/webhook`

### **Step 3: Google Apps Script Setup**
```bash
# clasp CLI インストール
npm install -g @google/clasp

# Google Apps Script認証
clasp login

# プロジェクト作成
clasp create --title "TimeTree Voice Notifier" --type standalone

# デプロイ
clasp push
clasp deploy
```

## 🔍 **セキュリティ監査チェックリスト**

### **認証・認可**
- [ ] すべてのAPIキーがGitHub Secretsで管理されている
- [ ] サービスアカウントが最小権限の原則に従っている
- [ ] 認証トークンの有効期限が設定されている
- [ ] 2要素認証が有効になっている

### **通信セキュリティ**
- [ ] すべてのAPI通信がHTTPS
- [ ] Webhook URLが適切に保護されている
- [ ] レート制限が実装されている
- [ ] タイムアウト設定が適切

### **データセキュリティ**
- [ ] 個人情報の最小限の収集・保存
- [ ] ログに機密情報が含まれていない
- [ ] 一時ファイルが適切に削除される
- [ ] データの暗号化が実装されている

### **運用セキュリティ**
- [ ] エラー通知システムが動作している
- [ ] 監査ログが記録されている
- [ ] 定期的な権限レビューが実施されている
- [ ] インシデント対応手順が文書化されている

## ⚠️ **緊急時対応手順**

### **認証情報漏洩時**
1. **即座に実行**:
   ```bash
   # 該当するAPIキーを無効化
   # Google Cloud
   gcloud iam service-accounts keys delete KEY_ID --iam-account=SA_EMAIL
   
   # LINE
   # LINE Developers Console でChannel Access Tokenを再生成
   
   # GitHub
   # Settings > Secrets でシークレットを更新
   ```

2. **新しい認証情報の生成と配布**
3. **影響範囲の調査とログ確認**
4. **インシデント報告書の作成**

### **システム障害時**
1. **GitHub Actions ワークフロー停止**:
   ```bash
   # 手動でワークフローを無効化
   gh workflow disable timetree-daily-sync.yml
   ```

2. **エラー通知の確認**
3. **ログの分析**
4. **修正とテスト**
5. **段階的な復旧**

## 📊 **セキュリティモニタリング**

### **監視対象**
- API呼び出し失敗率
- 認証エラー頻度
- 異常なアクセスパターン
- システムリソース使用量

### **アラート設定**
```yaml
alerts:
  - name: "Authentication Failures"
    condition: "auth_failures > 5 in 1h"
    action: "slack_notification"
  
  - name: "API Rate Limit"
    condition: "rate_limit_errors > 10 in 5m"
    action: "email_notification"
  
  - name: "System Down"
    condition: "success_rate < 50% in 10m"
    action: "immediate_escalation"
```

## 🔄 **定期メンテナンス**

### **月次タスク**
- [ ] 認証情報の有効期限確認
- [ ] アクセスログの監査
- [ ] 不使用リソースのクリーンアップ
- [ ] セキュリティアップデートの適用

### **四半期タスク**
- [ ] 権限の全体レビュー
- [ ] セキュリティポリシーの更新
- [ ] ペネトレーションテストの実施
- [ ] 災害復旧手順のテスト

この設定により、TimeTree Notifier v3.0は企業レベルのセキュリティ基準を満たした状態で運用できます。