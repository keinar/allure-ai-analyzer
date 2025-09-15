# Allure AI Failure Analyzer

> An intelligent CLI tool that transforms raw Allure test results into an interactive dashboard featuring a powerful AI analyst. Get visual insights, proactive summaries, and ask complex questions about your test failures in natural language.

---

<p align="center">
  <img src="https://raw.githubusercontent.com/keinar/allure-ai-analyzer/main/screenshot.png" width="900" alt="screenshot">
</p>

## Features

✨ **Interactive HTML Dashboard:** Displays grouped failures with expandable details, including stack traces and examples.  

🤖 **Integrated AI Analyst (Powered by Gemini):**  
- Conversational memory for follow-up questions.  
- Autonomous use of analysis tools (historical trends, bug frequency, etc.).  
- Natural language queries: *“What’s the difference between the last two reports?”*  

🚀 **Proactive Executive Summary:** Automatic summary of the latest run (configurable).  

📊 **Visual Data Dashboard:** Failures by epic, status breakdown, trends.  

📈 **Historical Trend Analysis:** Identify patterns and track bug recurrence over time.  

---

## Prerequisites

- **Python 3.11+**
- **pip**
- An **Allure results** directory from your test runs.

> macOS tip (Homebrew): `brew install python@3.11`

---

## Installation

```bash
pip install allure-ai-analyzer
```

---

## Quickstart

1. **Create a virtual environment (recommended):**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install the CLI:**
   ```bash
   pip install allure-ai-analyzer
   ```

3. **Configure your API key:**  
   Create a `.env` file in your automation project root:
   ```bash
   GEMINI_API_KEY="your-api-key-here"
   ```

4. **Generate a report:**  
   Run from the folder containing `allure-results`:
   ```bash
   allure-analyze generate
   ```

5. **View the dashboard + AI analyst:**  
   ```bash
   allure-analyze view
   ```
   Default server: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## Configuration

Override defaults with `allure-analyzer-config.yaml` in your project root.

Default config (`src/allure_analyzer/config/default_config.yaml`):
```yaml
top_n_groups_to_report: -1
include_broken: true
proactive_summary_on_load: true
```

CLI flags:
- `--path /path/to/results`
- `--config /path/to/config.yaml`
- `--top-n 10`
- `--exclude-broken`
- `--port 8001`
- `--no-proactive-summary`

---

## Usage Examples

- **Generate a report**:
  ```bash
  allure-analyze generate --top-n 10
  ```
- **View the dashboard**:
  ```bash
  allure-analyze view --port 9000
  ```

---

## Troubleshooting

- **Command not found:** Activate your venv and check `pip show allure-ai-analyzer`.  
- **No matching distribution:** Ensure you’re on Python ≥3.11.  
- **Assets not found:** Make sure you installed from PyPI, not a local copy missing `static/` or `templates/`.

---

## Using the AI Analyst

Example queries:
- “What is the difference between the last two reports?”  
- “Analyze failure trends for the last 30 days.”  
- “What was the most impacted epic in the latest run?”  
- “Summarize the key issues in the latest report.”  

---

## License

[MIT](LICENSE)
