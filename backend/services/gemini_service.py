"""
AI AutoForm - Gemini AI Service
企業解析とメッセージ生成
"""

import google.generativeai as genai
import os
from typing import Dict, Optional
import json

class GeminiService:
    """Google Gemini API連携サービス"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初期化
        
        Args:
            api_key: Gemini API Key（Noneの場合は環境変数から取得）
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def analyze_company_website(self, html_content: str, company_url: str) -> Dict:
        """
        企業Webサイトを解析
        
        Args:
            html_content: WebサイトのHTML
            company_url: 企業URL
        
        Returns:
            解析結果（JSON形式）
        """
        prompt = f"""
あなたは企業分析の専門家です。以下の企業Webサイトを詳細に分析してください。

企業URL: {company_url}

Webサイトのコンテンツ:
{html_content[:15000]}

以下の形式でJSON形式で出力してください:

{{
  "businessDescription": "事業内容の要約（100-200文字）",
  "industry": "業種（例: IT・ソフトウェア、製造業、コンサルティング）",
  "strengths": ["強み1", "強み2", "強み3"],
  "targetCustomers": "ターゲット顧客層の説明",
  "keyTopics": ["関心がありそうなトピック1", "トピック2", "トピック3"],
  "companySize": "企業規模（推定: 大企業/中堅企業/中小企業/スタートアップ）",
  "painPoints": ["想定される課題1", "課題2"]
}}

重要: 必ずJSON形式のみを出力してください。余計な説明は不要です。
        """
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.3,  # 一貫性を重視
                    'max_output_tokens': 2000,
                }
            )
            
            # JSON解析
            result_text = response.text.strip()
            # マークダウンのコードブロックを削除
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.startswith('```'):
                result_text = result_text[3:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            
            analysis = json.loads(result_text.strip())
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"JSON Parse Error: {e}")
            print(f"Response: {response.text}")
            # フォールバック
            return {
                "businessDescription": "解析結果の取得に失敗しました",
                "industry": "未分類",
                "strengths": [],
                "targetCustomers": "不明",
                "keyTopics": [],
                "companySize": "不明",
                "painPoints": []
            }
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            raise
    
    def generate_personalized_message(
        self,
        product_info: Dict,
        company_analysis: Dict,
        sender_info: Dict
    ) -> str:
        """
        パーソナライズされた営業メッセージを生成
        
        Args:
            product_info: 商材情報
            company_analysis: 企業分析結果
            sender_info: 送信者情報
        
        Returns:
            生成されたメッセージ
        """
        prompt = f"""
あなたはプロフェッショナルな営業メッセージ作成の専門家です。

【商材情報】
名称: {product_info.get('name')}
説明: {product_info.get('description')}
ターゲット: {product_info.get('target')}
特徴: {product_info.get('features', '')}

【対象企業の分析結果】
企業名: {company_analysis.get('companyName', '御社')}
事業内容: {company_analysis.get('businessDescription')}
業種: {company_analysis.get('industry')}
強み: {', '.join(company_analysis.get('strengths', []))}
ターゲット顧客: {company_analysis.get('targetCustomers')}
想定課題: {', '.join(company_analysis.get('painPoints', []))}

【送信者情報】
会社名: {sender_info.get('company')}
担当者名: {sender_info.get('name')}

上記を踏まえ、問い合わせフォーム用の営業メッセージを作成してください。

【条件】
- 文字数: 300-500文字
- トーン: 丁寧で専門的、押し付けがましくない
- 構成: 
  1. 簡潔な冒頭挨拶
  2. 対象企業の事業内容や強みへの具体的な言及
  3. 課題の提起（押し付けない）
  4. 解決策の提示（商材の紹介）
  5. 柔らかいCTA（まずは情報提供など）
- 企業の特性に合わせてパーソナライズ
- スパムに見えないよう、価値提供を重視

メッセージのみを出力してください。余計な説明は不要です。
        """
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,  # 創造性とバランス
                    'max_output_tokens': 1000,
                }
            )
            
            return response.text.strip()
            
        except Exception as e:
            print(f"Message Generation Error: {e}")
            raise
    
    def generate_custom_message_simple(
        self,
        company_info: Dict,
        project_info: Dict
    ) -> str:
        """
        Phase 2-A: 企業情報とプロジェクトテンプレートから最適化メッセージ生成
        
        Args:
            company_info: {
                'name': 企業名,
                'industry': 業界,
                'description': 会社概要・事業内容,
                'employee_count': 従業員数（オプション）,
                'established_year': 設立年（オプション）
            }
            project_info: {
                'name': 案件名,
                'message_template': メッセージテンプレート
            }
        
        Returns:
            カスタマイズされたメッセージ（300文字程度）
        """
        # 企業情報の準備
        company_name = company_info.get('name', '御社')
        industry = company_info.get('industry', '')
        description = company_info.get('description', '')
        employee_count = company_info.get('employee_count')
        established_year = company_info.get('established_year')
        
        # 企業プロフィール文の生成
        company_profile = f"【対象企業】\n企業名: {company_name}"
        if industry:
            company_profile += f"\n業界: {industry}"
        if description:
            company_profile += f"\n事業内容: {description}"
        if employee_count:
            company_profile += f"\n従業員数: {employee_count}名"
        if established_year:
            company_profile += f"\n設立: {established_year}年"
        
        # テンプレートの文字数を取得
        template_text = project_info.get('message_template', '')
        template_length = len(template_text)
        
        prompt = f"""
あなたはプロフェッショナルな営業メッセージ作成の専門家です。

{company_profile}

【メッセージテンプレート】
{template_text}

上記のテンプレートを、企業情報を踏まえて具体的にカスタマイズしてください。

【要件】
- テンプレートの構成・流れ・トーンを維持する
- 文字数: {template_length}文字前後（±50文字程度）
- 【業界】【具体的な課題】【企業特徴】などのプレースホルダーを企業の実際の情報に置き換える
- 企業の業界・事業内容に合わせた具体的な提案や事例を含める
- 丁寧なビジネス文書として、誠実なトーンを保つ
- 押し付けがましくなく、価値提供を重視

カスタマイズされたメッセージのみを出力してください。余計な説明や記号は不要です。
        """
        
        try:
            # Safety設定を緩和（正しい形式）
            from google.generativeai.types import HarmCategory, HarmBlockThreshold
            
            safety_settings = {
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
            
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.7,
                    'max_output_tokens': 2048,  # 800→2048に増加（日本語約500-700文字）
                },
                safety_settings=safety_settings
            )
            
            message = response.text.strip()
            
            # マークダウンなどの余計な記号を除去
            message = message.replace('```', '').replace('**', '').strip()
            
            return message
            
        except Exception as e:
            print(f"AI Message Generation Error: {e}")
            import traceback
            traceback.print_exc()
            # フォールバック: テンプレートをそのまま返す
            return project_info.get('message_template', '営業メッセージを生成できませんでした。')
    
    def generate_insight(self, company_analysis: Dict, product_info: Dict) -> str:
        """
        作業者向けのGemini Insightを生成
        
        Args:
            company_analysis: 企業分析結果
            product_info: 商材情報
        
        Returns:
            インサイト文（アプローチのヒント）
        """
        prompt = f"""
以下の企業に対して、営業メッセージを送る作業者へのアドバイスを簡潔に作成してください。

企業分析:
- 事業内容: {company_analysis.get('businessDescription')}
- 強み: {', '.join(company_analysis.get('strengths', []))}
- 想定課題: {', '.join(company_analysis.get('painPoints', []))}

商材: {product_info.get('name')}

以下の形式で、100文字以内で出力してください:
「この企業は〜という特徴があります。〜という点でアプローチすると効果的でしょう。」
        """
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.5,
                    'max_output_tokens': 200,
                }
            )
            
            return response.text.strip()
            
        except Exception as e:
            print(f"Insight Generation Error: {e}")
            return "企業の特性に合わせて丁寧にアプローチしてください。"


# テスト用
if __name__ == '__main__':
    # 環境変数チェック
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("⚠️  GEMINI_API_KEY が設定されていません")
        print("   .env ファイルに設定してください")
    else:
        print("✅ Gemini API Key が設定されています")
        
        # 簡単なテスト
        try:
            service = GeminiService()
            print("✅ GeminiService が正常に初期化されました")
        except Exception as e:
            print(f"❌ エラー: {e}")
