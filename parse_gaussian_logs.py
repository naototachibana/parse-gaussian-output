#!/usr/bin/env python3
"""Batch parser for Gaussian log files, inspired by parse_logs_sample.py."""

from __future__ import annotations

import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from cclib.io import ccread
from tqdm import tqdm

DEFAULT_INPUT_DIR = Path("./out_molecules/cid_75")
DEFAULT_PATTERN = "*.log"
EV_PER_HARTREE = 27.211386245988


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse Gaussian log files using cclib and aggregate the results."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default=DEFAULT_INPUT_DIR,
        type=Path,
        help=f"Directory containing Gaussian log files (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        default=DEFAULT_PATTERN,
        help=f"Glob pattern for log files (default: {DEFAULT_PATTERN})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Destination JSON file. Defaults to out_molecules_json/out_molecules.json",
    )
    parser.add_argument(
        "--separate",
        action="store_true",
        help="Create separate JSON file for each log file instead of aggregating into one file",
    )
    return parser


def safe_get(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default) if hasattr(obj, name) else default


def to_python(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value


def to_serializable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "tolist"):
        return to_serializable(value.tolist())
    if isinstance(value, dict):
        return {k: to_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_serializable(v) for v in value]
    # numpy scalar types
    try:
        import numpy as np  # type: ignore

        if isinstance(value, np.generic):
            return value.item()
    except ModuleNotFoundError:
        pass
    return str(value)


def parse_single_log(path: Path) -> Dict[str, Any]:
    record: Dict[str, Any] = {"file": path.name}
    try:
        data = ccread(str(path))
    except Exception as exc:
        logging.error(f"[Gaussian {path} ERROR] Encountered error when parsing: {str(exc)}")
        record["error"] = str(exc)
        return record

    if data is None:
        logging.error(f"[Gaussian {path} ERROR] cclib failed to parse the file.")
        record["error"] = "cclib failed to parse the file."
        return record

    scfenergies = safe_get(data, "scfenergies")
    scfenergies_au = (
        [float(e) / EV_PER_HARTREE for e in scfenergies] if scfenergies is not None else None
    )

    dipole_vectors = safe_get(data, "moments")
    dipole_vector = dipole_vectors[1] if dipole_vectors and len(dipole_vectors) > 1 else None
    dipole_moment = None
    if dipole_vector is not None:
        dipole_moment = {
            "x": float(dipole_vector[0]),
            "y": float(dipole_vector[1]),
            "z": float(dipole_vector[2]),
            "total": float(
                (dipole_vector[0] ** 2 + dipole_vector[1] ** 2 + dipole_vector[2] ** 2) ** 0.5
            ),
        }

    mulliken = safe_get(data, "mulliken_charges")
    atomcoords = safe_get(data, "atomcoords")

    record.update(
        {
            "metadata": safe_get(data, "metadata") or {},
            "charge": float(safe_get(data, "charge"))
            if safe_get(data, "charge") is not None
            else None,
            "multiplicity": int(safe_get(data, "mult"))
            if safe_get(data, "mult") is not None
            else None,
            "nbasis": int(safe_get(data, "nbasis"))
            if safe_get(data, "nbasis") is not None
            else None,
            "natoms": int(atomcoords[-1].shape[0]) if atomcoords is not None else None,
            "scf_energies_au": scfenergies_au,
            "final_scf_energy_au": scfenergies_au[-1] if scfenergies_au else None,
            "vibrations": {
                "frequencies_cm-1": to_python(safe_get(data, "vibfreqs")),
                "ir_intensities_km/mol": to_python(safe_get(data, "vibirs")),
                "force_constants_mDyneA": to_python(safe_get(data, "vibfconsts")),
                "reduced_masses_amu": to_python(safe_get(data, "vibredmass")),
            },
            "dipole_moment_debye": dipole_moment,
            "mulliken_charges": [float(x) for x in mulliken[-1]]
            if mulliken is not None
            else None,
            "zpe_au": float(safe_get(data, "zpve")) if safe_get(data, "zpve") is not None else None,
            "atom_numbers": to_python(safe_get(data, "atomnos")),
            "final_geometry_angstrom": to_python(atomcoords[-1]) if atomcoords is not None else None,
        }
    )
    return record


def discover_files(directory: Path, pattern: str) -> List[Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Input directory does not exist: {directory}")
    if not directory.is_dir():
        raise NotADirectoryError(f"Input path is not a directory: {directory}")
    return sorted(directory.glob(pattern))


def determine_output_path(directory: Path, output_arg: Optional[Path]) -> Path:
    if output_arg is not None:
        return output_arg
    output_dir = Path.cwd() / "out_molecules_json"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / "out_molecules.json"


def parse_directory(directory: Path, pattern: str) -> List[Dict[str, Any]]:
    files = discover_files(directory, pattern)
    if not files:
        print(f"No files matched '{pattern}' in {directory}")
        return []
    records: List[Dict[str, Any]] = []
    for path in tqdm(files, desc="Processing log files", unit="file"):
        records.append(parse_single_log(path))
    return records


def normalize_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for record in records:
        normalized.append({key: to_serializable(value) for key, value in record.items()})
    return normalized


def send_discord_notification(message: str) -> None:
    discord_url = os.getenv('DISCORD_URL')
    if not discord_url:
        logging.info("DISCORD_URL not set, skipping notification")
        return
    try:
        import requests  # type: ignore
        payload = {"content": message}
        response = requests.post(discord_url, json=payload)
        if response.status_code == 204:
            logging.info("Discord notification sent successfully")
        else:
            logging.error(f"Failed to send Discord notification: {response.status_code}")
    except ImportError:
        logging.warning("requests not installed, skipping Discord notification")
    except Exception as e:
        logging.error(f"Failed to send Discord notification: {e}")


def main() -> None:
    # Set up logging with separate files for INFO and ERROR+
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Set to lowest level

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # INFO handler
    info_handler = logging.FileHandler('parsing_info.log')
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    logger.addHandler(info_handler)

    # ERROR handler
    error_handler = logging.FileHandler('parsing_errors.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)

    parser = build_argument_parser()
    args = parser.parse_args()

    input_dir = args.input_dir.expanduser().resolve()

    logging.info(f"Starting parsing process for directory: {input_dir}")

    files = discover_files(input_dir, args.pattern)
    if not files:
        logging.warning(f"No files matched '{args.pattern}' in {input_dir}")
        print(f"No files matched '{args.pattern}' in {input_dir}")
        return

    logging.info(f"Found {len(files)} files to process")

    if args.separate:
        output_dir = Path.cwd() / "out_molecules_json"
        output_dir.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(parse_single_log, path): path for path in files}
            for future in tqdm(as_completed(futures), total=len(files), desc="Processing log files", unit="file"):
                path = futures[future]
                record = future.result()
                normalized = {key: to_serializable(value) for key, value in record.items()}
                output_file = output_dir / f"{path.stem}.cclib.json"
                output_file.write_text(json.dumps(normalized, indent=2, ensure_ascii=False))
    else:
        output_path = determine_output_path(input_dir, args.output)
        records = []
        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(parse_single_log, path): path for path in files}
            for future in tqdm(as_completed(futures), total=len(files), desc="Processing log files", unit="file"):
                records.append(future.result())
        normalized = normalize_records(records)
        output_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False))
        print(f"Wrote {len(normalized)} records to {output_path}")

    logging.info(f"Parsing completed successfully. Processed {len(files)} files.")
    send_discord_notification(f"Gaussian log parsing completed. Processed {len(files)} files in {input_dir}.")


if __name__ == "__main__":
    main()
