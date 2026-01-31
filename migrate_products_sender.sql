-- simple_products に送信者情報カラムを追加（Phase 2-B AutoExecutor対応）

ALTER TABLE simple_products
ADD COLUMN IF NOT EXISTS sender_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_last_name VARCHAR(50),
ADD COLUMN IF NOT EXISTS sender_first_name VARCHAR(50),
ADD COLUMN IF NOT EXISTS sender_last_name_kana VARCHAR(50),
ADD COLUMN IF NOT EXISTS sender_first_name_kana VARCHAR(50),
ADD COLUMN IF NOT EXISTS sender_gender VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_company VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_company_kana VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_company_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS sender_department VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_position VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_rep_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_rep_name_kana VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(50),
ADD COLUMN IF NOT EXISTS sender_phone_1 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_phone_2 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_phone_3 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_mobile_1 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_mobile_2 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_mobile_3 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_fax_1 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_fax_2 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_fax_3 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_email VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_email_company VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_email_personal VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_zipcode_1 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_zipcode_2 VARCHAR(10),
ADD COLUMN IF NOT EXISTS sender_prefecture VARCHAR(50),
ADD COLUMN IF NOT EXISTS sender_city VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_address VARCHAR(500),
ADD COLUMN IF NOT EXISTS sender_inquiry_title VARCHAR(500),
ADD COLUMN IF NOT EXISTS sender_inquiry_detail TEXT;

-- デフォルト送信者情報を設定（既存案件用）
UPDATE simple_products
SET 
    sender_name = '営業担当',
    sender_email = 'sales@example.com',
    sender_company = '株式会社サンプル',
    sender_phone = '03-0000-0000'
WHERE sender_name IS NULL;
