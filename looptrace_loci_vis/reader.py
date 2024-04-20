"""Reading locus-specific spots and points data from looptrace for visualisation in napari"""

import csv
import dataclasses
import logging
import os
from collections.abc import Callable
from enum import Enum
from math import floor
from pathlib import Path
from typing import Literal, Optional, Union

import numpy as np
from gertils.geometry import ImagePoint3D, LocatableXY, LocatableZ, ZCoordinate
from gertils.pathtools import find_multiple_paths_by_fov, get_fov_sort_key
from gertils.types import FieldOfViewFrom1, PixelArray
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId
from gertils.zarr_tools import read_zarr
from numpydoc_decorator import doc  # type: ignore[import-untyped]

__author__ = "Vince Reuter"
__credits__ = ["Vince Reuter"]

CsvRow = list[str]
FlatPointRecord = list[Union[float, ZCoordinate]]
LayerParams = dict[str, object]
ImageLayer = tuple[PixelArray, LayerParams, Literal["image"]]
PointsLayer = tuple[list[FlatPointRecord], LayerParams, Literal["points"]]
QCFailReasons = str
PathLike = str | Path
PathOrPaths = PathLike | list[PathLike]
Reader = Callable[[PathLike], list[ImageLayer | PointsLayer]]

# See: https://davidmathlogic.com/colorblind/
DEEP_SKY_BLUE = "#0C7BDC"
GOLDENROD = "#FFC20A"


class QCStatus(Enum):
    """Binary classification of QC status"""

    FAIL = "fail"
    PASS = "pass"  # noqa: S105

    @classmethod
    def from_csv_name(cls, fn: str) -> Optional["QCStatus"]:
        """Try to determine CSV status from given name of CSV file."""
        for qc in cls:
            if fn.endswith(qc.filename_extension):
                return qc
        return None

    @classmethod
    def from_csv_path(cls, fp: PathLike) -> Optional["QCStatus"]:
        """Try to determine CSV status from given path of CSV file."""
        return cls.from_csv_name(os.path.basename(fp))  # noqa: PTH119

    @property
    def filename_extension(self) -> str:  # noqa: D102
        return f".qc{self.value}.csv"


def do_not_parse(*, path: PathLike, why: str, level: int = logging.DEBUG) -> None:
    """Log a message about why a path can't be parsed."""
    logging.log(
        level,
        "%s, cannot be read as looptrace locus-specific points: %s",
        why,
        path,
    )


@doc(
    summary="Read and display locus-specific spots from looptrace.",
    parameters=dict(path="Path from which to parse layers"),
    raises=dict(RuntimeError="If collection of QC statuses inferred from files doesn't make sense"),
    returns="A function to create layers from folder path, if folder path is parsable",
)
def get_reader(path: PathOrPaths) -> Optional[Reader]:  # noqa: D103
    if not isinstance(path, str | Path):
        return None
    if not os.path.isdir(path):  # noqa: PTH112
        do_not_parse(path=path, why="Not a folder/directory")
        return None
    path_by_fov: dict[FieldOfViewFrom1, list[Path]] = find_multiple_paths_by_fov(
        path, extensions=(".zarr", *(qc.filename_extension for qc in QCStatus))
    )
    if len(path_by_fov) != 1:
        do_not_parse(
            path=path, why=f"Not exactly 1 FOV found, but rather {len(path_by_fov)}, found"
        )
        return None
    fov, files = next(iter(path_by_fov.items()))
    if len(files) != 3:  # noqa: PLR2004
        do_not_parse(
            path=path, why=f"Not exactly 3 files, but rather {len(files)}, found for {fov}"
        )
        return None
    path_by_status = {}
    for fp in files:
        qc = QCStatus.from_csv_path(fp)
        if qc is not None:
            path_by_status[qc] = fp
    try:
        fail_path = path_by_status.pop(QCStatus.FAIL)
        pass_path = path_by_status.pop(QCStatus.PASS)
    except KeyError:
        do_not_parse(path=path, why="Could not find 1 each of QC status (pass/fail)")
        return None
    if len(path_by_status) != 0:
        raise RuntimeError(f"Extra QC status/path pairs! {path_by_status}")
    left_to_match = [f for f in files if f not in [fail_path, pass_path]]
    if len(left_to_match) != 1:
        raise RuntimeError(
            f"Nonsense! After finding 2 QC files among 3 files of interest, only 1 should remain but got {len(left_to_match)}: {left_to_match}"
        )
    potential_zarr = left_to_match[0]
    if (
        potential_zarr.suffix != ".zarr"
        or get_fov_sort_key(potential_zarr, extension=".zarr") != fov
    ):
        do_not_parse(path=path, why=f"Could not find ZARR for FOV {fov}")
        return None

    def parse(_):  # type: ignore[no-untyped-def] # noqa: ANN202 ANN001
        image_layer: ImageLayer = (read_zarr(potential_zarr), {}, "image")
        failures_layer: PointsLayer = build_single_file_points_layer(fail_path)
        successes_layer: PointsLayer = build_single_file_points_layer(pass_path)
        return [image_layer, failures_layer, successes_layer]

    return parse


def build_single_file_points_layer(path: PathLike) -> PointsLayer:
    """Build the parser for a single file (ZARR or CSV relevant for locus points viewing)."""
    static_params = {
        "edge_width": 0.1,
        "edge_width_is_relative": True,
        "n_dimensional": False,
    }

    # Determine how to read and display the points layer to be parsed.
    qc = QCStatus.from_csv_path(path)
    if qc == QCStatus.PASS:
        logging.debug("Will parse sas QC-pass: %s", path)
        color = GOLDENROD
        read_rows = parse_passed
    elif qc == QCStatus.FAIL:
        logging.debug("Will parse as QC-fail: %s", path)
        color = DEEP_SKY_BLUE
        read_rows = parse_failed
    else:
        do_not_parse(path=path, why="Could not infer QC status", level=logging.ERROR)
        raise ValueError(
            f"Despite undertaking parse, file from which QC status could not be parsed was encountered: {path}"
        )

    base_meta = {"edge_color": color, "face_color": color}

    with open(path, newline="") as fh:  # noqa: PTH123
        rows = list(csv.reader(fh))
    point_records, center_flags, extra_meta = read_rows(rows)
    if not point_records:
        logging.warning("No data rows parsed!")
    shape_meta = {
        "symbol": ["*" if is_center else "o" for is_center in center_flags],
    }
    params = {**static_params, **base_meta, **extra_meta, **shape_meta}

    return [pt_rec.flatten() for pt_rec in point_records], params, "points"


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


@doc(
    summary="",
    parameters=dict(
        trace_id="ID of the trace with which the locus spot is associated",
        timepoint="Imaging timepoint in from which the point is coming",
        point="Coordinates of the centroid of the Gaussian fit to the spot image pixel data",
    ),
)
@dataclasses.dataclass(frozen=True, kw_only=True)
class PointRecord(LocatableXY, LocatableZ):  # noqa: D101
    trace_id: TraceId
    timepoint: Timepoint
    point: ImagePoint3D

    def __post_init__(self) -> None:
        bads: dict[str, object] = {}
        if not isinstance(self.trace_id, TraceId):
            bads["trace ID"] = self.trace_id  # type: ignore[unreachable]
        if not isinstance(self.timepoint, Timepoint):
            bads["timepoint"] = self.timepoint  # type: ignore[unreachable]
        if not isinstance(self.point, ImagePoint3D):
            bads["point"] = self.point  # type: ignore[unreachable]
        if bads:
            messages = "; ".join(f"Bad type ({type(v).__name__}) for {k}" for k, v in bads.items())
            raise TypeError(f"Cannot create point record: {messages}")

    @doc(summary="Flatten")
    def flatten(self) -> FlatPointRecord:
        """Create a simple list of components, as a row of layer data."""
        return [
            self.trace_id.get,
            self.timepoint.get,
            self.get_z_coordinate(),
            self.get_y_coordinate(),
            self.get_x_coordinate(),
        ]

    def get_x_coordinate(self) -> float:  # noqa: D102
        return self.point.x

    def get_y_coordinate(self) -> float:  # noqa: D102
        return self.point.y

    def get_z_coordinate(self) -> ZCoordinate:  # noqa: D102
        return self.point.z

    @doc(summary="Round point position to nearest z-slice")
    def with_truncated_z(self) -> "PointRecord":  # noqa: D102
        new_z: int = floor(self.get_z_coordinate())
        result: PointRecord = self.with_new_z(new_z)
        return result

    @doc(
        summary="Replace this instance's point with a copy with updated z.",
        parameters=dict(z="New z-coordinate value"),
    )
    def with_new_z(self, z: int) -> "PointRecord":  # noqa: D102
        pt = ImagePoint3D(x=self.point.x, y=self.point.y, z=z)
        return dataclasses.replace(self, point=pt)


@doc(
    summary="Create ancillary points from main point",
    parameters=dict(
        r="The record to expand along z-axis",
        z_max="The maximum z-coordinate",
    ),
    returns="""
        List of layer data rows to represent the original point along
        entire length of z-axis, paired with flag for each row
        indicating whether it's true center or not
    """,
)
def expand_along_z(  # noqa: D103
    r: PointRecord, *, z_max: Union[float, np.float64]
) -> tuple[list[PointRecord], list[bool]]:
    if not isinstance(z_max, int | float | np.float64):
        raise TypeError(f"Bad type for z_max: {type(z_max).__name__}")

    r = r.with_truncated_z()
    z_center = int(r.get_z_coordinate())
    z_max = int(floor(z_max))
    if not isinstance(z_center, int) or not isinstance(z_max, int):
        raise TypeError(
            f"Z center and Z max must be int; got {type(z_center).__name__} and"
            f" {type(z_max).__name__}"
        )

    # Check that max z and center z make sense together.
    if z_max < z_center:
        raise ValueError(f"Max z must be at least as great as central z ({z_center})")

    # Build the records and flags of where the center in z really is.
    predecessors = [(r.with_new_z(i), False) for i in range(z_center)]
    successors = [(r.with_new_z(i), False) for i in range(z_center + 1, z_max + 1)]
    points, params = zip(*[*predecessors, (r, True), *successors], strict=False)

    # Each record should give rise to a total of 1 + z_max records, since numbering from 0.
    if len(points) != 1 + z_max:
        raise RuntimeError(
            f"Number of points generated from single spot center isn't as expected! Point={r}, z_max={z_max}, len(points)={len(points)}"
        )
    return points, params  # type: ignore[return-value]


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
