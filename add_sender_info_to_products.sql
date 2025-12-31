-- 案件テーブルに送信者情報カラムを追加
-- Phase 2-A: 案件ごとに異なる送信者情報を管理

ALTER TABLE simple_products 
ADD COLUMN IF NOT EXISTS sender_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_email VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_company VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(50);

-- 既存データにデフォルト値を設定（必要に応じて修正）
UPDATE simple_products 
SET 
    sender_name = '山田太郎',
    sender_email = 'yamada@example.com',
    sender_company = '株式会社テスト',
    sender_phone = '03-1234-5678'
WHERE sender_name IS NULL;

-- 確認
SELECT id, name, sender_name, sender_email, sender_company, sender_phone 
FROM simple_products;
