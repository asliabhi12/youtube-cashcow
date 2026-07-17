#!/usr/bin/env python3
"""YouTube CashCow root entry point.

Loads environment variables and executes the Typer CLI interface.
"""

from dotenv import load_dotenv

# Load configuration environment variables from .env file
load_dotenv()

if __name__ == "__main__":
    from src.cli import app
    # Invoke the Typer CLI application
    app()
