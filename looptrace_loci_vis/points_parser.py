"""Abstractions related to points parsing"""

import abc
import csv
from collections.abc import Iterable, Sized
from enum import Enum
from typing import Generic, Protocol, TypeVar

import pandas as pd
from gertils.geometry import ImagePoint3D
from gertils.types import TimepointFrom0 as Timepoint
from gertils.types import TraceIdFrom0 as TraceId

from ._types import CsvRow, PathLike, QCFailReasons
from .point_record import PointRecord

Input = TypeVar("Input", contravariant=True)
I1 = TypeVar("I1")
I2 = TypeVar("I2", bound=Sized)


class MappingLike(Protocol, Sized):  # noqa: D101
    @abc.abstractmethod
    def __getitem__(self, key: str) -> object: ...

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

    TIME_INDEX_COLUMN = "timeIndex"

    @classmethod
    def _gen_records(cls, data: PathLike) -> Iterable[MappingLike]:
        for _, row in pd.read_csv(data).iterrows():
            yield row

    @classmethod
    def _parse_single_qcpass_record(cls, record: MappingLike) -> PointRecord:
        trace = TraceId(int(record["traceIndex"]))  # type: ignore[call-overload]
        timepoint = Timepoint(int(record[cls.TIME_INDEX_COLUMN]))  # type: ignore[call-overload]
        z = float(record["z"])  # type: ignore[arg-type]
        y = float(record["y"])  # type: ignore[arg-type]
        x = float(record["x"])  # type: ignore[arg-type]
        point = ImagePoint3D(z=z, y=y, x=x)
        return PointRecord(trace_id=trace, timepoint=timepoint, point=point)

    @classmethod
    def _parse_single_qcfail_record(cls, record: MappingLike) -> tuple[PointRecord, QCFailReasons]:
        """A fail record parses the same as a pass one, just with one additional field for QC fail reasons."""
        pt_rec = cls._parse_single_qcpass_record(record)
        fail_code = record["failCode"]
        if not isinstance(fail_code, str):
            raise TypeError(f"failCode is not str, but {type(fail_code).__name__}")
        fail_code: str = str(fail_code)  # type: ignore[no-redef]
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
        with open(data, newline="") as fh:  # noqa: PTH123
            return list(csv.reader(fh))

    @classmethod
    def _parse_single_qcpass_record(cls, record: CsvRow) -> PointRecord:
        return cls._parse_single_record(record, exp_len=cls._number_of_columns - 1)

    @classmethod
    def _parse_single_qcfail_record(cls, record: CsvRow) -> tuple[PointRecord, QCFailReasons]:
        pt_rec = cls._parse_single_record(record, exp_len=cls._number_of_columns)
        fail_code = record[cls.InputFileColumn.QC.get]
        return pt_rec, fail_code
