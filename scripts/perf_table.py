"""Fill the README performance section from the load-test and EXPLAIN files."""

import csv
import re
from pathlib import Path

MARK = "<!--PERF_TABLE-->"


def load(path):
    with open(path) as f:
        return {r["Name"]: r for r in csv.DictReader(f)}


def ms(row, col):
    return int(float(row[col]))


def exec_time(path):
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        return "n/a"
    m = re.search(r"Execution Time: ([\d.]+) ms", text)
    return f"{m.group(1)} ms" if m else "n/a"


before = load("loadtest/baseline_stats.csv")
after = load("loadtest/optimised_stats.csv")

lines = [
    "| Endpoint | p50 before | p50 after | p95 before | p95 after "
    "| req/s before | req/s after |",
    "|---|---|---|---|---|---|---|",
]
for name, b in before.items():
    a = after.get(name)
    if a is None:
        continue
    label = "**Total**" if name == "Aggregated" else f"`{name}`"
    lines.append(
        f"| {label} | {ms(b, '50%')} ms | {ms(a, '50%')} ms "
        f"| {ms(b, '95%')} ms | {ms(a, '95%')} ms "
        f"| {float(b['Requests/s']):.1f} | {float(a['Requests/s']):.1f} |"
    )

lines += [
    "",
    "Query plans (`EXPLAIN ANALYZE`, one monitor, 500k rows):",
    "",
    "| Query | Before index | After index |",
    "|---|---|---|",
    f"| Latest 50 checks | {exec_time('loadtest/explain_before.txt')} "
    f"| {exec_time('loadtest/explain_after.txt')} |",
    f"| 24h stats aggregate | {exec_time('loadtest/explain_stats_before.txt')} "
    f"| {exec_time('loadtest/explain_stats_after.txt')} |",
]
table = "\n".join(lines)

readme = Path("README.md")
text = readme.read_text()
if MARK in text:
    readme.write_text(text.replace(MARK, table))
    print("README updated")
else:
    print("marker not found; table printed below")
print(table)
