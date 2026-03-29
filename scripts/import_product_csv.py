import csv
import sys
from backend.database import SessionLocal
from sqlalchemy import text

csv_file = sys.argv[1] if len(sys.argv) > 1 else 'inport/product_new.csv'

session = SessionLocal()

with open(csv_file, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # 電話番号分割
        phone_parts = (row.get('sender_phone') or '').split('-')
        phone1 = phone_parts[0] if len(phone_parts) >= 1 else ''
        phone2 = phone_parts[1] if len(phone_parts) >= 2 else ''
        phone3 = phone_parts[2] if len(phone_parts) >= 3 else ''

        # 携帯番号分割
        mobile_parts = (row.get('sender_mobile') or '').split('-')
        mobile1 = mobile_parts[0] if len(mobile_parts) >= 1 else ''
        mobile2 = mobile_parts[1] if len(mobile_parts) >= 2 else ''
        mobile3 = mobile_parts[2] if len(mobile_parts) >= 3 else ''

        # FAX分割
        fax_parts = (row.get('sender_fax') or '').split('-')
        fax1 = fax_parts[0] if len(fax_parts) >= 1 else ''
        fax2 = fax_parts[1] if len(fax_parts) >= 2 else ''
        fax3 = fax_parts[2] if len(fax_parts) >= 3 else ''

        # 郵便番号分割
        zip_parts = (row.get('sender_zipcode') or '').split('-')
        zip1 = zip_parts[0] if len(zip_parts) >= 1 else ''
        zip2 = zip_parts[1] if len(zip_parts) >= 2 else ''

        # sender_name自動生成
        sender_name = f"{row.get('sender_last_name', '')} {row.get('sender_first_name', '')}".strip()

        session.execute(text("""
            INSERT INTO simple_products (
                name, description,
                sender_name, sender_last_name, sender_first_name,
                sender_last_name_kana, sender_first_name_kana,
                sender_gender, sender_company, sender_company_kana,
                sender_company_url, sender_department, sender_position,
                sender_phone, sender_phone_1, sender_phone_2, sender_phone_3,
                sender_mobile_1, sender_mobile_2, sender_mobile_3,
                sender_fax_1, sender_fax_2, sender_fax_3,
                sender_email, sender_email_company, sender_email_personal,
                sender_zipcode_1, sender_zipcode_2,
                sender_prefecture, sender_city, sender_address,
                message_template, sender_inquiry_title, inquiry_type_priority,
                created_at
            ) VALUES (
                :name, :description,
                :sender_name, :sender_last_name, :sender_first_name,
                :sender_last_name_kana, :sender_first_name_kana,
                :sender_gender, :sender_company, :sender_company_kana,
                :sender_company_url, :sender_department, :sender_position,
                :sender_phone, :phone1, :phone2, :phone3,
                :mobile1, :mobile2, :mobile3,
                :fax1, :fax2, :fax3,
                :sender_email, :sender_email_company, :sender_email_personal,
                :zip1, :zip2,
                :sender_prefecture, :sender_city, :sender_address,
                :message_template, :sender_inquiry_title, :inquiry_type_priority,
                NOW()
            ) RETURNING id
        """), {
            'name': row.get('name', ''),
            'description': row.get('description', ''),
            'sender_name': sender_name,
            'sender_last_name': row.get('sender_last_name', ''),
            'sender_first_name': row.get('sender_first_name', ''),
            'sender_last_name_kana': row.get('sender_last_name_kana', ''),
            'sender_first_name_kana': row.get('sender_first_name_kana', ''),
            'sender_gender': row.get('sender_gender', ''),
            'sender_company': row.get('sender_company', ''),
            'sender_company_kana': row.get('sender_company_kana', ''),
            'sender_company_url': row.get('sender_company_url', ''),
            'sender_department': row.get('sender_department', ''),
            'sender_position': row.get('sender_position', ''),
            'sender_phone': row.get('sender_phone', ''),
            'phone1': phone1, 'phone2': phone2, 'phone3': phone3,
            'mobile1': mobile1, 'mobile2': mobile2, 'mobile3': mobile3,
            'fax1': fax1, 'fax2': fax2, 'fax3': fax3,
            'sender_email': row.get('sender_email', ''),
            'sender_email_company': row.get('sender_email_company', ''),
            'sender_email_personal': row.get('sender_email_personal', ''),
            'zip1': zip1, 'zip2': zip2,
            'sender_prefecture': row.get('sender_prefecture', ''),
            'sender_city': row.get('sender_city', ''),
            'sender_address': row.get('sender_address', ''),
            'message_template': row.get('message_template', ''),
            'sender_inquiry_title': row.get('sender_inquiry_title', ''),
            'inquiry_type_priority': row.get('inquiry_type_priority', ''),
        })

        result = session.execute(text('SELECT lastval()'))
        new_id = result.fetchone()[0]
        print(f'Product作成: ID={new_id}, name={row.get("name", "")}')

session.commit()
session.close()
