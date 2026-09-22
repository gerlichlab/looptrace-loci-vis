## Viewing locus spots
First, check the general information about [installation and environment](./README.md#installation-and-environment).

### Quickstart
To visualise the locus spots, you need to __drag-and-drop a _folder___ into an active Napari window.

#### From a `looptrace` run
Drag __one FOV and region's folder__ from the locus spot visualisation block:
```text
Analysis_NNN_<timestamp>/B19_LOCUS_SPOT_VISUALISATION/P0001__Chr2a/
```
Folders are named `<fov>__<region name>`, or just `<fov>__` (e.g., `P0001__`) when the region has no name.

That folder holds only the image, `P0001__Chr2a.zarr`. The QC pass/fail CSVs are published by a different block, so the plugin reads them from the folder of the same name in the QC filtering block of the same analysis folder:
```text
Analysis_NNN_<timestamp>/
├── B17_LOCUS_SPOT_QC_FILTERING/P0001__Chr2a/P0001__Chr2a.qcpass.csv
│                                            P0001__Chr2a.qcfail.csv
└── B19_LOCUS_SPOT_VISUALISATION/P0001__Chr2a/P0001__Chr2a.zarr
```
The blocks are matched by the end of their names (`_LOCUS_SPOT_VISUALISATION`, `_LOCUS_SPOT_QC_FILTERING`), not by their numbers. If you copy the data elsewhere, keep both block folders side by side.

Dragging the QC filtering block's folder, or a whole block folder, loads no layers.

#### From any other folder
A folder can instead hold all __3 items__ itself:
    * ZARR (folder) array with name matching the folder it's in (up to the `.zarr` extension)
    * `*.qcfail.csv`: CSV file with coordinate of spot fit centers, and column encoding QC fail reasons
    * `*.qcpass.csv`: same as QC fail file, but without column for failures

The prefixes of these filenames must match the name of the folder they're in.

For the image layer, you'll want to select "continuous" rather than "once" for the "auto-contrast" setting in the upper-left area of the Napari window. 
For each new unit/collection of data to view, you'll need to clear the layers from the active Napari window, then drag in the next folder.

### What you should see / notice
* __Sliders__: A Napari window with four sliders (trace ID on bottom, regional barcode index above that, timepoint index in above that, $z$ slice on top) should be displayed. 
* __Colors__: Yellow indicates a locus spot that passed all QC filters, and blue indicates that the spot failed at least one QC filter. 
* __Sizes and Shapes__: A larger star indicates that you're viewing the $z$-slice corresponding to the truncation-toward-0 of the $z$-coordinate of the centroid of the Gaussian fit to the locus spot pixels. A smaller point/circle is shown when you're in a non-central $z$-slice. Text is shown for QC-fail points
* __Text__: Text labels encode [QC failure reasons](#qc-failure-codes).

### QC failure codes
* `O`: "*O*ut-of-bounds" -- the locus point's center is literally outside the bounding box, or within one standard deviation of its fit to at least one of the boundaries
* `R`: "far from *R*egion center" -- the locus spot's center is too far from its region barcode's spot's center
* `S`: "*S*ignal-to-noise (too low)" -- the fit's signal-to-noise ratio is too low.
* `xy`: The fit's too diffuse in `xy`.
* `z`: The fit's too diffuse in `z`.

### Details and troubleshooting
* Each image file should have a `.zarr` extension.
* Each points file should have a `.qc(pass|fail).csv` extension.
* Each `.zarr` should either have a `.zarray` immediately inside it, or have a single `0` subfolder which has a `.zarray` inside it.
* Each points file should have a header, with at least the columns `traceIndex`, `regionIndex`, `timeIndex`, `z`, `y` and `x`, plus `failCode` in the QC-fail file.
* Ensure that "continuous" rather than "once" is selected for the "auto-contrast" setting in the upper-left area of the Napari window.

### Frequently asked questions (FAQ)
1. __Why blue and yellow as the colors for QC-fail and QC-pass (respectively) spots?__\
    This pair of colors is relatively tends to be seen roughly the same (or at least to maintain sharp contrast) by a colorblind person as for a non-colorblind person.
1. __Why are the layers named the same (e.g., P0001[2], P0001[1], P0001s) but with little boxed numbers?__\
    The name for each layer comes from the file or folder represented. The bracketed numbers just distinguish the layers and may be regarded as arbitrary.
1. __Why are some points a different shape or size?__\
    A star is represents the center of the locus point's Gaussian fit when viewing the $z$-slice corresponding to the truncated-toward-0 $z$-coordinate of the center of that fit. In all other slices/planes, a circle/dot is used instead of a star.
1. __Why are some slices entirely empty?__\
    This can happen when the bounding box for the region went outside actual image boundaries, resulting in a case of unextractable data.
1. __Why do some slices lack a point at all?__\
    This can happen when the center of the Gaussian fit to the pixel volume's data lies outside that volume ($z$-stack / rectangular prism).
