-- StoryCoe Database Schema
-- Database: story_db
-- 使用 Snowflake ID (BIGINT) 作为主键
-- 禁止使用触发器和外键约束，全部靠代码实现

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY,
    phone VARCHAR(20) UNIQUE,
    wechat_open_id VARCHAR(100) UNIQUE,
    name VARCHAR(100) NOT NULL DEFAULT '小读者',
    avatar VARCHAR(500),
    role INTEGER NOT NULL DEFAULT 0,  -- 用户角色: 0=普通用户, 1=高级用户, 10=管理员
    level INTEGER NOT NULL DEFAULT 1,  -- 阅读等级（游戏化系统）
    books_read INTEGER NOT NULL DEFAULT 0,
    books_created INTEGER NOT NULL DEFAULT 0,
    stars INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    total_sentences_read INTEGER NOT NULL DEFAULT 0,
    last_read_date DATE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    banned_reason VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_users_phone ON users (phone);
CREATE INDEX IF NOT EXISTS ix_users_wechat_open_id ON users (wechat_open_id);

-- 用户设置表
CREATE TABLE IF NOT EXISTS user_settings (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    speed_label VARCHAR(10) NOT NULL DEFAULT '中',
    accent VARCHAR(10) NOT NULL DEFAULT 'US',
    loop_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_user_settings_user_id ON user_settings (user_id);

-- 验证码表
CREATE TABLE IF NOT EXISTS verification_codes (
    id BIGINT PRIMARY KEY,
    phone VARCHAR(20) NOT NULL,
    code VARCHAR(6) NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_verification_codes_phone ON verification_codes (phone);

-- 书籍表
CREATE TABLE IF NOT EXISTS books (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    progress INTEGER NOT NULL DEFAULT 0,
    cover_image VARCHAR(500),
    is_new BOOLEAN NOT NULL DEFAULT TRUE,
    has_audio BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    share_type VARCHAR(10) NOT NULL DEFAULT 'private',
    read_count INTEGER NOT NULL DEFAULT 0,
    shelf_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_books_user_id ON books (user_id);
CREATE INDEX IF NOT EXISTS ix_books_share_type ON books (share_type);
CREATE INDEX IF NOT EXISTS ix_books_status ON books (status);

-- 书籍页面表
CREATE TABLE IF NOT EXISTS book_pages (
    id BIGINT PRIMARY KEY,
    book_id BIGINT NOT NULL,
    page_number INTEGER NOT NULL,
    image_url VARCHAR(500),
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_book_pages_book_id ON book_pages (book_id);

-- 句子表
CREATE TABLE IF NOT EXISTS sentences (
    id BIGINT PRIMARY KEY,
    page_id BIGINT NOT NULL,
    sentence_order INTEGER NOT NULL,
    en TEXT NOT NULL DEFAULT '',
    zh TEXT NOT NULL DEFAULT '',
    audio_us_normal VARCHAR(500),  -- 美式英语正常语速音频
    audio_us_slow VARCHAR(500),    -- 美式英语慢速音频
    audio_gb_normal VARCHAR(500),  -- 英式英语正常语速音频
    audio_gb_slow VARCHAR(500),    -- 英式英语慢速音频
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, translating, generating_tts, completed, error
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_sentences_page_id ON sentences (page_id);

-- 阅读进度表
CREATE TABLE IF NOT EXISTS reading_progress (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    current_page INTEGER NOT NULL DEFAULT 0,
    total_pages INTEGER NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    last_read_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_reading_progress_user_id ON reading_progress (user_id);
CREATE INDEX IF NOT EXISTS ix_reading_progress_book_id ON reading_progress (book_id);

-- 书架表（收藏的绘本）
CREATE TABLE IF NOT EXISTS bookshelf (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    book_id BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_bookshelf_user_id ON bookshelf (user_id);
CREATE INDEX IF NOT EXISTS ix_bookshelf_book_id ON bookshelf (book_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_bookshelf_user_book ON bookshelf (user_id, book_id);

-- 成就表
CREATE TABLE IF NOT EXISTS achievements (
    id BIGINT PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500) NOT NULL,
    icon VARCHAR(50) NOT NULL DEFAULT 'star',
    requirement_type VARCHAR(50) NOT NULL,
    requirement_value INTEGER NOT NULL,
    reward_stars INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_achievements_code ON achievements (code);

-- 用户成就表
CREATE TABLE IF NOT EXISTS user_achievements (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    achievement_id BIGINT NOT NULL,
    unlocked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_user_achievements_user_id ON user_achievements (user_id);
CREATE INDEX IF NOT EXISTS ix_user_achievements_achievement_id ON user_achievements (achievement_id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_achievements_user_achievement ON user_achievements (user_id, achievement_id);

-- 每日任务表
CREATE TABLE IF NOT EXISTS daily_tasks (
    id BIGINT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    task_date DATE NOT NULL,
    read_books INTEGER NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    reward_claimed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_daily_tasks_user_id ON daily_tasks (user_id);
CREATE INDEX IF NOT EXISTS ix_daily_tasks_task_date ON daily_tasks (task_date);
CREATE UNIQUE INDEX IF NOT EXISTS ix_daily_tasks_user_date ON daily_tasks (user_id, task_date);

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_configs (
    id BIGINT PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    value TEXT NOT NULL,
    description VARCHAR(500),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_system_configs_key ON system_configs (key);