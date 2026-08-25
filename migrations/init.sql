-- ============================================================
-- AI-Assisted Requirements & Test Management Platform
-- Database Schema Initialization
-- ============================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),         -- nullable (OAuth-only users have no password)
    avatar_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);

-- ============================================================
-- JIRA CONNECTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS jira_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_url VARCHAR(512) NOT NULL,             -- e.g. https://myco.atlassian.net
    site_name VARCHAR(255) NOT NULL,
    auth_type VARCHAR(20) NOT NULL CHECK (auth_type IN ('oauth', 'pat')),
    encrypted_token TEXT NOT NULL,              -- AES-256/Fernet encrypted access token or PAT
    encrypted_refresh_token TEXT,              -- OAuth refresh token (encrypted), NULL for PAT
    encrypted_email TEXT,                       -- email used with PAT (encrypted)
    token_expires_at TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, site_url)
);

CREATE INDEX idx_jira_connections_user ON jira_connections(user_id);

-- ============================================================
-- GITHUB CONNECTIONS
-- ============================================================
CREATE TABLE IF NOT EXISTS github_connections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_base_url VARCHAR(512) NOT NULL DEFAULT 'https://api.github.com',  -- GHES support
    connection_name VARCHAR(255) NOT NULL,      -- e.g. "github.com" or "myco-ghes"
    auth_type VARCHAR(20) NOT NULL CHECK (auth_type IN ('oauth', 'pat')),
    encrypted_token TEXT NOT NULL,
    encrypted_refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    github_username VARCHAR(255),
    github_user_id VARCHAR(100),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, api_base_url)
);

CREATE INDEX idx_github_connections_user ON github_connections(user_id);

-- ============================================================
-- JIRA PROJECTS (cached metadata)
-- ============================================================
CREATE TABLE IF NOT EXISTS jira_projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES jira_connections(id) ON DELETE CASCADE,
    project_key VARCHAR(50) NOT NULL,
    project_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    project_type VARCHAR(100),
    description TEXT,
    avatar_url TEXT,
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(connection_id, project_key)
);

CREATE INDEX idx_jira_projects_connection ON jira_projects(connection_id);

-- ============================================================
-- GITHUB REPOS (cached metadata)
-- ============================================================
CREATE TABLE IF NOT EXISTS github_repos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    connection_id UUID NOT NULL REFERENCES github_connections(id) ON DELETE CASCADE,
    full_name VARCHAR(512) NOT NULL,        -- e.g. "org/repo"
    name VARCHAR(255) NOT NULL,
    clone_url TEXT,
    html_url TEXT,
    default_branch VARCHAR(255) DEFAULT 'main',
    is_private BOOLEAN NOT NULL DEFAULT FALSE,
    is_selected BOOLEAN NOT NULL DEFAULT FALSE,
    last_indexed_commit VARCHAR(40),        -- last commit SHA we indexed
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(connection_id, full_name)
);

CREATE INDEX idx_github_repos_connection ON github_repos(connection_id);

-- ============================================================
-- STORIES (cached JIRA issue snapshots)
-- ============================================================
CREATE TABLE IF NOT EXISTS stories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES jira_projects(id) ON DELETE CASCADE,
    jira_issue_id VARCHAR(100) NOT NULL,
    jira_issue_key VARCHAR(50) NOT NULL,
    summary TEXT NOT NULL,
    description JSONB,                      -- raw JIRA ADF (Atlassian Document Format)
    description_text TEXT,                  -- extracted plain-text from ADF
    status VARCHAR(100),
    issue_type VARCHAR(100),
    assignee VARCHAR(255),
    reporter VARCHAR(255),
    sprint VARCHAR(255),
    epic_key VARCHAR(50),
    story_points NUMERIC(6,2),
    labels JSONB DEFAULT '[]',
    acceptance_criteria TEXT,
    latest_score NUMERIC(5,2),
    embedding vector(768),                  -- pgvector for semantic matching
    jira_created_at TIMESTAMPTZ,
    jira_updated_at TIMESTAMPTZ,
    cached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, jira_issue_key)
);

CREATE INDEX idx_stories_project ON stories(project_id);
CREATE INDEX idx_stories_key ON stories(jira_issue_key);
CREATE INDEX idx_stories_embedding ON stories USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- STORY SCORE HISTORY (audit of scoring runs)
-- ============================================================
CREATE TABLE IF NOT EXISTS story_score_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    story_id UUID NOT NULL REFERENCES stories(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id),
    overall_score NUMERIC(5,2) NOT NULL,
    invest_scores JSONB NOT NULL,           -- {independent, negotiable, valuable, estimable, small, testable}
    ac_score NUMERIC(5,2),                  -- Gherkin AC completeness score
    gaps JSONB NOT NULL DEFAULT '[]',       -- list of gap strings
    proposed_summary TEXT,
    proposed_description TEXT,
    proposed_ac TEXT,
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES users(id),
    jira_comment_id VARCHAR(100),           -- JIRA comment ID after write-back
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_score_history_story ON story_score_history(story_id);
CREATE INDEX idx_score_history_user ON story_score_history(user_id);

-- ============================================================
-- TEST CASES (indexed from GitHub repos)
-- ============================================================
CREATE TABLE IF NOT EXISTS test_cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    repo_id UUID NOT NULL REFERENCES github_repos(id) ON DELETE CASCADE,
    file_path VARCHAR(2048) NOT NULL,
    test_type VARCHAR(30) NOT NULL CHECK (test_type IN ('gherkin', 'playwright_spec')),
    feature_name VARCHAR(512),              -- for gherkin: Feature name
    title TEXT NOT NULL,                   -- scenario/test name
    description TEXT,
    steps JSONB,                           -- structured steps/assertions
    tags JSONB DEFAULT '[]',
    raw_content TEXT NOT NULL,
    embedding vector(768),
    commit_sha VARCHAR(40) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(repo_id, file_path, title)
);

CREATE INDEX idx_test_cases_repo ON test_cases(repo_id);
CREATE INDEX idx_test_cases_file ON test_cases(file_path);
CREATE INDEX idx_test_cases_embedding ON test_cases USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- IMPACT ANALYSIS RUNS (background jobs)
-- ============================================================
CREATE TABLE IF NOT EXISTS impact_analysis_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    celery_task_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    story_ids JSONB NOT NULL DEFAULT '[]',
    repo_ids JSONB NOT NULL DEFAULT '[]',
    progress_pct INTEGER NOT NULL DEFAULT 0,
    results JSONB,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_analysis_runs_user ON impact_analysis_runs(user_id);
CREATE INDEX idx_analysis_runs_status ON impact_analysis_runs(status);

-- ============================================================
-- TEST CHANGE PROPOSALS (per impact analysis)
-- ============================================================
CREATE TABLE IF NOT EXISTS test_change_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id UUID NOT NULL REFERENCES impact_analysis_runs(id) ON DELETE CASCADE,
    story_id UUID REFERENCES stories(id),
    test_case_id UUID REFERENCES test_cases(id),     -- NULL for new tests
    proposal_type VARCHAR(20) NOT NULL
        CHECK (proposal_type IN ('modify', 'create', 'no_change')),
    original_content TEXT,
    proposed_content TEXT NOT NULL,
    rationale TEXT,
    confidence NUMERIC(4,3) CHECK (confidence BETWEEN 0 AND 1),
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    approved_at TIMESTAMPTZ,
    approved_by UUID REFERENCES users(id),
    branch_name VARCHAR(255),
    pr_url TEXT,
    commit_sha VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_proposals_run ON test_change_proposals(run_id);

-- ============================================================
-- PLAYWRIGHT RUNS (sandboxed execution)
-- ============================================================
CREATE TABLE IF NOT EXISTS playwright_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    proposal_id UUID REFERENCES test_change_proposals(id),
    script_content TEXT NOT NULL,
    base_url TEXT,
    env_vars JSONB DEFAULT '{}',            -- user-supplied env vars (NOT encrypted here — only passed to container at runtime)
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'passed', 'failed', 'error', 'timeout')),
    container_id VARCHAR(128),
    exit_code INTEGER,
    logs TEXT,
    artifacts_path TEXT,
    total_tests INTEGER,
    passed_tests INTEGER,
    failed_tests INTEGER,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_playwright_runs_user ON playwright_runs(user_id);

-- ============================================================
-- STORY GENERATION PROPOSALS (Feature C)
-- ============================================================
CREATE TABLE IF NOT EXISTS story_generation_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    test_case_id UUID NOT NULL REFERENCES test_cases(id),
    matched_story_id UUID REFERENCES stories(id),      -- NULL = no existing match
    match_confidence NUMERIC(4,3),
    proposed_summary TEXT,
    proposed_description TEXT,
    proposed_ac TEXT,
    target_project_id UUID REFERENCES jira_projects(id),
    approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    created_jira_issue_key VARCHAR(50),
    created_jira_issue_url TEXT,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_story_proposals_user ON story_generation_proposals(user_id);

-- ============================================================
-- AUDIT LOG (all JIRA/GitHub write operations)
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    action_type VARCHAR(50) NOT NULL,           -- e.g. 'story_updated', 'pr_created', 'issue_created'
    resource_type VARCHAR(50) NOT NULL,         -- e.g. 'jira_issue', 'github_pr', 'github_branch'
    resource_id TEXT NOT NULL,                  -- JIRA issue key, PR URL, etc.
    ai_suggestion_type VARCHAR(50),             -- 'score_history', 'change_proposal', 'story_proposal'
    ai_suggestion_id UUID,                      -- references the AI suggestion record
    before_content JSONB,
    after_content JSONB,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

-- ============================================================
-- Auto-update updated_at triggers
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER jira_connections_updated_at BEFORE UPDATE ON jira_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER github_connections_updated_at BEFORE UPDATE ON github_connections
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER test_cases_updated_at BEFORE UPDATE ON test_cases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
