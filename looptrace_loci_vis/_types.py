"""Type aliases used broadly"""

from collections.abc import Callable
from pathlib import Path
from typing import Literal, Union

from gertils.geometry import ZCoordinate
from gertils.types import PixelArray

FlatPointRecord = list[Union[float, ZCoordinate]]
LayerParams = dict[str, object]
ImageLayer = tuple[PixelArray, LayerParams, Literal["image"]]
PointsLayer = tuple[list[FlatPointRecord], LayerParams, Literal["points"]]
PathLike = str | Path
PathOrPaths = PathLike | list[PathLike]
QCFailReasons = str
Reader = Callable[[PathLike], list[ImageLayer | PointsLayer]]
