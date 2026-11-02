import os
import csv
from datetime import datetime
from collections import defaultdict

root_folder = r"C:\Users\Austin.Kimuhu\OneDrive\Desktop\Books\Maths"
output_file = "maths_inventory.csv"

rows = []


"""
For getting the inventory of all files in the specified folder and its subfolders.
"""
for root, dirs, files in os.walk(root_folder):
    for file in files:
        full_path = os.path.join(root, file)

        try:
            stat = os.stat(full_path)

            rows.append({
                "Full Path": full_path,
                "Filename": os.path.basename(full_path),
                "Extension": os.path.splitext(file)[1],
                "File Size (Bytes)": stat.st_size,
                "Modified Date": datetime.fromtimestamp(
                    stat.st_mtime
                ).strftime("%Y-%m-%d %H:%M:%S")
            })

        except Exception as e:
            print(f"Error reading {full_path}: {e}")

with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "Full Path",
            "Filename",
            "Extension",
            "File Size (Bytes)",
            "Modified Date"
        ]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"{len(rows):,} files exported to {output_file}")

"""
For getting the summary of file formats, their counts, total sizes, and required parsers, we can use the following code.
"""
summary = defaultdict(lambda: {"count": 0, "size": 0})

for row in rows:
    ext = row["Extension"].lower() or "[no extension]"
    summary[ext]["count"] += 1
    summary[ext]["size"] += row["File Size (Bytes)"]

parser_map = {
    ".pdf": "pymupdf",
    ".epub": "ebooklib",
    ".djvu": "djvulibre",
    ".mobi": "kindleunpack",
    ".docx": "python-docx",
    ".xlsx": "openpyxl",
    ".txt": "built-in",
    ".zip": "zipfile",
    ".rar": "rarfile"
}


with open("format_summary.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)

    writer.writerow([
        "Extension",
        "Count",
        "Total Size (MB)",
        "Parser Required"
    ])

    for ext, stats in sorted(summary.items()):
        writer.writerow([
            ext,
            stats["count"],
            round(stats["size"] / 1024 / 1024, 2),
            parser_map.get(ext, "UNKNOWN")
        ])