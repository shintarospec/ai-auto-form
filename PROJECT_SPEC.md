# AI Auto Form - 企画・仕様書

## 📋 プロジェクト概要

### プロジェクト名
**AI Auto Form**（AIオートフォーム）

### 目的
企業の問い合わせフォームへの営業アプローチを自動化し、効率的な新規顧客開拓を実現するシステム

### 対象ユーザー
- BtoB営業チーム
- マーケティング部門
- フリーランス営業代行
- SaaS企業の営業部門

---

## 🎯 プロジェクトの背景と課題

### 従来の課題

1. **手動作業の非効率性**
   - 企業の問い合わせフォーム入力に1件あたり5-10分
   - 100社にアプローチするだけで8-16時間必要
   - 単純作業による集中力の低下

2. **スケーラビリティの欠如**
   - 人手に依存するため大量処理が困難
   - 営業担当者の時間の大部分が単純作業に費やされる

3. **品質の不安定性**
   - 手動入力のミス
   - テンプレートの適用漏れ
   - 担当者による品質のばらつき

4. **reCAPTCHA問題**
   - 完全自動化は不可能
   - 人間による確認が必須

### 本システムの解決策

✅ **半自動化アプローチ**
- フォーム検出・入力は自動化
- reCAPTCHA解決と最終送信は人間が実行
- 1件あたり1-2分に短縮（80%削減）

✅ **VNCベースの可視化**
- ブラウザ画面をリアルタイム表示
- 人間が自然に操作できる
- トラブル時の即座な介入が可能

✅ **AI活用による柔軟性**
- Gemini APIでフォーム構造を解析
- 動的なセレクタ生成
- 様々なフォームに対応

---

## 🏗️ システム構成

### 機能の全体像

システムは大きく以下の機能群に分類されます：

#### ①企業DB（データ収集・管理）
- **企業リスト収集**: スクレイピングによる自動収集
- **企業情報生成（AI）**: URL→スクレイピング→AI解析→データ生成
- **企業情報更新**: 重複排除、情報鮮度管理
- **セグメンテーション**: 業界・規模による分類

#### ②ワーカーフォーム送信（実行・管理）
- **フォーム送信**: 自動入力+手動確認・送信（VNC統合）
- **ワーカー管理**: タスク振り分け、成果管理、評価
- **案件管理（AI）**: 企業別カスタマイズ
- **エラーハンドリング**: リトライ・ログ記録

#### ③分析・レポート（Phase 3以降）
- 成功率分析、ROI計算
- ワーカーパフォーマンス分析
- 日次・週次・月次レポート

#### ④認証・権限管理
- 管理者/ワーカー認証
- ロールベースアクセス制御（RBAC）
- APIトークン管理

---

### アーキテクチャ戦略：段階的進化

#### 🎯 基本方針：モノリシック → モジュラーモノリス → マイクロサービス

企業DBは単体でも価値があるサービスですが、初期段階では**モノリシック構成**を採用し、成長に応じて段階的に分離します。

##### Phase 1-2: モノリシック構成（現在〜6ヶ月）

**構成**:
```
┌─────────────────────────────────────┐
│    さくらVPS 2-4GB（単一サーバー）    │
│                                     │
│  Flask API Server                   │
│  ┌────────────┐  ┌────────────┐    │
│  │ 企業DB     │  │ ワーカー   │    │
│  │ Blueprint  │  │ Blueprint  │    │
│  └────────────┘  └────────────┘    │
│                                     │
│  PostgreSQL（単一DB、論理分離）      │
│  ┌────────────┐  ┌────────────┐    │
│  │ company_*  │  │ worker_*   │    │
│  │ テーブル群 │  │ テーブル群 │    │
│  └────────────┘  └────────────┘    │
└─────────────────────────────────────┘
```

**理由**:
- ✅ MVPの迅速な検証
- ✅ 低コスト・低リスク（月額3,000円程度）
- ✅ デプロイ・運用が容易
- ✅ データベーストランザクション管理が簡単

**データベース命名規則**:
```sql
-- 企業DB系（接頭辞: company_）
company_lists, company_info, company_scrape_logs

-- ワーカー系（接頭辞: worker_）
worker_accounts, worker_tasks, worker_performance

-- 共通
products, projects
```

##### Phase 3: モジュラーモノリス（6ヶ月〜1年）

**構成**: 同一サーバー、コードレベルで分離

```python
backend/
├── companies/          # 企業DB機能（独立性高）
│   ├── api.py         # API Blueprint
│   ├── models.py      # データモデル
│   ├── scraper.py     # スクレイピング
│   └── ai_analyzer.py # AI解析
├── workers/           # ワーカー機能
│   ├── api.py
│   ├── models.py
│   └── vnc_service.py
└── shared/            # 共通機能
    ├── auth.py
    └── database.py
```

**移行タイミングの判断基準**:
- コードベースが肥大化（10,000行超）
- 企業DBの単体販売を検討開始
- チーム規模が3名以上

##### Phase 4: マイクロサービス化（1年以降）

**構成**: サーバー分離

```
┌──────────────────────┐    ┌──────────────────────┐
│ VPS 1: 企業DBサーバー │◄───┤ VPS 2: ワーカーサーバー│
│  - REST API          │ API│  - タスク実行       │
│  - PostgreSQL        │    │  - VNC統合          │
│  - スクレイピング    │    │  - PostgreSQL       │
└──────────────────────┘    └──────────────────────┘
```

**移行判断基準**（以下3つ以上を満たす場合）:
- [ ] 月間売上が100万円以上
- [ ] 企業DBの単体販売ニーズが確定
- [ ] スケーリングボトルネックが明確
- [ ] 運用体制が整っている（DevOps経験者在籍）
- [ ] 月額インフラコスト1万円以上が許容可能

**メリット**:
- ✅ 独立スケーリング
- ✅ 企業DB単体での販売可能
- ✅ 障害の影響範囲を限定

**デメリット**:
- ❌ 開発・運用の複雑性増大
- ❌ コスト増（VPS 2台分）
- ❌ ネットワークレイテンシ

---

### Phase 2実装時のアーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│                    Webブラウザ（UI）                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  管理コンソール │  │ ワーカーコンソール │  │  noVNC Viewer │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────┬───────────────┬───────────────┬──────────┘
              │               │               │
         ┌────┴───────────────┴───────────────┴────┐
         │          Nginx（リバースプロキシ）        │
         └────┬───────────────┬───────────────┬────┘
              │               │               │
    ┌─────────▼────┐  ┌───────▼─────┐  ┌─────▼──────┐
    │  Flask API   │  │  WebSocket  │  │   Static   │
    │  (Port 5001) │  │  (Port 6080)│  │   Files    │
    └─────────┬────┘  └───────┬─────┘  └────────────┘
              │               │
    ┌─────────▼────────────────▼─────────────┐
    │         VNC環境（仮想ディスプレイ）      │
    │  ┌──────┐  ┌──────┐  ┌──────┐         │
    │  │ Xvfb │→│x11vnc│→│noVNC │         │
    │  └──────┘  └──────┘  └──────┘         │
    │      ↓                                 │
    │  ┌──────────────────────────┐         │
    │  │  Playwright + Chromium   │         │
    │  │  (自動フォーム入力)       │         │
    │  └──────────────────────────┘         │
    └────────────────────────────────────────┘
              │
    ┌─────────▼─────────┐
    │   PostgreSQL 16   │
    │   (データベース)   │
    └───────────────────┘
```

### 技術スタック

| レイヤー | 技術 | 用途 |
|---------|------|------|
| **フロントエンド** | HTML/CSS/JavaScript | UI（コンソール画面） |
| **バックエンド** | Flask 3.0 (Python 3.12) | REST API |
| **データベース** | PostgreSQL 16 | データ永続化 |
| **ブラウザ自動化** | Playwright 1.40 | フォーム入力自動化 |
| **VNC** | Xvfb + x11vnc + noVNC | リモートデスクトップ |
| **AI** | Google Gemini API | フォーム解析 |
| **リバースプロキシ** | Nginx | ルーティング・SSL |
| **インフラ** | さくらVPS (Ubuntu 24.04) | ホスティング |

---

## 📊 データベース設計

### Phase 1 MVP（シンプル版）

```sql
-- 企業マスター
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
    status VARCHAR(20) DEFAULT 'pending',  -- pending, in_progress, completed, failed
    form_data JSON,  -- 入力するフォームデータ
    screenshot_path TEXT,
    submitted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);
```

### Phase 2以降（完全版）

```sql
-- ワーカー管理
CREATE TABLE workers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'idle',  -- idle, busy, error, offline
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- プロジェクト管理
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ターゲット企業
CREATE TABLE targets (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    company_name VARCHAR(200) NOT NULL,
    form_url TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- タスク実行履歴
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    worker_id INTEGER REFERENCES workers(id),
    target_id INTEGER REFERENCES targets(id),
    product_id INTEGER REFERENCES products(id),
    status VARCHAR(20) DEFAULT 'pending',
    form_data JSON,
    screenshot_path TEXT,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);
```

---

## 🎨 機能仕様

### Phase 1 MVP（現在完成）

#### 1. シンプルコンソール UI
- **URL**: `/simple-console.html`
- **機能**:
  - タスク一覧表示（企業×商材）
  - タスク詳細表示
  - 統計情報（総数、未処理、完了、失敗）
  - リアルタイム更新（5秒間隔）

#### 2. 基本API（4エンドポイント）
- `GET /api/simple/tasks` - タスク一覧取得
- `GET /api/simple/tasks/:id` - 特定タスク取得
- `POST /api/simple/tasks/:id/execute` - 自動入力実行
- `POST /api/simple/tasks/:id/complete` - 完了マーク

#### 3. Playwright自動化
- フォームページを開く
- フォーム要素を検出（複数セレクタ試行）
- データを自動入力
- スクリーンショット撮影（headlessモード）

#### 4. 制約
- ❌ VNCなし（スクリーンショットのみ）
- ❌ 手動操作不可
- ❌ reCAPTCHA対応不可
- ✅ 開発環境（Codespaces）で動作確認済み

---

### Phase 2（VNC統合・ワーカー管理）

#### 1. VNC環境の構築
- **Xvfb**: 仮想ディスプレイ（:99）
- **x11vnc**: VNCサーバー（Port 5900）
- **noVNC**: WebベースVNCクライアント（Port 6080）
- **Playwright**: headless=False で仮想ディスプレイに接続

#### 2. ワーカー管理機能
- 複数ワーカーの登録・管理
- ワーカーごとのタスク割り当て
- ステータス監視（idle, busy, error, offline）
- ハートビート機能（死活監視）

#### 3. バッチ処理機能
- 複数タスクの一括実行
- エラーハンドリング＆自動リトライ
- 実行ログの記録
- 進捗通知

#### 4. VNC統合フロー
```
1. ユーザーがタスクを選択
2. 「自動入力実行」をクリック
3. VNC画面でブラウザが起動
4. Playwrightが自動入力を実行
5. ユーザーがVNC画面でフォーム内容を確認
6. reCAPTCHAを手動で解決
7. 送信ボタンを手動でクリック
8. 「送信完了」をクリックしてタスク完了
```

#### 5. ワーカーコンソール
- **URL**: `/worker-console.html`
- **機能**:
  - 自分に割り当てられたタスク一覧
  - VNC画面の埋め込み表示
  - タスク実行・完了操作
  - エラー報告

---

### Phase 3（AI統合・高度な自動化）

#### 1. Gemini API統合
- フォームHTML構造の自動解析
- 動的なセレクタ生成
- フォーム項目の自動マッピング

#### 2. 学習機能
- 成功したフォーム入力パターンを学習
- セレクタの精度向上
- エラーパターンの蓄積と回避

#### 3. 高度な機能
- 複数ステップフォームの対応
- 条件分岐の自動判定
- 添付ファイルのアップロード
- 確認画面の自動進行

#### 4. レポート機能
- 日次・週次・月次レポート
- 成功率の分析
- エラー傾向の可視化
- ROI計算

---

## 🔐 セキュリティ要件

### 1. 認証・認可
- JWT認証
- ロールベースアクセス制御（RBAC）
- セッション管理

### 2. データ保護
- 環境変数による機密情報管理
- データベース接続の暗号化
- パスワードのハッシュ化

### 3. 通信の暗号化
- SSL/TLS証明書（Let's Encrypt）
- HTTPS強制リダイレクト
- WebSocket通信の暗号化

### 4. アクセス制御
- ファイアウォール（UFW）
- fail2ban（ブルートフォース攻撃対策）
- IPホワイトリスト（管理画面）

### 5. ログ・監査
- アクセスログの記録
- エラーログの集約
- 監査ログ（重要操作の記録）

---

## 📈 非機能要件

### 1. パフォーマンス
- API応答時間: 200ms以内（95パーセンタイル）
- 同時実行タスク: 3-5タスク（2GBメモリ）
- データベースクエリ: 100ms以内

### 2. 可用性
- システム稼働率: 99%以上
- 自動再起動（systemd）
- ヘルスチェック機能

### 3. スケーラビリティ
- 水平スケーリング対応（将来）
- データベースパーティショニング（将来）
- キャッシュ層の導入（将来）

### 4. 保守性
- ログの一元管理
- 自動バックアップ（日次）
- ドキュメントの整備

---

## 🚀 デプロイ戦略

### 開発環境
- **場所**: GitHub Codespaces
- **用途**: Phase 1 MVP開発・テスト
- **制約**: VNC不可（headlessモードのみ）

### ステージング環境
- **場所**: さくらVPS 1G/2G
- **用途**: Phase 2 VNC統合テスト
- **構成**: 本番環境と同等

### 本番環境
- **場所**: さくらVPS 2G以上
- **用途**: 実運用
- **構成**:
  - Nginx（リバースプロキシ・SSL）
  - systemd（サービス管理）
  - PostgreSQL（データベース）
  - VNC環境（Xvfb + x11vnc + noVNC）

---

## 📅 リリース計画

### Phase 1 MVP（完了）
- ✅ シンプルな3テーブルDB
- ✅ 基本API（4エンドポイント）
- ✅ シンプルコンソールUI
- ✅ Playwright自動化（headless）
- ✅ Codespaces環境で動作確認

### Phase 2（2-3日）
- [ ] VPS環境構築
- [ ] VNC統合（Xvfb + x11vnc + noVNC）
- [ ] ワーカー管理機能
- [ ] バッチ処理機能
- [ ] ワーカーコンソールUI

### Phase 3（2-3日）
- [ ] Gemini API統合
- [ ] フォーム自動解析
- [ ] 学習機能
- [ ] レポート機能

---

## 💰 コスト見積もり

### 開発環境（現在）
- GitHub Codespaces: 無料枠内
- 合計: **¥0**

### 本番環境（月額）
| 項目 | 費用 |
|------|------|
| さくらVPS 2G | ¥2,200 |
| ドメイン | ¥100 |
| SSL証明書 | ¥0（Let's Encrypt） |
| Gemini API | ¥1,000（予想） |
| **合計** | **¥3,300/月** |

---

## 🎯 成功指標（KPI）

### 効率化指標
- **作業時間削減率**: 80%以上（10分→2分）
- **1日あたり処理可能数**: 100件以上
- **自動入力成功率**: 95%以上

### 品質指標
- **エラー率**: 5%以下
- **入力ミス率**: 1%以下
- **reCAPTCHA解決時間**: 平均30秒

### ビジネス指標
- **ROI**: 3ヶ月以内に投資回収
- **顧客満足度**: 4.5/5.0以上
- **継続利用率**: 90%以上

---

## 📚 参考資料

- [HANDOFF.md](HANDOFF.md) - VNC統合の技術仕様
- [VPS_DEPLOYMENT.md](VPS_DEPLOYMENT.md) - VPSデプロイ手順
- [VPS_SETUP_GUIDE.md](VPS_SETUP_GUIDE.md) - VPS初期セットアップ
- [PHASE1_MVP_GUIDE.md](PHASE1_MVP_GUIDE.md) - Phase 1完成ガイド
- [DEVELOPMENT_SCHEDULE_V2.md](DEVELOPMENT_SCHEDULE_V2.md) - 開発スケジュール

---

**作成日**: 2025年12月21日  
**バージョン**: 1.0  
**ステータス**: Phase 1 完了、Phase 2 準備中
