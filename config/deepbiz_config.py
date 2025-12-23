"""
DeepBiz API連携設定

開発環境（Codespaces）と本番環境（VPS）で切り替え可能
"""
import os

# DeepBiz API設定
DEEPBIZ_API_URL = os.getenv(
    'DEEPBIZ_API_URL',
    'http://localhost:5000/api'  # デフォルトはローカル
)

# Codespaces環境での設定例:
# export DEEPBIZ_API_URL="https://shintarospec-deepbiz-xxxx.githubpreview.dev/api"

# VPS環境での設定例:
# export DEEPBIZ_API_URL="http://10.0.0.1:5000/api"  # プライベートネットワーク
# または
# export DEEPBIZ_API_URL="https://deepbiz.yourdomain.com/api"  # パブリックURL

DEEPBIZ_API_TIMEOUT = int(os.getenv('DEEPBIZ_API_TIMEOUT', '10'))  # 秒
DEEPBIZ_API_RETRY = int(os.getenv('DEEPBIZ_API_RETRY', '3'))

# 開発モード（モックデータ使用）
USE_MOCK_DATA = os.getenv('USE_MOCK_DEEPBIZ', 'false').lower() == 'true'
