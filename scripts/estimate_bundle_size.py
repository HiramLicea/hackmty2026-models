"""Estimate source, artifact, and installed runtime dependency footprint."""

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

RUNTIME_DISTRIBUTIONS = (
    "fastapi",
    "joblib",
    "numpy",
    "pandas",
    "pydantic",
    "pydantic-settings",
    "scikit-learn",
    "statsmodels",
    "supabase",
    "uvicorn",
)


def directory_size(path: Path, suffixes: set[str] | None = None) -> int:
    if not path.exists():
        return 0
    return sum(
        file.stat().st_size
        for file in path.rglob("*")
        if file.is_file() and (suffixes is None or file.suffix in suffixes)
    )


def distribution_size(name: str) -> int:
    try:
        package = distribution(name)
    except PackageNotFoundError:
        return 0
    return sum(
        Path(file.locate()).stat().st_size
        for file in package.files or []
        if Path(file.locate()).is_file()
    )


def mib(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MiB"


def main() -> None:
    source = directory_size(Path("app"))
    artifacts = directory_size(Path("artifacts"))
    json_config = directory_size(Path("."), {".json"}) - artifacts
    dependencies = sum(distribution_size(name) for name in RUNTIME_DISTRIBUTIONS)
    estimated = source + artifacts + json_config + dependencies
    print(f"application code: {mib(source)}")
    print(f"artifact directory: {mib(artifacts)}")
    print(f"JSON configuration outside artifacts: {mib(max(json_config, 0))}")
    print(f"direct runtime distributions: {mib(dependencies)}")
    print(f"partial uncompressed estimate: {mib(estimated)}")
    print("Note: Vercel's final bundle also includes transitive dependencies and runtime files.")


if __name__ == "__main__":
    main()
