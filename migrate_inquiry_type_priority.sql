-- 種別優先キーワード機能追加マイグレーション
-- 2026-01-31

-- inquiry_type_priority カラム追加
ALTER TABLE simple_products
ADD COLUMN IF NOT EXISTS inquiry_type_priority VARCHAR(500);

-- コメント追加
COMMENT ON COLUMN simple_products.inquiry_type_priority IS '種別優先キーワード（カンマ区切り）例: その他,一般,お問い合わせ';
