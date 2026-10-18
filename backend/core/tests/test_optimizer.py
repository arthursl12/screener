import math
from dataclasses import asdict, dataclass
from typing import Any

import pytest
from helpers import (
    C1,
    C2,
    C3,
    C4_ENTRY,
    C5_TARGET,
    make_candles,
    make_candles_at,
    make_config,
    random_m30_candles,
    random_multi_day_candles,
    random_walk_candles,
)
from test_day_trade import M30_TIMES, ROWS_A, TIMES_A

from b3core.data import Timeframe
from b3core.engine import run_backtest
from b3core.metrics import compute_metrics
from b3core.optimizer import (
    BudgetExceeded,
    Constraints,
    GridSearch,
    ParamRange,
    ParamSpace,
    RandomSearch,
    TrialCache,
    data_fingerprint,
    describe_space,
    flag_drop,
    objective_value,
    optimize,
    run_hash,
    split_candles,
)
from b3core.score import score_v1
from b3core.strategy import STRATEGY_123

BASE = make_config()
WORKED = make_candles([C1, C2, C3, C4_ENTRY, C5_TARGET])


# --- parameter ranges and spaces -------------------------------------------------------------


def test_param_range_builds_values_from_an_integer_index() -> None:
    r = ParamRange(1, 5, 0.5)

    assert r.size == 9
    assert r.values() == [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]


def test_param_range_has_no_float_drift() -> None:
    r = ParamRange(0.1, 0.7, 0.1)

    assert r.size == 7
    assert r.values()[-1] == 0.7  # 0.1 + 6 * 0.1 is 0.7000000000000001 without index rounding
    assert ParamRange(0, 3, 1).values() == [0, 1, 2, 3]


def test_param_range_rejects_bad_arguments() -> None:
    with pytest.raises(ValueError, match="step"):
        ParamRange(1, 5, 0)
    with pytest.raises(ValueError, match="stop"):
        ParamRange(5, 1, 1)


def test_space_size_matches_the_brief_example() -> None:
    space = ParamSpace(
        {
            "target_mult": ParamRange(1, 5, 0.5),  # 9
            "entry_offset_ticks": ParamRange(0, 3, 1),  # 4
            "entry_validity_bars": ParamRange(1, 5, 1),  # 5
        }
    )

    assert space.size == 180


def test_fixed_values_and_option_lists_count_correctly() -> None:
    space = ParamSpace({"lot_size": 100, "stop_mode": ["C3", "C2"]})

    assert space.size == 2
    assert space.decode(0) == {"lot_size": 100, "stop_mode": "C3"}
    assert space.decode(1) == {"lot_size": 100, "stop_mode": "C2"}


def test_decode_enumerates_the_whole_space_with_the_last_parameter_fastest() -> None:
    space = ParamSpace(
        {"target_mult": ParamRange(1, 2, 1), "entry_offset_ticks": ParamRange(0, 2, 1)}
    )

    combos = [tuple(space.decode(i).values()) for i in range(space.size)]

    assert combos == [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    with pytest.raises(IndexError):
        space.decode(space.size)


def test_unknown_parameter_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="not_a_param"):
        ParamSpace({"not_a_param": 1})


def test_space_validation_catches_values_the_config_rejects() -> None:
    space = ParamSpace({"target_mult": ParamRange(0, 2, 1)})  # 0 is not above zero

    with pytest.raises(ValueError, match="target_mult"):
        space.validate(BASE)


def test_integer_fields_accept_integral_floats_and_reject_fractions() -> None:
    space = ParamSpace({"entry_validity_bars": ParamRange(1.0, 3.0, 1.0)})
    assert space.build_config(BASE, space.decode(2)).entry_validity_bars == 3

    bad = ParamSpace({"entry_validity_bars": ParamRange(1, 2, 0.5)})
    with pytest.raises(ValueError, match="entry_validity_bars"):
        bad.build_config(BASE, bad.decode(1))


def test_describe_space_reports_size_and_recommends_grid_when_small() -> None:
    small = ParamSpace(
        {"target_mult": ParamRange(1, 5, 0.5), "entry_offset_ticks": ParamRange(0, 3, 1)}
    )
    huge = ParamSpace(
        {"target_mult": ParamRange(1, 5, 0.01), "entry_offset_ticks": ParamRange(0, 30, 1)}
    )

    assert describe_space(small).size == 36
    assert describe_space(small).recommendation == "grid"
    assert describe_space(huge).recommendation == "genetic"


# --- objectives, constraints, hashing --------------------------------------------------------


def test_objectives_are_maximised_and_min_drawdown_is_negated() -> None:
    m = compute_metrics([100, -50, -30, 200, -300, 50], capital=1_000)

    assert objective_value(m, "result") == pytest.approx(m.result)
    assert objective_value(m, "profit_factor") == pytest.approx(m.profit_factor)
    assert objective_value(m, "ev") == pytest.approx(m.ev)
    assert objective_value(m, "min_drawdown") == pytest.approx(-0.30)
    assert objective_value(m, "score_v1") == pytest.approx(score_v1(m))
    with pytest.raises(ValueError, match="objective"):
        objective_value(m, "sharpe")


def test_constraints() -> None:
    m = compute_metrics([100, -50, -30, 200, -300, 50], capital=1_000)  # 6 trades, 30% drawdown

    assert Constraints().satisfied(m)
    assert Constraints(min_trades=6).satisfied(m)
    assert not Constraints(min_trades=7).satisfied(m)
    assert not Constraints(max_drawdown=0.2).satisfied(m)
    assert Constraints(max_drawdown=0.3).satisfied(m)


def test_run_hash_depends_on_config_and_data_only() -> None:
    fp = data_fingerprint(WORKED)

    assert run_hash(BASE, fp) == run_hash(make_config(), fp)
    assert run_hash(BASE, fp) != run_hash(make_config(max_risk_brl=201), fp)
    assert len(run_hash(BASE, fp)) == 64  # SHA-256 hex digest

    other = make_candles([C1, C2, C3, C4_ENTRY, (10.55, 11.31, 10.50, 11.25)])
    assert run_hash(BASE, fp) != run_hash(BASE, data_fingerprint(other))


# --- algorithms ------------------------------------------------------------------------------

RF_SPACE = ParamSpace({"target_mult": ParamRange(1, 3, 1)})


def test_grid_search_finds_the_known_best_and_reports_every_trial() -> None:
    # multiple 1: target 10.58, +187; 2: target 10.75, +374; 3: target 10.92 is never reached
    result = optimize(WORKED, BASE, RF_SPACE, objective="result", oos_fraction=0.0)

    assert result.n_trials == 3
    assert result.best.params["target_mult"] == 2
    assert result.best.metrics.net_pnl == pytest.approx(374.0)
    ranked = [t.params["target_mult"] for t in result.ranked_trials()]
    assert ranked == [2, 1, 3]


def test_constraints_push_infeasible_trials_to_the_bottom() -> None:
    result = optimize(
        WORKED,
        BASE,
        RF_SPACE,
        objective="result",
        constraints=Constraints(min_trades=1),
        oos_fraction=0.0,
    )

    infeasible = [t for t in result.trials if not t.feasible]
    assert [t.params["target_mult"] for t in infeasible] == [3]
    assert result.ranked_trials()[-1].params["target_mult"] == 3


def test_random_search_is_seeded_and_samples_without_repeats() -> None:
    space = ParamSpace(
        {"target_mult": ParamRange(1, 5, 0.5), "entry_offset_ticks": ParamRange(0, 3, 1)}
    )
    candles = random_walk_candles(200, seed=1)

    a = optimize(
        candles, BASE, space, algorithm=RandomSearch(seed=42, n_samples=10), oos_fraction=0.0
    )
    b = optimize(
        candles, BASE, space, algorithm=RandomSearch(seed=42, n_samples=10), oos_fraction=0.0
    )
    c = optimize(
        candles, BASE, space, algorithm=RandomSearch(seed=43, n_samples=10), oos_fraction=0.0
    )

    assert [t.index for t in a.trials] == [t.index for t in b.trials]
    assert [t.index for t in a.trials] != [t.index for t in c.trials]
    assert len({t.index for t in a.trials}) == 10


def test_random_search_never_asks_for_more_than_the_space_holds() -> None:
    result = optimize(
        WORKED, BASE, RF_SPACE, algorithm=RandomSearch(seed=1, n_samples=50), oos_fraction=0.0
    )

    assert result.n_trials == 3


def test_budget_caps_the_number_of_evaluations() -> None:
    with pytest.raises(BudgetExceeded):
        optimize(
            WORKED, BASE, RF_SPACE, algorithm=GridSearch(), max_evaluations=2, oos_fraction=0.0
        )


def test_repeated_configs_hit_the_cache_instead_of_running_again() -> None:
    cache = TrialCache()
    optimize(WORKED, BASE, RF_SPACE, cache=cache, oos_fraction=0.0)
    assert (cache.misses, cache.hits) == (3, 0)

    optimize(WORKED, BASE, RF_SPACE, cache=cache, oos_fraction=0.0)
    assert (cache.misses, cache.hits) == (3, 3)


def test_process_pool_gives_the_same_trials_as_a_single_process() -> None:
    space = ParamSpace(
        {"target_mult": ParamRange(1, 3, 1), "entry_offset_ticks": ParamRange(0, 2, 1)}
    )
    candles = random_walk_candles(300, seed=3)

    single = optimize(candles, BASE, space, workers=1, oos_fraction=0.0)
    pooled = optimize(candles, BASE, space, workers=2, oos_fraction=0.0)

    assert single.trials == pooled.trials


# --- split, validation and the result tables -------------------------------------------------


def test_split_is_chronological_and_never_overlaps() -> None:
    candles = random_walk_candles(100, seed=1)

    in_sample, out_of_sample = split_candles(candles, oos_fraction=0.3)

    assert (len(in_sample), len(out_of_sample)) == (70, 30)
    assert in_sample["ts"].iloc[-1] < out_of_sample["ts"].iloc[0]
    assert in_sample["ts"].iloc[0] == candles["ts"].iloc[0]


def test_flag_drop_handles_positive_and_negative_objectives() -> None:
    assert flag_drop(0.10, 0.04) is True  # fell below half of the in-sample value
    assert flag_drop(0.10, 0.06) is False
    assert flag_drop(-0.10, -0.20) is True  # drawdown objective (negated) got much worse
    assert flag_drop(-0.10, -0.12) is False
    assert flag_drop(0.10, -0.01) is True


def test_optimize_searches_in_sample_only_and_validates_the_top_results_out_of_sample() -> None:
    candles = random_walk_candles(800, seed=7)
    space = ParamSpace({"target_mult": ParamRange(1, 3, 1), "stop_mode": ["C3", "C2"]})

    result = optimize(candles, BASE, space, objective="result", oos_fraction=0.3, top_n=3)

    in_sample, out_of_sample = split_candles(candles, 0.3)
    assert result.n_trials == 6
    assert len(result.validation) == 3
    # the trials equal a plain search over the in-sample candles only
    expected = optimize(in_sample, BASE, space, objective="result", oos_fraction=0.0)
    assert result.trials == expected.trials
    # validation rows are the top in-sample results and match a direct out-of-sample run
    top = result.ranked_trials()[:3]
    for row, trial in zip(result.validation, top, strict=True):
        assert row.index == trial.index
        direct = run_backtest(out_of_sample, space.build_config(BASE, trial.params))
        assert row.out_of_sample.metrics == direct.metrics


def test_result_tables_have_one_row_per_trial_and_per_validated_result() -> None:
    candles = random_walk_candles(800, seed=7)
    space = ParamSpace({"target_mult": ParamRange(1, 3, 1), "stop_mode": ["C3", "C2"]})

    result = optimize(candles, BASE, space, oos_fraction=0.3, top_n=2)

    trials = result.trials_table()
    assert len(trials) == 6
    assert {"target_mult", "stop_mode", "objective", "feasible", "n_trades", "run_hash"} <= set(
        trials.columns
    )

    validation = result.validation_table()
    assert len(validation) == 2
    assert {"rank", "is_objective", "oos_objective", "dropped"} <= set(validation.columns)


def test_same_inputs_give_identical_optimization_results() -> None:
    candles = random_walk_candles(400, seed=5)
    space = ParamSpace(
        {"target_mult": ParamRange(1, 3, 1), "entry_offset_ticks": ParamRange(0, 2, 1)}
    )

    a = optimize(candles, BASE, space, oos_fraction=0.3, top_n=3)
    b = optimize(candles.copy(), BASE, space, oos_fraction=0.3, top_n=3)

    assert a.trials == b.trials
    assert a.validation == b.validation


def test_profit_factor_objective_can_be_infinite_and_still_ranks() -> None:
    result = optimize(WORKED, BASE, RF_SPACE, objective="profit_factor", oos_fraction=0.0)

    assert math.isinf(result.best.objective)  # one winning trade and no losses


# --- day trade ---------------------------------------------------------------------------------


DAY_BASE = make_config(day_trade=True)


def test_run_hash_depends_on_the_timeframe_and_the_finer_candles() -> None:
    intraday = make_candles_at([(10.64, 10.70, 10.60, 10.66)], ["2024-01-03 16:00"])

    plain = data_fingerprint(WORKED)
    assert data_fingerprint(WORKED, timeframe=Timeframe.H2) != plain
    assert data_fingerprint(WORKED, timeframe=Timeframe.H4) != data_fingerprint(
        WORKED, timeframe=Timeframe.H2
    )
    assert data_fingerprint(WORKED, intraday=intraday) != plain


def test_invalid_entry_windows_are_dropped_before_evaluating() -> None:
    space = ParamSpace(
        {
            "min_entry_time": ["00:00", "15:00", "16:00"],
            "max_entry_time": ["12:00", "15:30"],
        }
    )

    restricted = space.restricted(DAY_BASE)

    # kept: (00:00, 12:00), (00:00, 15:30), (15:00, 15:30); the other three have min >= max
    assert restricted.size == 3
    assert [tuple(restricted.decode(i).values()) for i in range(3)] == [
        ("00:00", "12:00"),
        ("00:00", "15:30"),
        ("15:00", "15:30"),
    ]
    assert describe_space(space, base=DAY_BASE).size == 3
    result = optimize(
        random_multi_day_candles(6, seed=1),
        DAY_BASE,
        space,
        timeframe=Timeframe.H2,
        oos_fraction=0,
    )
    assert result.n_trials == 3


def test_a_space_with_no_valid_window_is_an_error() -> None:
    space = ParamSpace({"min_entry_time": ["16:00"], "max_entry_time": ["12:00"]})

    with pytest.raises(ValueError, match="entry window"):
        space.restricted(DAY_BASE)


def test_day_trade_without_a_timeframe_fails_with_a_clear_message() -> None:
    with pytest.raises(ValueError, match="timeframe"):
        optimize(
            random_multi_day_candles(4, seed=1),
            DAY_BASE,
            ParamSpace({"target_mult": ParamRange(1, 2, 1)}),
            oos_fraction=0,
        )


def test_the_exit_policy_can_be_optimized_with_finer_candles() -> None:
    candles = make_candles_at(ROWS_A, TIMES_A)
    intraday = make_candles_at(
        [(10.64, 10.70, 10.60, 10.66), (10.72, 11.30, 10.70, 11.25), (10.70, 10.72, 10.60, 10.65)],
        M30_TIMES,
    )
    space = ParamSpace({"day_exit_policy": ["auto", "last_candle_open", "last_candle_close"]})

    result = optimize(
        candles, DAY_BASE, space, timeframe=Timeframe.H2, intraday=intraday, oos_fraction=0
    )

    pnl = {t.params["day_exit_policy"]: t.metrics.net_pnl for t in result.trials}
    assert pnl["auto"] == pytest.approx(341.0)  # pinpointed 16:30 open, 10.72
    assert pnl["last_candle_open"] == pytest.approx(121.0)  # the 16:00 candle's open, 10.52
    assert pnl["last_candle_close"] == pytest.approx(231.0)  # the 16:00 candle's close, 10.62


def test_finer_candles_are_split_with_the_out_of_sample_cut() -> None:
    candles = random_multi_day_candles(20, seed=4)
    intraday = random_m30_candles(20, seed=4)
    space = ParamSpace({"target_mult": ParamRange(1, 3, 1), "min_entry_time": ["00:00", "11:00"]})

    result = optimize(
        candles,
        DAY_BASE,
        space,
        timeframe=Timeframe.H2,
        intraday=intraday,
        oos_fraction=0.3,
        top_n=2,
    )

    in_sample, out_of_sample = split_candles(candles, 0.3)
    cut = out_of_sample["ts"].iloc[0]
    expected_in = optimize(
        in_sample,
        DAY_BASE,
        space,
        timeframe=Timeframe.H2,
        intraday=intraday[intraday["ts"] < cut].reset_index(drop=True),
        oos_fraction=0,
    )
    assert result.trials == expected_in.trials
    for row in result.validation:
        config = space.build_config(DAY_BASE, row.params)
        direct = run_backtest(
            out_of_sample,
            config,
            timeframe=Timeframe.H2,
            intraday=intraday[intraday["ts"] >= cut].reset_index(drop=True),
        )
        assert row.out_of_sample.metrics == direct.metrics


# --- strategies ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ToyConfig:
    gain: float = 1.0
    losses: int = 0

    def __post_init__(self) -> None:
        if self.losses > 3:
            raise ValueError("losses must be at most 3")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ToyStrategy:
    """A strategy that never touches the engine: one winning trade of `gain`, then `losses`."""

    id: str = "toy"
    version: int = 1
    config_type: type = ToyConfig
    constrained_params: tuple[str, ...] = ("gain", "losses")
    restriction: str = "gain and losses"

    def run(self, candles: Any, config: ToyConfig, *, timeframe: Any, intraday: Any) -> Any:
        return compute_metrics([config.gain] + [-1.0] * config.losses, capital=100.0)

    def combination_is_valid(self, base: ToyConfig, params: Any) -> bool:
        return params.get("losses", base.losses) <= 2  # a made-up relation, to test the hook


TOY_SPACE = ParamSpace({"gain": ParamRange(1, 3, 1), "losses": ParamRange(0, 4, 1)}, ToyStrategy())


def test_run_hash_depends_on_the_strategy() -> None:
    fp = data_fingerprint(WORKED)
    toy = ToyStrategy()

    assert run_hash(BASE, fp) == run_hash(BASE, fp, STRATEGY_123)
    assert run_hash(ToyConfig(), fp, toy) != run_hash(ToyConfig(), fp, ToyStrategy(id="other"))
    assert run_hash(ToyConfig(), fp, toy) != run_hash(ToyConfig(), fp, ToyStrategy(version=2))


def test_the_optimizer_runs_any_strategy_and_drops_what_its_hook_rejects() -> None:
    result = optimize(WORKED, ToyConfig(), TOY_SPACE, objective="result", oos_fraction=0.0)

    assert TOY_SPACE.restricted(ToyConfig()).size == 9  # losses 3 and 4 dropped: 3 gains x 3
    assert result.n_trials == 9
    assert result.best.params == {"gain": 3, "losses": 0}
    assert len({t.run_hash for t in result.trials}) == 9


def test_a_config_from_another_strategy_is_rejected() -> None:
    with pytest.raises(TypeError, match="toy"):
        optimize(WORKED, BASE, TOY_SPACE, oos_fraction=0.0)


def test_a_space_where_the_hook_rejects_everything_names_the_restriction() -> None:
    space = ParamSpace({"losses": [3, 4]}, ToyStrategy())

    with pytest.raises(ValueError, match="gain and losses"):
        space.restricted(ToyConfig())


def test_validation_leaves_constrained_parameters_to_the_hook() -> None:
    # losses=4 alone is a bad config, but the hook drops it with the others, so validate must
    # not reject it one value at a time
    optimize(WORKED, ToyConfig(), TOY_SPACE, oos_fraction=0.0)
