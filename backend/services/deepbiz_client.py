"""
DeepBiz API クライアント

企業DB（DeepBiz）との連携を担当
"""
import requests
from typing import List, Dict, Optional
import logging

import sys
sys.path.append('/workspaces/ai-auto-form')
from config.deepbiz_config import (
    DEEPBIZ_API_URL,
    DEEPBIZ_API_TIMEOUT,
    DEEPBIZ_API_RETRY,
    USE_MOCK_DATA
)

logger = logging.getLogger(__name__)


class DeepBizClient:
    """DeepBiz API クライアント"""
    
    def __init__(self):
        self.base_url = DEEPBIZ_API_URL
        self.timeout = DEEPBIZ_API_TIMEOUT
        self.retry = DEEPBIZ_API_RETRY
        self.use_mock = USE_MOCK_DATA
        
        logger.info(f"DeepBiz Client initialized: {self.base_url}")
        if self.use_mock:
            logger.warning("Using MOCK data (USE_MOCK_DEEPBIZ=true)")
    
    def get_companies(self, 
                     limit: int = 100, 
                     industry: Optional[str] = None,
                     has_form: bool = True) -> List[Dict]:
        """
        企業リストを取得
        
        Args:
            limit: 取得件数
            industry: 業界フィルタ
            has_form: 問い合わせフォームがある企業のみ
        
        Returns:
            企業情報のリスト
        """
        if self.use_mock:
            return self._get_mock_companies(limit)
        
        try:
            params = {
                'limit': limit,
                'has_form': has_form
            }
            if industry:
                params['industry'] = industry
            
            response = requests.get(
                f"{self.base_url}/companies",
                params=params,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Retrieved {len(data.get('companies', []))} companies from DeepBiz")
            return data.get('companies', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepBiz API error: {e}")
            # フォールバック: モックデータを返す
            logger.warning("Falling back to mock data")
            return self._get_mock_companies(limit)
    
    def get_company_detail(self, company_id: int) -> Optional[Dict]:
        """
        企業詳細情報を取得
        
        Args:
            company_id: 企業ID
        
        Returns:
            企業詳細情報
        """
        if self.use_mock:
            return self._get_mock_company_detail(company_id)
        
        try:
            response = requests.get(
                f"{self.base_url}/companies/{company_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"DeepBiz API error: {e}")
            return None
    
    def _get_mock_companies(self, limit: int) -> List[Dict]:
        """モック企業データ"""
        mock_data = [
            {
                'id': 1,
                'name': '株式会社テストカンパニー',
                'website_url': 'https://example.com',
                'form_url': 'https://example.com/contact',
                'industry': 'IT・ソフトウェア',
                'description': 'Webサービス開発企業',
                'employee_count': 50,
                'created_at': '2025-12-01T00:00:00Z'
            },
            {
                'id': 2,
                'name': '株式会社サンプル商事',
                'website_url': 'https://sample-corp.example',
                'form_url': 'https://sample-corp.example/inquiry',
                'industry': '商社',
                'description': '総合商社',
                'employee_count': 200,
                'created_at': '2025-12-02T00:00:00Z'
            },
            {
                'id': 3,
                'name': '合同会社デモ企画',
                'website_url': 'https://demo-planning.example',
                'form_url': 'https://demo-planning.example/contact-us',
                'industry': '広告・マーケティング',
                'description': 'マーケティング支援',
                'employee_count': 30,
                'created_at': '2025-12-03T00:00:00Z'
            }
        ]
        
        return mock_data[:limit]
    
    def _get_mock_company_detail(self, company_id: int) -> Dict:
        """モック企業詳細データ"""
        companies = self._get_mock_companies(100)
        for company in companies:
            if company['id'] == company_id:
                return company
        return None


# グローバルインスタンス
deepbiz_client = DeepBizClient()
