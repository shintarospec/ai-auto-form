# AI AutoForm - API仕様

## ベースURL

- **GitHub Codespaces**: `https://laughing-spoon-x5gwpjvxr5w72vpv4-5000.app.github.dev`
- **ローカル開発**: `http://localhost:5001`

## 認証

現在は認証なし（LocalStorageベース）

将来的にJWT認証を実装予定

## エンドポイント一覧

### ヘルスチェック

#### GET /api/health

システムの稼働状況を確認

**レスポンス**
```json
{
  "service": "AI AutoForm API",
  "status": "healthy",
  "version": "2.0.0"
}
```

---

### タスク管理

#### POST /api/tasks/{task_id}/submit

フォームの自動送信を実行

**リクエスト**
```json
{
  "companyUrl": "https://example.com/contact",
  "formData": {
    "company": "株式会社AIソリューションズ",
    "name": "山田 太郎",
    "email": "yamada@ai-solutions.co.jp",
    "phone": "03-1234-5678",
    "message": "貴社のビジネスに最適なソリューションをご提案させていただきたく..."
  }
}
```

**レスポンス（成功・送信完了）**
```json
{
  "success": true,
  "submitted": true,
  "fields_filled": ["name", "email", "company", "phone", "message"],
  "has_recaptcha": false,
  "screenshot": "/tmp/form_screenshot_1234567890.png",
  "final_url": "https://example.com/thank-you",
  "message": "5個のフィールドに入力完了 → 送信完了"
}
```

**レスポンス（成功・入力のみ）**
```json
{
  "success": true,
  "submitted": false,
  "fields_filled": ["name", "email", "company", "phone", "message"],
  "has_recaptcha": false,
  "screenshot": "/tmp/form_screenshot_1234567890.png",
  "final_url": "http://localhost:8000/test-form.html",
  "message": "5個のフィールドに入力完了 → 送信未完了"
}
```

**レスポンス（エラー）**
```json
{
  "error": "Target page, context or browser has been closed",
  "traceback": "..."
}
```

**ステータスコード**
- `200 OK` - 処理成功
- `400 Bad Request` - リクエストエラー
- `500 Internal Server Error` - サーバーエラー

**レート制限**
- 10リクエスト/分

---

## データモデル

### TaskSubmission

フォーム送信リクエストのデータ構造

```typescript
interface TaskSubmissionRequest {
  companyUrl: string;        // フォームURL
  formData: {
    company: string;         // 会社名
    name: string;            // 担当者名
    email: string;           // メールアドレス
    phone?: string;          // 電話番号（オプション）
    message: string;         // メッセージ本文
  };
}
```

### TaskSubmissionResponse

フォーム送信結果のデータ構造

```typescript
interface TaskSubmissionResponse {
  success: boolean;          // 処理成功フラグ
  submitted: boolean;        // 送信完了フラグ
  fields_filled: string[];   // 入力されたフィールド
  has_recaptcha: boolean;    // reCAPTCHA存在フラグ
  screenshot?: string;       // スクリーンショットパス
  final_url: string;         // 最終URL
  message: string;           // 結果メッセージ
  error?: string;            // エラーメッセージ
}
```

---

## エラーハンドリング

### エラーレスポンス形式

```json
{
  "error": "エラーメッセージ",
  "traceback": "詳細なスタックトレース（開発環境のみ）"
}
```

### 一般的なエラー

| エラーメッセージ | 原因 | 対処法 |
|----------------|------|--------|
| `URLとフォームデータは必須です` | リクエストパラメータ不足 | companyUrlとformDataを確認 |
| `Target page, context or browser has been closed` | ブラウザクラッシュ | Playwrightの再インストール |
| `Host system is missing dependencies` | システム依存関係不足 | `playwright install-deps` |
| `No module named 'playwright'` | Playwrightが未インストール | `pip install playwright` |

---

## 将来の拡張予定

### 企業分析API（準備中）

#### POST /api/companies/analyze

企業サイトをAI分析

**リクエスト**
```json
{
  "url": "https://example.com",
  "companyName": "Example株式会社"
}
```

**レスポンス**
```json
{
  "businessDescription": "...",
  "strengths": [...],
  "targetCustomers": "...",
  "keyTopics": [...]
}
```

### メッセージ生成API（準備中）

#### POST /api/messages/generate

AIメッセージ生成

**リクエスト**
```json
{
  "companyAnalysis": {...},
  "productInfo": {...}
}
```

**レスポンス**
```json
{
  "message": "貴社の...",
  "tone": "professional"
}
```

---

## 使用例

### cURL

```bash
curl -X POST http://localhost:5001/api/tasks/1/submit \
  -H "Content-Type: application/json" \
  -d '{
    "companyUrl": "http://localhost:8000/test-form.html",
    "formData": {
      "company": "株式会社テスト",
      "name": "山田太郎",
      "email": "test@example.com",
      "phone": "03-1234-5678",
      "message": "テストメッセージです"
    }
  }'
```

### JavaScript

```javascript
const response = await fetch('http://localhost:5001/api/tasks/1/submit', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    companyUrl: 'http://localhost:8000/test-form.html',
    formData: {
      company: '株式会社テスト',
      name: '山田太郎',
      email: 'test@example.com',
      phone: '03-1234-5678',
      message: 'テストメッセージです'
    }
  })
});

const result = await response.json();
console.log(result);
```
