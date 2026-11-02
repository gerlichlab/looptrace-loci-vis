# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
* Support for Python 3.13, alongside 3.12. gertils v0.8.0 and the rest of the dependencies allow it, and CI runs the tests, the formatting check and the linting on both versions.
The lock takes `numpydoc_decorator` 2.3.0 on both, since 2.2.1 declares itself incompatible with 3.13. Nothing resolves differently between the two.
The Nix shell stays on 3.12, and ruff targets it, as the lower of the two.

### Changed
* Depend on `gertils` v0.8.0, which requires zarr 3, and whose `read_zarr` reads zarr format 3 as well as format 2: the plugin opens a locus's images in either format.
See [looptrace issue 579](https://github.com/gerlichlab/looptrace/issues/579), which moves looptrace to zarr 3.
* The plugin no longer declares zarr, which it never imports: it reads its stores through gertils, and gertils v0.8.0 requires zarr 3.1 to 4. The declaration allowed zarr 2, with which neither gertils v0.8.0 nor the tests work. The tests, which write their stores with zarr 3, declare it in their dependency group.
* Type-check with `pyright` instead of `mypy`, as looptrace, gertils and spotfishing do. The package is checked strictly and the tests at the standard level.
* Format at ruff's default line length of 88, where it was 100, as in the other repositories behind looptrace.
* The reader logs through its module's logger, `looptrace_loci_vis.reader`, instead of the root logger, so that napari or an application can set the plugin's log level apart from its own.
* ruff 0.7.4 -> 0.17.3 and pyright 1.1.411 -> 1.1.414, the newest releases, as in looptrace, gertils and the other plugins. The configuration names the rules that ruff renamed (`TC002`, `TC003`), no longer names those it removed (`ANN101`, `ANN102`), and ignores two that every rule now brings in: a copyright notice in each file (`CPY001`), as the LICENSE covers them all, and `X | None` for `Optional[X]` (`UP045`), which ruff split out of `UP007`, already ignored. pyright 1.1.414 finds nothing new.

### Removed
* The module-level type variables of `looptrace_loci_vis.points_parser`, `Input`, `I1` and `I2`: its generic parser classes declare their own type parameters, as ruff asks for Python 3.12.
* Support for napari 0.4 on macOS: looptrace-loci-vis allows napari 0.5 to 0.9. napari 0.4.19.post1 requires numpy below 2, while the zarr and numcodecs this release is tested with need numpy 2. looptrace kept napari 0.4.19 by holding numpy below 1.25, which it can't with gertils v0.8.0, as that requires numpy 1.26. The reader passes only the names that napari has used for a point's outline since 0.5, `border_*`, where it chose between them and napari 0.4's `edge_*`.
* Support for Python 3.11. The floor is Python 3.12, which gertils v0.8.0 and the newest releases of numpy, zarr and numcodecs all need, and which looptrace already requires.

### Fixed
* A QC pass or fail CSV with only its header, as when every spot of a field of view passed QC or every one failed, no longer stops the folder from opening with `ValueError: max() iterable argument is empty`. The folder opens with an empty points layer for that file, and the warning names the file.
* A folder whose `.zarr` is a file, or whose QC CSV is a folder, is declined, so napari moves on to other readers. The reader accepted a `.zarr` file and then failed to read it, and failed outright on a CSV folder, with `RuntimeError: Unexpected path!`.
* pyright runs in the Nix shell on Linux too (#19). The shell now provides Node.js, which the pyright package from PyPI runs on, as the shells of gertils, spotfishing and looptrace-regionals-vis do; without it, pyright downloaded its own Node.js, which failed on Linux.

## [v0.4.0] - 2026-10-13

### Changed
* Depend on `gertils` v0.7.0.
* Drop support for Python 3.10, which gertils v0.7.0 no longer supports: looptrace-loci-vis requires Python 3.11 or 3.12.
* Allow napari 0.5 to 0.9 on macOS, as well as 0.4.19.post1, where it was pinned at 0.4.19.post1 since napari 0.9 needs Python 3.11. The plugin's own lock and macOS CI use napari 0.9.2; looptrace, which holds numpy below the 1.25 that napari 0.9 needs, keeps 0.4.19.
* The Nix shell uses nixpkgs 26.05, with Poetry 2, and `poetry.lock` is in Poetry 2's format.
* CI installs the newest Poetry, as it already did: the `poetry-version` the workflows set, `1.7.1`, is not an input of the action that installs Poetry, so it had no effect. Each CI job caches its environment separately, per Python.

## [v0.3.7] - 2026-10-07

### Changed
* Open under napari 0.5 and later as well as 0.4. napari 0.5 renamed the Points layer's `edge_width`, `edge_width_is_relative` and `edge_color` arguments to `border_*`, and later releases refuse the old names, so a locus-spot folder failed to open with `add_points() got an unexpected keyword argument 'edge_width'` (seen on napari 0.9.2). The reader now passes whichever names the installed napari uses. The napari pin (`==0.4.19.post1` on macOS) is unchanged: napari 0.9 needs Python 3.11 or later, and this project still supports 3.10.

## [v0.3.6] - 2026-09-22

### Added
* Read the output published by `looptrace`'s Nextflow pipeline: when the dragged folder is in a `*_LOCUS_SPOT_VISUALISATION` block and holds only the ZARR, take the QC pass/fail CSVs from the same-named folder in the `*_LOCUS_SPOT_QC_FILTERING` block beside it.
* The search runs in that direction only, by design: the visualisation folder is the one to drop, and dropping the QC filtering folder is refused rather than resolved in reverse. The image is what the points are drawn on and what napari orders first, so one folder is the anchor; the mirror search would be the same code with the suffixes swapped, and is left out so there is a single story and a single set of failure modes. The refusal names the folder to drop instead.

### Changed
* Fix the usage docs, which said points files must have no header.
* A folder that cannot be read because it is the wrong half of the pair now says which folder to drop. Both halves previously refused with "Not exactly 3 files", which is true of either and says nothing about the choice; dropping the QC filtering folder is the likeliest mistake, since that is where somebody looking for QC results will click first. The refusal from a visualisation folder likewise says that the QC filtering block was searched for and what was found.

## [v0.3.5] - 2025-11-03

### Changed
* Depend on newest version (v0.6.1) of `gertils`, and adapt code accordingly.

## [v0.3.4] - 2025-04-01

### Changed
* Pin Napari at 0.4.19.post1
* Switch build to Poetry

## [v0.3.3] - 2025-03-28

### Changed
* Fix `ruff` at version 0.7.4, to try to avoid the metadata info version bump from 2.3 to 2.4.

## [v0.3.2] - 2025-03-26

### Changed
* Bump `ruff` back to v0.8.0, and pin the dependency there, since that's the [last `ruff` version before the updating metadata info version](https://github.com/astral-sh/ruff/issues/14681), which requires at least version 1.8.5 of Poetry.

## [v0.3.1] - 2025-03-21

### Changed
* Bump version of `gertils` dependency to v0.6.0.

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
