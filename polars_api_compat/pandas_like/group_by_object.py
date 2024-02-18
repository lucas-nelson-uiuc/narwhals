from __future__ import annotations

import collections
from typing import Any
from typing import Iterable

from polars_api_compat.pandas_like.dataframe_object import LazyFrame
from polars_api_compat.spec import DataFrame as DataFrameT
from polars_api_compat.spec import GroupBy as GroupByT
from polars_api_compat.spec import IntoExpr
from polars_api_compat.spec import LazyFrame as LazyFrameT
from polars_api_compat.spec import LazyGroupBy as LazyGroupByT
from polars_api_compat.utils import dataframe_from_dict
from polars_api_compat.utils import evaluate_simple_aggregation
from polars_api_compat.utils import horizontal_concat
from polars_api_compat.utils import is_simple_aggregation
from polars_api_compat.utils import parse_into_exprs


class GroupBy(GroupByT):
    def __init__(self, df: DataFrameT, keys: list[str], api_version: str) -> None:
        self._df = df
        self._keys = list(keys)
        self.api_version = api_version

    def agg(
        self,
        *aggs: IntoExpr | Iterable[IntoExpr],
        **named_aggs: IntoExpr,
    ) -> DataFrameT:
        return (
            LazyGroupBy(self._df.lazy(), self._keys, self.api_version)
            .agg(*aggs, **named_aggs)
            .collect()
        )


class LazyGroupBy(LazyGroupByT):
    def __init__(self, df: LazyFrameT, keys: list[str], api_version: str) -> None:
        self._df = df
        self._keys = list(keys)
        self.api_version = api_version

    def agg(
        self,
        *aggs: IntoExpr | Iterable[IntoExpr],
        **named_aggs: IntoExpr,
    ) -> LazyFrameT:
        exprs = parse_into_exprs(
            self._df.__lazyframe_namespace__(),
            *aggs,
            **named_aggs,
        )
        grouped = self._df.dataframe.groupby(
            list(self._keys),
            sort=False,
            as_index=False,
        )
        implementation: str = self._df._implementation  # type: ignore[attr-defined]

        dfs: list[Any] = []
        to_remove: list[int] = []
        for i, expr in enumerate(exprs):
            if is_simple_aggregation(expr):
                dfs.append(evaluate_simple_aggregation(expr, grouped))
                to_remove.append(i)
        exprs = [expr for i, expr in enumerate(exprs) if i not in to_remove]

        out: dict[str, list[Any]] = collections.defaultdict(list)
        for key, _df in grouped:
            for _key, _name in zip(key, self._keys):
                out[_name].append(_key)
            for expr in exprs:
                # TODO: it might be better to use groupby(...).apply
                # in this case, but I couldn't get the multi-output
                # case to work for cuDF.
                result = expr.call(
                    LazyFrame(
                        _df,
                        api_version=self.api_version,
                        implementation=implementation,
                    )
                )
                for _result in result:
                    out[_result.name].append(_result.item())

        result = dataframe_from_dict(out, implementation=implementation)
        result = horizontal_concat([result, *dfs], implementation=implementation)
        return LazyFrame(
            result,
            api_version=self.api_version,
            implementation=self._df._implementation,  # type: ignore[attr-defined]
        )
