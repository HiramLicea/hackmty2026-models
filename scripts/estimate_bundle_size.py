"""Estimate source, artifact, and installed runtime dependency footprint."""

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

RUNTIME_DISTRIBUTIONS = (
    "fastapi",
    "joblib",
    "numpy",
    "pydantic",
    "pydantic-settings",
    "scikit-learn",
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


def dependency_closure_size(names: tuple[str, ...]) -> int:
    """Sum unique installed files for runtime dependencies and their requirements."""
    pending = list(names)
    visited: set[str] = set()
    files: set[Path] = set()
    while pending:
        name = pending.pop()
        canonical_name = canonicalize_name(name)
        if canonical_name in visited:
            continue
        visited.add(canonical_name)
        try:
            package = distribution(name)
        except PackageNotFoundError:
            continue
        for file in package.files or []:
            located = Path(file.locate()).resolve()
            if located.is_file():
                files.add(located)
        for requirement_text in package.requires or []:
            requirement = Requirement(requirement_text)
            if requirement.marker is None or requirement.marker.evaluate():
                pending.append(requirement.name)
    return sum(file.stat().st_size for file in files)


def mib(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MiB"


def main() -> None:
    source = directory_size(Path("app"), {".py"})
    artifacts = directory_size(Path("artifacts"))
    vercel_config = Path("vercel.json")
    json_config = vercel_config.stat().st_size if vercel_config.is_file() else 0
    dependencies = dependency_closure_size(RUNTIME_DISTRIBUTIONS)
    estimated = source + artifacts + json_config + dependencies
    print(f"application code: {mib(source)}")
    print(f"artifact directory: {mib(artifacts)}")
    print(f"JSON configuration outside artifacts: {mib(max(json_config, 0))}")
    print(f"runtime dependency closure: {mib(dependencies)}")
    print(f"uncompressed application estimate: {mib(estimated)}")
    print("Note: Vercel's final bundle also includes platform runtime files.")


if __name__ == "__main__":
    main()
