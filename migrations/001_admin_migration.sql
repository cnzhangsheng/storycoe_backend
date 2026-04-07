-- StoryCoe 数据库迁移脚本
-- 用于后台管理功能所需的字段和表扩展
-- 执行时间: 2026-04-07

-- ========================================
-- 1. User 表添加新字段
-- ========================================

-- 添加 is_active 字段（账户状态）
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- 添加 is_banned 字段（是否封禁）
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE;

-- 添加 banned_reason 字段（封禁原因）
ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_reason VARCHAR(500);

-- 添加 last_login_at 字段（最后登录时间）
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMP WITH TIME ZONE;

-- ========================================
-- 2. 创建 SystemConfig 表
-- ========================================

CREATE TABLE IF NOT EXISTS system_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS ix_system_configs_key ON system_configs(key);

-- ========================================
-- 3. 插入默认系统配置（可选）
-- ========================================

-- INSERT INTO system_configs (key, value, description) VALUES
-- ('app_name', 'StoryCoe', '应用名称'),
-- ('max_books_per_user', '50', '每个用户最大绘本数'),
-- ('max_pages_per_book', '20', '每本绘本最大页数');

-- ========================================
-- 验证迁移
-- ========================================

-- 检查 users 表新字段
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'users'
AND column_name IN ('is_active', 'is_banned', 'banned_reason', 'last_login_at');

-- 检查 system_configs 表
SELECT table_name FROM information_schema.tables WHERE table_name = 'system_configs';