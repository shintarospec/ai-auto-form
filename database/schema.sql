-- AI AutoForm - Database Schema
-- PostgreSQL 12+

-- ========================================
-- 企業テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    url VARCHAR(500),
    industry VARCHAR(100),
    form_url VARCHAR(500),
    analyzed BOOLEAN DEFAULT FALSE,
    analysis_data JSONB,
    notes TEXT,
    list_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_companies_analyzed ON companies(analyzed);
CREATE INDEX idx_companies_list_id ON companies(list_id);
CREATE INDEX idx_companies_industry ON companies(industry);

-- ========================================
-- 商材テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    target VARCHAR(200),
    features TEXT,
    prompt_template TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_products_status ON products(status);

-- ========================================
-- 作業者テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS workers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    avatar VARCHAR(10),
    total_points INTEGER DEFAULT 0,
    rank VARCHAR(50) DEFAULT 'Bronze',
    status VARCHAR(50) DEFAULT 'active',
    monthly_points INTEGER DEFAULT 0,
    total_completed INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_workers_email ON workers(email);
CREATE INDEX idx_workers_status ON workers(status);

-- ========================================
-- プロジェクトテーブル
-- ========================================
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    company_list_id INTEGER,
    product_id INTEGER REFERENCES products(id),
    status VARCHAR(50) DEFAULT 'analyzing',
    total_targets INTEGER DEFAULT 0,
    completed INTEGER DEFAULT 0,
    reward_per_task INTEGER DEFAULT 50,
    ai_analysis_completed BOOLEAN DEFAULT FALSE,
    created_by INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_product ON projects(product_id);

-- ========================================
-- プロジェクト-作業者 関連テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS project_workers (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    worker_id INTEGER REFERENCES workers(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(project_id, worker_id)
);

CREATE INDEX idx_project_workers_project ON project_workers(project_id);
CREATE INDEX idx_project_workers_worker ON project_workers(worker_id);

-- ========================================
-- タスクテーブル
-- ========================================
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    company_id INTEGER REFERENCES companies(id),
    assigned_worker_id INTEGER REFERENCES workers(id),
    status VARCHAR(50) DEFAULT 'pending',
    generated_message TEXT,
    edited_message TEXT,
    insight TEXT,
    completed_at TIMESTAMP,
    reward_points INTEGER DEFAULT 50,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_worker ON tasks(assigned_worker_id);
CREATE INDEX idx_tasks_project ON tasks(project_id);
CREATE INDEX idx_tasks_company ON tasks(company_id);

-- ========================================
-- 統計テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS stats (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    total_sent INTEGER DEFAULT 0,
    pending_ai_analysis INTEGER DEFAULT 0,
    active_projects INTEGER DEFAULT 0,
    active_workers INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stats_date ON stats(date);

-- ========================================
-- 管理者テーブル
-- ========================================
CREATE TABLE IF NOT EXISTS admins (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(200) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'admin',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ========================================
-- Triggers: updated_at 自動更新
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workers_updated_at BEFORE UPDATE ON workers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- 初期データ投入（開発用）
-- ========================================

-- 管理者アカウント（パスワード: admin123）
INSERT INTO admins (username, email, password_hash, role) VALUES
('admin', 'admin@aiautoform.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYL5obAJ.Gy', 'admin')
ON CONFLICT (username) DO NOTHING;

-- サンプル商材
INSERT INTO products (name, description, target, features, status) VALUES
('クラウド会計ソフト', '中小企業向けの簡単・安全なクラウド会計システム', '中小企業、個人事業主', '自動仕訳、レシート読取、確定申告対応', 'active'),
('営業支援SaaS', 'AIを活用した次世代営業支援ツール', '営業部門を持つ中堅企業', '商談管理、AI分析、モバイル対応', 'active')
ON CONFLICT DO NOTHING;

-- サンプル作業者
INSERT INTO workers (name, email, avatar, status) VALUES
('山田太郎', 'yamada@example.com', '山田', 'active'),
('佐藤花子', 'sato@example.com', '佐藤', 'active'),
('田中一郎', 'tanaka@example.com', '田中', 'active')
ON CONFLICT (email) DO NOTHING;
