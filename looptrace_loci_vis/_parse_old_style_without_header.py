"""Definitions related to parsing simple table-like file with no header"""

from enum import Enum
import logging

from numpydoc_decorator import doc

from gertils.geometry import ImagePoint3D
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId

from .point_record import PointRecord
from ._types import CsvRow, QCFailReasons


@doc(
    summary="Parse records from points which passed QC.",
    parameters=dict(rows="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates,
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_passed_records(rows: list[CsvRow]) -> list[PointRecord]: # noqa: D103
    return [parse_simple_record(r, exp_num_fields=5) for r in rows]


@doc(
    summary="Parse records from points which failed QC.",
    parameters=dict(rows="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates,
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_failed(rows: list[CsvRow]) -> list[tuple[PointRecord, QCFailReasons]]: # noqa: D103
    record_qc_pairs: list[tuple[PointRecord, QCFailReasons]] = []
    for row in rows:
        try:
            qc = row[InputFileColumn.QC.get]
            rec = parse_simple_record(row, exp_num_fields=6)
        except IndexError:
            logging.exception("Bad row: %s", row)
            raise
        record_qc_pairs.append((rec, qc))
    return record_qc_pairs


@doc(
    summary="Parse single-point from a single record (e.g., row from a CSV file).",
    parameters=dict(
        r="Record (e.g. CSV row) to parse",
        exp_num_fields=("The expected number of data fields (e.g., columns) in the record"),
    ),
    returns="""
        A pair of values in which the first element represents a locus spot's trace ID and timepoint,
        and the second element represents the (z, y, x) coordinates of the centroid of the spot fit.
    """,
)
def parse_simple_record(r: CsvRow, *, exp_num_fields: int) -> "PointRecord":
    """Parse a single line from an input CSV file."""
    if not isinstance(r, list):
        raise TypeError(f"Record to parse must be list, not {type(r).__name__}")
    if len(r) != exp_num_fields:
        raise ValueError(f"Expected record of length {exp_num_fields} but got {len(r)}: {r}")
    trace = TraceId(int(r[InputFileColumn.TRACE.get]))
    timepoint = Timepoint(int(r[InputFileColumn.TIMEPOINT.get]))
    z = float(r[InputFileColumn.Z.get])
    y = float(r[InputFileColumn.Y.get])
    x = float(r[InputFileColumn.X.get])
    point = ImagePoint3D(z=z, y=y, x=x)
    return PointRecord(trace_id=trace, timepoint=timepoint, point=point)


class InputFileColumn(Enum):
    """Indices of the different columns to parse as particular fields"""

    TRACE = 0
    TIMEPOINT = 1
    Z = 2
    Y = 3
    X = 4
    QC = 5

    @property
    def get(self) -> int:
        """Alias for the value of this enum member"""
        return self.value
