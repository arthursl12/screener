"""The seam between the optimizer and a trading strategy. Pure: no I/O, no clock.

The optimizer needs four things from a strategy: an identity for `run_hash`, the config class
whose fields are the searchable parameters, a way to run one config and get its metrics, and a
hook that tells it which parameter combinations make no sense.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd

from b3core.data import Timeframe
from b3core.engine import BacktestConfig, run_backtest, window_is_valid
from b3core.metrics import Metrics

# The entry window is a relation between three parameters (brief section 12, rule 1).
_WINDOW_PARAMS = ("min_entry_time", "max_entry_time", "exit_time")


class Strategy(Protocol):
    # Read-only properties, so that frozen dataclasses satisfy the protocol.
    @property
    def id(self) -> str:
        """Goes into run_hash: two strategies never share a cache entry."""
        ...

    @property
    def version(self) -> int:
        """Bump when the rules change, so old cached results stop matching."""
        ...

    @property
    def config_type(self) -> type:
        """A frozen dataclass with to_dict(); its fields are the searchable parameters."""
        ...

    @property
    def constrained_params(self) -> tuple[str, ...]:
        """The parameters that `combination_is_valid` looks at."""
        ...

    @property
    def restriction(self) -> str:
        """Names the restriction in the "no valid combination" error."""
        ...

    def run(
        self,
        candles: pd.DataFrame,
        config: Any,
        *,
        timeframe: Timeframe | None,
        intraday: pd.DataFrame | None,
    ) -> Metrics: ...

    def combination_is_valid(self, base: Any, params: Mapping[str, Any]) -> bool:
        """`params` holds the constrained parameters that the search varies; the others come
        from `base`."""
        ...


@dataclass(frozen=True)
class Strategy123:
    """123 de compra (brief section 7), run by `b3core.engine`."""

    id: str = "123_compra"
    version: int = 1
    config_type: type = BacktestConfig
    constrained_params: tuple[str, ...] = _WINDOW_PARAMS
    restriction: str = "entry window"

    def run(
        self,
        candles: pd.DataFrame,
        config: BacktestConfig,
        *,
        timeframe: Timeframe | None,
        intraday: pd.DataFrame | None,
    ) -> Metrics:
        return run_backtest(candles, config, timeframe=timeframe, intraday=intraday).metrics

    def combination_is_valid(self, base: BacktestConfig, params: Mapping[str, Any]) -> bool:
        merged = {name: getattr(base, name) for name in _WINDOW_PARAMS} | dict(params)
        return window_is_valid(
            merged["min_entry_time"], merged["max_entry_time"], merged["exit_time"]
        )


STRATEGY_123 = Strategy123()
