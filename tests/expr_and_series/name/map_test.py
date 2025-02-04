from __future__ import annotations

from contextlib import nullcontext as does_not_raise

import polars as pl
import pytest

import narwhals.stable.v1 as nw
from tests.utils import Constructor
from tests.utils import assert_equal_data

data = {"foo": [1, 2, 3], "BAR": [4, 5, 6]}


def map_func(s: str | None) -> str:
    return str(s)[::-1].lower()


def test_map(request: pytest.FixtureRequest, constructor: Constructor) -> None:
    if "pyspark" in str(constructor):
        request.applymarker(pytest.mark.xfail)

    df = nw.from_native(constructor(data))
    result = df.select((nw.col("foo", "BAR") * 2).name.map(function=map_func))
    expected = {map_func(k): [e * 2 for e in v] for k, v in data.items()}
    assert_equal_data(result, expected)


def test_map_after_alias(
    request: pytest.FixtureRequest, constructor: Constructor
) -> None:
    if "pyspark" in str(constructor):
        request.applymarker(pytest.mark.xfail)

    df = nw.from_native(constructor(data))
    result = df.select((nw.col("foo")).alias("alias_for_foo").name.map(function=map_func))
    expected = {map_func("foo"): data["foo"]}
    assert_equal_data(result, expected)


def test_map_raise_anonymous(
    request: pytest.FixtureRequest, constructor: Constructor
) -> None:
    if "pyspark" in str(constructor):
        request.applymarker(pytest.mark.xfail)

    df_raw = constructor(data)
    df = nw.from_native(df_raw)

    context = (
        does_not_raise()
        if isinstance(df_raw, (pl.LazyFrame, pl.DataFrame))
        else pytest.raises(
            ValueError,
            match="Anonymous expressions are not supported in `.name.map`.",
        )
    )

    with context:
        df.select(nw.all().name.map(function=map_func))
