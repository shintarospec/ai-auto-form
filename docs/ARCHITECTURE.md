# AI AutoForm - システム構成

## 概要
AI AutoFormは、フォーム営業を自動化するシステムです。企業のお問い合わせフォームに対して、AIが分析した最適なメッセージを自動入力し、作業者が最終確認・送信を行います。

## システム構成

### フロントエンド
- **技術スタック**
  - Vanilla JavaScript (ES6+)
  - Tailwind CSS
  - Chart.js
  - LocalStorage

- **画面構成**
  - `admin-console.html` - 管理者画面
  - `worker-console.html` - 作業者画面
  - `test-form.html` - テスト用フォーム

### バックエンド
- **技術スタック**
  - Python 3.11+
  - Flask 3.0.0
  - Flask-CORS
  - Flask-JWT-Extended
  - Flask-Limiter

- **主要サービス**
  - `backend/app.py` - メインAPI
  - `backend/services/automation_service.py` - フォーム自動化
  - `backend/services/gemini_service.py` - AI分析（準備中）

### ブラウザ自動化
- **Playwright 1.40.0**
  - Webkit（Safari）- macOS環境
  - Chromium - その他の環境
  - ヘッドレスモード対応

### データ管理
- **現在**: LocalStorage
- **将来**: PostgreSQL

## アーキテクチャ図

```
┌─────────────────┐
│  管理者画面      │
│  - 企業管理      │
│  - プロジェクト  │
│  - 作業者管理    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────────┐
│  作業者画面      │◄────►│  Flask API       │
│  - タスク実行    │      │  - /api/tasks    │
│  - フォーム送信  │      │  - /api/submit   │
└────────┬────────┘      └────────┬─────────┘
         │                        │
         ▼                        ▼
┌─────────────────┐      ┌──────────────────┐
│  Playwright      │      │  Gemini API      │
│  - Webkit        │      │  - 企業分析      │
│  - Chromium      │      │  - メッセージ生成│
└─────────────────┘      └──────────────────┘
```

## データフロー

### フォーム送信フロー
1. 作業者が「自動送信スタート」をクリック
2. APIが `FormAutomationService` を起動
3. Playwrightがブラウザを開く
4. フォームに自動入力
5. 作業者がreCAPTCHA対応・送信
6. 送信完了を検出（3つの方法）
7. タスクステータスを更新
   - `submitted: true` → ポイント付与
   - `submitted: false` → 再実行可能

### 送信完了の検出方法
1. **URL変化** - thank-you、success等のキーワード
2. **成功メッセージ表示** - DOM要素の表示確認
3. **フォームリセット** - 入力値が空になる

## セキュリティ

### CORS設定
- GitHub Codespaces: `*.app.github.dev`
- ローカル開発: `http://localhost:*`

### レート制限
- Flask-Limiter使用
- API制限: 10リクエスト/分

## 環境

### 開発環境
- **GitHub Codespaces** - ヘッドレスモード
- **ローカル (macOS)** - ブラウザ表示モード

### ポート構成
- フロントエンド: 8000
- バックエンドAPI: 5001 (macOS) / 5000 (その他)

## スケーラビリティ

### Phase 1 ✅ 完了
- LocalStorageベースのプロトタイプ
- 基本的なフォーム自動化

### Phase 2 🚧 準備中
- PostgreSQLデータベース
- タスク履歴の永続化

### Phase 3 📋 計画中
- 複数作業者の並列処理
- リアルタイム進捗管理
