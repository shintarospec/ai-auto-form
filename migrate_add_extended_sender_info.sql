-- 案件DBの送信者情報拡張マイグレーション
-- 実行日: 2025-12-31

-- 基本情報（氏名・フリガナ）
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_last_name VARCHAR(50);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_first_name VARCHAR(50);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_last_name_kana VARCHAR(50);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_first_name_kana VARCHAR(50);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_gender VARCHAR(10);

-- 会社情報
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_company_kana VARCHAR(200);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_company_url VARCHAR(500);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_department VARCHAR(100);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_position VARCHAR(100);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_rep_name VARCHAR(100);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_rep_name_kana VARCHAR(100);

-- 連絡先（分割対応）
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_phone_1 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_phone_2 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_phone_3 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_mobile_1 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_mobile_2 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_mobile_3 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_fax_1 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_fax_2 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_fax_3 VARCHAR(10);

-- メールアドレス
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_email_company VARCHAR(200);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_email_personal VARCHAR(200);

-- 住所（分割対応）
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_zipcode_1 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_zipcode_2 VARCHAR(10);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_prefecture VARCHAR(50);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_city VARCHAR(100);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_address VARCHAR(500);

-- お問い合わせ内容
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_inquiry_title VARCHAR(500);
ALTER TABLE simple_products ADD COLUMN IF NOT EXISTS sender_inquiry_detail TEXT;

-- 確認
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'simple_products' 
  AND column_name LIKE 'sender_%'
ORDER BY ordinal_position;
