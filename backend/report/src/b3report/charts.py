"""Plotly charts and tables for notebooks. No trading logic: it only presents core results."""

import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from b3core.engine import BacktestResult, Trade
from b3core.ifr2 import Ifr2Result

DISCLAIMER = (
    "This project is educational and is not investment advice. Backtest and optimizer results "
    "are historical and do not predict future results."
)

LOCAL_TIMEZONE = "America/Sao_Paulo"
_GAIN, _LOSS = "#2e7d32", "#c62828"
_TEMPLATE = "plotly_white"


def equity_curve_figure(result: BacktestResult) -> go.Figure:
    curve = result.equity_curve()
    fig = go.Figure(
        go.Scatter(x=curve["ts"], y=curve["equity"], mode="lines", line_shape="hv", name="equity")
    )
    fig.update_layout(
        title="Equity curve (initial capital plus cumulative PnL)",
        yaxis_title="R$",
        template=_TEMPLATE,
    )
    return fig


def ifr2_equity_figure(result: Ifr2Result, candles: pd.DataFrame) -> go.Figure:
    """Daily equity (open trade marked at the close) and its fall from the running peak."""
    if len(candles) != len(result.equity):
        raise ValueError("candles must be the candles the result was computed on")
    equity = pd.Series(result.equity)
    peak = equity.cummax()  # the curve sits at the capital until the first entry
    drawdown = (equity - peak) / peak
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3])
    fig.add_trace(go.Scatter(x=candles["ts"], y=equity, mode="lines", name="equity"), row=1, col=1)
    fig.add_trace(
        go.Scatter(
            x=candles["ts"],
            y=drawdown,
            mode="lines",
            fill="tozeroy",
            line={"color": _LOSS},
            name="drawdown",
        ),
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="R$", row=1, col=1)
    fig.update_yaxes(title_text="from peak", tickformat=".0%", row=2, col=1)
    fig.update_layout(title="IFR2 equity curve and drawdown", template=_TEMPLATE)
    return fig


def monthly_returns(result: BacktestResult | Ifr2Result) -> pd.DataFrame:
    """PnL per exit month (São Paulo time) and its return over the initial capital."""
    columns = ["year", "month", "pnl", "return"]
    if not result.trades:
        return pd.DataFrame(columns=columns)

    exits = pd.DatetimeIndex([t.exit_ts for t in result.trades]).tz_convert(LOCAL_TIMEZONE)
    frame = pd.DataFrame(
        {"year": exits.year, "month": exits.month, "pnl": [t.pnl for t in result.trades]}
    )
    table = frame.groupby(["year", "month"], as_index=False)["pnl"].sum()
    table["return"] = table["pnl"] / result.config.capital_brl
    return table[columns]


def monthly_returns_figure(result: BacktestResult | Ifr2Result) -> go.Figure:
    table = monthly_returns(result)
    labels = [f"{y}-{m:02d}" for y, m in zip(table["year"], table["month"], strict=True)]
    fig = go.Figure(
        go.Bar(
            x=labels,
            y=table["return"],
            marker_color=[_GAIN if r >= 0 else _LOSS for r in table["return"]],
            name="monthly return",
        )
    )
    fig.update_layout(
        title="Monthly returns (over initial capital)",
        yaxis_tickformat=".1%",
        template=_TEMPLATE,
    )
    return fig


def _local_labels(ts: pd.Series) -> list[str]:
    return list(ts.dt.tz_convert(LOCAL_TIMEZONE).dt.strftime("%Y-%m-%d %H:%M"))


def trade_chart(candles: pd.DataFrame, trade: Trade, context: int = 10) -> go.Figure:
    """Candles around one trade, with its entry, exit, stop and target."""
    first = max(0, trade.entry_index - context)
    last = min(len(candles), trade.exit_index + context + 1)
    window = candles.iloc[first:last]
    labels = _local_labels(window["ts"])

    fig = go.Figure(
        go.Candlestick(
            x=labels,
            open=window["open"],
            high=window["high"],
            low=window["low"],
            close=window["close"],
            name="candles",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[labels[trade.entry_index - first]],
            y=[trade.entry],
            mode="markers",
            marker={"symbol": "triangle-up", "size": 12, "color": "#1565c0"},
            name="entry",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[labels[trade.exit_index - first]],
            y=[trade.exit],
            mode="markers",
            marker={"symbol": "x", "size": 12, "color": _GAIN if trade.pnl > 0 else _LOSS},
            name="exit",
        )
    )
    fig.add_hline(y=trade.stop, line_dash="dash", line_color=_LOSS, annotation_text="stop")
    fig.add_hline(y=trade.target, line_dash="dash", line_color=_GAIN, annotation_text="target")
    fig.update_layout(
        title=(
            f"Trade {trade.n}: PnL R$ {trade.pnl:,.2f} "
            f"({trade.r_multiple:.2f} R, {trade.exit_reason})"
        ),
        xaxis={"type": "category", "rangeslider": {"visible": False}},
        template=_TEMPLATE,
    )
    return fig


def heatmap_figure(
    table: pd.DataFrame, x: str, y: str, value: str = "objective", agg: str = "mean"
) -> go.Figure:
    """Objective over two parameters. Other parameters are aggregated (`agg`) in each cell.

    Infinite values (a profit factor without losses) are shown as gaps so they do not wash out
    the colour scale. A good point surrounded by bad neighbours is an overfitting warning;
    a broad plateau is a good sign.
    """
    for column in (x, y, value):
        if column not in table.columns:
            raise ValueError(f"column {column!r} not in the trials table")

    cleaned = table.assign(
        **{value: table[value].where(table[value].map(math.isfinite), float("nan"))}
    )
    grid = cleaned.pivot_table(index=y, columns=x, values=value, aggfunc=agg, dropna=False)
    fig = go.Figure(
        go.Heatmap(z=grid.to_numpy(), x=list(grid.columns), y=list(grid.index), colorscale="RdYlGn")
    )
    fig.update_layout(
        title=f"{value} by {x} and {y}",
        xaxis={"title": x, "type": "category"},
        yaxis={"title": y, "type": "category"},
        template=_TEMPLATE,
    )
    return fig
