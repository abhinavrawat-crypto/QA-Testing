# Product Requirements Document
## AI-Assisted Requirements & Test Management Platform

**Version:** 0.1 (Draft for review)
**Date:** August 22, 2026
**Status:** Draft — pending stakeholder review

---

## 1. Overview

### 1.1 Problem Statement
QA and product teams manually review JIRA user stories for quality, manually trace which test cases are affected when a story changes, and manually write new test cases and automation scripts. This is slow, inconsistent, and error-prone at scale — especially across multiple JIRA projects and GitHub repositories.

### 1.2 Product Vision
A web application that connects to a user's JIRA instance(s) and GitHub repositories and uses AI (Google Gemini) to:
1. Score and improve the quality of user stories.
2. Perform impact analysis between user stories and existing test cases, and generate/update test cases and Playwright automation.
3. Reverse-generate missing user stories from existing test cases.

All AI suggestions are **human-in-the-loop**: the AI proposes, the user reviews/edits, and only explicit user approval results in a write-back to JIRA or GitHub. No simulated/mock data — all reads and writes hit live JIRA and GitHub APIs the user is authorized to access.

### 1.3 Goals
- Reduce time spent writing/refining user stories to meet a consistent quality bar.
- Eliminate manual tracing of "which tests break when this story changes."
- Speed up test authoring and automation script generation.
- Keep humans in control of every write operation to JIRA/GitHub.
- Support multiple JIRA projects and multiple GitHub repos concurrently, per user.

### 1.4 Non-Goals (v1)
- Fully autonomous writes without human approval.
- Support for test frameworks other than Playwright for script generation (v1 scope).
- Native mobile app.

---

## 2. Personas

| Persona | Needs |
|---|---|
| **QA Engineer** | Wants to know what tests are impacted by a story change and get draft test cases/scripts fast. |
| **Business Analyst / Product Owner** | Wants story quality feedback before handing stories to the team. |
| **SDET / Automation Engineer** | Wants reviewable Playwright scripts they can run or PR without starting from scratch. |
| **Engineering Manager** | Wants traceability between stories and tests across many repos/projects. |

---

## 3. Recommended Standards (for review/approval)

Since these weren't specified, here are the recommendations baked into this PRD — flag if you want different defaults:

- **User story quality standard:** **INVEST** (Independent, Negotiable, Valuable, Estimable, Small, Testable) for the story itself, plus **Given-When-Then (Gherkin) acceptance criteria** structure for testability. This gives a concrete, checkable rubric rather than a vague "well-written" judgment.
- **Test case format:** **Gherkin `.feature` files** (industry standard for BDD, and it's what most Playwright-BDD tooling — e.g. `playwright-bdd` — consumes). This also gives Feature 2 and 3 a shared structured language to match stories ↔ tests semantically instead of via fuzzy text search alone.
- Both are configurable per-project later; v1 ships with these as defaults.

---

## 4. Functional Requirements

### 4.0 Onboarding / Connection Flow
- On first login, user must connect at least one **JIRA site** and one **GitHub account/org**.
- Auth supports **both** OAuth 2.0 (3-legged for JIRA Cloud, GitHub OAuth App) **and** Personal Access Tokens, user's choice per connection.
- After connecting, the app pulls **only the JIRA projects and GitHub repos the user has access to** (via `/myself` + assigned/watched projects for JIRA; via GitHub's authenticated `/user/repos` and org membership for GitHub).
- User can connect **multiple JIRA sites** and **multiple GitHub repos/orgs**, and switch/select context per session.
- Landing page after connection shows **three action cards** (no numbering), each describing the outcome:
  - *"Improve and align a user story with quality standards"*
  - *"Find and update test cases impacted by a story change"*
  - *"Discover user stories missing for existing test cases"*

### 4.1 Feature A — User Story Quality & Confidence Scoring
**Flow:**
1. User selects a JIRA project → selects one or more stories (search/filter by sprint, epic, assignee, status).
2. System scores each story (0–100 confidence) against INVEST + Gherkin AC completeness, and returns:
   - Overall score + sub-scores per INVEST dimension.
   - Specific gaps (e.g., "No acceptance criteria," "Story mixes two independent pieces of work," "Not estimable — missing NFRs").
   - A **proposed rewritten version** of the story (title, description, acceptance criteria).
3. UI shows current vs. proposed **side by side** (diff view).
4. User can **edit the proposed version inline** before accepting.
5. On approval, system writes the update back to the JIRA issue (via JIRA REST API `PUT /issue/{id}`), preserving history/comments; adds a comment noting the AI-assisted edit and linking back to who approved it.
6. Nothing is written to JIRA without explicit approval per story.

### 4.2 Feature B — Story → Test Case Impact Analysis & Test Generation
**Flow:**
1. User selects one or more JIRA stories and one or more GitHub repos (test case source).
2. System indexes existing test cases (`.feature` files, or detected format) from the repo(s) — see §6.3 indexing strategy for scale.
3. System performs impact analysis and returns, per story:
   - **Impacted test cases** (existing tests likely affected), with a reason/rationale and confidence.
   - **Unaffected test cases** (explicitly listed as "reviewed, not impacted" for traceability).
   - For each impacted test case: a **diff-style suggested change**.
   - **Gap list**: scenarios with no existing coverage → **suggested new test cases** (drafted in Gherkin).
4. User reviews, edits inline, and approves/rejects each suggestion individually or in bulk.
5. On approval:
   - System writes the approved test case changes to a **new branch** in the target repo and asks if the user wants to **open a Pull Request** (via GitHub API — never pushes directly to a protected branch).
   - System asks separately: **"Generate Playwright scripts for these test cases?"**
6. If yes to Playwright generation:
   - System generates Playwright test scripts (TypeScript/JS) mapped from the Gherkin scenarios.
   - User can **copy the script**, or **run it directly** in-app.
7. **In-app execution**: triggers a Playwright run in an **ephemeral sandboxed container** (see §6.4), streams logs/results (pass/fail, screenshots, trace) back to the UI in near-real-time.

### 4.3 Feature C — Test Case → Missing User Story Discovery
**Flow:**
1. User selects GitHub repo(s) and selects test cases (or a whole feature file / directory).
2. System matches each selected test case against existing JIRA stories (semantic match using Gemini embeddings, not just keyword match) across the user's connected JIRA project(s).
3. Output: for each test case —
   - **Matched to existing story** (link + confidence), or
   - **No matching story found** → system drafts a **proposed new user story** (title, description, INVEST-formatted, Gherkin AC derived from the test case).
4. User reviews/edits proposed stories, selects target JIRA project, and approves.
5. On approval, system creates the story in JIRA (`POST /issue`) and links it back to the source test case (custom field or issue link / comment with repo+file path).

### 4.4 Cross-Cutting Requirements
- All AI suggestions must be **reviewable and editable** before any write to JIRA/GitHub — no silent writes, ever.
- Every write action is logged with: user, timestamp, what changed, AI suggestion vs. final approved content (audit trail).
- Must support **batch operations** (multiple stories/test cases selected at once) without blocking the UI — long-running analysis runs as background jobs with progress status.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Scale** | Must handle multiple JIRA sites and multiple GitHub repos per user; test-case corpora in the thousands per repo. Analysis must not require re-reading an entire repo on every request (see indexing, §6.3). |
| **Real data only** | No mock/sample/simulated data anywhere — all reads/writes go through live JIRA and GitHub APIs against resources the authenticated user can access. |
| **Security** | OAuth tokens and PATs encrypted at rest (e.g., via a secrets manager/KMS or Postgres `pgcrypto` for local dev); scoped least-privilege API access; per-user data isolation. |
| **Auditability** | Every JIRA/GitHub write traceable to a user, an AI suggestion, and an approval event. |
| **Latency** | Story scoring: target < 15s per story. Impact analysis: async job with progress updates for large batches. |
| **Portability** | v1 runs fully local via Docker Compose; must be structured (12-factor, env-based config) for a clean migration to GCP (Cloud Run / GKE, Cloud SQL) later without architecture rework. |
| **Extensibility** | AI provider should be abstracted behind an internal interface so Gemini can be swapped/extended later (per note in Q&A that provider might evolve). |

---

## 6. System Architecture

### 6.1 High-Level Approach
Microservice architecture, Python + FastAPI backend services, React frontend, PostgreSQL as primary datastore (one logical database, schema-per-service, to keep local deployment simple — can split into separate DBs at GCP migration time).

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend (SPA)                     │
└───────────────────────────────┬─────────────────────────────────┘
                                 │  HTTPS / REST + WebSocket (job status, test run logs)
┌───────────────────────────────▼─────────────────────────────────┐
│                       API Gateway / BFF (FastAPI)                │
│         Auth, request routing, rate limiting, aggregation        │
└───┬───────────┬───────────┬───────────┬───────────┬─────────────┘
    │           │           │           │           │
┌───▼───┐   ┌───▼────┐  ┌───▼────┐  ┌───▼─────┐ ┌───▼──────────┐
│ Auth &│   │  JIRA  │  │ GitHub │  │   AI /  │ │ Test Runner  │
│ Conn  │   │ Integr.│  │ Integr.│  │ Analysis│ │  Orchestrator│
│ Svc   │   │  Svc   │  │  Svc   │  │   Svc   │ │    Svc       │
└───┬───┘   └───┬────┘  └───┬────┘  └───┬─────┘ └───┬──────────┘
    │           │           │           │           │
    └─────────────────┬─────┴───────────┴───────────┘
                       │
              ┌────────▼─────────┐        ┌───────────────────┐
              │   PostgreSQL      │        │  Job Queue         │
              │ (schema per svc)  │        │ (Redis + Celery/   │
              └───────────────────┘        │  RQ/Arq)           │
                                            └────────┬───────────┘
                                                      │
                                        ┌─────────────▼──────────────┐
                                        │ Ephemeral Docker containers │
                                        │  (Playwright execution)     │
                                        └──────────────────────────────┘
```

### 6.2 Services (v1)

1. **Auth & Connection Service** — manages user identity, OAuth flows + PAT storage (encrypted) for JIRA and GitHub, connection health checks, and which JIRA projects / GitHub repos a user has selected as "active."
2. **JIRA Integration Service** — wraps JIRA REST API v3: fetch assigned/accessible stories, fetch/update issue content, create issues, add comments, manage multiple JIRA sites per user.
3. **GitHub Integration Service** — wraps GitHub REST/GraphQL API: list accessible repos, read files/trees, create branches, commit changes, open PRs, manage multiple repos per user. Supports **both github.com and GitHub Enterprise Server**, with a configurable API base URL stored per connection.
4. **AI / Analysis Service** — the core intelligence layer:
   - Story scoring (INVEST + Gherkin AC) via Gemini.
   - Story rewrite suggestions.
   - Story ↔ test-case semantic matching (embeddings + Gemini reasoning) for impact analysis and gap detection.
   - Test case generation (Gherkin) and Playwright script generation.
   - Abstracted behind an internal `AIProvider` interface so the model/vendor can change without touching callers.
5. **Test Indexing Service** (sub-component or its own service) — periodically/​on-demand indexes `.feature` files (or detected test format) from connected repos into Postgres + a vector store (e.g., `pgvector`) for fast semantic search at scale, instead of re-scanning full repos per request.
6. **Test Runner Orchestrator Service** — accepts an approved Playwright script, spins up an **ephemeral sandboxed Docker container** (resource + time limited, network-restricted to the target under test), executes the run, streams logs/results back via WebSocket, tears the container down, and stores results (pass/fail, trace, screenshots) in Postgres/object storage.
7. **Notification/Job Status Service** (can be folded into API Gateway) — tracks long-running background jobs (batch impact analysis, indexing) and pushes progress to the frontend.

### 6.3 Test Case Indexing Strategy (for scale)
- On repo connection, run an initial index using **two parsing pipelines**, auto-selected per file:
  - **Gherkin pipeline** — parses `.feature` files into scenarios/steps.
  - **Code-spec pipeline** — statically parses plain Playwright `test()`/`describe()` blocks (AST-based, e.g. Babel/TS-Morph) into an equivalent structured representation (test name, description, key assertions/locators), for repos with no BDD layer.
  - A single repo can contain a mix of both; both pipelines normalize into the same structured `test_cases` schema so downstream matching logic doesn't care which pipeline produced a given entry.
- Chunk by scenario/test, generate embeddings (via Gemini embeddings API), store in `pgvector`.
- Subsequent runs use **incremental indexing** via GitHub webhooks or a diff against the last-indexed commit SHA — never a full re-scan.
- Impact analysis queries use vector similarity search + Gemini reasoning over the top-N candidates, not a brute-force scan of every test case — this is what makes "multiple repos, high volume" tractable.

### 6.4 Playwright Execution Sandbox
- Approved scripts run in **on-demand, ephemeral Docker containers** (per your preference) built from a pinned Playwright image.
- Each run: isolated container, capped CPU/memory, execution timeout, no persistent state, no access to other users' data or the host network beyond what's needed to reach the target app.
- **Target URL resolution:** the Orchestrator reads `use.baseURL` from the repo's `playwright.config.ts`/`.js` to determine what environment to point the run at, resolving statically-defined env-var references where possible. If `baseURL` can't be resolved (e.g., injected only via CI secrets at runtime), the UI prompts the user for a URL before the run starts.
- **Residual risk:** the platform cannot auto-discover runtime secrets the spec needs (test-account credentials, API keys, etc.). The user is responsible for supplying any required environment variables to the sandbox for a given run; the UI should surface a clear "this run may need env vars — provide them here" step rather than failing silently.
- Container lifecycle managed by the Test Runner Orchestrator via the Docker Engine API (local) — this is the same abstraction that maps cleanly to **Cloud Run Jobs** or **GKE Jobs** when you migrate to GCP later.
- Results (video/trace/screenshots) written to object storage (local: MinIO or filesystem volume; GCP later: Cloud Storage).

### 6.5 Data Model (high-level entities)
- `users`, `jira_connections`, `github_connections`
- `jira_projects` (cached metadata, per user/connection)
- `github_repos` (cached metadata, per user/connection)
- `stories` (cached JIRA issue snapshot + latest AI score + status)
- `story_score_history` (audit of scoring runs + proposed vs approved content)
- `test_cases` (indexed from repo, with embedding vector, source file path, commit SHA)
- `impact_analysis_runs` (batch job: stories in, test cases out, per-item verdict + rationale)
- `test_change_proposals` (diff, approval status, PR link once raised)
- `playwright_runs` (script, container run id, status, artifacts location)
- `story_generation_proposals` (test case → draft story, approval status, created JIRA issue link)
- `audit_log` (every write action, actor, before/after, linked AI suggestion id)

---

## 7. Tech Stack Summary

| Layer | Choice |
|---|---|
| Frontend | React (SPA), WebSocket client for job/run status |
| Backend | Python, FastAPI (per microservice) |
| Database | PostgreSQL (+ `pgvector` extension for embeddings) |
| Job queue | Redis + Celery (or Arq) for async/background analysis jobs |
| AI provider | Google Gemini (via abstracted `AIProvider` interface) |
| Test execution | Playwright, run in ephemeral Docker containers orchestrated via Docker Engine API |
| Local orchestration | Docker Compose |
| Future cloud target | GCP — Cloud Run/GKE, Cloud SQL (Postgres), Cloud Storage, Memorystore (Redis) |
| Auth to 3rd parties | OAuth 2.0 (JIRA Cloud OAuth 2.0 3LO, GitHub OAuth App) + PAT, both supported |

---

## 8. Resolved Decisions (formerly Open Questions)

1. **JIRA deployment type** — **JIRA Cloud only** for v1. Auth uses OAuth 2.0 3LO (+ PAT/API token as the alternate option per §4.0). Data Center/Server support is explicitly out of scope; revisit only if a future customer requires it, since it needs a different auth path (Basic auth/PAT, different base URLs).
2. **GitHub deployment type** — **Both github.com and GitHub Enterprise Server** must be supported. The GitHub Integration Service must accept a configurable API base URL per connection (github.com vs. a customer's GHES instance) rather than hardcoding `api.github.com`, and must handle GHES version differences in the REST/GraphQL API surface.
3. **Non-Gherkin test cases** — Build a **proper secondary parser for plain code-based Playwright specs** (`.spec.ts`/`.spec.js` with no BDD layer), not just best-effort text matching. This means the Test Indexing Service (§6.3) needs two parsing/extraction pipelines:
   - **Gherkin pipeline:** parse `.feature` files into scenarios/steps directly.
   - **Code-spec pipeline:** statically parse Playwright `test()`/`describe()` blocks (via an AST parser, e.g. Babel/TS-Morph) to extract test names, descriptions, assertions, and locators into an equivalent structured representation, so both pipelines feed the same downstream embedding/matching logic.
   - Repos are auto-detected per file type at indexing time; a repo can mix both formats.
4. **Rate limits** — **Caching + backoff is sufficient for v1.** No dedicated rate-budgeting/prioritization service needed now; each integration service implements standard exponential backoff + local response caching (§6.2/6.3 as already described). Revisit if usage volume grows materially post-GCP migration.
5. **Approval model** — **Single-approver v1**: the requesting user's own approval is sufficient to trigger any JIRA/GitHub write. No second-reviewer workflow in v1. (Design the approval data model in §6.5 so a second-approver step could be added later without a schema rewrite — e.g., `approval_status` as an extensible enum rather than a boolean.)
6. **Target environment for Playwright runs** — The Test Runner Orchestrator **reads the target URL from the repo's own Playwright config** (`playwright.config.ts` → `use.baseURL`, resolving any env-var references it can from the repo/CI config where accessible) rather than requiring manual per-project URL entry. If `baseURL` can't be resolved statically (e.g., it's injected purely via CI secrets), the UI falls back to prompting the user for a URL at run time. This should be noted as a residual risk: **runtime secrets/env vars used by the app under test are not something this platform can discover automatically** — the user is responsible for ensuring the sandbox container has any environment variables the spec needs (e.g., test-account credentials) to execute successfully.

---

## 9. Suggested Phased Delivery

- **Phase 1 (Foundation):** Auth/Connection service, JIRA + GitHub integration services, Postgres schema, React shell with the 3 action cards, Docker Compose local setup.
- **Phase 2:** Feature A (story scoring + rewrite + approval + JIRA write-back).
- **Phase 3:** Test indexing service + Feature B impact analysis (read-only suggestions first).
- **Phase 4:** Feature B write-back (branch + PR) + Playwright script generation + copy-to-clipboard.
- **Phase 5:** Test Runner Orchestrator (in-app sandboxed execution) — highest infra complexity, sequenced last.
- **Phase 6:** Feature C (test → missing story discovery).
- **Phase 7:** GCP migration.

---

## 10. Approval

| Reviewer | Decision | Date |
|---|---|---|
| | | |
