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
from looptrace_loci_vis.reader import get_reader

VISUALISATION_BLOCK = "B19_LOCUS_SPOT_VISUALISATION"
QC_FILTERING_BLOCK = "B17_LOCUS_SPOT_QC_FILTERING"

# The folder name is <fov>__<region name>, and just <fov>__ when the region has no name.
KEYS = ["P0001__Chr2a", "P0001__"]

QCPASS_LINES = [
    "regionTime,traceId,locusTime,traceIndex,regionIndex,timeIndex,z,y,x",
    "83,1,1,0,0,0,8.2,16.7,8.7",
    "83,1,5,0,0,1,9.0,15.0,10.5",
]
QCFAIL_LINES = [
    "regionTime,traceId,locusTime,traceIndex,regionIndex,timeIndex,z,y,x,failCode",
    "83,1,3,0,0,1,9.7,15.8,8.8,z",
]


def write_zarr(folder: Path, key: str, *, zarr_format: Literal[2, 3] = 2) -> None:
    """Write the image as looptrace publishes it: a ZARR array inside a folder that is a ZARR group.

    The store is in the given zarr format, 2 unless told otherwise.
    """
    root = zarr.open_group(str(folder), mode="a", zarr_format=zarr_format)
    root.zeros(name=f"{key}.zarr", shape=(1, 1, 2, 12, 24, 24), dtype="uint16")


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
    (folder / f"{key}.qcpass.csv").write_text("\n".join(QCPASS_LINES) + "\n")
    (folder / f"{key}.qcfail.csv").write_text("\n".join(QCFAIL_LINES) + "\n")


@pytest.mark.parametrize("zarr_format", [2, 3])
@pytest.mark.parametrize("key", KEYS)
def test_visualisation_folder_is_read_with_csvs_from_qc_filtering_block(
    tmp_path: Path, key: str, zarr_format: Literal[2, 3]
):
    dragged = tmp_path / VISUALISATION_BLOCK / key
    write_zarr(dragged, key, zarr_format=zarr_format)
    write_csvs(tmp_path / QC_FILTERING_BLOCK / key, key)

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    assert [layer_type for _, _, layer_type in layers] == ["image", "points", "points"]


@pytest.mark.parametrize("zarr_format", [2, 3])
@pytest.mark.parametrize("key", KEYS)
def test_folder_holding_all_three_items_is_read(
    tmp_path: Path, key: str, zarr_format: Literal[2, 3]
):
    dragged = tmp_path / key
    write_zarr(dragged, key, zarr_format=zarr_format)
    write_csvs(dragged, key)

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    assert [layer_type for _, _, layer_type in layers] == ["image", "points", "points"]


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


@pytest.mark.parametrize("odd_path", ["zarr_is_a_file", "csv_is_a_folder"])
def test_folder_with_a_zarr_file_or_a_csv_folder_is_refused(
    tmp_path: Path, odd_path: str
):
    """get_reader is how napari asks whether the plugin reads a path, so it should decline, not fail."""
    dragged = tmp_path / "P0001"
    write_csvs(dragged, "P0001")
    if odd_path == "zarr_is_a_file":
        (dragged / "P0001.zarr").write_bytes(b"not a ZARR store")
    else:
        write_zarr(dragged, "P0001")
        csv = dragged / "P0001.qcpass.csv"
        csv.unlink()
        csv.mkdir()

    assert get_reader(dragged) is None


def test_visualisation_folder_without_same_named_qc_filtering_folder_is_refused(
    tmp_path: Path,
):
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0002__Chr2a", "P0002__Chr2a")

    assert get_reader(dragged) is None


def test_qc_filtering_folder_is_refused(tmp_path: Path):
    write_zarr(tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a", "P0001__Chr2a")
    dragged = tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a"
    write_csvs(dragged, "P0001__Chr2a")

    assert get_reader(dragged) is None


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
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a", "P0001__Chr2a")
    write_csvs(
        tmp_path / "B18_LOCUS_SPOT_QC_FILTERING" / "P0001__Chr2a", "P0001__Chr2a"
    )

    with caplog.at_level(logging.DEBUG):
        assert get_reader(dragged) is None
    assert "but 2 do" in caplog.text
    assert QC_FILTERING_BLOCK in caplog.text
    assert "B18_LOCUS_SPOT_QC_FILTERING" in caplog.text


def test_qc_filtering_block_is_not_searched_from_outside_visualisation_block(
    tmp_path: Path,
):
    dragged = tmp_path / "copied" / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a", "P0001__Chr2a")

    assert get_reader(dragged) is None


def test_more_than_one_qc_filtering_block_is_refused(tmp_path: Path):
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a", "P0001__Chr2a")
    write_csvs(
        tmp_path / "B18_LOCUS_SPOT_QC_FILTERING" / "P0001__Chr2a", "P0001__Chr2a"
    )

    assert get_reader(dragged) is None


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
