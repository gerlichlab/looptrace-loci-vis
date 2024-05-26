"""Reading locus-specific spots and points data from looptrace for visualisation in napari"""

import csv
import logging
import os
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Optional

from gertils.pathtools import find_multiple_paths_by_fov, get_fov_sort_key
from gertils.types import FieldOfViewFrom1
from gertils.zarr_tools import read_zarr
from numpydoc_decorator import doc  # type: ignore[import-untyped]

from ._parse_old_style_no_header import parse_failed, parse_passed
from ._types import ImageLayer, PathLike, PathOrPaths, PointsLayer, Reader


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
