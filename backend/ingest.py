"""Load the curated reference data in ``backend/data/`` into the database.

This is the only path by which rows enter the database. There is no synthetic or
dummy seed data: everything here comes from ``ddr_scavenger/build_evidence.py``, which
harvests ClinicalTrials.gov, GDSC and PubMed and validates every row against the
SQLModel classes in ``models.py`` before writing the JSON.

Files consumed (both are plain JSON lists of flat objects whose keys are field names of
the corresponding SQLModel class, so ``Evidence(**row)`` works directly):

    data/ddr_compounds.json   -> Compound rows (the controlled drug dictionary)
    data/ddr_evidence.json    -> Evidence rows (the fact table)

Explicit nulls are omitted from those files to keep them small; every omitted field is
Optional with a ``None`` default, so the loaded object is identical either way.

Startup contract
----------------
``load_reference_data()`` is called from ``main.py`` inside a try/except. It is:

  * **idempotent** - if either table already has rows it loads nothing and returns
    ``skipped=True``, so restarts and multiple workers are safe;
  * **fail-loud on missing files** - it raises ``FileNotFoundError``, which ``main.py``
    catches and turns into a warning. An empty database is a valid state for the API, so
    a missing data file must not stop the app from booting;
  * **batched** - inserts are flushed in blocks of ``BATCH_SIZE`` rather than one commit
    per row.

CLI
---
    python ingest.py             # load if empty (same as startup)
    python -m ingest             # same
    python ingest.py --reset     # DELETE all rows, then reload from the JSON files
    python ingest.py --recreate  # DROP and recreate the tables, then reload
    python ingest.py --dry-run   # validate the files, report counts, write nothing

``--recreate`` exists because ``--reset`` only deletes rows: it cannot fix a
table whose *columns* are stale. ``init_db()`` calls ``create_all``, which
creates missing tables but never alters existing ones, so a database created
under an older version of ``models.py`` keeps its old columns and every query
for a new field fails with ``UndefinedColumn``.

This project has no migration tool yet, so a schema change is applied by
dropping and reloading. That is safe precisely because the JSON files are the
source of truth and nothing is authored in the database itself. The moment
anyone edits rows through the API and expects them to persist, this needs
Alembic instead.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from sqlalchemy import delete
from sqlmodel import Session, SQLModel, select

from database import engine, init_db
from models import Compound, Evidence

log = logging.getLogger("uvicorn.error")

DATA_DIR = Path(__file__).parent / "data"
COMPOUNDS_FILE = DATA_DIR / "ddr_compounds.json"
EVIDENCE_FILE = DATA_DIR / "ddr_evidence.json"

# Rows per flush. Large enough that the flush overhead is negligible, small enough that
# the pending-object set stays bounded on a small container.
BATCH_SIZE = 2000


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _require(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(
            f"{label} reference data not found at {path}. Generate it with "
            f"ddr_scavenger/build_evidence.py, or start with an empty database."
        )


def _iter_rows(path: Path, label: str) -> Iterator[dict[str, Any]]:
    """Yield the objects of a JSON list file one at a time.

    The curation pipeline writes these files with one object per line, which lets us
    parse row by row and keep peak memory flat - the evidence file is tens of megabytes.
    Any file that is not in that layout (hand-edited, reformatted by a tool) falls back
    to a plain ``json.load``, so the format is an optimisation and never a requirement.
    """
    _require(path, label)
    with path.open("r", encoding="utf-8") as fh:
        first = fh.readline().strip()
        if first != "[":
            fh.seek(0)
            yield from _load_whole(path, label)
            return
        for line in fh:
            line = line.strip()
            if not line or line == "]":
                continue
            if line.endswith(","):
                line = line[:-1]
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                # Not one-object-per-line after all; restart with the whole-file parser.
                yield from _load_whole(path, label)
                return
            if not isinstance(row, dict):
                raise ValueError(f"{path} must contain a list of objects, "
                                 f"got {type(row).__name__}")
            yield row


def _load_whole(path: Path, label: str) -> Iterator[dict[str, Any]]:
    _require(path, label)
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(rows, list):
        raise ValueError(f"{path} must contain a JSON list, got {type(rows).__name__}")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path} must contain a list of objects, "
                             f"got {type(row).__name__}")
        yield row


def _read_rows(path: Path, label: str) -> list[dict[str, Any]]:
    return list(_iter_rows(path, label))


def _batched(rows: Iterable[dict], size: int) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _insert(session: Session, model, rows: Iterable[dict], label: str) -> int:
    """Insert rows through the model class so types are validated on the way in.

    Takes an iterable so the caller can stream a large file. Nothing is committed here:
    the caller commits once, which keeps a partial load from ever being visible.
    """
    inserted = 0
    for batch in _batched(rows, BATCH_SIZE):
        try:
            session.add_all([model(**row) for row in batch])
        except TypeError as exc:
            raise ValueError(
                f"{label}: a row does not match the {model.__name__} schema ({exc}). "
                f"Regenerate the JSON with ddr_scavenger/build_evidence.py."
            ) from exc
        session.flush()
        # Detach the flushed objects so peak memory stays flat over a large file.
        session.expunge_all()
        inserted += len(batch)
    log.info("ingest: staged %d %s rows", inserted, label)
    return inserted


def _count(session: Session, model) -> int:
    # select(model.id) rather than count(*) so this works the same on SQLite and Postgres
    # without importing a dialect-specific function.
    return len(session.exec(select(model.id)).all())


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def load_reference_data(session: Optional[Session] = None) -> dict:
    """Load ``backend/data/*.json`` into the DB if the tables are empty.

    Idempotent: when either table already contains rows, nothing is written and the
    existing counts are returned with ``skipped=True``.

    Args:
        session: an open session to use. When omitted a session is created and closed
            here. A supplied session is committed but not closed, so the caller keeps
            control of its lifetime.

    Returns:
        ``{"compounds": N, "evidence": M, "skipped": bool}`` - N and M are the row counts
        now in the database (not necessarily the number inserted by this call).

    Raises:
        FileNotFoundError: neither data file is present. ``main.py`` catches this so a
            deployment without curated data still boots with an empty database.
        ValueError: a file exists but is malformed or does not match the schema.
    """
    own_session = session is None
    sess = session or Session(engine)
    try:
        n_compounds = _count(sess, Compound)
        n_evidence = _count(sess, Evidence)
        if n_compounds or n_evidence:
            log.info("ingest: database already populated (%d compounds, %d evidence); "
                     "skipping load", n_compounds, n_evidence)
            return {"compounds": n_compounds, "evidence": n_evidence, "skipped": True}

        # Require both files up front so a missing second file fails before any work.
        # The evidence file is then streamed rather than parsed whole, and the single
        # commit at the end means a failure part-way through leaves the DB untouched.
        _require(COMPOUNDS_FILE, "Compound")
        _require(EVIDENCE_FILE, "Evidence")

        n_c = _insert(sess, Compound, _iter_rows(COMPOUNDS_FILE, "Compound"), "compound")
        n_e = _insert(sess, Evidence, _iter_rows(EVIDENCE_FILE, "Evidence"), "evidence")
        sess.commit()

        result = {"compounds": n_c, "evidence": n_e, "skipped": False}
        log.info("ingest: loaded %s", result)
        return result
    except Exception:
        sess.rollback()
        raise
    finally:
        if own_session:
            sess.close()


def reset_and_load(session: Optional[Session] = None) -> dict:
    """Delete every Compound and Evidence row, then reload from the JSON files.

    Used by ``python ingest.py --reset`` to repopulate a database by hand. The files are
    read and parsed *before* anything is deleted, so a bad data file leaves the existing
    contents intact.
    """
    own_session = session is None
    sess = session or Session(engine)
    try:
        _require(COMPOUNDS_FILE, "Compound")
        _require(EVIDENCE_FILE, "Evidence")

        deleted_e = _count(sess, Evidence)
        deleted_c = _count(sess, Compound)
        for model in (Evidence, Compound):
            sess.exec(delete(model))
        sess.flush()
        log.info("ingest --reset: deleted %d evidence and %d compound rows",
                 deleted_e, deleted_c)

        n_c = _insert(sess, Compound, _iter_rows(COMPOUNDS_FILE, "Compound"), "compound")
        n_e = _insert(sess, Evidence, _iter_rows(EVIDENCE_FILE, "Evidence"), "evidence")
        sess.commit()
        return {"compounds": n_c, "evidence": n_e, "skipped": False,
                "deleted_compounds": deleted_c, "deleted_evidence": deleted_e}
    except Exception:
        sess.rollback()
        raise
    finally:
        if own_session:
            sess.close()


def recreate_and_load() -> dict:
    """Drop the Evidence/Compound tables, recreate them, then load the files.

    For applying a schema change to an existing database. Destructive by
    definition: everything in those two tables is discarded. The data files are
    validated *before* the drop, so a bad file cannot leave the database empty.
    """
    _require(COMPOUNDS_FILE, "Compound")
    _require(EVIDENCE_FILE, "Evidence")
    checked = dry_run()
    log.info("ingest --recreate: validated %s; dropping tables", checked)

    # Only this app's tables, not everything in the schema.
    tables = [Evidence.__table__, Compound.__table__]
    SQLModel.metadata.drop_all(engine, tables=tables)
    SQLModel.metadata.create_all(engine, tables=tables)
    log.info("ingest --recreate: tables recreated from the current models.py")

    with Session(engine) as sess:
        try:
            n_c = _insert(sess, Compound, _iter_rows(COMPOUNDS_FILE, "Compound"), "compound")
            n_e = _insert(sess, Evidence, _iter_rows(EVIDENCE_FILE, "Evidence"), "evidence")
            sess.commit()
        except Exception:
            sess.rollback()
            raise
    return {"compounds": n_c, "evidence": n_e, "skipped": False, "recreated": True}


def dry_run() -> dict:
    """Parse and schema-check both files without touching the database."""
    counts = {}
    for key, label, model, path in (("compounds", "compound", Compound, COMPOUNDS_FILE),
                                    ("evidence", "evidence", Evidence, EVIDENCE_FILE)):
        allowed = set(model.model_fields)
        n = 0
        for i, row in enumerate(_iter_rows(path, label)):
            extra = set(row) - allowed
            if extra:
                raise ValueError(f"{label} row {i}: unknown field(s) {sorted(extra)}")
            model(**row)
            n += 1
        counts[key] = n
    return {**counts, "skipped": True}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest",
        description="Load backend/data/*.json into the evidence database.")
    parser.add_argument("--reset", action="store_true",
                        help="delete all Compound and Evidence rows, then reload")
    parser.add_argument("--recreate", action="store_true",
                        help="DROP and recreate both tables, then reload "
                             "(applies a schema change; discards all rows)")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate the data files and report counts; write nothing")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # The CLI is the one place that talks to a possibly brand-new database file.
    if not args.dry_run:
        init_db()

    try:
        if args.dry_run:
            result = dry_run()
        elif args.recreate:
            result = recreate_and_load()
        elif args.reset:
            result = reset_and_load()
        else:
            result = load_reference_data()
    except (FileNotFoundError, ValueError) as exc:
        print(f"ingest failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
