ALTER TABLE simple_products 
ADD COLUMN IF NOT EXISTS sender_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS sender_email VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_company VARCHAR(200),
ADD COLUMN IF NOT EXISTS sender_phone VARCHAR(50);

UPDATE simple_products 
SET 
    sender_name = COALESCE(sender_name, '山田太郎'),
    sender_email = COALESCE(sender_email, 'yamada@example.com'),
    sender_company = COALESCE(sender_company, '株式会社テスト'),
    sender_phone = COALESCE(sender_phone, '03-1234-5678');

SELECT id, name, sender_name, sender_email, sender_company, sender_phone FROM simple_products;
