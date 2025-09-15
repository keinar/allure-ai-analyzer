import os
import json
from concurrent.futures import ProcessPoolExecutor
from typing import List, Dict, Any

def _safe_read_attachment(path: str) -> str:
    """Reads attachment content, ignoring errors."""
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read(20_000) # Read up to 20KB
    except (IOError, OSError):
        return ""

def _collect_all_failures_recursive(node: Dict, results_dir: str) -> List[Dict[str, Any]]:
    """
    Recursively traverses the entire step tree and collects ALL meaningful failure nodes.
    This is the core logic to capture every single failed/broken step.
    """
    all_failures = []

    # 1. Check if the current node itself is a meaningful failure
    if node.get("status") in ["failed", "broken"]:
        details = node.get("statusDetails", {})
        message = details.get("message", "")
        trace = details.get("trace", "")
        status = node.get("status")

        # Enhance with attachment data if details are sparse
        if not trace and 'attachments' in node:
            for att in node.get('attachments', []):
                att_name = att.get('name', '').lower()
                if any(kw in att_name for kw in ['trace', 'stack', 'error', 'console']):
                    trace = _safe_read_attachment(os.path.join(results_dir, att['source']))
                    if not message:
                        message = trace.split('\n')[0]
                    break 

        # A "meaningful" failure must have some content
        if message or trace:
            all_failures.append({
                "step_name": node.get("name", ""),
                "message": message,
                "trace": trace,
                "status": status
            })

    # 2. ALWAYS traverse deeper to find more failures in sub-steps
    for step in node.get("steps", []):
        all_failures.extend(_collect_all_failures_recursive(step, results_dir))
        
    return all_failures

def _process_single_file(path: str) -> List[Dict]:
    """Processes one Allure result file and returns a LIST of all failures found within it."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError):
        return []

    if data.get("status") not in ["failed", "broken"]:
        return []
        
    results_dir = os.path.dirname(path)
    
    # This now returns a list of all failures found in the steps
    failures_from_steps = _collect_all_failures_recursive(data, results_dir)
    
    # If no specific failures were found inside steps, create a single fallback failure
    if not failures_from_steps:
        top_level_details = data.get("statusDetails", {})
        fallback_failure = {
            "step_name": "Top Level Failure",
            "message": top_level_details.get("message", "Test failed without specific step details."),
            "trace": top_level_details.get("trace", ""),
            "status": data.get("status")
        }
        failures_from_steps.append(fallback_failure)

    # Add common test-level data to each failure found in this file
    final_failures = []
    for failure_detail in failures_from_steps:
        final_failures.append({
            "name": data.get("name", "Unknown Test"),
            "fullName": data.get("fullName", ""),
            "labels": data.get("labels", []),
            "_source": os.path.basename(path),
            "status": failure_detail.get("status"),
            "failing_step_name": failure_detail.get("step_name"),
            "message": failure_detail.get("message"),
            "trace": failure_detail.get("trace")
        })
    
    return final_failures

def collect_failures_from_allure(results_dir: str) -> List[Dict]:
    """Collects all individual failure instances from all result files."""
    if not os.path.isdir(results_dir):
        print(f"❌ Error: Directory not found at '{results_dir}'")
        return []

    all_files = [os.path.join(results_dir, f) for f in os.listdir(results_dir) if f.endswith('-result.json')]
    
    if not all_files:
        print(f"🟡 Warning: No '*-result.json' files found.")
        return []

    all_failures_flat_list = []
    # Use max_workers=None to let the library choose the optimal number of processes
    with ProcessPoolExecutor(max_workers=None) as executor:
        future_to_file = {executor.submit(_process_single_file, file_path): file_path for file_path in all_files}
        for future in future_to_file:
            # Each future returns a LIST of failures for one file
            failures_in_file = future.result()
            if failures_in_file:
                all_failures_flat_list.extend(failures_in_file)
    
    return all_failures_flat_list