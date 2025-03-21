"""A single point's record in a file on disk."""

import dataclasses
from math import floor
from typing import Union

import numpy as np
from gertils.geometry import ImagePoint3D, LocatableXY, LocatableZ, ZCoordinate
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId
from numpydoc_decorator import doc  # type: ignore[import-untyped]

from ._types import FlatPointRecord


@doc(
    summary="Representation of a subpixel localization contextualized by 'placement' within imaging experiment",
    parameters=dict(
        trace_id="ID of the trace with which the locus spot is associated",
        region_time="Regional barcode imaging timepoint",
        timepoint="Imaging timepoint in from which the point is coming",
        point="Coordinates of the centroid of the Gaussian fit to the spot image pixel data",
    ),
)
@dataclasses.dataclass(frozen=True, kw_only=True)
class PointRecord(LocatableXY, LocatableZ):  # noqa: D101
    trace_id: TraceId
    region_time: Timepoint
    timepoint: Timepoint
    point: ImagePoint3D

    def __post_init__(self) -> None:
        bads: dict[str, object] = {}
        if not isinstance(self.trace_id, TraceId):
            bads["trace ID"] = self.trace_id  # type: ignore[unreachable]
        if not isinstance(self.region_time, Timepoint):
            bads["region index"] = self.region_time  # type: ignore[unreachable]
        if not isinstance(self.timepoint, Timepoint):
            bads["time index"] = self.timepoint  # type: ignore[unreachable]
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
            self.region_time.get,
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
    z_center: int = int(r.get_z_coordinate())
    z_max: int = floor(z_max)  # type: ignore[no-redef]
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
