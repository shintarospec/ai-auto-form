# DeepBiz統合ガイド

## 📋 概要

本ワーカーシステムと企業DB「DeepBiz」の連携方法を説明します。

---

## 🏗️ アーキテクチャ

### 開発環境（Codespaces）

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│ Codespace 1: DeepBiz        │     │ Codespace 2: Worker         │
│                             │     │                             │
│  PostgreSQL (企業DB)        │     │  PostgreSQL (タスクDB)      │
│       ↓                     │     │       ↓                     │
│  Flask API (:5000)          │────▶│  Flask API (:5001)          │
│   /api/companies            │ API │   DeepBizClient             │
│   /api/companies/:id        │     │   ↓                         │
│                             │     │  Playwright + VNC           │
└─────────────────────────────┘     └─────────────────────────────┘
         │                                    │
         └─────────┬──────────────────────────┘
                   │
      GitHub Codespaces Port Forwarding
```

### 本番環境（VPS）

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│ VPS-1: DeepBiz (4GB)        │     │ VPS-2: Worker (4GB)         │
│ IP: 10.0.0.1                │     │ IP: 10.0.0.2                │
│                             │     │                             │
│  PostgreSQL (企業DB)        │     │  PostgreSQL (タスクDB)      │
│  ├─ company_lists           │     │  ├─ simple_tasks            │
│  ├─ company_info            │     │  ├─ simple_companies        │
│  └─ scrape_logs             │     │  └─ simple_products         │
│       ↓                     │     │       ↓                     │
│  Flask API                  │────▶│  Flask API                  │
│  Scrapy (常時稼働)          │     │  VNC + Playwright           │
└─────────────────────────────┘     └─────────────────────────────┘
         │                                    │
         └─────────┬──────────────────────────┘
                   │
           プライベートネットワーク
         または VPN/SSH トンネル
```

---

## 🔧 セットアップ

### 1. 開発環境での連携

#### DeepBiz側（Codespace 1）

1. **ポートフォワーディングURLを取得**:
   ```bash
   # CodespacesでFlaskを起動
   cd /path/to/deepbiz
   flask run --host=0.0.0.0 --port=5000
   
   # VS CodeのPORTSタブでポート5000の「転送されたアドレス」をコピー
   # 例: https://shintarospec-deepbiz-xxxxx.githubpreview.dev
   ```

2. **CORS設定を追加**:
   ```python
   # deepbiz/backend/app.py
   from flask_cors import CORS
   
   app = Flask(__name__)
   CORS(app)  # 重要: Codespaces間通信に必要
   ```

#### Worker側（Codespace 2 = 本Workspace）

1. **環境変数を設定**:
   ```bash
   # .env.development
   DEEPBIZ_API_URL=https://shintarospec-deepbiz-xxxxx.githubpreview.dev/api
   USE_MOCK_DEEPBIZ=false
   ```

2. **テスト実行**:
   ```bash
   cd /workspaces/ai-auto-form
   python3 << 'EOF'
   from backend.services.deepbiz_client import deepbiz_client
   
   # 企業リスト取得
   companies = deepbiz_client.get_companies(limit=5)
   for company in companies:
       print(f"{company['id']}: {company['name']} - {company['form_url']}")
   EOF
   ```

---

### 2. 本番環境での連携

#### VPS間プライベートネットワーク設定

**さくらVPS推奨構成**:

```bash
# VPS-1 (DeepBiz): 10.0.0.1
# VPS-2 (Worker):  10.0.0.2

# 両VPSでプライベートネットワーク設定
sudo ip addr add 10.0.0.X/24 dev eth1
sudo ip link set eth1 up

# 永続化
sudo tee -a /etc/network/interfaces << 'EOF'
auto eth1
iface eth1 inet static
    address 10.0.0.X
    netmask 255.255.255.0
EOF
```

#### Worker側（VPS-2）の環境変数

```bash
# /opt/ai-auto-form/.env
DEEPBIZ_API_URL=http://10.0.0.1:5000/api
DEEPBIZ_API_TIMEOUT=10
DEEPBIZ_API_RETRY=3
USE_MOCK_DEEPBIZ=false
```

---

## 📡 API仕様

### DeepBiz API エンドポイント

#### 1. 企業リスト取得

```
GET /api/companies
```

**パラメータ**:
- `limit` (int): 取得件数（デフォルト: 100）
- `industry` (string): 業界フィルタ（オプション）
- `has_form` (bool): 問い合わせフォームがある企業のみ（デフォルト: true）

**レスポンス**:
```json
{
  "companies": [
    {
      "id": 1,
      "name": "株式会社テストカンパニー",
      "website_url": "https://example.com",
      "form_url": "https://example.com/contact",
      "industry": "IT・ソフトウェア",
      "description": "Webサービス開発企業",
      "employee_count": 50,
      "created_at": "2025-12-01T00:00:00Z"
    }
  ],
  "total": 1000
}
```

#### 2. 企業詳細取得

```
GET /api/companies/:id
```

**レスポンス**:
```json
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
  "form_structure": {
    "fields": [
      {"name": "company", "type": "text", "required": true},
      {"name": "name", "type": "text", "required": true}
    ]
  },
  "created_at": "2025-12-01T00:00:00Z",
  "updated_at": "2025-12-15T10:30:00Z"
}
```

---

## 🧪 テストとモック

### モックモードの使用

DeepBizが利用不可の場合、自動的にモックデータを使用:

```bash
# 強制的にモックを使用
export USE_MOCK_DEEPBIZ=true

# テスト
python3 << 'EOF'
from backend.services.deepbiz_client import deepbiz_client
companies = deepbiz_client.get_companies(limit=3)
print(f"Retrieved {len(companies)} companies (mock mode)")
EOF
```

### エラーハンドリング

DeepBiz APIがエラーの場合、自動的にフォールバック:

```python
# DeepBizClient内部で自動処理
try:
    companies = deepbiz_client.get_companies()
except Exception:
    # モックデータを使用（ログに記録）
    companies = self._get_mock_companies()
```

---

## 🚀 VPS展開戦略

### Phase 2B-1: 2GB × 2台スタート（¥2,200/月）

**制約**:
- DeepBiz: 並列スクレイピング1プロセス、深夜のみ
- Worker: タスク1件ずつ実行

**期間**: 1-2ヶ月（負荷確認）

### Phase 2B-2: 4GB × 2台アップグレード（¥4,400/月）

**拡張**:
- DeepBiz: 並列2-3プロセス、24時間稼働
- Worker: 同時3-5タスク実行

**判断基準**:
- CPU使用率が常時70%超
- メモリスワップ発生
- タスク失敗率5%超

---

## 📊 監視とメトリクス

### 監視項目

```python
# backend/services/monitoring.py
import psutil
import requests

def check_deepbiz_health():
    """DeepBiz APIヘルスチェック"""
    try:
        response = requests.get(
            f"{DEEPBIZ_API_URL}/health",
            timeout=5
        )
        return response.status_code == 200
    except:
        return False

def get_resource_usage():
    """リソース使用状況"""
    return {
        'cpu_percent': psutil.cpu_percent(interval=1),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'deepbiz_api_status': check_deepbiz_health()
    }
```

---

## 📝 チェックリスト

### 開発環境セットアップ

- [ ] DeepBiz CodespaceのポートフォワーディングURL取得
- [ ] Worker Codespaceの環境変数設定
- [ ] DeepBiz APIのCORS設定
- [ ] 連携テスト実施
- [ ] モックモード動作確認

### VPS展開

- [ ] VPS 2台契約（2GBまたは4GB）
- [ ] プライベートネットワーク設定
- [ ] DeepBiz VPSセットアップ
- [ ] Worker VPSセットアップ（VNC統合）
- [ ] API連携テスト
- [ ] 監視設定
- [ ] 負荷テスト実施

---

**作成日**: 2025年12月22日  
**対象**: Phase 2B VPS展開
