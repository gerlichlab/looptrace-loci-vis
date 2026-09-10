"""Plugin-wide constants"""

from enum import Enum

# Suffixes of the looptrace block folders holding the locus spot images and the QC pass/fail CSVs
LOCUS_SPOT_VISUALISATION_BLOCK_SUFFIX = "_LOCUS_SPOT_VISUALISATION"
LOCUS_SPOT_QC_FILTERING_BLOCK_SUFFIX = "_LOCUS_SPOT_QC_FILTERING"


class PointColor(Enum):
    # See: https://davidmathlogic.com/colorblind/
    DEEP_SKY_BLUE = "#0C7BDC"
    GOLDENROD = "#FFC20A"
