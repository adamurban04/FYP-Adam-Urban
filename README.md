# Auditable financial reconciliation

Final Year Project, BSc Computer Systems, University of Limerick  
Adam Urban · Supervisor: Meghana Kshirsagar

The project will use a tool-assisted AI agent to investigate differences between
ledger and bank records. Unresolved cases will go to a human reviewer with the
evidence behind the recommendation.

This repository currently contains the small deterministic starter used to check
the first reconciliation cases. The AI agent is not implemented yet.

## Run locally

Python 3.10 or later is required. There are no third-party packages at this stage.

```bash
python3 -m venv .venv
source .venv/bin/activate
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python demo.py
```

The demo writes `results.json`, `audit.jsonl` and `audit_head.txt` to `output/demo`.
It keeps previous output intact. For another run, choose a new folder:

```bash
PYTHONPATH=src python demo.py --out output/second-run
```

## Current behaviour

Amounts use integer cents. A strict match requires the same non-empty reference,
amount and date. There must be one candidate, and that bank record cannot also
be claimed by another ledger entry. Everything else receives `review`; this is
a recorded status, not a working human-review interface.

The four synthetic demo cases are:

| Case | Expected output |
| --- | --- |
| EUR 2,450 unique exact match | match |
| EUR 1,850 with two exact bank candidates | review |
| EUR 4,200 against EUR 4,020 | review |
| EUR 750 with no bank record | review |

Eleven tests cover money precision, candidate allocation and the local audit
chain. These tests establish specific starter behaviours, not agent accuracy.

The audit file records input records, amount/date comparisons and decisions.
Each event links to the previous event by its hash. This can expose edits or
truncation when checked against a trusted head. The local head file can itself
be changed, so this is not tamper-proof storage. Concurrent writes, access
controls and durable database persistence are not implemented.

## Files

- `src/recon/core.py`: transaction records, money conversion, matching and audit checks
- `demo.py` and `data/cases.json`: the four small examples
- `tests/test_core.py`: the eleven checks
- `design/`: draft database schema and agent tool contracts

## Next

Connect the bounded LangGraph agent to deterministic tools, persist cases and
events in PostgreSQL, then add CSV imports, FastAPI and the review interface.
Candidate evidence comparisons, stability checks and reopening after new
competing records are planned research features. They are not present in this
starter. The initial scope is one organisation, EUR and no live payments.
