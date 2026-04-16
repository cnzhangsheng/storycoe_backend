-- 添加 wechat_open_id 字段到用户表
-- 用于微信小程序登录

ALTER TABLE users ADD COLUMN IF NOT EXISTS wechat_open_id VARCHAR(100);

-- 创建唯一索引
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_wechat_open_id ON users(wechat_open_id) WHERE wechat_open_id IS NOT NULL;

-- 注释
COMMENT ON COLUMN users.wechat_open_id IS '微信小程序 open_id';