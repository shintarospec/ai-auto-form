# AI AutoForm ワーカーシステム - DeepBiz連携仕様書

**作成日**: 2025年12月22日  
**対象**: DeepBiz開発チーム  
**目的**: ワーカーフォーム送信システムとの連携仕様共有

---

## 📋 目次

1. [プロジェクト概要](#プロジェクト概要)
2. [システム構成と役割分担](#システム構成と役割分担)
3. [現在の開発状況](#現在の開発状況)
4. [連携仕様（API）](#連携仕様api)
5. [データベース設計](#データベース設計)
6. [VPS展開計画](#vps展開計画)
7. [開発環境での連携方法](#開発環境での連携方法)
8. [技術スタック](#技術スタック)
9. [次のステップ](#次のステップ)

---

## 📋 プロジェクト概要

### プロジェクト名
**AI Auto Form**（AIオートフォーム）

### 目的
企業の問い合わせフォームへの営業アプローチを自動化し、効率的な新規顧客開拓を実現する

### 解決する課題
- 手動フォーム入力の非効率性（1件あたり5-10分）
- reCAPTCHA問題（完全自動化は不可能）
- 品質の不安定性

### 解決策：半自動化アプローチ
```
1. フォーム検出・入力は自動化（Playwright）
2. reCAPTCHA解決と最終送信は人間が実行
3. VNCで画面をリアルタイム表示
4. 1件あたり1-2分に短縮（80%削減）
```

---

## 🏗️ システム構成と役割分担

### 2つの主要システム

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│ ① DeepBiz                   │     │ ② Worker System             │
│   (企業DB・データ収集)        │────▶│   (フォーム送信・実行管理)    │
│                             │ API │                             │
│ - 企業リスト収集             │     │ - タスク管理                 │
│ - スクレイピング             │     │ - フォーム自動入力           │
│ - 企業情報生成（AI）         │     │ - VNC統合                   │
│ - データ管理・更新           │     │ - ワーカー管理               │
│ - セグメンテーション         │     │ - 成果追跡                   │
└─────────────────────────────┘     └─────────────────────────────┘
         │                                    │
         └────────────┬───────────────────────┘
                      │
              企業情報API連携
           (REST API、将来的に分離)
```

### 役割の明確化

#### DeepBiz（企業DB側）の役割
- ✅ 企業リストの収集・蓄積
- ✅ Webスクレイピング（常時実行）
- ✅ AI解析による企業情報生成
- ✅ データ品質管理
- ✅ **企業情報API提供** ← Worker側へ

#### Worker System（本システム）の役割
- ✅ DeepBizから企業情報を取得
- ✅ タスク生成・管理
- ✅ Playwrightによるフォーム自動入力
- ✅ VNC環境でのブラウザ画面表示
- ✅ ワーカー（作業者）管理
- ✅ 送信結果の記録・分析

---

## ✅ 現在の開発状況

### Phase 1 MVP（完成✅）

**達成内容**:
- ✅ PostgreSQL 3テーブル稼働中
- ✅ Flask API 4エンドポイント
- ✅ Simple Console UI
- ✅ Playwright自動入力（headless=True）

**データベース（PostgreSQL）**:
```sql
-- 企業マスター（一時的：将来DeepBizから取得）
CREATE TABLE simple_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    website_url TEXT NOT NULL,
    form_url TEXT NOT NULL,
    industry VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 商材マスター
CREATE TABLE simple_products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    message_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- タスク（実行単位）
CREATE TABLE simple_tasks (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES simple_companies(id),
    product_id INTEGER REFERENCES simple_products(id),
    status VARCHAR(20) DEFAULT 'pending',
    form_data JSON,
    screenshot_path TEXT,
    submitted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

**API エンドポイント**:
```
GET  /api/simple/tasks         - タスク一覧
GET  /api/simple/tasks/<id>    - タスク詳細
POST /api/simple/tasks/<id>/execute - 自動入力実行
POST /api/simple/tasks/<id>/complete - 完了マーク
```

### Phase 2（実装中）

**予定内容**:
- [ ] VNC統合（Xvfb + x11vnc + noVNC）
- [ ] Playwright GUI表示モード対応
- [ ] ワーカーコンソールUI
- [ ] **DeepBiz API連携** ← 重要！
- [ ] バッチ処理機能

---

## 🔗 連携仕様（API）

### DeepBiz側に実装してほしいAPI

Worker側からDeepBizへのAPI呼び出しを想定しています。

#### 1. 企業リスト取得

```http
GET /api/companies
```

**パラメータ**:
| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| limit | int | No | 取得件数（デフォルト: 100） |
| offset | int | No | オフセット（デフォルト: 0） |
| industry | string | No | 業界フィルタ |
| has_form | bool | No | 問い合わせフォームがある企業のみ（デフォルト: true） |
| status | string | No | ステータスフィルタ（例: "active", "pending"） |

**レスポンス例**:
```json
{
  "success": true,
  "companies": [
    {
      "id": 1,
      "name": "株式会社テストカンパニー",
      "website_url": "https://example.com",
      "form_url": "https://example.com/contact",
      "industry": "IT・ソフトウェア",
      "description": "Webサービス開発企業",
      "employee_count": 50,
      "address": "東京都渋谷区...",
      "phone": "03-1234-5678",
      "email": "info@example.com",
      "has_contact_form": true,
      "form_structure": {
        "fields": [
          {"name": "company", "type": "text", "required": true},
          {"name": "name", "type": "text", "required": true},
          {"name": "email", "type": "email", "required": true},
          {"name": "message", "type": "textarea", "required": true}
        ]
      },
      "last_contacted_at": null,
      "created_at": "2025-12-01T00:00:00Z",
      "updated_at": "2025-12-15T10:30:00Z"
    }
  ],
  "total": 1000,
  "limit": 100,
  "offset": 0
}
```

#### 2. 企業詳細取得

```http
GET /api/companies/:id
```

**レスポンス例**:
```json
{
  "success": true,
  "company": {
    "id": 1,
    "name": "株式会社テストカンパニー",
    "website_url": "https://example.com",
    "form_url": "https://example.com/contact",
    "industry": "IT・ソフトウェア",
    "description": "Webサービス開発企業",
    "employee_count": 50,
    "address": "東京都渋谷区...",
    "phone": "03-1234-5678",
    "email": "info@example.com",
    "has_contact_form": true,
    "form_structure": {
      "fields": [
        {
          "name": "company",
          "type": "text",
          "label": "会社名",
          "required": true,
          "selector": "#company_name"
        },
        {
          "name": "name",
          "type": "text",
          "label": "お名前",
          "required": true,
          "selector": "#your_name"
        },
        {
          "name": "email",
          "type": "email",
          "label": "メールアドレス",
          "required": true,
          "selector": "#email"
        },
        {
          "name": "phone",
          "type": "tel",
          "label": "電話番号",
          "required": false,
          "selector": "#phone"
        },
        {
          "name": "message",
          "type": "textarea",
          "label": "お問い合わせ内容",
          "required": true,
          "selector": "#message"
        }
      ],
      "submit_button_selector": "button[type='submit']"
    },
    "ai_analysis": {
      "business_summary": "Webサービス開発を主力事業とする...",
      "recommended_approach": "技術的な課題解決を訴求...",
      "target_decision_maker": "CTO、開発部門マネージャー"
    },
    "scraping_history": {
      "last_scraped_at": "2025-12-20T15:30:00Z",
      "scrape_count": 5,
      "data_freshness": "recent"
    },
    "created_at": "2025-12-01T00:00:00Z",
    "updated_at": "2025-12-20T15:30:00Z"
  }
}
```

#### 3. 企業ステータス更新（Worker側から）

```http
PATCH /api/companies/:id/status
```

**リクエスト**:
```json
{
  "last_contacted_at": "2025-12-22T10:00:00Z",
  "contact_status": "contacted",
  "notes": "フォーム送信完了"
}
```

**レスポンス**:
```json
{
  "success": true,
  "message": "Company status updated"
}
```

#### 4. ヘルスチェック

```http
GET /api/health
```

**レスポンス**:
```json
{
  "service": "DeepBiz API",
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "scraper_status": "running"
}
```

---

## 📊 データベース設計

### Worker側のテーブル構成

```sql
-- タスク管理（Worker側）
CREATE TABLE simple_tasks (
    id SERIAL PRIMARY KEY,
    company_id INTEGER,  -- DeepBizのcompany_id
    product_id INTEGER REFERENCES simple_products(id),
    status VARCHAR(20) DEFAULT 'pending',
    form_data JSON,
    screenshot_path TEXT,
    submitted BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- 商材マスター（Worker側で管理）
CREATE TABLE simple_products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    message_template TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### DeepBiz側のテーブル構成（想定）

```sql
-- 企業マスター（DeepBiz側）
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    website_url TEXT NOT NULL,
    form_url TEXT,
    industry VARCHAR(100),
    description TEXT,
    employee_count INTEGER,
    address TEXT,
    phone VARCHAR(20),
    email VARCHAR(100),
    has_contact_form BOOLEAN DEFAULT FALSE,
    form_structure JSON,  -- フォーム構造（Gemini解析結果）
    ai_analysis JSON,     -- AI解析結果
    last_contacted_at TIMESTAMP,
    contact_status VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- スクレイピング履歴
CREATE TABLE scrape_logs (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    scrape_type VARCHAR(50),
    status VARCHAR(20),
    data JSON,
    error_message TEXT,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🚀 VPS展開計画

### アーキテクチャ戦略

段階的にシステムを分離していく方針です。

#### Phase 2B-1: 最初の1-2ヶ月（現在）

```
VPS-1: DeepBiz (2GB, ¥1,100/月) 【既に稼働中】
├─ スクレイピング: 並列1プロセス
├─ 実行時間: 深夜集中（00:00-06:00）
└─ 企業DB API提供: 24時間

VPS-2: Worker (2GB, ¥1,100/月) 【これから展開】
├─ VNC統合
├─ タスク実行: 1件ずつ
└─ 実行時間: 日中（08:00-20:00）

合計コスト: ¥2,200/月
```

#### Phase 2B-2: 負荷確認後（2-3ヶ月後）

```
VPS-1: DeepBiz (4GB, ¥2,200/月)
├─ 並列: 2-3プロセス
└─ 24時間稼働

VPS-2: Worker (4GB, ¥2,200/月)
├─ 同時: 3-5タスク実行
└─ 安定稼働

合計コスト: ¥4,400/月
```

### サーバー間通信

**開発環境**: インターネット経由（HTTPS）
**本番環境**: プライベートネットワーク推奨

```bash
# さくらVPSのプライベートネットワーク設定例
# VPS-1 (DeepBiz): 10.0.0.1
# VPS-2 (Worker):  10.0.0.2

# Worker側の環境変数
DEEPBIZ_API_URL=http://10.0.0.1:5000/api
```

---

## 🔧 開発環境での連携方法

### DeepBiz側（VPS）

1. **CORS設定を追加**:
```python
# backend/app.py
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 重要: 外部からのAPI呼び出しを許可
```

2. **APIエンドポイントを公開**:
```python
@app.route('/api/companies', methods=['GET'])
def get_companies():
    limit = request.args.get('limit', 100, type=int)
    has_form = request.args.get('has_form', 'true').lower() == 'true'
    
    # DeepBizのDBから企業情報を取得
    companies = Company.query.filter_by(
        has_contact_form=has_form
    ).limit(limit).all()
    
    return jsonify({
        'success': True,
        'companies': [c.to_dict() for c in companies],
        'total': Company.query.count()
    })
```

3. **VPSのIPアドレスまたはドメインを共有**:
```
例: http://123.456.789.012:5000/api
または: https://deepbiz.yourdomain.com/api
```

### Worker側（Codespaces）

1. **環境変数を設定**:
```bash
# .env
DEEPBIZ_API_URL=http://123.456.789.012:5000/api
USE_MOCK_DEEPBIZ=false
```

2. **DeepBiz APIクライアントを使用**:
```python
from backend.services.deepbiz_client import deepbiz_client

# 企業リスト取得
companies = deepbiz_client.get_companies(limit=10, has_form=True)

# 企業詳細取得
company = deepbiz_client.get_company_detail(company_id=1)
```

---

## 💻 技術スタック

### 共通
| レイヤー | 技術 |
|---------|------|
| 言語 | Python 3.11+ |
| フレームワーク | Flask 3.0 |
| データベース | PostgreSQL 16 |
| インフラ | さくらVPS (Ubuntu 24.04) |

### DeepBiz固有
| レイヤー | 技術 |
|---------|------|
| スクレイピング | Scrapy / Playwright / BeautifulSoup |
| AI | Google Gemini API |
| キュー管理 | Celery + Redis (推奨) |

### Worker固有
| レイヤー | 技術 |
|---------|------|
| ブラウザ自動化 | Playwright 1.40 |
| VNC | Xvfb + x11vnc + noVNC |
| UI | Vanilla JavaScript + Tailwind CSS |

---

## 📝 次のステップ

### DeepBiz側でお願いしたいこと

#### 1. **API実装**（優先度: 高）
- [ ] `GET /api/companies` - 企業リスト取得
- [ ] `GET /api/companies/:id` - 企業詳細取得
- [ ] `PATCH /api/companies/:id/status` - ステータス更新
- [ ] `GET /api/health` - ヘルスチェック

#### 2. **CORS設定**（優先度: 高）
```python
from flask_cors import CORS
CORS(app)
```

#### 3. **API仕様書の共有**（優先度: 中）
- エンドポイント一覧
- レスポンス形式
- 認証方法（API Keyの有無）

#### 4. **接続情報の共有**（優先度: 高）
- VPSのIPアドレスまたはドメイン
- APIのベースURL（例: `http://xxx.xxx.xxx.xxx:5000/api`）
- 認証情報（必要な場合）

#### 5. **データベーススキーマの共有**（優先度: 中）
- 企業テーブルの構造
- 利用可能なフィールド一覧

### Worker側で実施すること

#### 1. **連携テスト**
- [ ] DeepBiz APIへの接続確認
- [ ] 企業データの取得テスト
- [ ] エラーハンドリングの確認

#### 2. **VNC統合開発**（Phase 2）
- [ ] Xvfb + x11vnc + noVNC セットアップ
- [ ] Playwright GUI表示モード対応
- [ ] ワーカーコンソールUI開発

#### 3. **VPS展開**
- [ ] Worker用VPS契約（2GB）
- [ ] 環境構築
- [ ] DeepBizとのAPI連携設定

---

## 🤝 連絡・調整事項

### 質問がある場合

以下の項目について不明点があれば、気軽に相談してください：

1. **API仕様**: レスポンス形式、フィールド名、データ型
2. **認証方法**: API Key、JWT、Basic認証など
3. **レート制限**: API呼び出しの頻度制限
4. **データ鮮度**: スクレイピングの更新頻度
5. **エラーハンドリング**: エラーレスポンスの形式

### 相互確認が必要なこと

- [ ] APIエンドポイントの最終仕様
- [ ] データベーススキーマの整合性
- [ ] VPS間のネットワーク設定
- [ ] セキュリティ設定（IP制限、HTTPS等）

---

## 📚 参考資料

### 本ドキュメントの元資料

- [HANDOFF.md](HANDOFF.md) - Phase 1完成状態
- [PROJECT_SPEC.md](PROJECT_SPEC.md) - プロジェクト全体仕様
- [docs/API.md](docs/API.md) - Worker側API仕様
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - システム構成
- [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md) - VPS展開ガイド

---

**連絡先**: GitHub Issues または直接連絡  
**最終更新**: 2025年12月22日  
**バージョン**: 1.0

---

## 🎯 まとめ

### DeepBizとWorkerシステムの関係

```
DeepBiz（企業データ提供）
    ↓ API連携
Workerシステム（フォーム送信実行）
    ↓
営業活動の効率化
```

**現状**:
- DeepBiz: 2GB VPSで稼働中
- Worker: Phase 1完成、Phase 2開発中（Codespaces）

**次のステップ**:
1. DeepBiz側でAPI実装
2. Worker側で連携テスト
3. Worker用VPS展開（2GB）
4. 統合テスト・本番運用開始

ご協力よろしくお願いいたします！🚀
