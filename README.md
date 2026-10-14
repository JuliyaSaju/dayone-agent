<div style="font-family: 'Times New Roman', Times, serif; font-size: 16px; line-height: 1.7; color: #1a1a1a; max-width: 900px; margin: 0 auto; padding: 20px;">

<h1 align="center" style="font-size: 28px; font-weight: normal; margin-bottom: 6px; letter-spacing: 0.5px;">
  Day-One Agent: Autonomous IT Onboarding with Ground-Truth Verification
</h1>

<p align="center" style="font-size: 15px; color: #555; margin-top: 0; margin-bottom: 25px; font-style: italic;">
  A reliable, zero-trust autonomous agent for employee provisioning across Mattermost and Gitea
</p>

<hr style="border: none; border-top: 1px solid #ccc; margin: 20px 0;">

<h2>1. Project Overview</h2>

<p>
This project is an autonomous AI agent system designed to handle employee onboarding and offboarding operations across real enterprise applications. Instead of an IT administrator manually navigating through multiple administrative consoles to create users, assign team channels, and provision repository permissions, the administrator provides a single natural language instruction:
</p>

<blockquote style="background: #f9f9f9; border-left: 4px solid #333; margin: 15px 0; padding: 10px 18px; font-style: italic;">
  "Priya Sharma joins Monday as a designer"<br>
  "Rahul Verma left today"
</blockquote>

<p>
From this input, the agent extracts the user intent, consults organizational policy rules, invokes the appropriate REST APIs across Mattermost and Gitea, safely handles potential network dropouts, and runs an independent verification suite against the live services.
</p>

<hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">

<h2>2. Core Motivation and Problem Statement</h2>

<p>
When building autonomous agents powered by large language models, the most dangerous failure mode is <b>unverified self-reporting</b>. A standard LLM will frequently report that an operation was successful even if an underlying API call dropped the connection, timed out, or returned an unparsed error. In access control, this causes severe silent failures: employees missing critical channels, orphan accounts, or unintended privilege escalation.
</p>

<p>
Furthermore, relying on language models for security decisions exposes the company to prompt injection attacks, where a malicious instruction could coerce the agent into granting administrator privileges.
</p>

<p>
To solve these challenges, I built this system on three fundamental engineering principles:
</p>

<ol>
  <li><b>Separation of Reasoning and Policy:</b> The language model is strictly used to parse conversational input and select appropriate tools. Company access policies are hard-coded in deterministic Python logic, meaning the model is mathematically incapable of granting unauthorized permissions regardless of user phrasing.</li>
  <li><b>Human-in-the-Loop Safeguards:</b> High-risk operations—specifically account deactivations during offboarding and requests for sensitive resources (such as finance access)—pause execution and require explicit interactive confirmation from a human supervisor.</li>
  <li><b>Zero-AI Ground-Truth Verification:</b> After the agent finishes its work, an independent verification engine queries the real application APIs directly. The agent's final status is determined solely by verified ground truth, never by the AI model's own completion text.</li>
</ol>

<hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">

<h2>3. End-to-End Implementation Workflow</h2>

<p>
The project was constructed methodically in eight interconnected stages:
</p>

<h3>Phase 1: Local Application Infrastructure</h3>
<p>
To ensure the agent works against production-grade services rather than artificial mocks, I deployed containerized instances of <b>Mattermost</b> (team messaging on port 8065) and <b>Gitea</b> (git hosting on port 3000) using Docker Compose. All network communications occur via authenticated HTTP REST protocols.
</p>

<h3>Phase 2: Declarative Policy Specifications</h3>
<p>
I created a declarative configuration file in <code>config/roles.yaml</code> specifying the exact resources permitted for each role. For example, a designer is authorized only for the Mattermost <code>design</code> channel and the Gitea <code>ui-kit</code> repository. All other departments (engineering, finance, hr-private) are prohibited by default under the principle of least privilege.
</p>

<h3>Phase 3: Application Client Integrations</h3>
<p>
In <code>tools/apps.py</code>, I implemented concrete REST client interfaces for both platforms. Sensitive administrative tokens and credentials are kept strictly in a local <code>.env</code> file excluded from source control, with a clean template provided in <code>.env.example</code>.
</p>

<h3>Phase 4: Deterministic Policy Gate</h3>
<p>
In <code>agent/policy.py</code>, I built a pre-execution security gate. If an incoming request asks for permissions outside the defined role boundaries, the policy gate strips those requests before any tool can be executed. Sensitive actions automatically trigger an interactive confirmation prompt in the terminal.
</p>

<h3>Phase 5: Idempotent Execution and Fault Tolerance</h3>
<p>
In <code>agent/executor.py</code>, I engineered resilient tool dispatching. When creating users, the tool checks whether the account already exists. If a network connection drops after account creation, the subsequent retry returns an existing status cleanly without producing duplicate accounts. Transient network errors (HTTP 5xx, socket timeouts) trigger automated exponential backoff retries. Every action is recorded in a persistent SQLite audit log.
</p>

<h3>Phase 6: Independent Ground-Truth Verifier</h3>
<p>
In <code>verify/verifier.py</code>, I implemented an autonomous verification suite containing zero AI dependencies. The verifier checks positive team and channel membership, proves negative non-membership across all unauthorized channels and repositories, and conducts an active authentication test to prove the credentials work (or in offboarding, confirms that login is strictly blocked).
</p>

<h3>Phase 7: Frontier Model Integration</h3>
<p>
I integrated Google Gemini (<code>gemini-3.5-flash-lite</code>) through an OpenAI-compatible adapter in <code>agent/llm.py</code>. During testing, I identified and resolved an API protocol incompatibility where multi-turn assistant tool calls required preserving Gemini's internal cryptographic <code>thought_signature</code> attribute.
</p>

<h3>Phase 8: Systematic Benchmark Evaluation</h3>
<p>
I developed an evaluation harness in <code>scripts/evaluate.py</code> to empirically test the system across eight diverse scenarios: role-based onboarding, sensitive access approval, sensitive access denial, injected network faults, prompt injection resistance, nonexistent user offboarding, and silent write failure detection.
</p>

<hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">

<h2>4. Evaluation Results and Empirical Evidence</h2>

<h3>A. Single Employee Autonomous Onboarding</h3>
<p>
Below is the terminal execution output demonstrating the autonomous onboarding of Maya Lin as a designer. The agent parsed the natural language sentence, created the accounts, assigned only the approved resources, and passed all 12 independent ground-truth verification checks in 15.27 seconds.
</p>

<div align="center" style="margin: 20px 0;">
  <img src="screenshots/onboarding_verified.png" alt="Autonomous Onboarding Terminal Execution" style="max-width: 100%; border: 1px solid #ccc; border-radius: 4px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
</div>

<h3>B. Complete Benchmark Reliability Suite</h3>
<p>
To demonstrate statistical robustness, I executed the full eight-scenario benchmark suite against live local applications. Below is the unedited terminal output showing the completion of all evaluation passes.
</p>

<div align="center" style="margin: 20px 0;">
  <img src="screenshots/evaluation_results.png" alt="Empirical Benchmark Evaluation Execution" style="max-width: 100%; border: 1px solid #ccc; border-radius: 4px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);">
</div>

<h3>C. Summary of Performance Metrics</h3>

<table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 15px; border: 1px solid #bbb;">
  <thead>
    <tr style="background-color: #f2f2f2; text-align: left;">
      <th style="padding: 10px 14px; border: 1px solid #bbb;">Evaluated Metric</th>
      <th style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">Measured Result</th>
      <th style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">Target Benchmark</th>
      <th style="padding: 10px 14px; border: 1px solid #bbb;">Engineering Significance</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Verified Completion Rate</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center; font-weight: bold;">100.0%</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">Maximize</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Proportion of valid tasks confirmed by ground-truth checks</td>
    </tr>
    <tr style="background-color: #fafafa;">
      <td style="padding: 10px 14px; border: 1px solid #bbb;">False-Completion Rate</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center; font-weight: bold;">0.0%</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">0.0%</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Zero false successes reported during simulated drops</td>
    </tr>
    <tr>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Duplicate Account Creation</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center; font-weight: bold;">0</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">0</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Proves idempotency across network failure recoveries</td>
    </tr>
    <tr style="background-color: #fafafa;">
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Fault Recovery Rate</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center; font-weight: bold;">100.0%</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">Maximize</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Tasks that recovered smoothly from injected timeouts</td>
    </tr>
    <tr>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Unauthorized Access Grants</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center; font-weight: bold;">0</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">0</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Prompt injections and unapproved grants successfully blocked</td>
    </tr>
    <tr style="background-color: #fafafa;">
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Average Execution Latency</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">39.46s</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">Report</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Mean runtime per complete autonomous execution</td>
    </tr>
    <tr>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Average Tool Calls per Task</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">7.12</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb; text-align: center;">Report</td>
      <td style="padding: 10px 14px; border: 1px solid #bbb;">Total API calls dispatched including retry attempts</td>
    </tr>
  </tbody>
</table>

<hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">

<h2>5. System Architecture and File Structure</h2>

<p>
The codebase is structured into clear, single-responsibility modules:
</p>

<ul>
  <li><b>config/roles.yaml:</b> Declarative specification of organizational roles and permitted channels/repositories.</li>
  <li><b>agent/runtime.py:</b> The central execution loop orchestrating intent parsing, tool selection, and verification calls.</li>
  <li><b>agent/policy.py:</b> Pure Python policy engine enforcing role boundaries and intercepting sensitive actions for human approval.</li>
  <li><b>agent/executor.py:</b> Tool dispatcher handling transient failure classification, exponential backoff, and SQLite audit logging.</li>
  <li><b>agent/llm.py:</b> Provider-agnostic adapter supporting Gemini, OpenAI, Claude, and local mock testing backends.</li>
  <li><b>tools/apps.py:</b> Concrete REST API client implementations for Mattermost (port 8065) and Gitea (port 3000).</li>
  <li><b>tools/registry.py:</b> Pydantic schemas exposing typed tool parameters to the language model.</li>
  <li><b>verify/verifier.py:</b> Independent verification suite checking positive access, negative access, and live login state.</li>
  <li><b>scripts/evaluate.py:</b> Automated eight-scenario benchmark runner.</li>
  <li><b>scripts/seed.py:</b> Environment initialization script populating baseline company teams, repos, and accounts.</li>
  <li><b>scripts/check_setup.py:</b> Diagnostic script verifying that all ten container and API endpoints are reachable.</li>
  <li><b>tests/test_agent.py:</b> Fourteen unit test cases evaluating logic against in-memory mock applications.</li>
</ul>

<hr style="border: none; border-top: 1px solid #eee; margin: 25px 0;">

<h2>6. Instructions for Running the System</h2>

<p>
To run and test the complete system locally, follow these steps:
</p>

<h3>Step 1: Clone and Set Up the Python Environment</h3>
<pre style="background: #f7f7f7; border: 1px solid #ddd; padding: 12px; border-radius: 4px; font-family: Consolas, monospace; font-size: 14px;">
git clone https://github.com/&lt;your-username&gt;/dayone-agent.git
cd dayone-agent

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
</pre>

<h3>Step 2: Start Local Containers</h3>
<pre style="background: #f7f7f7; border: 1px solid #ddd; padding: 12px; border-radius: 4px; font-family: Consolas, monospace; font-size: 14px;">
docker compose -f docker/docker-compose.yml up -d
</pre>

<h3>Step 3: Configure Environment Variables</h3>
<pre style="background: #f7f7f7; border: 1px solid #ddd; padding: 12px; border-radius: 4px; font-family: Consolas, monospace; font-size: 14px;">
copy .env.example .env
</pre>
<p>
Generate a Gitea administrator access token using the Docker CLI, then add the token and your model API key to <code>.env</code>.
</p>

<h3>Step 4: Seed Applications and Test Connections</h3>
<pre style="background: #f7f7f7; border: 1px solid #ddd; padding: 12px; border-radius: 4px; font-family: Consolas, monospace; font-size: 14px;">
python -m scripts.seed
python -m scripts.check_setup
</pre>

<h3>Step 5: Execute the Agent</h3>
<pre style="background: #f7f7f7; border: 1px solid #ddd; padding: 12px; border-radius: 4px; font-family: Consolas, monospace; font-size: 14px;">
# Autonomous onboarding:
python run.py "Priya Sharma joins Monday as a designer"

# Interactive offboarding:
python run.py "Rahul Verma left today"

# Fault injection and idempotent recovery:
python run.py "Aarav Patel joins Monday as a developer" --faults mm_create_user=fail_after_once
</pre>

<h3>Step 6: Run Unit Tests and Benchmark Suite</h3>
<pre style="background: #f7f7f7; border: 1px solid #ddd; padding: 12px; border-radius: 4px; font-family: Consolas, monospace; font-size: 14px;">
# Unit test suite (14 mock tests in under 1 second):
python -m pytest tests/ -v

# 8-scenario live benchmark evaluation:
python -m scripts.evaluate
</pre>

<hr style="border: none; border-top: 1px solid #ccc; margin: 30px 0 15px 0;">

<p align="center" style="font-size: 14px; color: #777;">
  Project repository submitted as part of the technical evaluation for autonomous agent engineering.
</p>

</div>
