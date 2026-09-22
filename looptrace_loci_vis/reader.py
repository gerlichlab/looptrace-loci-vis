"""Reading locus-specific spots and points data from looptrace for visualisation in napari"""

import logging
import os
from enum import Enum
from pathlib import Path
from typing import Optional

from expression import Option
from expression.collections.seq import choose
from gertils.zarr_tools import read_zarr
from numpydoc_decorator import doc  # type: ignore[import-untyped]

from ._const import (
    LOCUS_SPOT_QC_FILTERING_BLOCK_SUFFIX,
    LOCUS_SPOT_VISUALISATION_BLOCK_SUFFIX,
    PointColor,
)
from ._types import (
    ImageLayer,
    LayerParams,
    PathLike,
    PathOrPaths,
    PointsLayer,
    QCFailReasons,
    Reader,
)
from .point_record import PointRecord, expand_along_z
from .points_parser import HeadedTraceTimePointParser, PointsParser


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


@doc(
    summary="Read and display locus-specific spots from looptrace.",
    parameters=dict(path="Path from which to parse layers"),
    raises=dict(RuntimeError="If collection of QC statuses inferred from files doesn't make sense"),
    returns="A function to create layers from folder path, if folder path is parsable",
)
def get_reader(path: PathOrPaths) -> Optional[Reader]:  # noqa: D103, C901, PLR0911, PLR0912
    if isinstance(path, str):
        path: Path = Path(path)  # type: ignore[no-redef]
    if not isinstance(path, Path):
        return _do_not_parse(path=path, why=f"Not a str or Path, but {type(path).__name__}")  # type: ignore[arg-type, func-returns-value, no-any-return]
    if not path.is_dir():
        return _do_not_parse(path=path, why="Not a folder/directory")  # type: ignore[func-returns-value, no-any-return]

    keyed_paths: dict[str, list[Path]] = _collect_keyed_paths(path)
    # A folder in looptrace's locus spot visualisation block holds only the ZARR;
    # the QC pass/fail CSVs are in the same-named folder of the QC filtering block.
    if not any(
        QCStatus.from_csv_path(fp) is not None for fps in keyed_paths.values() for fp in fps
    ):
        qc_folder: Optional[Path] = _find_qc_filtering_folder(path)
        if qc_folder is not None:
            for key, files in _collect_keyed_paths(qc_folder).items():
                keyed_paths.setdefault(key, []).extend(files)

    match list(keyed_paths.items()):
        case [(key, files)]:
            if path.name != key:
                return _do_not_parse(  # type: ignore[func-returns-value, no-any-return]
                    path=path,
                    why=f"Key ({key}) derived from folder contents doesn't match path name ({path.name})",
                )
            if len(files) != 3:  # noqa: PLR2004
                why = f"Not exactly 3 files, but rather {len(files)}, found for key '{key}'"
                hint: Optional[str] = _hint_at_the_folder_to_drop(path)
                if hint is not None:
                    why = f"{why}. {hint}"
                return _do_not_parse(path=path, why=why)  # type: ignore[func-returns-value, no-any-return]

            path_by_status = dict(
                choose(
                    lambda fp: Option.of_optional(QCStatus.from_csv_path(fp)).map(  # type: ignore[arg-type]
                        lambda status: (status, fp)
                    )
                )(files)
            )
            try:
                fail_path = path_by_status.pop(QCStatus.FAIL)
                pass_path = path_by_status.pop(QCStatus.PASS)
            except KeyError:
                return _do_not_parse(  # type: ignore[func-returns-value, no-any-return]
                    path=path,
                    why=f"Could not find 1 each of QC status (pass/fail); path by status: {path_by_status}",
                )
            if len(path_by_status) != 0:  # after popping out the required key-value pairs
                raise RuntimeError(f"Extra QC status/path pairs! {path_by_status}")
            left_to_match = [f for f in files if f not in [fail_path, pass_path]]
            if (
                len(left_to_match) != 1
            ):  # Now there should be exactly the single .zarr path remaining.
                raise RuntimeError(
                    f"Nonsense! After finding 2 QC files among 3 files of interest, only 1 should remain but got {len(left_to_match)}: {left_to_match}"
                )
            potential_zarr: Path = left_to_match[0]
            if potential_zarr.suffix != ".zarr" or potential_zarr.name.removesuffix(".zarr") != key:
                return _do_not_parse(path=path, why=f"Could not find ZARR for key '{key}'")  # type: ignore[func-returns-value, no-any-return]

            def parse(_):  # type: ignore[no-untyped-def] # noqa: ANN202 ANN001
                image_layer: ImageLayer = (read_zarr(potential_zarr), {}, "image")
                failures_layer: PointsLayer = build_single_file_points_layer(fail_path)
                successes_layer: PointsLayer = build_single_file_points_layer(pass_path)
                return [image_layer, failures_layer, successes_layer]

            return parse

        case _:
            return _do_not_parse(  # type: ignore[func-returns-value, no-any-return]
                path=path,
                why=f"Not exactly 1 key, but rather {len(keyed_paths)} keys, were found: {', '.join(keyed_paths.keys())}",
            )


def _collect_keyed_paths(folder: Path) -> dict[str, list[Path]]:
    """Group the ZARR and QC pass/fail CSV paths directly in the given folder by filename prefix."""
    keyed_paths: dict[str, list[Path]] = {}
    for curr_path in folder.iterdir():
        message: Optional[str] = None
        for suffix in (".zarr", *(qc.filename_extension for qc in QCStatus)):
            if not curr_path.name.endswith(suffix):
                continue
            key: str = curr_path.name.removesuffix(suffix)
            if suffix == ".zarr" and curr_path.is_dir():
                message = f"Accepting ZARR data folder ({key}): {curr_path}"
            elif curr_path.is_file():
                message = f"Accepting data file ({key}): {curr_path}"
            if message is None:
                raise RuntimeError(f"Unexpected path! {curr_path}")
            logging.debug(message)
            keyed_paths.setdefault(key, []).append(curr_path)
    return keyed_paths


def _qc_filtering_candidates(folder: Path) -> list[Path]:
    """The same-named folders under a QC filtering block beside the given folder's block.

    One definition, used both to find the CSVs and to say what was found when the
    count is not 1, so a refusal cannot describe a different search than the one
    that ran.
    """
    return [
        block / folder.name
        for block in folder.parent.parent.iterdir()
        if block.name.endswith(LOCUS_SPOT_QC_FILTERING_BLOCK_SUFFIX)
        and (block / folder.name).is_dir()
    ]


def _find_qc_filtering_folder(folder: Path) -> Optional[Path]:
    """Find the same-named folder in the QC filtering block beside the visualisation block holding the given folder."""
    # Deliberately one-directional: visualisation -> QC filtering, never the
    # reverse. The image is what the points are drawn on and what napari orders
    # first, so the visualisation folder is the one to drop, and there is exactly
    # one way to be wrong about it. The mirror search would be the same lines
    # with the suffixes swapped; it is left out so there is one story and one set
    # of failure modes, and a QC filtering folder gets told where to go instead.
    if not folder.parent.name.endswith(LOCUS_SPOT_VISUALISATION_BLOCK_SUFFIX):
        return None
    candidates: list[Path] = _qc_filtering_candidates(folder)
    if len(candidates) != 1:
        logging.debug(
            "Not exactly 1 QC filtering folder, but rather %d, found for %s: %s",
            len(candidates),
            folder,
            candidates,
        )
        return None
    return candidates[0]


def _hint_at_the_folder_to_drop(folder: Path) -> Optional[str]:
    """Name the folder to drop, when the one dropped is the wrong half of a pair.

    One field of view's data is split across two looptrace blocks: the image in
    ``*_LOCUS_SPOT_VISUALISATION``, the QC pass/fail CSVs in the same-named
    folder under ``*_LOCUS_SPOT_QC_FILTERING``. Only the visualisation folder can
    be dropped, because only that direction is searched.

    Without this, both halves refuse with "Not exactly 3 files", which is true of
    either and says nothing about which one to use. That matters most for the QC
    filtering folder, since it is where somebody looking for QC results will
    click first.
    """
    parent: str = folder.parent.name
    if parent.endswith(LOCUS_SPOT_QC_FILTERING_BLOCK_SUFFIX):
        return (
            "This is the QC filtering folder, which holds only the CSVs; drop the"
            f" '{folder.name}' folder of the {LOCUS_SPOT_VISUALISATION_BLOCK_SUFFIX}"
            " block instead, and these CSVs will be picked up from here"
        )
    if parent.endswith(LOCUS_SPOT_VISUALISATION_BLOCK_SUFFIX):
        candidates: list[Path] = _qc_filtering_candidates(folder)
        found: str = (
            "none does"
            if not candidates
            else f"but {len(candidates)} do: {', '.join(c.parent.name for c in candidates)}"
        )
        return (
            "The QC pass/fail CSVs are not here but in the QC filtering block:"
            f" exactly one {LOCUS_SPOT_QC_FILTERING_BLOCK_SUFFIX} block holding a"
            f" '{folder.name}' folder must sit beside '{parent}', {found}"
        )
    return None


def build_single_file_points_layer(path: PathLike) -> PointsLayer:
    """Build the parser for a single file (ZARR or CSV relevant for locus points viewing)."""
    static_params = {
        "edge_width": 0.1,
        "edge_width_is_relative": True,
        "n_dimensional": False,
    }

    qc = QCStatus.from_csv_path(path)

    # Determine how to read and display the points layer to be parsed.
    # First, determine the parsing strategy based on file header.
    parser: PointsParser[PathLike]
    if _has_header(path):
        logging.debug("Will parse has having header: %s", path)
        parser = HeadedTraceTimePointParser
    else:
        raise NotImplementedError("Parsing headerless CSV is no longer supported (v0.3.0).")
    # Then, determine the functions to used based on inferred QC status.
    if qc == QCStatus.PASS:
        logging.debug("Will parse sas QC-pass: %s", path)
        color = PointColor.GOLDENROD
        read_file = parser.parse_all_qcpass
        process_records = records_to_qcpass_layer_data
    elif qc == QCStatus.FAIL:
        logging.debug("Will parse as QC-fail: %s", path)
        color = PointColor.DEEP_SKY_BLUE
        read_file = parser.parse_all_qcfail  # type: ignore[assignment]
        process_records = records_to_qcfail_layer_data  # type: ignore[assignment]
    else:
        _do_not_parse(path=path, why="Could not infer QC status", level=logging.ERROR)
        raise ValueError(
            f"Despite undertaking parse, file from which QC status could not be parsed was encountered: {path}"
        )

    # Use the information gleaned from filename and from file header to determine point color and to read data.
    color_meta = {"edge_color": color.value, "face_color": color.value}
    base_point_records = read_file(path)
    point_records, center_flags, extra_meta = process_records(base_point_records)

    if not point_records:
        logging.warning("No data rows parsed!")
    shape_meta = {"symbol": ["*" if is_center else "o" for is_center in center_flags]}
    params = {**static_params, **color_meta, **extra_meta, **shape_meta}

    return [pt_rec.flatten() for pt_rec in point_records], params, "points"


def records_to_qcpass_layer_data(
    records: list[PointRecord],
) -> tuple[list[PointRecord], list[bool], LayerParams]:
    """Extend the given records partially through a z-stack, designate appropriately as central-plane or not."""
    max_z = max(r.point.z for r in records)
    points: list[PointRecord] = []
    center_flags: list[bool] = []
    for rec in records:
        new_points, new_flags = expand_along_z(rec, z_max=max_z)
        points.extend(new_points)
        center_flags.extend(new_flags)
    sizes = [1.5 if is_center else 1.0 for is_center in center_flags]
    return points, center_flags, {"size": sizes}


def records_to_qcfail_layer_data(
    record_qc_pairs: list[tuple[PointRecord, QCFailReasons]],
) -> tuple[list[PointRecord], list[bool], LayerParams]:
    """Extend the given records partially through a z-stack, designate appropriately as central-plane or not; also set fail codes text."""
    max_z = max(r.point.z for r, _ in record_qc_pairs)
    points: list[PointRecord] = []
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
            "color": PointColor.DEEP_SKY_BLUE.value,
        },
        "properties": {"failCodes": codes},
    }
    return points, center_flags, params


def _do_not_parse(*, path: PathLike, why: str, level: int = logging.DEBUG) -> None:
    """Log a message about why a path can't be parsed."""
    logging.log(
        level,
        "%s, cannot be read as looptrace locus-specific points: %s",
        why,
        path,
    )


def _has_header(path: PathLike) -> bool:
    with open(path) as fh:  # noqa: PTH123
        header = fh.readline()
    return HeadedTraceTimePointParser.TIME_INDEX_COLUMN in header
