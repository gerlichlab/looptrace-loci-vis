"""Abstractions related to points parsing"""

import abc
from collections.abc import Iterable, Sized
from typing import Generic, Protocol, TypeVar

import pandas as pd
from gertils.geometry import ImagePoint3D
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId

from ._types import PathLike, QCFailReasons
from .point_record import PointRecord

Input = TypeVar("Input", contravariant=True)  # noqa: PLC0105
I1 = TypeVar("I1")
I2 = TypeVar("I2", bound=Sized)


class MappingLike(Sized, Protocol):  # noqa: D101
    @abc.abstractmethod
    def __getitem__(self, key: str, /) -> object: ...

    @abc.abstractmethod
    def __len__(self) -> int: ...


class PointsParser(Protocol, Generic[Input]):
    """Something capable of parsing a QC-pass or -fail CSV file"""

    @classmethod
    @abc.abstractmethod
    def parse_all_qcpass(cls, data: Input) -> list[PointRecord]: ...  # noqa: D102

    @classmethod
    @abc.abstractmethod
    def parse_all_qcfail(cls, data: Input) -> list[tuple[PointRecord, QCFailReasons]]: ...  # noqa: D102


class IterativePointsParser(Generic[I1, I2], PointsParser[I1]):
    """Something that yields records, each of type I2 from value of type I1, to parse QC-pass/-fail points"""

    @classmethod
    @abc.abstractmethod
    def _gen_records(cls, data: I1) -> Iterable[I2]: ...

    @classmethod
    @abc.abstractmethod
    def _parse_single_qcpass_record(cls, record: I2) -> PointRecord: ...

    @classmethod
    @abc.abstractmethod
    def _parse_single_qcfail_record(cls, record: I2) -> tuple[PointRecord, QCFailReasons]: ...

    @classmethod
    def parse_all_qcpass(cls, data: I1) -> list[PointRecord]:  # noqa: D102
        return [cls._parse_single_qcpass_record(r) for r in cls._gen_records(data)]

    @classmethod
    def parse_all_qcfail(cls, data: I1) -> list[tuple[PointRecord, QCFailReasons]]:  # noqa: D102
        return [cls._parse_single_qcfail_record(r) for r in cls._gen_records(data)]


class HeadedTraceTimePointParser(IterativePointsParser[PathLike, MappingLike]):
    """Something capable of parsing a headed CSV of QC-pass/-fail points records"""

    REGION_INDEX_COLUMN = "regionIndex"
    TIME_INDEX_COLUMN = "timeIndex"

    @classmethod
    def _gen_records(cls, data: PathLike) -> Iterable[MappingLike]:
        # pandas-stubs leaves parts of read_csv's signature and the type of each row unknown.
        frame: pd.DataFrame = pd.read_csv(data)  # pyright: ignore[reportUnknownMemberType]
        for _, row in frame.iterrows():  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            yield row

    @classmethod
    def _parse_single_qcpass_record(cls, record: MappingLike) -> PointRecord:
        # A cell is whatever scalar pandas read, so only int() and float() can tell
        # whether it converts.
        trace = TraceId(int(record["traceIndex"]))  # pyright: ignore[reportArgumentType]
        region_time = Timepoint(int(record[cls.REGION_INDEX_COLUMN]))  # pyright: ignore[reportArgumentType]
        timepoint = Timepoint(int(record[cls.TIME_INDEX_COLUMN]))  # pyright: ignore[reportArgumentType]
        z = float(record["z"])  # pyright: ignore[reportArgumentType]
        y = float(record["y"])  # pyright: ignore[reportArgumentType]
        x = float(record["x"])  # pyright: ignore[reportArgumentType]
        point = ImagePoint3D(z=z, y=y, x=x)
        return PointRecord(
            trace_id=trace, region_time=region_time, timepoint=timepoint, point=point
        )

    @classmethod
    def _parse_single_qcfail_record(cls, record: MappingLike) -> tuple[PointRecord, QCFailReasons]:
        """A fail record parses the same as a pass one, just with one additional field for QC fail reasons."""
        pt_rec = cls._parse_single_qcpass_record(record)
        fail_code = record["failCode"]
        if not isinstance(fail_code, str):
            raise TypeError(f"failCode is not str, but {type(fail_code).__name__}")
        return pt_rec, fail_code
