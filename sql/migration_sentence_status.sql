-- Migration: Add status field to sentences table
-- Date: 2026-04-20
-- Description: 为句子添加处理状态字段，追踪翻译和 TTS 生成进度

-- 添加 status 字段
ALTER TABLE sentences ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending';

-- 状态说明：
-- pending: 待处理（新创建或英文更新后）
-- translating: 正在翻译中文
-- generating_tts: 正在生成 TTS 音频
-- completed: 处理完成（有翻译和音频）
-- error: 处理失败

-- 将已有句子的状态更新为 completed（如果已有音频）
UPDATE sentences SET status = 'completed'
WHERE audio_us_normal IS NOT NULL OR audio_gb_normal IS NOT NULL;

-- 其他句子更新为 pending
UPDATE sentences SET status = 'pending'
WHERE status = 'pending' AND (audio_us_normal IS NULL AND audio_gb_normal IS NULL);