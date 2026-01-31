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

    def analyze_form_fields(self, form_html: str, form_url: str) -> Dict:
        """
        フォームのHTML構造をAIで解析し、フィールド情報を抽出
        
        Args:
            form_html: フォームのHTML（input/textarea/select要素を含む）
            form_url: フォームのURL（コンテキスト用）
        
        Returns:
            {
                "fields": [
                    {
                        "selector": "input[name='sei']",
                        "name": "sei",
                        "type": "text",
                        "field_category": "last_name",
                        "confidence": 0.95
                    },
                    ...
                ],
                "summary": "お問い合わせフォーム"
            }
        """
        # HTMLを短縮（max_output_tokens超過を防ぐ）
        form_html_truncated = form_html[:5000] if len(form_html) > 5000 else form_html
        
        prompt = f"""日本語Webフォームの入力フィールドを解析し、各フィールドのfield_categoryを判定してください。

【フォームHTML（JSON形式）】
{form_html_truncated}

【出力形式】JSONのみ（説明不要）：
{{"fields":[{{"name":"属性値","type":"input種別","label":"ラベル","field_category":"下記から選択"}}]}}

【field_category一覧（この値のみ使用可能）】
■ 名前系
- last_name: 姓（ラベル例：姓、せい）
- first_name: 名（ラベル例：名、めい）
- full_name: 氏名（ラベル例：お名前、氏名、ご担当者名）
- last_name_kana: 姓カナ（ラベル例：セイ、フリガナ(姓)）
- first_name_kana: 名カナ（ラベル例：メイ、フリガナ(名)）
- name_kana: ふりがな一体型（ラベル例：ふりがな、フリガナ、カナ、よみがな、name属性にfuri/kanaを含む）

■ 連絡先
- email: メールアドレス（ラベル例：メールアドレス、E-mail）
- phone: 電話番号（ラベル例：電話番号、TEL、お電話番号）
- phone1: 市外局番（3つに分割された電話の1番目）
- phone2: 市内局番（3つに分割された電話の2番目）
- phone3: 加入者番号（3つに分割された電話の3番目）

■ 会社情報
- company: 会社名・組織名（ラベル例：会社名、企業名、組織名、法人名、団体名）
- department: 部署名（ラベル例：部署、部署名）
- position: 役職（ラベル例：役職、肩書き）

■ 住所系
- zipcode: 郵便番号（一体型）
- zipcode1: 郵便番号前半（3桁）
- zipcode2: 郵便番号後半（4桁）
- prefecture: 都道府県（selectで47都道府県を選択）
- city: 市区町村
- address: 住所・番地・建物名

■ 問い合わせ関連
- subject: お問い合わせ種別（ラベル例：お問い合わせ種別、お問い合わせ先、ご用件、カテゴリ）
- message: 問い合わせ内容（ラベル例：お問い合わせ内容、内容、本文、ご質問）

■ 同意・チェックボックス系
- privacy_agreement: プライバシーポリシー同意（ラベル例：プライバシーポリシーに同意、個人情報の取り扱いに同意、Privacy Policy）
- terms_agreement: 利用規約同意（ラベル例：利用規約に同意、規約に同意）
- checkbox: その他のチェックボックス（メルマガ希望、ニュースレター購読など）

■ その他
- other: 上記のどれにも該当しない場合のみ使用

【重要な判定ルール】
1. **ラベルを最優先で判定** - labelフィールドの日本語を最優先で使う
2. 「ふりがな」「フリガナ」「カナ」「よみがな」を含むラベル → name_kana
3. name属性に「furi」「kana」を含む → name_kana
4. selectで「お問い合わせ先」「種別」を選ぶ場合 → subject
5. selectで都道府県（北海道〜沖縄県）を選ぶ場合 → prefecture
6. 連続する名前フィールドは1番目=last_name、2番目=first_name
7. 連続する電話番号フィールドは順にphone1、phone2、phone3
8. **チェックボックス分類ルール**:
   - 「プライバシー」「個人情報」「Privacy」を含む → privacy_agreement
   - 「利用規約」「terms」を含む → terms_agreement
   - 上記以外のチェックボックス → checkbox
9. **otherは最後の手段** - 明らかに上記のどれにも該当しない場合のみ

【禁止】上記以外のカテゴリ名は使用禁止。"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.0,  # 最も一貫性重視
                    'max_output_tokens': 8000,
                }
            )
            
            result_text = response.text.strip()
            
            # マークダウンのコードブロックを削除
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.startswith('```'):
                result_text = result_text[3:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            
            result_text = result_text.strip()
            
            try:
                analysis = json.loads(result_text)
            except json.JSONDecodeError as first_error:
                # JSONが不完全な場合、修復を試みる
                print(f"⚠️ JSON修復を試みます: {first_error}")
                
                # 方法1: 末尾の不完全なオブジェクトを削除
                # 最後の完全なオブジェクト（}で終わる）を見つける
                last_complete = result_text.rfind('},')
                if last_complete > 0:
                    # fieldsの配列を閉じる
                    repaired = result_text[:last_complete+1] + '],"summary":"AI解析（修復）"}'
                    try:
                        analysis = json.loads(repaired)
                        print(f"✅ JSON修復成功（方法1）")
                    except json.JSONDecodeError:
                        # 方法2: もっと前の完全なオブジェクトを探す
                        for i in range(3):
                            last_complete = result_text.rfind('},', 0, last_complete)
                            if last_complete > 0:
                                repaired = result_text[:last_complete+1] + '],"summary":"AI解析（修復）"}'
                                try:
                                    analysis = json.loads(repaired)
                                    print(f"✅ JSON修復成功（方法2-{i+1}）")
                                    break
                                except:
                                    continue
                        else:
                            raise first_error
                else:
                    raise first_error
            
            print(f"✅ AI フォーム解析完了: {len(analysis.get('fields', []))}フィールド検出")
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"❌ AI解析結果のJSONパースエラー: {e}")
            # デバッグ用：レスポンスの最後200文字を出力
            print(f"   レスポンス末尾: ...{result_text[-200:] if len(result_text) > 200 else result_text}")
            return {"fields": [], "analysis_summary": "解析に失敗しました", "error": str(e)}
        except Exception as e:
            print(f"❌ AIフォーム解析エラー: {e}")
            return {"fields": [], "analysis_summary": "解析に失敗しました", "error": str(e)}

    def generate_field_mapping(self, form_structure: Dict, available_data: Dict) -> Dict:
        """
        フォーム構造と利用可能なデータからマッピングを生成
        
        Args:
            form_structure: analyze_form_fields()の結果
            available_data: 入力可能なデータ（name, email, phone等）
        
        Returns:
            マッピング情報
        """
        prompt = f"""
あなたはフォーム自動入力の専門家です。

【タスク】
以下のフォーム構造に対して、利用可能なデータをマッピングしてください。

【フォーム構造】
{json.dumps(form_structure, ensure_ascii=False, indent=2)}

【利用可能なデータ】
{json.dumps(available_data, ensure_ascii=False, indent=2)}

【出力形式】
以下のJSON形式で出力してください：
{{
  "mappings": [
    {{
      "selector": "input[name='sei']",
      "field_category": "last_name",
      "data_key": "last_name",
      "value": "利用可能なデータから取得した値",
      "confidence": 0.95
    }}
  ],
  "unmapped_fields": [
    {{
      "selector": "select[name='category']",
      "reason": "選択肢が不明のため自動入力不可"
    }}
  ]
}}
"""
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.2,
                    'max_output_tokens': 3000,
                }
            )
            
            result_text = response.text.strip()
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.startswith('```'):
                result_text = result_text[3:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            
            return json.loads(result_text.strip())
            
        except Exception as e:
            print(f"❌ マッピング生成エラー: {e}")
            return {"mappings": [], "unmapped_fields": [], "error": str(e)}


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
