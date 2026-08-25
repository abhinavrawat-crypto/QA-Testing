# QualityAI Enterprise — Requirements & Test Impact Intelligence

QualityAI is an advanced AI-driven Pair-Programming & Quality Governance platform that unifies JIRA user stories and automated Playwright test suites. Powered by Google Gemini, vector search embeddings, and human-in-the-loop governance, it helps engineering teams keep requirements and test cases in perfect synchronization.

---

## 🚀 Key Features

### 1. INVEST Story Auditing & AI Rewriting (Story Audit)
* **INVEST Quality Scoring:** Evaluates JIRA backlog items against industry-standard INVEST criteria (Independent, Negotiable, Valuable, Estimable, Small, Testable).
* **Gherkin Acceptance Criteria:** Automatically verifies and formats acceptance criteria using Gherkin syntax (`Given/When/Then`).
* **Visual Diff Canvas:** Provides side-by-side diff comparison between original user stories and AI-proposed revisions.
* **JIRA Write-Back:** One-click syncing of approved changes back to the JIRA ticket.

### 2. Vector-Based Test Impact Analysis
* **pgvector Search Engine:** Indexes Gherkin test scenarios and Playwright specifications into a vector space.
* **Semantic Impact Tracing:** Ranks test cases by impact when JIRA story descriptions change.
* **Automated Playwright Gen:** Instantly generates or updates automated Playwright test scripts based on requirements changes.
* **PR Automation:** Automatically creates branches, commits files, and opens pull requests on GitHub/GitLab.

### 3. Coverage Gap Discovery (Story Discovery)
* **Reverse Index Scanner:** Scans your test suites to identify automated test cases that do not map to any active JIRA user stories.
* **AI Requirement Drafts:** Generates fully formatted user stories for unmatched test files.
* **Backlog Insertion:** Pushes newly created stories directly to your JIRA backlog.

### 4. Integration Hub
* **Multi-Account Integrations:** Seamlessly manage multiple JIRA and GitHub connection keys.
* **AES-256 Encryption:** All JIRA and GitHub connection secrets are securely encrypted at rest.

---

## 🛠️ Architecture & Tech Stack

* **Frontend:** React (Vite, modern ES6, CSS variables)
* **Backend:** FastAPI (Python, Uvicorn, SQLAlchemy async)
* **Database:** PostgreSQL with `pgvector` extension for vector operations
* **Background Tasks:** Redis & Celery (for async code generation & analysis)
* **AI Model:** Google Gemini API (`gemini-1.5-pro` & `text-embedding-004`)

---

## ⚙️ Quick Start Setup

### Prerequisites
* [Docker & Docker Compose](https://docs.docker.com/engine/install/)
* A Google Gemini API Key
* A JIRA account/API token
* A GitHub Personal Access Token

### Local Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/abhinavrawat-crypto/Quality-AI.git
   cd Quality-AI
   ```

2. **Configure Environment Variables:**
   Copy the example environment file and fill in your keys:
   ```bash
   cp .env.example .env
   # Open .env and add your GEMINI_API_KEY, database settings, and JIRA/GitHub client secrets
   ```

3. **Start the Platform (Docker Compose):**
   ```bash
   docker-compose up --build
   ```

   Once running, the applications are available at:
   * **Frontend Dashboard:** `http://localhost:3000`
   * **Backend REST API:** `http://localhost:8000`
   * **API Swagger Docs:** `http://localhost:8000/docs`

---

## 💻 Local Development Run (Without Docker)

### Backend Setup
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

---

## 🔒 Security & Governance
* **Human-in-the-Loop:** QualityAI does not write code or update JIRA tickets autonomously. Every branch creation, PR opening, and requirement update requires explicit human confirmation.
* **Credential Isolation:** API keys and connection tokens are never hardcoded. All database credentials and external API tokens are decrypted dynamically at the application layer.
