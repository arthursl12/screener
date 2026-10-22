# B3 Backtester

Notebook-first backtester for B3 instruments (stocks, BDRs, ETFs, indices) with a parameter optimizer, in the spirit of QuantBrasil. It is a portfolio project, and the owner is using it to learn the stack, so teaching and review come before writing code.

Read `docs/brief.md` before starting any phase or task. It is the source of truth for architecture, trading rules (sections 6 and 7), the optimizer (section 12) and the roadmap (section 10).

**Current phase: Phase 0, barebones MVP. On hold since Oct 22, 2026:** no strategy tested beat the CDI out-of-sample (see `README.md`), so the owner paused the project. Notebook, candles from CSV files and yfinance, no Docker, no database, no CI. Update this line when a phase ends or work resumes.

## Learning mode (applies to every task)

The owner wants to learn every part of this project well enough to defend it in an interview. There are three modes: **Learn** (the owner writes, Claude teaches and reviews), **Refresh** (Claude drafts, the owner rewrites parts), **Delegate** (Claude writes, the owner explains it back). The owner can switch any task's mode at any time by saying so.

| Mode | Areas |
| --- | --- |
| Learn | Engine, 123 rules, metrics, data providers, optimizer, notebooks, database (SQLAlchemy, Alembic, Postgres), Redis and ARQ, MT5 collector, CD |
| Refresh | Minimal setup (the owner writes the first core test), React UI and TanStack Query, Docker and Compose, GitHub Actions CI |
| Delegate | Linting and config |
| Later | DuckDB cache, only after the benchmark gate in the brief |

Starting points: React is rusty; FastAPI, Postgres, Redis, SQLAlchemy, DuckDB and Docker were only used briefly; TanStack Query and CD are new; CI is somewhat new. TDD is already familiar, so skip TDD primers and go straight to the test.

**At the start of every task:**

1. Say which mode the task falls under.
2. For a Learn task, give a short primer (what the concept is, why it is used here, one common pitfall), name the failing test the owner writes first, then stop and wait.
3. Do not write production code in a Learn area unprompted. If the owner says to just do it, state in one line what learning is skipped, then do it.
4. Review the owner's code with specific findings and the concept behind each, not a rewrite.
5. For Refresh and Delegate tasks, write the code, then walk through the non-obvious parts.

**At the end of every slice:**

- Ask two or three explain-back questions about what was just built, wait for the answers, and correct them kindly.
- Add an entry to `docs/learning-log.md`: concept, where it is used, status (explained, shaky, to revisit) and date.
- Prompt the owner to write the ADR for any decision made, in their own words.
- Merge only when the owner can explain the change without looking at it.

## Rules

1. **Thin vertical slices.** Write a failing test, make it pass with the smallest change, refactor, commit. Never write a large module before its first test.
2. **The spec is the source of truth.** Implement only trading rules written in brief sections 6 and 7. If a rule is ambiguous or missing, stop, add it to the open questions in section 10 of the brief, and ask. Never guess a market rule.
3. **Keep `core` pure.** No FastAPI, SQLAlchemy, Redis or network code in it. DataFrames or arrays in, plain results out.
4. **Be deterministic.** The same inputs give the same outputs. No wall-clock reads, and randomness only from a seeded generator.
5. **Time and prices.** UTC timestamps; trading rules evaluated in `America/Sao_Paulo`. Prices are float64, rounded to the instrument tick when filling orders.
6. **No new dependencies** outside brief section 3 without asking. Pin versions and commit the lockfiles.
7. **Never commit** credentials, `.env` files or real vendor market data (candles, files in `samples/` or `data/`). Commit only small synthetic fixtures. **Notebook outputs** are stripped by default (nbstripout is installed as a git filter). The owner may publish the outputs of a results notebook, for the portfolio, by unsetting its filter in `.gitattributes`. A published notebook may show derived results only (metrics, counts, charts) and never a table of raw candles; `make lint` runs `tools/check_notebook_outputs.py` to refuse that. Decided by the owner on Oct 21, 2026, on the reading that results derived from public Yahoo Finance data, not the data itself, are being shown. The Yahoo terms still restrict redistributing the data, so the rule is about derived results only.
8. **Commit style.** Conventional Commits, one logical change per commit, `main` stays green.
9. **Document decisions** as short ADRs in `docs/adr/` (context, decision, consequences). The owner writes them.
10. **Report honestly.** If a test fails, a benchmark misses its budget, or a result looks too good, say so instead of tuning until it passes.

**Definition of done:** tests written first and passing, `make lint` and `make test` green, types checked, docs or ADR updated if behaviour changed, and, from Phase 1 on, `docker compose up` still brings the stack up healthy.

## Commands

Phase 0: `make test`, `make lint`, `make fmt`, `make notebook`, `make check-notebooks` (part of `make lint`). From Phase 1: `make up`, `make down`, `make migrate`. Do not assume a command exists before the Makefile defines it.

## GitHub Copilot

Copilot in VS Code is the owner's typing assistant for code they are already writing. Claude is for design, explanation and review. Never suggest or accept a trading rule or metric formula without a test that pins its behaviour.

## Disclaimer

The app is educational and is not investment advice. Say so in the first cell of every notebook, on every results page and in the README.
