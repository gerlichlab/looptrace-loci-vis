"""Definitions related to parsing table-like file with header"""

import logging
from typing import Protocol, runtime_checkable

import pandas as pd

from gertils.geometry import ImagePoint3D
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId

from .point_record import PointRecord
from ._types import LayerParams, PathLike


@runtime_checkable
class MappingLike(Protocol):
    def __getitem__(k: str) -> object: ...


def parse_passed(points_file: PathLike) -> tuple[list[PointRecord], list[bool], LayerParams]:
    logging.debug("Reading as QC-pass: %s", points_file)
    points_table: pd.DataFrame = pd.read_csv(points_file)
    return [parse_simple_record(row) for _, row in points_table.iterrows()]


def parse_simple_record(r: MappingLike) -> PointRecord:
    trace = TraceId(int(r["traceId"]))
    timepoint = Timepoint(int(r["timeIndex"]))
    z = float(r["z"])
    y = float(r["y"])
    x = float(r["x"])
    point = ImagePoint3D(z=z, y=y, x=x)
    return PointRecord(trace_id=trace, timepoint=timepoint, point=point)
