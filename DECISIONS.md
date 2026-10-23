# Decisions

## Part 2 - skeleton
- Chose a package-per-concern layout (api / db / core / worker) over a single
  main.py because the worker must run as a separate process from the API.
- Chose venv + requirements.txt over Poetry: fewer moving parts for a solo
  project.
