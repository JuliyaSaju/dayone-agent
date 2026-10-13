# DECISIONS.md — Day-One Agent Project Diary & Engineering Guide

This document records the exact step-by-step technical decisions, commands executed, architecture rationale, and division of work between the AI mentor and the engineer. It serves as both our audit log and interview preparation guide.

---

## Step 0: Project Strategy & Route Choice
- **What Was Decided:** We chose **Route A** (walking through and rigorously understanding the reference implementation) over Route B (rewriting everything from scratch).
- **Commands Executed:**
  - `python --version` (verified Python 3.12.9 is installed on Windows).
- **Why This Step Was Done:** With a submission deadline tomorrow and a 20-hour window, building 14 modules from zero would risk running out of time. Route A allows us to deeply inspect every line of code, execute real verification tests, practice live interview modifications, and connect to live applications while meeting the deadline.
- **Division of Work:**
  - **AI Mentor:** Checked Python version and directory structure; provided transparent trade-offs between both paths.
  - **Engineer (Me):** Decided on Route A with the requirement that every file must be thoroughly understood and modifiable on demand.

---

## Step 1: Environment & Sandbox Infrastructure Setup
- **What Was Built:** An isolated Python 3.12 virtual environment (`venv`), installation of all project dependencies, and installation/startup of Docker Desktop with WSL 2.
- **Commands Executed:**
  - `python -m venv venv` (created isolated virtual environment).
  - `venv\Scripts\activate.bat` (activated virtual environment in Command Prompt).
  - `pip install -r requirements.txt` (installed httpx, pydantic, pyyaml, python-dotenv, pytest, anthropic, openai).
  - `docker compose -f docker/docker-compose.yml up -d` (pulled and started Gitea and Mattermost containers).
- **Why This Step Was Done:**
  - The virtual environment prevents library conflicts with system-wide packages.
  - The hiring assessment requires interacting with *real* applications rather than mocked HTTP calls. Docker allows us to run isolated, local instances of Mattermost (port 8065) and Gitea (port 3000) with zero cost and no external credentials.
- **Division of Work:**
  - **AI Mentor:** Diagnosed command line execution issues between PowerShell and Command Prompt; identified a corrupted Docker download and guided a clean retry.
  - **Engineer (Me):** Configured Docker Desktop, resolved WSL 2 prerequisites, executed terminal commands, and confirmed web services loaded locally in the browser.

---

## Step 2: Unit Testing Against In-Memory Mocks
- **What Was Built:** Ran the complete test suite verifying 14 key agent scenarios against in-memory mock applications (`tests/fakes.py`).
- **Commands Executed:**
  - `python -m pytest tests/ -v`
- **Why This Step Was Done:** Before wiring our agent to live network sockets, we must prove that the core control loop, policy gates, idempotency guarantees, and retry logic pass every specification. All 14 tests passed in 0.57s.
  - *Scenarios verified:* Successful onboarding, missing role clarifications, username conflict resolution, recovery from post-creation timeouts without duplicate accounts, pre-call transient error retries, verifier detection of silent failures, prompt injection resistance, human approval gates for sensitive access, offboarding verification, and boundary gate enforcement.
- **Division of Work:**
  - **AI Mentor:** Explained pytest test architecture and how fake in-memory applications simulate network failures.
  - **Engineer (Me):** Executed the test runner in the terminal and validated that all 14 test cases passed.

---

## Step 3: Application Provisioning & Secrets Management
- **What Was Built:** Created administrator accounts on Gitea and Mattermost, generated an administrative API access token, and configured local environment variables.
- **Commands Executed:**
  - `docker exec -u git dayone-gitea gitea admin user create --admin --username dayone-admin --password Admin-Pass-12345! --email admin@example.test`
  - `docker exec -u git dayone-gitea gitea admin user generate-access-token --username dayone-admin --token-name agent --scopes all`
  - `copy .env.example .env`
- **Why This Step Was Done:**
  - Real API operations require authenticated credentials. Gitea uses an Authorization Token (`token <token>`), while Mattermost authenticates via administrative session cookies/tokens.
  - Security Best Practice: All tokens and credentials are kept strictly in `.env`, which is listed in `.gitignore`. The repository template `.env.example` remains free of secrets so sensitive keys are never pushed to GitHub.
- **Division of Work:**
  - **AI Mentor:** Provided the CLI commands to provision users inside the running container and guided secure token handling.
  - **Engineer (Me):** Ran the user creation and token generation commands, copied the template to `.env`, securely added the token, and set up the Mattermost web administrator.

---

## Step 4: Environment Seeding & API Verification
- **What Was Built:** Initialized company data structures across both applications according to `config/roles.yaml` and verified each HTTP endpoint individually.
- **Commands Executed:**
  - `python -m scripts.seed` (created team, private channels, private repos, and initial employee Rahul Verma).
  - `python -m scripts.check_setup` (verified all 10 network and database checks).
- **What Was Verified in the Real Apps:**
  - **Mattermost:** Admin session authentication succeeded; Team `acme` exists; Channels `design`, `engineering`, `finance`, and `hr-private` confirmed.
  - **Gitea:** Admin token authenticated successfully; User listing returned `dayone-admin` and `rahul.verma`; Repositories `ui-kit`, `backend`, and `finance-reports` confirmed.
- **Why This Step Was Done:** Seeding provides a consistent baseline state, and checking each endpoint individually ensures no misconfigured URLs or tokens before the agent loop begins.
- **Division of Work:**
  - **AI Mentor:** Explained the idempotency of the seed script and how `check_setup.py` isolates API failures.
  - **Engineer (Me):** Ran both commands in the terminal and confirmed 100% green checks across both local apps.

---

## Step 5: Live Execution & Real Application Validation (3 Scenarios)
- **What Was Built/Tested:** Executed the complete end-to-end agent loop against live Mattermost and Gitea servers across three core operational scenarios: onboarding, sensitive offboarding with human sign-off, and fault-injected recovery.
- **Commands Executed:**
  1. `python run.py "Priya Sharma joins Monday as a designer"`
  2. `python run.py "Rahul Verma left today"`
  3. `python run.py "Aarav Patel joins Monday as a developer" --faults mm_create_user=fail_after_once`

### Deep Dive into the 3 Scenarios:

#### Scenario 1: Autonomous Onboarding (Priya Sharma)
- **Execution:**
  - The AI extracted the intent: Action = `onboard`, First Name = `Priya`, Last Name = `Sharma`, Role = `designer`.
  - The policy gate looked up `roles.yaml` and computed the approved state: `design` channel in Mattermost, `ui-kit` repository in Gitea.
  - The agent created the accounts in both platforms and assigned the authorized resources.
  - The independent verifier ran fresh HTTP queries directly against both applications. It confirmed that Priya possessed the exact allowed channels and repositories, possessed zero unauthorized resources (`engineering`, `finance`, `hr-private`, `backend`, `finance-reports` were all confirmed `False`), and verified that her credentials successfully authenticated.
  - Status: `VERIFIED` in 12.53 seconds.

#### Scenario 2: Sensitive Offboarding & Human Approval Gate (Rahul Verma)
- **Execution:**
  - The AI parsed: Action = `offboard`, Name = `Rahul Verma`.
  - Because account deactivation is destructive, `agent/policy.py` flagged the action as sensitive and blocked tool calls until approved.
  - The terminal paused execution and prompted interactively: `[approval needed] Deactivate ALL accounts for Rahul Verma (rahul.verma@example.test)? (yes/no)`.
  - Only after typing `y` did the agent deactivate the Mattermost user, disable the Gitea user, and strip collaborator permissions across all repositories.
  - The independent verifier physically attempted to log in using Rahul's password on both Mattermost and Gitea, confirming that access was completely refused (`[PASS] Mattermost: login is refused`, `[PASS] Gitea: login is refused`).
  - Status: `VERIFIED` in 10.72 seconds.

#### Scenario 3: Fault Injection & Idempotent Recovery (Aarav Patel)
- **What Happened Under the Hood:**
  1. The agent called `mm_create_user` to provision Aarav's Mattermost account.
  2. Mattermost successfully created the account in its database.
  3. Our injected fault flag (`--faults mm_create_user=fail_after_once`) simulated a network drop right after creation, causing the initial HTTP response to fail.
  4. The executor caught the transient network error and triggered an automatic retry with backoff.
  5. On the retry attempt, `mm_create_user` checked if the account with `aarav.patel@example.test` already existed.
  6. Rather than crashing with an "Account already exists" error or spawning duplicate users, the idempotent tool returned `{'status': 'exists', 'username': 'aarav.patel'}`.
  7. The agent recognized the existing resource, gracefully continued with Gitea provisioning and repo assignment, and finished with all 12 independent checks passing.
  8. Status: `VERIFIED` in 12.88 seconds.

- **Why This Matters for Interviews:**
  - In distributed systems, network partitions and timeouts are inevitable. Naive AI agents crash or produce duplicate entities upon retrying.
  - By guaranteeing **idempotent tools** (checking existence before creating and handling conflict codes cleanly) alongside an **independent verifier**, our system guarantees zero duplicate accounts and 100% reliable state transitions.

- **Division of Work:**
  - **AI Mentor:** Explained the internal retry loop, fault simulation mechanics, and the difference between `'status': 'created'` vs `'status': 'exists'`.
  - **Engineer (Me):** Ran all three CLI scenarios in the console, interacted with the human approval prompt, and verified user accounts across the live browser interfaces.

---

## Step 6: Core Architectural Walkthrough & Code Review
- **What Was Built/Reviewed:** Detailed line-by-line inspection and teach-back comprehension of all five core modules:
  1. `config/roles.yaml` (declarative single source of truth for organizational access).
  2. `agent/policy.py` (pre-execution security gate enforcing least-privilege boundaries).
  3. `agent/runtime.py` (8-stage main agent loop; status derived solely from verification).
  4. `verify/verifier.py` (independent verification checking positive membership, negative non-membership, and live login lockout).
  5. `agent/executor.py` (audit logging, transient vs permanent error classification, exponential backoff, and idempotency guarantees).
- **Why This Step Was Done:** Ensures the engineer can explain every single design decision and line of code in live interview scenarios.
- **Division of Work:**
  - **AI Mentor:** Guided the walkthrough and quizzed key distributed systems and security concepts.
  - **Engineer (Me):** Explained back each module in my own words, verified least-privilege security rationale, and traced error handling.

---

## Step 7: Frontier LLM Integration & Gemini Compatibility Debugging
- **What Was Built:** Connected the agent loop to a live frontier model using Google Gemini (`gemini-3.5-flash-lite`) via the OpenAI-compatible endpoint.
- **Commands Executed:**
  - `python run.py "Maya Lin joins Monday as a designer"`
- **The Engineering Challenge & Real-World Fix:**
  - When switching from the MockLLM to Gemini, multi-turn tool calling failed with HTTP 400: `Function call is missing a thought_signature in functionCall parts`.
  - *Diagnosis:* Google Gemini attaches an internal cryptographic `thought_signature` inside `extra_content` for function calls. Our standard OpenAI adapter was dropping `extra_content` when passing assistant tool calls back in the conversation history.
  - *Resolution:* Enhanced `agent/llm.py` and `agent/runtime.py` to preserve `extra_content` across multi-turn messages without breaking any existing provider formats.
  - *Validation:* All 14 pytest unit tests passed (0.37s), and the live agent completed onboarding for Maya Lin with full independent verification in 15.27s.
- **Division of Work:**
  - **AI Mentor:** Diagnosed the API protocol discrepancy and proposed the non-breaking adapter update.
  - **Engineer (Me):** Generated the Gemini API key in Google AI Studio, updated `.env`, approved the code edits, and executed the live Gemini agent run.



