"""Tests for which dragged folders the reader accepts, and where it finds the files for the layers."""

import logging
from pathlib import Path
from typing import Literal

import pytest
import zarr

from looptrace_loci_vis._const import (
    LOCUS_SPOT_QC_FILTERING_BLOCK_SUFFIX as QC_FILTERING_BLOCK_SUFFIX,
)
from looptrace_loci_vis._const import (
    LOCUS_SPOT_VISUALISATION_BLOCK_SUFFIX as VISUALISATION_BLOCK_SUFFIX,
)
from looptrace_loci_vis.reader import QCStatus, get_reader

VISUALISATION_BLOCK = "B19_LOCUS_SPOT_VISUALISATION"
QC_FILTERING_BLOCK = "B17_LOCUS_SPOT_QC_FILTERING"

# Before looptrace v0.24.0, the folder name is <fov>__<region name>, and just <fov>__
# when the region has no name.
KEYS = ["P0001__Chr2a", "P0001__"]
# From looptrace v0.24.0, the folder name is <fov>, and <fov>.TG_<group> for a trace group.
CURRENT_KEYS = ["P0001", "P0001.TG_g"]


CSV_LINES = {
    QCStatus.PASS: [
        "regionTime,traceId,locusTime,traceIndex,regionIndex,timeIndex,z,y,x",
        "83,1,1,0,0,0,8.2,16.7,8.7",
        "83,1,5,0,0,1,9.0,15.0,10.5",
    ],
    QCStatus.FAIL: [
        "regionTime,traceId,locusTime,traceIndex,regionIndex,timeIndex,z,y,x,failCode",
        "83,1,3,0,0,1,9.7,15.8,8.8,z",
    ],
}


def write_zarr(folder: Path, key: str, *, zarr_format: Literal[2, 3] = 2) -> None:
    """Write the image as looptrace publishes it: a ZARR array inside a folder that is a ZARR group.

    The store is in the given zarr format, 2 unless told otherwise.
    """
    root = zarr.open_group(str(folder), mode="a", zarr_format=zarr_format)
    root.zeros(name=f"{key}.zarr", shape=(1, 1, 2, 12, 24, 24), dtype="uint16")


def write_csv_lines(folder: Path, key: str, status: QCStatus) -> None:
    lines = CSV_LINES[status]
    (folder / f"{key}.qc{status.value}.csv").write_text("\n".join(lines) + "\n")


def write_zarr_with_array_at_0(
    folder: Path, key: str, *, zarr_format: Literal[2, 3]
) -> None:
    """Write the image as a ZARR group whose array is its member ``0``, the other layout read."""
    group = zarr.open_group(
        str(folder / f"{key}.zarr"), mode="a", zarr_format=zarr_format
    )
    group.zeros(name="0", shape=(1, 1, 2, 12, 24, 24), dtype="uint16")


def write_csvs(folder: Path, key: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    write_csv_lines(folder=folder, key=key, status=QCStatus.PASS)
    write_csv_lines(folder=folder, key=key, status=QCStatus.FAIL)


def get_expected_layer_types(qc_statuses: list[QCStatus]) -> list[str]:
    points_layer_names: list[str]
    if qc_statuses == []:
        points_layer_names = []
    elif qc_statuses in ([QCStatus.PASS], [QCStatus.FAIL]):
        points_layer_names = ["points"]
    elif len(qc_statuses) == 2 and set(qc_statuses) == {QCStatus.PASS, QCStatus.FAIL}:  # noqa: PLR2004
        points_layer_names = ["points", "points"]
    else:
        raise ValueError(f"Unexpected QC statuses: {qc_statuses}")
    return ["image", *points_layer_names]


@pytest.mark.parametrize("key", KEYS)
def test_visualisation_with_no_qc_filtering_folder_is_not_read(
    tmp_path: Path, key: str, caplog: pytest.LogCaptureFixture
):
    dragged = tmp_path / VISUALISATION_BLOCK / key
    write_zarr(dragged, key)

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    exp_msg = f"Not exactly 1 QC filtering folder, but rather 0, found for {dragged}"
    assert exp_msg in caplog.text


@pytest.mark.parametrize("zarr_format", [2, 3])
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize(
    "fail_statuses_to_write",
    [[QCStatus.PASS], [QCStatus.FAIL], [QCStatus.PASS, QCStatus.FAIL]],
    ids=["pass-only", "fail-only", "pass-and-fail"],
)
def test_visualisation_folder_with_csvs_from_qc_filtering_block_is_read(
    tmp_path: Path,
    key: str,
    fail_statuses_to_write: list[QCStatus],
    zarr_format: Literal[2, 3],
):
    dragged = tmp_path / VISUALISATION_BLOCK / key
    write_zarr(dragged, key, zarr_format=zarr_format)
    qc_filtering_block_folder = tmp_path / QC_FILTERING_BLOCK / key
    qc_filtering_block_folder.mkdir(parents=True, exist_ok=True)
    for qc_status in fail_statuses_to_write:
        write_csv_lines(folder=qc_filtering_block_folder, key=key, status=qc_status)

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    expected_layer_types = get_expected_layer_types(fail_statuses_to_write)
    assert [layer_type for _, _, layer_type in layers] == expected_layer_types


@pytest.mark.parametrize("zarr_format", [2, 3])
@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize(
    "fail_statuses_to_write",
    [[QCStatus.PASS], [QCStatus.FAIL], [QCStatus.PASS, QCStatus.FAIL]],
    ids=["pass-only", "fail-only", "pass-and-fail"],
)
def test_folder_directly_containing_zarr_any_nonempty_subset_of_expected_csvs_is_read(
    tmp_path: Path,
    key: str,
    fail_statuses_to_write: list[QCStatus],
    zarr_format: Literal[2, 3],
):
    dragged = tmp_path / key
    write_zarr(dragged, key, zarr_format=zarr_format)
    for qc_status in fail_statuses_to_write:
        write_csv_lines(folder=dragged, key=key, status=qc_status)

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    expected_layer_types = get_expected_layer_types(fail_statuses_to_write)
    assert [layer_type for _, _, layer_type in layers] == expected_layer_types


@pytest.mark.parametrize("key", CURRENT_KEYS)
@pytest.mark.parametrize(
    "statuses_to_write",
    [[QCStatus.PASS], [QCStatus.FAIL], [QCStatus.PASS, QCStatus.FAIL]],
    ids=["pass-only", "fail-only", "pass-and-fail"],
)
def test_visualisation_folder_holding_its_own_csvs_is_read(
    tmp_path: Path, key: str, statuses_to_write: list[QCStatus]
):
    """From looptrace v0.24.0, the CSVs are beside the ZARR, and the QC filtering block holds no folder per field of view."""
    dragged = tmp_path / VISUALISATION_BLOCK / key
    write_zarr(dragged, key)
    for qc_status in statuses_to_write:
        write_csv_lines(folder=dragged, key=key, status=qc_status)
    qc_filtering_block = tmp_path / QC_FILTERING_BLOCK
    qc_filtering_block.mkdir()
    (qc_filtering_block / "run.traces.enriched.filtered.csv").write_text("traceId\n")

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    expected_layer_types = get_expected_layer_types(statuses_to_write)
    assert [layer_type for _, _, layer_type in layers] == expected_layer_types


def test_visualisation_folder_holding_its_own_csvs_takes_no_csvs_from_qc_filtering_block(
    tmp_path: Path,
):
    """The folder's own CSVs are what it shows, even beside a QC filtering folder of the same name."""
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001"
    write_zarr(dragged, "P0001")
    write_csv_lines(folder=dragged, key="P0001", status=QCStatus.PASS)
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0001", "P0001")

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    assert [layer_type for _, _, layer_type in layers] == ["image", "points"]


@pytest.mark.parametrize("missing", [QCStatus.PASS, QCStatus.FAIL])
def test_a_missing_csv_is_warned_about(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, missing: QCStatus
):
    """Without the warning, a missing layer looks just like a field of view with no spots of that status."""
    dragged = tmp_path / "P0001"
    write_zarr(dragged, "P0001")
    present = QCStatus.PASS if missing == QCStatus.FAIL else QCStatus.FAIL
    write_csv_lines(folder=dragged, key="P0001", status=present)

    with caplog.at_level(logging.WARNING):
        reader = get_reader(dragged)

    assert reader is not None
    assert f"No QC {missing.value} CSV" in caplog.text
    assert str(dragged) in caplog.text


@pytest.mark.parametrize("in_visualisation_block", [False, True])
def test_folder_with_a_zarr_and_no_csv_is_refused(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    in_visualisation_block: bool,  # noqa: FBT001
):
    """A ZARR alone gives no points to show, and may well be another plugin's to read."""
    dragged = (
        tmp_path / VISUALISATION_BLOCK / "P0001"
        if in_visualisation_block
        else tmp_path / "P0001"
    )
    write_zarr(dragged, "P0001")
    # Even a same-named QC filtering folder doesn't help if it holds no CSV.
    (tmp_path / QC_FILTERING_BLOCK / "P0001").mkdir(parents=True)

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    assert "Neither a QC pass nor a QC fail CSV found for key 'P0001'" in caplog.text
    # A folder that's refused isn't warned about, as napari may ask about any folder.
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.parametrize("zarr_format", [2, 3])
def test_zarr_holding_its_array_at_0_is_read(
    tmp_path: Path, zarr_format: Literal[2, 3]
):
    dragged = tmp_path / "P0001"
    write_zarr_with_array_at_0(dragged, "P0001", zarr_format=zarr_format)
    write_csvs(dragged, "P0001")

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    assert [layer_type for _, _, layer_type in layers] == ["image", "points", "points"]
    image_layer = layers[0]
    assert image_layer[2] == "image"
    assert image_layer[0].shape == (1, 1, 2, 12, 24, 24)


@pytest.mark.parametrize("empty_status", ["pass", "fail"])
def test_qc_csv_with_only_its_header_gives_an_empty_points_layer(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, empty_status: str
):
    """A field of view where every spot passed QC, or every spot failed, has a CSV with no rows."""
    dragged = tmp_path / "P0001"
    write_zarr(dragged, "P0001")
    write_csvs(dragged, "P0001")
    empty_csv = dragged / f"P0001.qc{empty_status}.csv"
    header = empty_csv.read_text().splitlines()[0]
    empty_csv.write_text(header + "\n")

    reader = get_reader(dragged)

    assert reader is not None
    with caplog.at_level(logging.WARNING):
        layers = reader(dragged)
    assert [layer_type for _, _, layer_type in layers] == ["image", "points", "points"]
    # The reader gives the QC-fail layer before the QC-pass one.
    _, (failures, _, _), (successes, _, _) = layers
    assert (len(failures) == 0) == (empty_status == "fail")
    assert (len(successes) == 0) == (empty_status == "pass")
    assert str(empty_csv) in caplog.text


def test_folder_whose_zarr_is_a_file_is_refused(tmp_path: Path):
    """get_reader is how napari asks whether the plugin reads a path, so it should decline, not fail."""
    dragged = tmp_path / "P0001"
    write_csvs(dragged, "P0001")
    (dragged / "P0001.zarr").write_bytes(b"not a ZARR store")

    assert get_reader(dragged) is None


def test_qc_csv_that_is_a_folder_is_left_out_like_a_missing_one(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """Not a CSV, so it gives no layer; the other CSV still does, as for a missing CSV."""
    dragged = tmp_path / "P0001"
    write_zarr(dragged, "P0001")
    write_csvs(dragged, "P0001")
    csv = dragged / "P0001.qcpass.csv"
    csv.unlink()
    csv.mkdir()

    with caplog.at_level(logging.WARNING):
        reader = get_reader(dragged)

    assert reader is not None
    assert [layer_type for _, _, layer_type in reader(dragged)] == ["image", "points"]
    assert "No QC pass CSV" in caplog.text


def test_visualisation_folder_without_same_named_qc_filtering_folder_is_refused(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0002__Chr2a", "P0002__Chr2a")

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    exp_msg = f"Not exactly 1 QC filtering folder, but rather 0, found for {dragged}"
    assert exp_msg in caplog.text


def test_qc_filtering_folder_is_refused(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    write_zarr(tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a", "P0001__Chr2a")
    dragged = tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a"
    write_csvs(dragged, "P0001__Chr2a")

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    exp_msg = (
        "After accounting for spot points' CSVs, no path remains to parse as image data"
    )
    assert exp_msg in caplog.text


def test_refusing_the_qc_filtering_folder_names_the_one_to_drop(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """The likeliest mistake, so the refusal should not merely count files.

    Somebody looking for QC results clicks the QC filtering block first, and both
    halves of the pair refuse with "Not exactly 3 files" -- true of either, and
    no help in choosing.
    """
    write_zarr(tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a", "P0001__Chr2a")
    dragged = tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a"
    write_csvs(dragged, "P0001__Chr2a")

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    assert VISUALISATION_BLOCK_SUFFIX in caplog.text
    assert "P0001__Chr2a' folder of the" in caplog.text


def test_refusing_a_visualisation_folder_says_the_qc_block_is_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """The other half: the search happened and found nothing, which the refusal should say."""
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    assert QC_FILTERING_BLOCK_SUFFIX in caplog.text
    assert "none does" in caplog.text


def test_refusal_counts_the_qc_blocks_it_actually_found(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    """Saying none was found would be false when several were; the message shares the search."""
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(
        tmp_path / "B17_LOCUS_SPOT_QC_FILTERING" / "P0001__Chr2a", "P0001__Chr2a"
    )
    write_csvs(
        tmp_path / "B18_LOCUS_SPOT_QC_FILTERING" / "P0001__Chr2a", "P0001__Chr2a"
    )

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    assert "but 2 do" in caplog.text
    assert "B17_LOCUS_SPOT_QC_FILTERING" in caplog.text
    assert "B18_LOCUS_SPOT_QC_FILTERING" in caplog.text


def test_qc_filtering_block_is_not_searched_from_outside_visualisation_block(
    tmp_path: Path,
):
    dragged = tmp_path / "copied" / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a", "P0001__Chr2a")

    assert get_reader(dragged) is None


def test_more_than_one_qc_filtering_block_is_refused(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
):
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    csv_folder_1 = tmp_path / "B17_LOCUS_SPOT_QC_FILTERING" / "P0001__Chr2a"
    csv_folder_2 = tmp_path / "B18_LOCUS_SPOT_QC_FILTERING" / "P0001__Chr2a"
    write_csvs(csv_folder_1, "P0001__Chr2a")
    write_csvs(csv_folder_2, "P0001__Chr2a")

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    exp_msg = f"Not exactly 1 QC filtering folder, but rather 2, found for {dragged}:"
    assert exp_msg in caplog.text
    assert str(csv_folder_1) in caplog.text
    assert str(csv_folder_2) in caplog.text


def test_points_are_outlined_by_the_names_napari_uses_since_0_5(tmp_path: Path):
    # napari 0.5 renamed the Points layer's edge_* arguments to border_*, and refuses the old ones since.
    dragged = tmp_path / "P0001"
    write_zarr(dragged, "P0001")
    write_csvs(dragged, "P0001")

    reader = get_reader(dragged)

    assert reader is not None
    for _, params, layer_type in reader(dragged):
        if layer_type != "points":
            continue
        assert {"border_width", "border_width_is_relative", "border_color"} <= set(
            params
        )
        assert not any(name.startswith("edge_") for name in params)
