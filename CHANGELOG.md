# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.3.0] - 2025-02-15

### Added
* Support reading data from ROIs merged into tracing groups.

### Changed
* Relaxed the rules around the naming conventions/expectations for input data: namely, now the ZARR and CSV inputs need not have a name which corresponds exactly to the encoding of a one-based field of view count
* Removed support for parsing CSVs with no header.
* A new slider is now present, for regional barcode imaging timepoint (to support ROI merger into tracing groups).

## [v0.2.3] - 2024-11-27

### Changed
* Change example and test to match what will now come from `looptrace` v0.11

## [v0.2.2] - 2024-11-21

### Changed
* Update to newest version of `gertils` (v0.5.1).

## [v0.2.1] - 2024-11-21
This is compatible with the 0.11.x line of `looptrace`.

### Changed
* Support Python 3.12.
* Bump up dependencies on `gertils` and `numpydoc_decorator`.

## [v0.2.0] - 2024-05-30

### Changed
* This project now can use `pandas` and parses a table-like file (CSV) _with_ header, to support upstream changes in data generation by `looptrace`.
* Splitting old functionality out into separate modules

## [v0.1.0] - 2024-04-20
 
### Added
* This package, first release
