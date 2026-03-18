-- MoodMeshi initial DDL
-- Run this in Supabase Dashboard > SQL Editor

-- User preferences (Slack / Web dual support)
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id          TEXT PRIMARY KEY,
    allergy_notes    TEXT,
    preference_notes TEXT,
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

-- Search sessions (1 proposal generation = 1 row)
CREATE TABLE IF NOT EXISTS search_sessions (
    id                BIGSERIAL PRIMARY KEY,
    user_id           TEXT NOT NULL,
    slack_channel_id  TEXT,
    user_input        TEXT NOT NULL,
    mood_keywords     TEXT[],
    target_categories TEXT[],
    greeting          TEXT,
    closing_message   TEXT,
    context_summary   TEXT,
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_search_sessions_user_id ON search_sessions (user_id, created_at DESC);

-- Proposed meals (up to 6 rows per session)
CREATE TABLE IF NOT EXISTS proposed_meals (
    id                 BIGSERIAL PRIMARY KEY,
    session_id         BIGINT REFERENCES search_sessions(id) ON DELETE CASCADE,
    rank               INT NOT NULL,
    recipe_id          TEXT,
    recipe_title       TEXT NOT NULL,
    recipe_url         TEXT,
    food_image_url     TEXT,
    recipe_description TEXT,
    recipe_indication  TEXT,
    recipe_cost        TEXT,
    category_name      TEXT,
    why_recommended    TEXT,
    nutrition_point    TEXT,
    seasonal_point     TEXT,
    arrange_tip        TEXT,
    is_favorited       BOOLEAN DEFAULT false,
    created_at         TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_proposed_meals_session_id ON proposed_meals (session_id, rank);
