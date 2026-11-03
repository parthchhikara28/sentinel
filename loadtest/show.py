import csv
import sys

COLS = ["Name", "Request Count", "Failure Count", "50%", "95%", "99%", "Requests/s"]
for path in sys.argv[1:]:
    print(path)
    with open(path) as f:
        for row in csv.DictReader(f):
            print(" | ".join(str(row[c])[:30] for c in COLS))
