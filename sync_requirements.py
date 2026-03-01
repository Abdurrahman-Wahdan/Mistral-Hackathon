#!/usr/bin/env python3
"""Sync wizard requirements with actually imported third-party libraries.

Workflow:
1) Parse Python imports from project files.
2) Read current requirements entries.
3) Resolve each requirement to installed distribution metadata.
4) Keep only requirements whose top-level modules are imported.
5) Pin kept requirements to exact installed versions using `pip freeze`.
6) Optionally add newly detected imported packages (`--include-new`).
"""

from __future__ import annotations

import argparse
import ast
import importlib.metadata as md
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "tests",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "logs",
}


def canonicalize(name: str) -> str:
    return "".join("-" if c in "_." else c.lower() for c in name).replace("--", "-")


@dataclass
class RequirementEntry:
    raw: str
    name: str


def parse_requirement_name(line: str) -> str | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    for marker in (" #", "\t#"):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
    if text.startswith(("-r", "--")):
        return None

    first = text.split(";", 1)[0].strip()
    if "[" in first:
        first = first.split("[", 1)[0]

    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "@"):
        if sep in first:
            first = first.split(sep, 1)[0].strip()
            break

    first = first.strip()
    return first or None


def load_requirements(path: Path) -> list[RequirementEntry]:
    entries: list[RequirementEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = parse_requirement_name(line)
        if name:
            entries.append(RequirementEntry(raw=line, name=name))
    return entries


def iter_python_files(project_root: Path) -> Iterable[Path]:
    for path in project_root.rglob("*.py"):
        parts = set(path.parts)
        if parts.intersection(SKIP_DIRS):
            continue
        yield path


def collect_imported_modules(project_root: Path) -> set[str]:
    imports: set[str] = set()

    for py_file in iter_python_files(project_root):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".", 1)[0])

    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    stdlib.update(sys.builtin_module_names)
    return {m for m in imports if m and m not in stdlib}


def get_freeze_map() -> dict[str, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=True,
        capture_output=True,
        text=True,
    )

    freeze_map: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue

        if " @ " in text:
            pkg = text.split(" @ ", 1)[0].strip()
        elif "==" in text:
            pkg = text.split("==", 1)[0].strip()
        else:
            continue

        if pkg:
            freeze_map[canonicalize(pkg)] = text

    return freeze_map


def get_installed_distributions() -> dict[str, md.Distribution]:
    dists: dict[str, md.Distribution] = {}
    for dist in md.distributions():
        name = dist.metadata.get("Name")
        if name:
            dists[canonicalize(name)] = dist
    return dists


def get_package_to_distributions() -> dict[str, list[str]]:
    raw = md.packages_distributions()
    return {pkg: sorted(set(dists)) for pkg, dists in raw.items()}


def dist_top_levels(dist: md.Distribution) -> set[str]:
    top = dist.read_text("top_level.txt")
    if top:
        return {line.strip() for line in top.splitlines() if line.strip()}

    name = dist.metadata.get("Name", "")
    fallback = name.replace("-", "_").replace(".", "_").strip()
    return {fallback} if fallback else set()


def sync_requirements(
    project_root: Path,
    requirements_path: Path,
    output_path: Path | None,
    force: bool,
    include_new: bool,
) -> int:
    imported_modules = collect_imported_modules(project_root)
    requirements = load_requirements(requirements_path)
    freeze_map = get_freeze_map()
    installed = get_installed_distributions()
    package_to_distributions = get_package_to_distributions()

    kept: list[str] = []
    added: list[str] = []
    removed: list[str] = []
    missing_installed: list[str] = []
    unresolved_imports: list[str] = []
    included_canons: set[str] = set()

    for req in requirements:
        canon = canonicalize(req.name)
        dist = installed.get(canon)
        if not dist:
            missing_installed.append(req.name)
            continue

        tops = dist_top_levels(dist)
        if imported_modules.isdisjoint(tops):
            removed.append(req.name)
            continue

        pinned = freeze_map.get(canon)
        if pinned:
            kept.append(pinned)
        else:
            pinned_name = dist.metadata.get("Name", req.name)
            kept.append(f"{pinned_name}=={dist.version}")
        included_canons.add(canon)

    if include_new:
        for module in sorted(imported_modules):
            dist_names = package_to_distributions.get(module, [])
            if not dist_names:
                unresolved_imports.append(module)
                continue

            for dist_name in dist_names:
                canon = canonicalize(dist_name)
                if canon in included_canons:
                    continue
                dist = installed.get(canon)
                if not dist:
                    continue
                pinned = freeze_map.get(canon)
                if pinned:
                    added.append(pinned)
                else:
                    pinned_name = dist.metadata.get("Name", dist_name)
                    added.append(f"{pinned_name}=={dist.version}")
                included_canons.add(canon)
                break

    out_lines = sorted(set(kept + added), key=str.lower)
    if requirements and not out_lines and not force:
        print(
            "Refusing to write empty requirements. "
            "Likely wrong Python environment is active.",
            file=sys.stderr,
        )
        print(
            "Activate the wizard virtualenv and rerun, or pass --force.",
            file=sys.stderr,
        )
        return 2

    target = output_path or requirements_path
    target.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    print("Imported third-party modules found:")
    print(", ".join(sorted(imported_modules)) if imported_modules else "(none)")
    print()

    print(f"Updated: {target}")
    print(f"Kept ({len(out_lines)}): {', '.join(out_lines) if out_lines else '(none)'}")
    if include_new:
        print(f"Added ({len(set(added))}): {', '.join(sorted(set(added))) if added else '(none)'}")
    print(f"Removed ({len(removed)}): {', '.join(sorted(set(removed))) if removed else '(none)'}")
    if missing_installed:
        print(
            "Missing from current environment "
            f"({len(missing_installed)}): {', '.join(sorted(set(missing_installed)))}"
        )
    if include_new and unresolved_imports:
        print(
            "Could not map imports to installed distributions "
            f"({len(unresolved_imports)}): {', '.join(sorted(set(unresolved_imports)))}"
        )

    return 0


def main() -> int:
    default_project_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Filter requirements.txt to only imported libraries and pin exact versions"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=default_project_root,
        help=f"Project root (default: {default_project_root})",
    )
    parser.add_argument(
        "--requirements",
        type=Path,
        default=default_project_root / "requirements.txt",
        help="Path to requirements.txt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path (default: overwrite --requirements)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow writing even if the resulting requirements list is empty",
    )
    parser.add_argument(
        "--include-new",
        action="store_true",
        help="Also add installed distributions inferred from imported modules",
    )
    args = parser.parse_args()

    return sync_requirements(
        project_root=args.project_root.resolve(),
        requirements_path=args.requirements.resolve(),
        output_path=args.output.resolve() if args.output else None,
        force=args.force,
        include_new=args.include_new,
    )


if __name__ == "__main__":
    raise SystemExit(main())
