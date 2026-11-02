from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import pandas as pd

# ==========================================
# CONFIGURATION
# ==========================================

LIBRARY_ROOT = Path(r"C:\Users\Austin.Kimuhu\OneDrive\Desktop\Books\Maths")
OUTPUT_CSV = Path("data/processed_metadata/file_hashes.csv")

CHUNK_SIZE = 1024 * 1024
MAX_WORKERS = 4

# If True, OneDrive cloud-only files are never read (so never downloaded),
# which means duplicates among them go undetected.
# If False, only cloud-only files that collide on size get downloaded and hashed.
SKIP_CLOUD_ONLY = False

# Windows file attribute flags for OneDrive placeholders
RECALL_ON_DATA_ACCESS = 0x00400000
RECALL_ON_OPEN = 0x00040000
OFFLINE = 0x00001000

# ==========================================
# HELPERS
# ==========================================


def is_cloud_placeholder(st: os.stat_result) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & (RECALL_ON_DATA_ACCESS | RECALL_ON_OPEN | OFFLINE))


def sha256_file(path: str) -> str | None:
    """SHA256 without loading the whole file into memory."""
    sha = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK_SIZE):
                sha.update(chunk)
        return sha.hexdigest()
    except OSError as e:
        print(f"Failed: {path} ({e})")
        return None


def walk_files(root: Path):
    """Yield os.DirEntry for every file under root (no symlink following)."""
    stack = [str(root)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            yield entry
                    except OSError as e:
                        print(f"Skipped {entry.path} ({e})")
        except OSError as e:
            print(f"Cannot open {current} ({e})")


# ==========================================
# MAIN
# ==========================================


def main() -> None:
    # ---- 1. Inventory (metadata only, no file reads) ----
    records: list[dict] = []
    for i, entry in enumerate(walk_files(LIBRARY_ROOT), start=1):
        try:
            st = entry.stat()
        except OSError as e:
            print(f"Error processing {entry.path}: {e}")
            continue

        suffix = Path(entry.name).suffix.lower()
        records.append(
            {
                "resource_id": f"R{i:06d}",
                "path": entry.path,
                "filename": entry.name,
                "extension": suffix if suffix else "[no extension]",
                "size_bytes": st.st_size,
                "modified_date": datetime.fromtimestamp(st.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "cloud_only": is_cloud_placeholder(st),
                "sha256": None,
            }
        )

    n_cloud = sum(r["cloud_only"] for r in records)
    n_sizes = len({r["size_bytes"] for r in records})
    print(f"{len(records):,} files scanned")
    print(f"  cloud-only placeholders: {n_cloud:,}")
    print(f"  unique file sizes:       {n_sizes:,}")

    if not records:
        print("No files found. Check LIBRARY_ROOT.")
        return

    # ---- 2. Only files sharing a size can be duplicates ----
    by_size: dict[int, list[dict]] = defaultdict(list)
    for r in records:
        if SKIP_CLOUD_ONLY and r["cloud_only"]:
            continue
        by_size[r["size_bytes"]].append(r)

    candidates = [r for group in by_size.values() if len(group) > 1 for r in group]
    print(f"Hashing {len(candidates):,} size-collision candidates")

    # ---- 3. Hash candidates ----
    if candidates:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
            hashes = pool.map(sha256_file, (r["path"] for r in candidates))
            for r, h in zip(candidates, hashes):
                r["sha256"] = h

    # ---- 4. Flag duplicates ----
    df = pd.DataFrame(records)

    # Unhashed / failed files have sha256 = None and never count as duplicates.
    counts = df["sha256"].value_counts()  # drops NaN/None by default
    df["is_duplicate"] = df["sha256"].map(counts).fillna(0).gt(1)

    df["duplicate_group"] = pd.NA
    dup = df["is_duplicate"]
    df.loc[dup, "duplicate_group"] = df.loc[dup, "sha256"].factorize()[0] + 1
    df["duplicate_group"] = df["duplicate_group"].astype("Int64")

    # ---- 5. Export ----
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    print(f"\nProcessed {len(df):,} files")
    print(f"Duplicates found: {int(df['is_duplicate'].sum()):,}")
    print(f"Duplicate groups: {df['duplicate_group'].nunique():,}")
    print(f"Saved: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()