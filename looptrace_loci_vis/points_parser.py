"""Abstractions related to points parsing"""

from collections.abc import Iterable, Sized
import csv
from enum import Enum
from typing import Generic, Protocol, TypeVar

import pandas as pd

from gertils.geometry import ImagePoint3D
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId

from .point_record import PointRecord
from ._types import CsvRow, PathLike, QCFailReasons

Input = TypeVar("Input", contravariant=True)
I1 = TypeVar("I1")
I2 = TypeVar("I2", bound=Sized)


class MappingLike(Protocol):
    def __getitem__(key: str) -> object: ...


class PointsParser(Protocol, Generic[Input]):

    @classmethod
    def parse_all_qcpass(cls, data: Input) -> list[PointRecord]: ...
    
    @classmethod
    def parse_all_qcfail(cls, data: Input) -> list[tuple[PointRecord, QCFailReasons]]: ...


class IterativePointsParser(Generic[I1, I2], PointsParser[I1]):
    
    @classmethod
    def _gen_records(cls, data: I1) -> Iterable[I2]: ...

    @classmethod
    def _parse_single_qcpass_record(cls, record: I2) -> PointRecord: ...

    @classmethod
    def _parse_single_qcfail_record(cls, record: I2) -> tuple[PointRecord, QCFailReasons]: ...

    @classmethod
    def parse_all_qcpass(cls, data: I1) -> list[PointRecord]:
        return [cls._parse_single_qcpass_record(r) for r in cls._gen_records(data)]
    
    @classmethod
    def parse_all_qcfail(cls, data: I1) -> list[tuple[PointRecord, QCFailReasons]]:
        return [cls._parse_single_qcfail_record(r) for r in cls._gen_records(data)]


class HeadedTraceTimePointParser(IterativePointsParser[PathLike, MappingLike]):

    TIME_INDEX_COLUMN = "timeIndex"

    @classmethod
    def _gen_records(cls, data: PathLike) -> pd.DataFrame:
        return pd.read_csv(data)
    
    @classmethod
    def _parse_single_qcpass_record(cls, record: MappingLike) -> PointRecord:
        trace = TraceId(int(record["traceId"]))
        timepoint = Timepoint(int(record[cls.TIME_INDEX_COLUMN]))
        z = float(record["z"])
        y = float(record["y"])
        x = float(record["x"])
        point = ImagePoint3D(z=z, y=y, x=x)
        return PointRecord(trace_id=trace, timepoint=timepoint, point=point)

    @classmethod
    def _parse_single_qcfail_record(cls, record: MappingLike) -> tuple[PointRecord, QCFailReasons]:
        """A fail record parses the same as a pass one, just with one additional field for QC fail reasons."""
        pt_rec = cls._parse_single_qcpass_record(record)
        fail_code = record["failCode"]
        return pt_rec, fail_code


class HeadlessTraceTimePointParser(IterativePointsParser[PathLike, CsvRow]):
    """Parser for input file with no header, and field for trace ID and timepoint in addition to coordinates"""
    
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

    _number_of_columns = sum(1 for _ in InputFileColumn)

    @classmethod
    def _parse_single_record(cls, r: CsvRow, *, exp_len: int) -> PointRecord:
        if not isinstance(r, list):
            raise TypeError(f"Record to parse must be list, not {type(r).__name__}")
        if len(r) != exp_len:
            raise ValueError(f"Expected record of length {exp_len} but got {len(r)}: {r}")
        trace = TraceId(int(r[cls.InputFileColumn.TRACE.get]))
        timepoint = Timepoint(int(r[cls.InputFileColumn.TIMEPOINT.get]))
        z = float(r[cls.InputFileColumn.Z.get])
        y = float(r[cls.InputFileColumn.Y.get])
        x = float(r[cls.InputFileColumn.X.get])
        point = ImagePoint3D(z=z, y=y, x=x)
        return PointRecord(trace_id=trace, timepoint=timepoint, point=point)

    @classmethod
    def _gen_records(cls, data: PathLike) -> Iterable[CsvRow]:
        with open(data, newline="") as fh: # noqa: PTH123
            rows = list(csv.reader(fh))
        return rows
    
    @classmethod
    def _parse_single_qcpass_record(cls, record: CsvRow) -> PointRecord:
        return cls._parse_single_record(record, exp_len=cls._number_of_columns - 1)

    @classmethod    
    def _parse_single_qcfail_record(cls, record: CsvRow) -> tuple[PointRecord, QCFailReasons]:
        pt_rec = cls._parse_single_record(record, exp_len=cls._number_of_columns)
        fail_code = record[cls.InputFileColumn.QC.get]
        return pt_rec, fail_code
