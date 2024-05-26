from numpydoc_decorator import doc

from gertils.geometry import ImagePoint3D
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId

from .point_record import PointRecord, expand_along_z
from ._types import LayerParams, QCFailReasons

CsvRow = list[str]


@doc(
    summary="Parse records from points which passed QC.",
    parameters=dict(rows="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates,
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_passed(  # noqa: D103
    rows: list[CsvRow],
) -> tuple[list["PointRecord"], list[bool], LayerParams]:
    records = [parse_simple_record(r, exp_num_fields=5) for r in rows]
    max_z = max(r.get_z_coordinate() for r in records)
    points: list["PointRecord"] = []
    center_flags: list[bool] = []
    for rec in records:
        new_points, new_flags = expand_along_z(rec, z_max=max_z)
        points.extend(new_points)
        center_flags.extend(new_flags)
    sizes = [1.5 if is_center else 1.0 for is_center in center_flags]
    return points, center_flags, {"size": sizes}


@doc(
    summary="Parse records from points which failed QC.",
    parameters=dict(rows="Records to parse"),
    returns="""
        A pair in which the first element is the array-like of points coordinates,
        and the second element is the mapping from attribute name to list of values (1 per point).
    """,
    notes="https://napari.org/stable/plugins/guides.html#layer-data-tuples",
)
def parse_failed(  # noqa: D103
    rows: list[CsvRow],
) -> tuple[list["PointRecord"], list[bool], LayerParams]:
    record_qc_pairs: list[tuple[PointRecord, QCFailReasons]] = []
    for row in rows:
        try:
            qc = row[InputFileColumn.QC.get]
            rec = parse_simple_record(row, exp_num_fields=6)
        except IndexError:
            logging.exception("Bad row: %s", row)
            raise
        record_qc_pairs.append((rec, qc))
    max_z = max(r.get_z_coordinate() for r, _ in record_qc_pairs)
    points: list["PointRecord"] = []
    center_flags: list[bool] = []
    codes: list[QCFailReasons] = []
    for rec, qc in record_qc_pairs:
        new_points, new_flags = expand_along_z(rec, z_max=max_z)
        points.extend(new_points)
        center_flags.extend(new_flags)
        codes.extend([qc] * len(new_points))
    params = {
        "size": 0,  # Make the point invisible and just use text.
        "text": {
            "string": "{failCodes}",
            "color": DEEP_SKY_BLUE,
        },
        "properties": {"failCodes": codes},
    }
    return points, center_flags, params


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
