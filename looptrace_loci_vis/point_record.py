"""A single point's record in a file on disk."""

import dataclasses
from math import floor
from typing import Union, cast

import numpy as np
from gertils.geometry import ImagePoint3D
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId

from ._types import FlatPointRecord


@dataclasses.dataclass(frozen=True, kw_only=True)
class PointRecord:
    """Representation of a subpixel localization contextualized by 'placement' within imaging experiment.

    Parameters
    ----------
    trace_id : TraceIdFrom0
        ID of the trace with which the locus spot is associated.
    region_time : TimepointFrom0
        Regional barcode imaging timepoint.
    timepoint : TimepointFrom0
        Imaging timepoint in from which the point is coming.
    point : ImagePoint3D
        Coordinates of the centroid of the Gaussian fit to the spot image
        pixel data.

    """

    trace_id: TraceId
    region_time: Timepoint
    timepoint: Timepoint
    point: ImagePoint3D

    def __post_init__(self) -> None:
        # Checked at runtime, since callers may pass any type despite the annotations.
        bads: dict[str, object] = {}
        if not isinstance(cast("object", self.trace_id), TraceId):
            bads["trace ID"] = self.trace_id
        if not isinstance(cast("object", self.region_time), Timepoint):
            bads["region index"] = self.region_time
        if not isinstance(cast("object", self.timepoint), Timepoint):
            bads["time index"] = self.timepoint
        if not isinstance(cast("object", self.point), ImagePoint3D):
            bads["point"] = self.point
        if bads:
            messages = "; ".join(
                f"Bad type ({type(v).__name__}) for {k}" for k, v in bads.items()
            )
            raise TypeError(f"Cannot create point record: {messages}")

    def flatten(self) -> FlatPointRecord:
        """Create a simple list of components, as a row of layer data.

        Returns
        -------
        FlatPointRecord

        """
        return [
            self.trace_id.get,
            self.region_time.get,
            self.timepoint.get,
            self.point.z,
            self.point.y,
            self.point.x,
        ]

    def with_truncated_z(self) -> "PointRecord":
        """Round point position to nearest z-slice.

        Returns
        -------
        PointRecord

        """
        new_z: int = floor(self.point.z)
        result: PointRecord = self.with_new_z(new_z)
        return result

    def with_new_z(self, z: int) -> "PointRecord":
        """Replace this instance's point with a copy with updated z.

        Parameters
        ----------
        z : int
            New z-coordinate value.

        Returns
        -------
        PointRecord

        """
        pt = ImagePoint3D(x=self.point.x, y=self.point.y, z=z)
        return dataclasses.replace(self, point=pt)


def expand_along_z(
    r: PointRecord, *, z_max: Union[float, np.float64]
) -> tuple[list[PointRecord], list[bool]]:
    """Create ancillary points from main point.

    Parameters
    ----------
    r : PointRecord
        The record to expand along z-axis.
    z_max : float or float64
        The maximum z-coordinate.

    Returns
    -------
    tuple[list of PointRecord, list of bool]
        List of layer data rows to represent the original point along entire
        length of z-axis, paired with flag for each row indicating whether
        it's true center or not.

    """
    # Checked at runtime, since callers may pass any type despite the annotation.
    # np.float64 is a subclass of float.
    if not isinstance(cast("object", z_max), int | float):
        raise TypeError(f"Bad type for z_max: {type(z_max).__name__}")

    r = r.with_truncated_z()
    z_center: int = int(r.point.z)
    z_top: int = floor(z_max)

    # Check that max z and center z make sense together.
    if z_top < z_center:
        raise ValueError(f"Max z must be at least as great as central z ({z_center})")

    # Build the records and flags of where the center in z really is.
    predecessors = [(r.with_new_z(i), False) for i in range(z_center)]
    successors = [(r.with_new_z(i), False) for i in range(z_center + 1, z_top + 1)]
    pairs = [*predecessors, (r, True), *successors]
    points = [point for point, _ in pairs]
    center_flags = [is_center for _, is_center in pairs]

    # Each record should give rise to a total of 1 + z_max records, since numbering from 0.
    if len(points) != 1 + z_top:
        raise RuntimeError(
            f"Number of points generated from single spot center isn't as expected! Point={r}, z_max={z_top}, len(points)={len(points)}"
        )
    return points, center_flags
