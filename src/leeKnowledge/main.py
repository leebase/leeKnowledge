"""
Main entry point for leeKnowledge.

Created on 2026-04-07 by Lee Harrington.
"""

import argparse


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        prog="leeKnowledge",
        description="leeKnowledge - AI-agent project",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    parser.add_argument(
        "name",
        nargs="?",
        default="World",
        help="Name to greet (default: World)",
    )

    args = parser.parse_args()
    print(f"Hello from leeKnowledge, {args.name}!")


if __name__ == "__main__":
    main()
