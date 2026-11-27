CREATE TABLE wrong_questions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attempt_id TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    role_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    question_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    question_json TEXT NOT NULL,
    original_answer_json TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    mastered INTEGER NOT NULL DEFAULT 0 CHECK(mastered IN (0,1)),
    mastery_updated_at TEXT,
    UNIQUE(user_id, attempt_id, question_id)
);
CREATE INDEX idx_wrong_questions_owner ON wrong_questions(user_id, collected_at DESC, id DESC);
CREATE TABLE wrong_question_practices (
    id TEXT PRIMARY KEY,
    wrong_question_id TEXT NOT NULL REFERENCES wrong_questions(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    request_id TEXT NOT NULL,
    selected_json TEXT NOT NULL,
    is_correct INTEGER NOT NULL CHECK(is_correct IN (0,1)),
    created_at TEXT NOT NULL,
    UNIQUE(user_id, wrong_question_id, request_id)
);
CREATE INDEX idx_wrong_practices_owner ON wrong_question_practices(user_id, wrong_question_id, created_at DESC);
