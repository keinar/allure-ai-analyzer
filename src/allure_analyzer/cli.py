import argparse
import os
import sys
import webbrowser
from .server import app, initialize_config

def main():
    parser = argparse.ArgumentParser(
        description="Allure AI Failure Analyzer: An intelligent CLI to analyze Allure reports with AI."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    # --- Generate Command ---
    generate_parser = subparsers.add_parser(
        "generate", 
        help="Analyze Allure results and generate a new report into the central history folder."
    )
    generate_parser.add_argument(
        "--path",
        type=str,
        default="./allure-results",
        help="Path to the Allure results directory. Defaults to './allure-results'."
    )
    generate_parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to a custom 'allure-analyzer-config.yaml' file to override default settings."
    )
    generate_parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Override the number of top failure groups to report."
    )
    generate_parser.add_argument(
        "--exclude-broken",
        action="store_true",
        help="Flag to exclude tests with 'broken' status from the analysis."
    )

    # --- View Command ---
    view_parser = subparsers.add_parser(
        "view", 
        help="Launch the web server to view all generated reports."
    )
    view_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the web server on. Defaults to 8000."
    )
    view_parser.add_argument(
        "--no-proactive-summary",
        action="store_true",
        help="Flag to disable the automatic AI executive summary on load."
    )

    args = parser.parse_args()

    # Import analysis runner here to avoid circular dependencies
    from .analyzer.core import run_analysis
    
    if args.command == "generate":
        print("Starting analysis...")
        allure_path = os.path.abspath(args.path)
        if not os.path.isdir(allure_path):
            print(f"❌ Error: Allure results directory not found at '{allure_path}'")
            sys.exit(1)
        
        # Pass all parsed CLI arguments to the analysis runner
        run_analysis(allure_results_path=allure_path, cli_args=args)
        print("\n✅ Analysis complete.")
        print("To view the dashboard, run: allure-analyze view")

    elif args.command == "view":
        print("Starting the Allure AI Analyzer web server...")
        
        # Prepare overrides for the server based on CLI flags
        cli_overrides = {
            # If --no-proactive-summary is passed, this will be False. Otherwise, it will be True.
            "proactive_summary_on_load": not args.no_proactive_summary
        }
        
        initialize_config(cli_overrides)
        
        url = f"http://localhost:{args.port}"
        print(f"✅ Server is running. View the dashboard at: {url}")
        
        try:
            webbrowser.open_new_tab(url)
            app.run(host='127.0.0.1', port=args.port, debug=False)
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()