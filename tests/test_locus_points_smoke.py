"""Smoketests for locus-specific points"""

from math import ceil
from looptrace_loci_vis.points_parser import HeadlessTraceTimePointParser
from looptrace_loci_vis.reader import records_to_qcfail_layer_data

FAIL_LINES_SAMPLE = """0,13,5.880338307654485,12.20211975317036,10.728294496728491,S
0,17,10.594366532607864,10.95875680073854,20.711938561802768,R;S;xy;z
0,47,10.198132167665957,14.398450914314138,15.378219719077295,R
0,48,0.7173811741523715,13.999908344240598,2.011625563698183,R;z
0,49,6.274792365451074,14.440034853392085,8.81613597404698,S
0,69,10.03907938905064,18.453449673327853,7.594187495036839,R;S;xy;z
0,71,8.157075382512406,12.780500232574296,3.1916456736466685,R
0,74,7.03360935199292,15.324188332927145,3.6995859572616823,xy
0,76,2.426576702500344,20.546530442060508,2.151493771689803,R;S;xy;O
0,77,6.0415531254567885,13.910733825016758,10.238202728231837,S
"""


def test_failed_sample_line_count(tmp_path):
    lines = FAIL_LINES_SAMPLE.splitlines(keepends=True)
    data_file = tmp_path / "spots.qcfail.csv"
    with data_file.open(mode="w") as fh:
        for data_line in lines:
            fh.write(data_line)
    exp_line_count = 10
    assert len(lines) == exp_line_count, f"Expected {exp_line_count} lines but got {len(lines)}"
    z_field = 2
    obs_z_ceil = ceil(max(float(l.split(",")[z_field]) for l in lines))  # noqa: E741
    exp_z_ceil = 11
    assert obs_z_ceil == exp_z_ceil, f"Expected max Z of {exp_z_ceil} but got {obs_z_ceil}"
    exp_record_count = exp_z_ceil * exp_line_count
    init_recs = HeadlessTraceTimePointParser.parse_all_qcfail(data_file) # noqa: E741
    records, _, _ = records_to_qcfail_layer_data(init_recs)
    assert (
        len(records) == exp_record_count
    ), f"Expected {exp_record_count} records but got {len(records)}"
