from collections import Counter
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple
import datetime as dt

def generate_report_json(sorted_groups: List[Tuple[str, List[Dict]]], history_base_dir: Path):
    """
    Generates the final JSON report data and saves it to a new, timestamped
    directory within the centralized history folder.
    """
    
    # Create a timestamped directory for the current report
    timestamp = dt.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    report_dir = history_base_dir / timestamp
    os.makedirs(report_dir, exist_ok=True)
    
    json_path = report_dir / 'failure_analysis_report.json'

    total_failures = sum(len(group) for _, group in sorted_groups)

    report_data = {
        "metadata": {
            "generation_date": dt.datetime.now().isoformat(),
            "total_failures": total_failures,
            "unique_groups": len(sorted_groups),
        },
        "groups": []
    }

    for i, (fingerprint, items) in enumerate(sorted_groups, 1):
        norm_message, code_loc = fingerprint.split('|', 1) if '|' in fingerprint else (fingerprint, '')
        example = items[0]

        epics = sorted(list({
            label['value']
            for item in items
            for label in item.get('labels', [])
            if label.get('name') == 'epic' and 'value' in label
        }))
        features = sorted(list({
            label['value']
            for item in items
            for label in item.get('labels', [])
            if label.get('name') == 'feature' and 'value' in label
        }))

        ctr = Counter((item.get('status') or '').lower() for item in items)
        failed_count = int(ctr.get('failed', 0))
        broken_count = int(ctr.get('broken', 0))

        group_size = len(items)
        
        group_obj = {
            "id": i,
            "title": norm_message,
            "count": group_size,
            "failure_count": group_size, # For backward compatibility with some UIs
            "status_counts": {
                "failed": failed_count,
                "broken": broken_count,
            },
            "fingerprint_what": norm_message,
            "fingerprint_where": code_loc,
            "epics": epics,
            "features": features,
            "example": {
                "test_name": example.get('fullName') or example.get('name'),
                "message": example.get('message', '(No message)'),
                "trace": example.get('trace', '(No trace)'),
            }
        }
        report_data["groups"].append(group_obj)

    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Report data successfully generated at: {json_path}")
    except IOError as e:
        print(f"❌ Error writing report file: {e}")