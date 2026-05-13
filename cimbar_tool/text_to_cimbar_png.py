"""Batch encode text files into cimbar PNG frames.

This script is a small Windows-friendly wrapper around the libcimbar command
line encoder. Install or build libcimbar separately, then point this script at
the resulting ``cimbar.exe``.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_EXTENSIONS = (
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".jsonl",
    ".xml",
    ".html",
    ".htm",
    ".log",
    ".ini",
    ".cfg",
    ".yaml",
    ".yml",
)


@dataclass(frozen=True)
class EncodeResult:
    source: Path
    output_prefix: Path
    png_files: list[Path]
    skipped: bool = False


def normalize_extensions(raw_extensions: str | None) -> set[str]:
    if not raw_extensions:
        return set(DEFAULT_EXTENSIONS)

    extensions: set[str] = set()
    for raw_extension in raw_extensions.split(","):
        extension = raw_extension.strip().lower()
        if not extension:
            continue
        if not extension.startswith("."):
            extension = f".{extension}"
        extensions.add(extension)

    if not extensions:
        raise ValueError("At least one text extension must be provided.")
    return extensions


def iter_text_files(src_dir: Path, extensions: set[str], recursive: bool) -> Iterable[Path]:
    pattern = "**/*" if recursive else "*"
    for path in sorted(src_dir.glob(pattern)):
        if path.is_file() and path.suffix.lower() in extensions:
            yield path


def safe_path_part(value: str) -> str:
    safe_chars = []
    for char in value:
        if char.isalnum() or char in ("-", "_", "."):
            safe_chars.append(char)
        else:
            safe_chars.append("_")
    safe_value = "".join(safe_chars).strip("._")
    return safe_value or "file"


def output_prefix_for(source: Path, src_dir: Path, output_dir: Path) -> Path:
    relative = source.relative_to(src_dir)
    safe_parent_parts = [safe_path_part(part) for part in relative.parent.parts]
    output_parent = output_dir.joinpath(*safe_parent_parts)
    source_folder = f"{safe_path_part(source.stem)}_{safe_path_part(source.suffix.lstrip('.'))}"
    return output_parent / source_folder / safe_path_part(source.stem)


def local_binary_candidates(script_dir: Path) -> list[Path]:
    return [
        script_dir / "bin" / "cimbar.exe",
        script_dir / "bin" / "cimbar",
        script_dir / "cimbar.exe",
        script_dir / "cimbar",
    ]


def resolve_cimbar_binary(binary_arg: str | None, script_dir: Path) -> Path:
    requested = binary_arg or os.environ.get("CIMBAR_BIN")
    if requested:
        requested_path = Path(requested).expanduser()
        if requested_path.is_dir():
            names = ("cimbar.exe", "cimbar")
            for name in names:
                candidate = requested_path / name
                if candidate.is_file():
                    return candidate
        if requested_path.is_file():
            return requested_path
        found = shutil.which(requested)
        if found:
            return Path(found)
        raise FileNotFoundError(f"Cannot find cimbar executable: {requested}")

    for candidate in local_binary_candidates(script_dir):
        if candidate.is_file():
            return candidate

    for command in ("cimbar.exe", "cimbar"):
        found = shutil.which(command)
        if found:
            return Path(found)

    raise FileNotFoundError(
        "Cannot find cimbar executable. Pass --cimbar-bin, set CIMBAR_BIN, "
        "put cimbar.exe in cimbar_tool\\bin, or add it to PATH."
    )


def existing_pngs(prefix: Path) -> list[Path]:
    return sorted(prefix.parent.glob(f"{prefix.name}*.png"))


def encode_one(
    cimbar_binary: Path,
    source: Path,
    output_prefix: Path,
    overwrite: bool,
    dry_run: bool,
) -> EncodeResult:
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    current_pngs = existing_pngs(output_prefix)

    if current_pngs and not overwrite:
        return EncodeResult(source=source, output_prefix=output_prefix, png_files=current_pngs, skipped=True)

    if overwrite:
        for png_file in current_pngs:
            png_file.unlink()

    command = [str(cimbar_binary), "--encode", "-i", str(source), "-o", str(output_prefix)]
    if dry_run:
        print("DRY RUN:", subprocess.list2cmdline(command))
        return EncodeResult(source=source, output_prefix=output_prefix, png_files=[])

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        message = [
            f"cimbar failed for {source}",
            f"command: {subprocess.list2cmdline(command)}",
            f"exit code: {completed.returncode}",
        ]
        if completed.stdout:
            message.append(f"stdout:\n{completed.stdout.strip()}")
        if completed.stderr:
            message.append(f"stderr:\n{completed.stderr.strip()}")
        raise RuntimeError("\n".join(message))

    return EncodeResult(source=source, output_prefix=output_prefix, png_files=existing_pngs(output_prefix))


def write_manifest(output_dir: Path, results: Sequence[EncodeResult]) -> None:
    manifest = {
        "generated_by": "cimbar_tool/text_to_cimbar_png.py",
        "items": [
            {
                "source": str(result.source),
                "output_prefix": str(result.output_prefix),
                "png_files": [str(path) for path in result.png_files],
                "skipped": result.skipped,
            }
            for result in results
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Encode text files under a directory into cimbar PNG frames.",
    )
    parser.add_argument("src_dir", help="Directory containing text files.")
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Output directory. Defaults to <src_dir>/export_cimbar.",
    )
    parser.add_argument(
        "--cimbar-bin",
        help="Path to cimbar.exe/cimbar, or to a directory containing it. Defaults to CIMBAR_BIN, local bin, then PATH.",
    )
    parser.add_argument(
        "--extensions",
        help="Comma-separated text file extensions. Defaults to common text extensions.",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Scan src_dir recursively.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate PNG files when matching output already exists.",
    )
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue processing other files after an encode error.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cimbar commands without running them.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    script_dir = Path(__file__).resolve().parent

    try:
        src_dir = Path(args.src_dir).expanduser().resolve()
        if not src_dir.is_dir():
            raise NotADirectoryError(f"Source directory does not exist: {src_dir}")

        extensions = normalize_extensions(args.extensions)
        output_dir = (
            Path(args.output_dir).expanduser().resolve()
            if args.output_dir
            else (src_dir / "export_cimbar").resolve()
        )
        cimbar_binary = resolve_cimbar_binary(args.cimbar_bin, script_dir)

        sources = list(iter_text_files(src_dir, extensions, args.recursive))
        if not sources:
            print(f"No text files found in {src_dir}")
            return 0

        results: list[EncodeResult] = []
        failures = 0
        print(f"Using cimbar executable: {cimbar_binary}")
        print(f"Found {len(sources)} text file(s). Output: {output_dir}")

        for index, source in enumerate(sources, start=1):
            output_prefix = output_prefix_for(source, src_dir, output_dir)
            try:
                result = encode_one(
                    cimbar_binary=cimbar_binary,
                    source=source,
                    output_prefix=output_prefix,
                    overwrite=args.overwrite,
                    dry_run=args.dry_run,
                )
            except Exception as exc:  # noqa: BLE001 - show clear batch failure and optionally continue.
                failures += 1
                print(f"[{index}/{len(sources)}] ERROR {source}: {exc}", file=sys.stderr)
                if not args.keep_going:
                    return 1
                continue

            results.append(result)
            action = "SKIP" if result.skipped else "OK"
            print(f"[{index}/{len(sources)}] {action} {source} -> {output_prefix} ({len(result.png_files)} png)")

        if not args.dry_run:
            write_manifest(output_dir, results)

        if failures:
            print(f"Finished with {failures} failure(s).", file=sys.stderr)
            return 1
        print("Finished successfully.")
        return 0
    except Exception as exc:  # noqa: BLE001 - command line entry point.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
