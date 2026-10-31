"""Dispatch B0->B1 Teacher generation to a static client-specific module."""

from __future__ import annotations

import argparse
import runpy
import sys


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    args, remainder = parser.parse_known_args()
    sys.argv = [sys.argv[0], *remainder]
    runpy.run_module(
        f"stage2_local_v12.evolution.bootstrap_bank_{args.client.lower()}",
        run_name="__main__",
    )


if __name__ == "__main__":
    main()
