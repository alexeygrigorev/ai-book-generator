#!/usr/bin/env python3
"""
AI Book Generator - Main Entry Point

Launches the Streamlit web interface for the AI Book Generator.
"""

import sys
from pathlib import Path


def main():
    """Launch the Streamlit app."""
    ui_app_path = Path(__file__).parent / "ui" / "streamlit_app.py"

    if not ui_app_path.exists():
        print(f"Error: Streamlit app not found at {ui_app_path}")
        sys.exit(1)

    # Update sys.argv to tell Streamlit which script to run
    sys.argv = ["streamlit", "run", str(ui_app_path)]

    # Import and run Streamlit CLI
    from streamlit.web import cli as stcli

    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
