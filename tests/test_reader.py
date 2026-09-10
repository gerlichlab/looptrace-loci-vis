"""Tests for which dragged folders the reader accepts, and where it finds the files for the layers."""

from pathlib import Path

import pytest
import zarr  # type: ignore[import-untyped]

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


def write_zarr(folder: Path, key: str) -> None:
    """Write the image as looptrace publishes it: a ZARR array inside a folder that is a ZARR group."""
    root = zarr.open_group(str(folder), mode="a")
    root.zeros(f"{key}.zarr", shape=(1, 1, 2, 12, 24, 24), dtype="uint16")


def write_csvs(folder: Path, key: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{key}.qcpass.csv").write_text("\n".join(QCPASS_LINES) + "\n")
    (folder / f"{key}.qcfail.csv").write_text("\n".join(QCFAIL_LINES) + "\n")


@pytest.mark.parametrize("key", KEYS)
def test_visualisation_folder_is_read_with_csvs_from_qc_filtering_block(tmp_path: Path, key: str):
    dragged = tmp_path / VISUALISATION_BLOCK / key
    write_zarr(dragged, key)
    write_csvs(tmp_path / QC_FILTERING_BLOCK / key, key)

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    assert [layer_type for _, _, layer_type in layers] == ["image", "points", "points"]


@pytest.mark.parametrize("key", KEYS)
def test_folder_holding_all_three_items_is_read(tmp_path: Path, key: str):
    dragged = tmp_path / key
    write_zarr(dragged, key)
    write_csvs(dragged, key)

    reader = get_reader(dragged)

    assert reader is not None
    layers = reader(dragged)
    assert [layer_type for _, _, layer_type in layers] == ["image", "points", "points"]


def test_visualisation_folder_without_same_named_qc_filtering_folder_is_refused(tmp_path: Path):
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0002__Chr2a", "P0002__Chr2a")

    assert get_reader(dragged) is None


def test_qc_filtering_folder_is_refused(tmp_path: Path):
    write_zarr(tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a", "P0001__Chr2a")
    dragged = tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a"
    write_csvs(dragged, "P0001__Chr2a")

    assert get_reader(dragged) is None


def test_qc_filtering_block_is_not_searched_from_outside_visualisation_block(tmp_path: Path):
    dragged = tmp_path / "copied" / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a", "P0001__Chr2a")

    assert get_reader(dragged) is None


def test_more_than_one_qc_filtering_block_is_refused(tmp_path: Path):
    dragged = tmp_path / VISUALISATION_BLOCK / "P0001__Chr2a"
    write_zarr(dragged, "P0001__Chr2a")
    write_csvs(tmp_path / QC_FILTERING_BLOCK / "P0001__Chr2a", "P0001__Chr2a")
    write_csvs(tmp_path / "B18_LOCUS_SPOT_QC_FILTERING" / "P0001__Chr2a", "P0001__Chr2a")

    assert get_reader(dragged) is None
