import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Export interview questions from a script folder under interview_script/ into a CSV. "
            "Scans module*.json files and outputs columns: fields, content, type, requirement, max_sec."
        )
    )
    parser.add_argument(
        "folder",
        help=(
            "Name or path of the interview script folder (e.g., 'minwage_script_v2'). "
            "If a relative name is provided, it is resolved under interviewer_agent/interview_script/."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Output CSV file path. Defaults to interviewer_agent/interview_script/csvs/<folder>/<folder>_questions.csv if not provided."
        ),
    )
    return parser.parse_args()


def resolve_folder_path(folder_arg: str) -> Path:
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir / "interview_script"
    candidate = Path(folder_arg)
    if candidate.is_absolute():
        return candidate
    # Try as a direct child of interview_script/
    return (base_dir / folder_arg).resolve()


def _extract_module_number(path: Path) -> int:
    stem = path.stem  # e.g., 'module12'
    digits = "".join(ch for ch in stem if ch.isdigit())
    try:
        return int(digits)
    except ValueError:
        return 0


def find_module_files(folder_path: Path) -> List[Path]:
    files = list(folder_path.glob("module*.json"))
    return sorted(files, key=lambda p: (_extract_module_number(p), p.name))


def sorted_question_items(module_data: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    def key_func(item: Tuple[str, Any]) -> Tuple[int, str]:
        qid, _ = item
        # Extract numeric portion if present (e.g., 'q12' -> 12) for stable ordering
        num = 0
        try:
            num = int("".join(ch for ch in qid if ch.isdigit()))
        except ValueError:
            num = 0
        return (num, qid)

    return sorted(module_data.items(), key=key_func)


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_output_path(folder_path: Path, output_arg: str | None) -> Path:
    if output_arg:
        out_path = Path(output_arg)
        if out_path.is_dir():
            return (out_path / f"{folder_path.name}_questions.csv").resolve()
        return out_path.resolve()
    # Default to interviewer_agent/interview_script/csvs/<folder>/<folder>_questions.csv
    script_dir = Path(__file__).resolve().parent
    default_dir = script_dir / "interview_script" / "csvs" / folder_path.name
    return (default_dir / f"{folder_path.name}_questions.csv").resolve()


def export_questions(folder: Path, output_csv: Path) -> None:
    module_files = find_module_files(folder)
    if not module_files:
        raise FileNotFoundError(
            f"No module*.json files found in folder: {folder}"
        )

    fieldnames = ["module", "fields", "content", "type", "requirement", "max_sec"]
    rows: List[Dict[str, Any]] = []

    for module_file in module_files:
        module_num = _extract_module_number(module_file)
        data = read_json(module_file)
        for _, q in sorted_question_items(data):
            # Gracefully handle missing keys by defaulting to empty string or 0
            if q.get("type") == "non-question":
                continue
            rows.append(
                {
                    "module": module_num,
                    "fields": q.get("fields", ""),
                    "content": q.get("content", ""),
                    "type": q.get("type", ""),
                    "requirement": q.get("requirement", ""),
                    "max_sec": q.get("max_sec", 0),
                }
            )

    # Ensure parent directory exists
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    folder_path = resolve_folder_path(args.folder)
    if not folder_path.exists() or not folder_path.is_dir():
        raise NotADirectoryError(
            f"Provided folder is not a directory: {folder_path}"
        )

    output_csv = ensure_output_path(folder_path, args.output)
    export_questions(folder_path, output_csv)
    print(str(output_csv))


if __name__ == "__main__":
    main()


