import os
import json
import yaml
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_from_directory
from google import genai
from google.genai import types
from dotenv import load_dotenv
from typing import Dict, Any, List
import importlib.resources

# Load .env from the current working directory where the user runs the command
load_dotenv(Path.cwd() / ".env")

app = Flask(
    __name__,
    template_folder='templates',
    static_folder='static'
)

# Centralized storage in the user's home directory
HOME_DIR = Path.home()
HISTORY_BASE_DIR = HOME_DIR / ".allure-analyzer" / "reports_history"

# Global variables that will be initialized by the CLI
client = None
server_config = {}
chat_histories: Dict[str, List[types.Content]] = {}

def initialize_config(cli_overrides: Dict = None):
    """
    Initializes the server's configuration and the Gemini client.
    This is called by cli.py before the server starts.
    """
    global client, server_config
    
    # Initialize Gemini Client
    if not client:
        try:
            client = genai.Client()
            print("✅ Gemini API Client initialized successfully.")
        except Exception as e:
            print(f"❌ Error initializing Gemini Client: {e}")

    # Load and merge configurations
    try:
        default_config_text = importlib.resources.read_text('allure_analyzer.config', 'default_config.yaml')
        config = yaml.safe_load(default_config_text) or {}
    except Exception:
        print("⚠️ WARNING: Could not load default config.")
        config = {}

    if cli_overrides:
        config.update(cli_overrides)
    
    server_config = config

# --- The AI's "Toolbox" ---

def get_list_of_all_reports() -> List[str]:
    """
    Returns a sorted list of all available report timestamps, from newest to oldest.
    """
    print("TOOLBOX: Called get_list_of_all_reports")
    if not os.path.isdir(HISTORY_BASE_DIR):
        return []
    return sorted(
        [d for d in os.listdir(HISTORY_BASE_DIR) if os.path.isdir(os.path.join(HISTORY_BASE_DIR, d))],
        reverse=True
    )

def read_data_from_report(timestamp: str) -> Dict[str, Any]:
    """
    Reads and returns the full JSON data for a single report given its timestamp.
    """
    print(f"TOOLBOX: Called read_data_from_report with timestamp: {timestamp}")
    report_path = os.path.join(HISTORY_BASE_DIR, timestamp, 'failure_analysis_report.json')
    if not os.path.exists(report_path):
        return {"error": f"Report with timestamp '{timestamp}' not found."}
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return json.loads(content) if content else {"error": "File is empty."}
    except Exception as e:
        return {"error": f"Error reading report '{timestamp}': {str(e)}"}

def get_reports_in_date_range(days_ago: int) -> List[str]:
    """
    Returns a list of report timestamps from the last N days.
    """
    from datetime import datetime, timedelta
    print(f"TOOLBOX: Called get_reports_in_date_range for last {days_ago} days")
    start_date = datetime.now() - timedelta(days=days_ago)
    all_reports = get_list_of_all_reports()
    return [
        r for r in all_reports 
        if datetime.strptime(r.split('_')[0], '%Y-%m-%d') >= start_date
    ]

def analyze_failure_trends(days_ago: int) -> Dict[str, Any]:
    """
    Analyzes all reports from the last N days to identify trends.
    """
    print(f"TOOLBOX: Called analyze_failure_trends for last {days_ago} days")
    report_timestamps = get_reports_in_date_range(days_ago)
    if not report_timestamps:
        return {"error": f"No reports found in the last {days_ago} days."}

    trends = {}
    for timestamp in reversed(report_timestamps):
        data = read_data_from_report(timestamp)
        if data and "groups" in data and isinstance(data["groups"], list):
            for group in data["groups"]:
                fingerprint = group.get("fingerprint_what")
                if not fingerprint: continue
                
                if fingerprint not in trends:
                    trends[fingerprint] = {
                        "total_occurrences": 0,
                        "first_seen": timestamp.split('_')[0],
                        "last_seen": timestamp.split('_')[0],
                        "seen_in_reports": 0,
                        "title": group.get("title")
                    }
                
                trends[fingerprint]["total_occurrences"] += group.get("count", 0)
                trends[fingerprint]["last_seen"] = timestamp.split('_')[0]
                trends[fingerprint]["seen_in_reports"] += 1

    return trends

# --- Flask Routes ---
@app.route('/')
def index():
    proactive_summary = server_config.get('proactive_summary_on_load', True)
    return render_template('report.html', proactive_summary_enabled=proactive_summary)

@app.route('/reports')
def list_reports():
    return jsonify(get_list_of_all_reports())

@app.route('/reports/<path:timestamp>')
def get_report_data(timestamp):
    if '..' in timestamp or timestamp.startswith('/'):
        return "Invalid path", 400
    file_path = os.path.join(HISTORY_BASE_DIR, timestamp, 'failure_analysis_report.json')
    if os.path.exists(file_path):
        return send_from_directory(os.path.dirname(file_path), os.path.basename(file_path))
    else:
        return "Report not found", 404

@app.route('/chat', methods=['POST'])
def chat():
    if not client:
        return jsonify({"error": "Gemini Client is not configured. Check API key and server logs."}), 500

    data = request.json
    user_question = data.get('question', '')
    session_id = data.get('session_id')
    if not all([user_question, session_id]):
        return jsonify({"error": "Missing user question or session_id"}), 400

    if session_id not in chat_histories:
        print(f"Creating and priming new chat session for ID: {session_id}")
        system_instruction = """
You are an expert QA analyst agent. Your task is to answer user questions about test failure reports by using the provided tools.

**Your thinking process MUST be:**
1.  Analyze the user's question to understand what information is needed.
2.  If you don't know what reports are available, your first step is ALWAYS to call `get_list_of_all_reports()` to see what files exist.
3.  Once you have the list of reports, use `read_data_from_report(timestamp)` or `analyze_failure_trends(days_ago)` to get the content you need.
4.  After gathering all necessary data, synthesize it into a final, helpful answer for the user.

**Example Conversation:**
* User asks: "What's the difference between the two most recent reports?"
* Your internal thought process: The user wants to compare. First, I need to know what reports are available. I must call `get_list_of_all_reports`.
* (You then proceed to call the tool).
"""
        chat_histories[session_id] = [
            types.Content(role='user', parts=[types.Part(text=system_instruction)]),
            types.Content(role='model', parts=[types.Part(text="Understood. I am a QA analyst agent, ready to help. How can I assist with the test reports?")])
        ]
    
    history = chat_histories[session_id]
    history.append(types.Content(role='user', parts=[types.Part(text=user_question)]))

    tools = [get_list_of_all_reports, read_data_from_report, get_reports_in_date_range, analyze_failure_trends]
    
    try:
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=history,
            config=types.GenerateContentConfig(tools=tools),
        )
        
        history.append(response.candidates[0].content)
        return jsonify({"response": response.text})

    except Exception as e:
        print(f"An error occurred during content generation: {e}")
        if history and history[-1].role == 'user':
            history.pop()
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500