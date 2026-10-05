# B3 Backtester

Notebook-first backtester for B3 instruments, with a parameter optimizer.

> **Disclaimer.** This project is educational and is not investment advice. Backtest and optimizer results are historical and do not predict future results.

## Status

Phase 0 (barebones MVP): candles from MT5 CSV exports, the 123 de compra strategy (lowest-low pattern with an EMA trend context, as specified in the brief), metrics, a grid and random-search optimizer with out-of-sample validation, and Plotly charts, all driven from a notebook. Day-trade mode (entry window and a forced exit at 16:30, by default at the close of the candle that contains it) is in, and one real QuantBrasil trade is reproduced exactly (`docs/data-notes.md`). 123 de venda, `score_v1` and the genetic algorithm are not done yet. The rules and open questions are in [`docs/brief.md`](docs/brief.md).

## Quick start

```bash
cd backend && uv sync   # Python 3.12 and dependencies
make test               # pytest (golden, property-based and unit tests)
make lint               # ruff and mypy
make notebook           # JupyterLab on notebooks/
```

Candle files are real vendor data and are never committed. Put MT5 "export bars" CSV files in `samples/` (or `data/`), both gitignored, named like `PETR4_H2_201610031000_202609301600.csv`, then open `notebooks/123_de_compra.ipynb`.

## Layout

- `backend/core` (`b3core`): pure domain, data providers, engine, metrics, optimizer. No web or database code.
- `backend/report` (`b3report`): Plotly charts and tables for notebooks.
- `notebooks/`: backtests and optimization, no trading logic.
- `docs/`: the brief, the learning log and (later) ADRs.
