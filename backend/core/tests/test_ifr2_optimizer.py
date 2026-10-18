"""IFR2 as the second strategy of the optimizer (brief sections 7 and 12)."""

import pytest
from helpers import random_walk_candles

from b3core.ifr2 import Ifr2Config, run_ifr2
from b3core.optimizer import ParamRange, ParamSpace, data_fingerprint, optimize, run_hash
from b3core.strategy import STRATEGY_123, Ifr2Strategy

IFR2 = Ifr2Strategy()
BASE = Ifr2Config.preset()  # exit_mode "target", rsi_exit 70, target_lookback 2


def space(**axes: object) -> ParamSpace:
    return ParamSpace(axes, IFR2)  # type: ignore[arg-type]


def combos(s: ParamSpace) -> list[tuple[object, ...]]:
    return [tuple(s.decode(i).values()) for i in range(s.size)]


def test_the_strategy_has_its_own_identity() -> None:
    fp = data_fingerprint(random_walk_candles(50, seed=1))

    assert IFR2.id == "ifr2_compra"
    assert IFR2.config_type is Ifr2Config
    assert run_hash(BASE, fp, IFR2) != run_hash(BASE, fp, STRATEGY_123)


def test_the_target_lookback_is_dropped_when_the_mode_has_no_target() -> None:
    s = space(exit_mode=["rsi", "target"], target_lookback=[2, 3, 4])
    s = s.restricted(Ifr2Config.preset(rsi_exit=70, target_lookback=2))

    # "rsi" ignores the lookback, so it keeps only the base value; "target" keeps all three
    assert combos(s) == [("rsi", 2), ("target", 2), ("target", 3), ("target", 4)]


def test_the_rsi_exit_level_is_dropped_when_the_mode_has_no_rsi_exit() -> None:
    s = space(exit_mode=["target", "rsi", "target_or_rsi"], rsi_exit=[60, 70])
    s = s.restricted(BASE)

    assert combos(s) == [("target", 70), ("rsi", 60), ("rsi", 70), ("target_or_rsi", 60),
                         ("target_or_rsi", 70)]  # fmt: skip


def test_an_rsi_exit_at_or_below_the_entry_level_is_dropped() -> None:
    s = space(exit_mode="rsi", rsi_entry=[10, 30, 50], rsi_exit=[30, 70])
    s = s.restricted(BASE)

    # (30, 30) and (50, 30) fail rsi_entry < rsi_exit
    assert combos(s) == [("rsi", 10, 30), ("rsi", 10, 70), ("rsi", 30, 70), ("rsi", 50, 70)]


def test_the_entry_level_is_not_compared_with_an_unused_rsi_exit() -> None:
    s = space(rsi_entry=[30, 80]).restricted(BASE)  # mode "target": rsi_exit 70 is unused

    assert combos(s) == [(30,), (80,)]


def test_a_space_where_nothing_is_valid_is_an_error() -> None:
    with pytest.raises(ValueError, match="exit rule"):
        space(exit_mode="rsi", rsi_entry=[80], rsi_exit=[70]).restricted(BASE)


def test_the_optimizer_runs_ifr2_and_validates_out_of_sample() -> None:
    candles = random_walk_candles(900, seed=11)
    s = space(rsi_entry=ParamRange(10, 40, 10), exit_mode=["target", "rsi"], rsi_exit=[60, 70])

    result = optimize(candles, BASE, s, objective="score_v1", oos_fraction=0.3, top_n=2)

    # target: rsi_exit fixed at 70 (4 entries x 1); rsi: 4 entries x 2 exit levels
    assert result.n_trials == 12
    assert len(result.validation) == 2
    best = result.best
    direct = run_ifr2(
        candles.iloc[: round(900 * 0.7)].reset_index(drop=True),
        s.build_config(BASE, best.params),
    )
    assert best.metrics == direct.metrics


def test_a_123_config_is_rejected_by_an_ifr2_space() -> None:
    from helpers import make_config

    with pytest.raises(TypeError, match="ifr2_compra"):
        optimize(random_walk_candles(50, seed=1), make_config(), space(rsi_entry=[20]),
                 oos_fraction=0.0)  # fmt: skip


def test_target_or_rsi_keeps_both_the_lookback_and_the_rsi_exit() -> None:
    s = space(exit_mode="target_or_rsi", target_lookback=[2, 3], rsi_exit=[60, 70])

    assert len(s.restricted(BASE).decode(0)) == 3
    assert s.restricted(BASE).size == 4


def test_an_intraday_timeframe_is_refused_by_the_ifr2_strategy() -> None:
    from b3core.data import Timeframe

    with pytest.raises(ValueError, match="daily"):
        optimize(random_walk_candles(50, seed=1), BASE, space(rsi_entry=[20]),
                 timeframe=Timeframe.H2, oos_fraction=0.0)  # fmt: skip
