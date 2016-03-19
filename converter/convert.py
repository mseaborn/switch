# Copyright 2016 The Switch Authors. All rights reserved.
# Licensed under the Apache License, Version 2, which is in the LICENSE file.

import csv
import os
import shutil

import v1_example
import v2_example


def main():
    if os.path.exists('tmp'):
        shutil.rmtree('tmp')
    os.mkdir('tmp')

    v1_inputs = os.path.join('tmp', 'v1_inputs')
    os.mkdir(v1_inputs)
    v1_example.write_example(v1_inputs)

    v2_inputs = os.path.join('tmp', 'v2_inputs')
    os.mkdir(v2_inputs)
    v2_example.write_example(v2_inputs)

    def read_v1_table(name):
        fh = open(os.path.join(v1_inputs, '%s.tab' % name), 'r')
        header = fh.readline()

        # TODO: Check more
        assert header.startswith('ampl.tab')

        return list(csv.DictReader(fh, delimiter='\t'))

    files_left_to_convert = set(os.listdir(v2_inputs))

    def write_v2_table(name, fields, rows):
        files_left_to_convert.remove('%s.tab' % name)
        filename = os.path.join(v2_inputs, '%s.tab' % name)
        fh = open(filename, 'w')

        print '\n%s:' % filename
        rows = list(rows)
        for row in rows:
            print row

        writer = csv.DictWriter(fh, fields, delimiter='\t')
        writer.writeheader()
        writer.writerows(rows)
        fh.close()

    study_hours = read_v1_table('study_hours')
    print study_hours
    by_series = {}
    for row in study_hours:
        key = (row['period'], row['date'])
        by_series.setdefault(key, []).append(row)
    # Example: Nicaragua v1 model has median & peak time series for
    # each month, so 2*12 = 24 per year.  It has 12 time points per
    # time series.
    #
    # e.g. For the "peak January day" time series, v1 study_hours has
    # 12 rows (time points) each with hours_in_sample=8.  Where does 8
    # come from?  Each row represents 24/12 = 2 hours per day.  The
    # model has 4 years per investment period, so:
    #
    #   2 hours per row * 4 occurrences per investment period
    #   = 8 hours per investment period per row
    write_v2_table(
        'timeseries',
        ['TIMESERIES', 'ts_period', 'ts_duration_of_tp',
         'ts_num_tps', 'ts_scale_to_period'],
        ({'TIMESERIES': series,
          'ts_period': period,
          # Duration in hours.  v1's time series are always 24 hours each.
          'ts_duration_of_tp': 24.0 / len(rows),
          # Redundant: can be calculated from v2's "timepoints" table.
          'ts_num_tps': len(rows),
          'ts_scale_to_period':
              sum(float(row['hours_in_sample']) for row in rows) / 24.0}
         for (period, series), rows in sorted(by_series.iteritems())))
    write_v2_table(
        'timepoints',
        ['timepoint_id', 'timeseries'],
        ({'timepoint_id': row['hour'],
          'timeseries': row['date']}
         for row in study_hours))

    load_areas = read_v1_table('load_area')
    write_v2_table(
        'load_zones',
        ['LOAD_ZONE'],
        ({'LOAD_ZONE': row['load_area']} for row in load_areas))

    demand = read_v1_table('la_hourly_demand')
    write_v2_table(
        'loads',
        ['LOAD_ZONE', 'TIMEPOINT', 'lz_demand_mw'],
        ({'LOAD_ZONE': row['load_area'],
          'TIMEPOINT': row['hour'],
          'lz_demand_mw': row['load_mw']}
         for row in demand))

    for name in sorted(files_left_to_convert):
        print 'remaining:', name

    v2_outputs = os.path.join('tmp', 'v2_outputs')
    import switch_mod.solve
    switch_mod.solve.main(['--inputs=%s' % v2_inputs,
                           '--outputs=%s' % v2_outputs])

    # Check that we got some output.
    assert os.path.exists(os.path.join(v2_outputs, 'DispatchProj.tab'))


if __name__ == '__main__':
    main()
