import os
from pathlib import Path
from typing import Dict, List, Tuple
import yaml
import importlib.resources
import argparse

from .ingestion import collect_failures_from_allure
from .fingerprinter import Fingerprinter
from .reporting import generate_report_json

def _load_config(user_config_path: str = None) -> Dict:
    """
    Loads default config from within the package and merges a user's 
    config file over it if provided.
    """
    try:
        # Load default config bundled with the package
        default_config_text = importlib.resources.read_text('allure_analyzer.config', 'default_config.yaml')
        config = yaml.safe_load(default_config_text) or {}
    except Exception:
        print("⚠️ WARNING: Default config not found. Using empty config.")
        config = {}

    # If a user config path is provided, load it and merge its settings
    if user_config_path and os.path.exists(user_config_path):
        print(f"Loading user-defined config from: {user_config_path}")
        try:
            with open(user_config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}
                # The update() method merges the user's settings, overwriting defaults
                config.update(user_config)
        except Exception as e:
            print(f"❌ Error loading user config file: {e}. Proceeding with defaults.")
    
    return config

def run_analysis(allure_results_path: str, cli_args: argparse.Namespace):
    """
    The main analysis function. It orchestrates the entire process of
    ingestion, fingerprinting, and reporting, considering CLI overrides.
    """
    config = _load_config(cli_args.config)

    # --- Prioritize CLI arguments over config files ---
    if cli_args.top_n is not None:
        config['top_n_groups_to_report'] = cli_args.top_n
    
    if cli_args.exclude_broken:
        config['include_broken'] = False
    # ---------------------------------------------------
    
    print(f"Scanning Allure results in: {allure_results_path}")
    all_failures = collect_failures_from_allure(allure_results_path)
    
    if not all_failures:
        print("No failures found to analyze. Exiting.")
        return

    print(f"Found {len(all_failures)} individual failure steps.")

    # Filter out broken tests if configured to do so
    if not config.get('include_broken', True):
        print("Filtering out 'broken' status tests based on configuration.")
        failures = [f for f in all_failures if f.get('status', '').lower() != 'broken']
    else:
        failures = all_failures
    
    if not failures:
        print("No 'failed' tests found after filtering. Exiting.")
        return

    print("Fingerprinting and grouping failures...")
    fp = Fingerprinter()
    groups: Dict[str, List[Dict]] = {}
    for failure in failures:
        key = fp.create_fingerprint(failure)
        groups.setdefault(key, []).append(failure)

    sorted_groups = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)
    
    top_n = config.get('top_n_groups_to_report', -1)
    if top_n and top_n > 0:
        print(f"Selecting top {top_n} failure groups for the report.")
        groups_to_report = sorted_groups[:top_n]
    else:
        print("Including all failure groups in the report.")
        groups_to_report = sorted_groups

    # Define the centralized history path in the user's home directory
    home_dir = Path.home()
    history_base_dir = home_dir / ".allure-analyzer" / "reports_history"
    history_base_dir.mkdir(parents=True, exist_ok=True)
    
    # Pass all necessary data to the reporting function
    generate_report_json(
        sorted_groups=groups_to_report, 
        history_base_dir=history_base_dir
    )