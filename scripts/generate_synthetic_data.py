"""CLI for reproducible synthetic financial-profile generation."""

import argparse
import json
from pathlib import Path

from scripts.synthetic import generate_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--users", type=int, default=120)
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--output-dir", type=Path, default=Path("data/generated"))
    args = parser.parse_args()
    if args.users < 1 or args.months < 3:
        parser.error("users must be positive and months must be at least 3")
    print(
        json.dumps(generate_dataset(args.seed, args.users, args.months, args.output_dir), indent=2)
    )


if __name__ == "__main__":
    main()
