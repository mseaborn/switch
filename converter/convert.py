# Copyright 2016 The Switch Authors. All rights reserved.
# Licensed under the Apache License, Version 2, which is in the LICENSE file.

import csv
import os
import shutil

import v1_example


def write_file(filename, data):
    fh = open(filename, "w")
    try:
        fh.write(data)
    finally:
        fh.close()


def group_by(rows, key):
    d = {}
    for row in rows:
        d.setdefault(key(row), []).append(row)
    return sorted(d.iteritems())


def assert_eq(x, y):
    if x != y:
        raise AssertionError('%r != %r' % (x, y))


def main():
    if os.path.exists('tmp'):
        shutil.rmtree('tmp')
    os.mkdir('tmp')

    v1_inputs = os.path.join('tmp', 'v1_inputs')
    os.mkdir(v1_inputs)
    v1_example.write_example(v1_inputs)

    v2_inputs = os.path.join('tmp', 'v2_inputs')
    os.mkdir(v2_inputs)

    def read_v1_table(name):
        fh = open(os.path.join(v1_inputs, '%s.tab' % name), 'r')
        header = fh.readline()

        # TODO: Check more
        assert header.startswith('ampl.tab')

        return list(csv.DictReader(fh, delimiter='\t'))

    def write_v2_table(name, fields, rows):
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
    by_series = group_by(study_hours, lambda row: (row['period'], row['date']))
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
         for (period, series), rows in sorted(by_series)))
    write_v2_table(
        'timepoints',
        ['timepoint_id', 'timeseries'],
        ({'timepoint_id': row['hour'],
          'timeseries': row['date']}
         for row in study_hours))

    misc_params = open(os.path.join(v1_inputs, 'misc_params.dat'), 'r').read()
    # TODO: Parse this from the file
    num_years_per_period = 4
    assert 'num_years_per_period := %d;' % num_years_per_period in misc_params
    periods = list(sorted(set(int(row['period']) for row in study_hours)))
    for i in xrange(len(periods) - 1):
        assert periods[i + 1] == periods[i] + num_years_per_period
    write_v2_table(
        'periods',
        ['INVESTMENT_PERIOD', 'period_start', 'period_end'],
        ({'INVESTMENT_PERIOD': year,
          'period_start': year,
          'period_end': year + num_years_per_period - 1}
         for year in periods))

    def map_table(out_name, in_name, fields):
        def map_field(row, f):
            if isinstance(f, str):
                return row[f]
            else:
                return f(row)

        def convert(row):
            return dict((a, map_field(row, b)) for a, b in fields)

        write_v2_table(
            out_name,
            [a for a, b in fields],
            (convert(row) for row in read_v1_table(in_name)))

    map_table('load_zones', 'load_area',
              [('LOAD_ZONE', 'load_area'),
               # Needed when adding local_td module:
               ('existing_local_td', lambda row: 0),
               ('local_td_annual_cost_per_mw', lambda row: 9999)])

    map_table('loads', 'la_hourly_demand',
              [('LOAD_ZONE', 'load_area'),
               ('TIMEPOINT', 'hour'),
               ('lz_demand_mw', 'load_mw')])

    map_table('generator_info', 'generator_info',
              [('generation_technology', 'technology'),
               ('g_max_age', 'max_age_years'),
               ('g_is_variable', 'intermittent'),
               ('g_is_baseload', 'baseload'),
               ('g_is_flexible_baseload', 'flexible_baseload'),
               ('g_is_cogen', 'cogen'),
               # Dummy value: should be overridden at project level.
               ('g_variable_o_m', lambda row: 9999),
               ('g_energy_source', 'fuel'),
               # Dummy value: should be overridden at project level.
               ('g_full_load_heat_rate', lambda row: 9999),
               ('g_forced_outage_rate', 'forced_outage_rate'),
               ])

    map_table('project_info', 'existing_plants',
              [('PROJECT', 'project_id'),
               ('proj_gen_tech', 'technology'),
               ('proj_load_zone', 'load_area'),
               ('proj_connect_cost_per_mw', 'connect_cost_per_mw')])

    map_table('proj_existing_builds', 'existing_plants',
              [('PROJECT', 'project_id'),
               ('build_year', 'start_year'),
               ('proj_existing_cap', 'capacity_mw')])

    map_table('proj_build_costs', 'existing_plants',
              [('PROJECT', 'project_id'),
               ('build_year', 'start_year'),
               ('proj_overnight_cost', 'overnight_cost'),
               ('proj_fixed_om', 'fixed_o_m')])

    map_table('fuels', 'fuel_info',
              [('fuel', 'fuel'),
               ('co2_intensity', 'carbon_content')])

    # Generate some mappings that help when averaging over years
    # within a period.
    year_to_period = {}
    period_to_years = {}
    for start_year in periods:
        years = range(start_year, start_year + num_years_per_period)
        period_to_years[start_year] = years
        for year in years:
            year_to_period[year] = start_year

    # Calculate fuel costs per investment period.  In v1, the costs
    # are specified per year, though this finer granularity is never
    # used.  We calculate average costs across the years within each
    # investment period, just as Switch v1 does.
    groups = group_by(read_v1_table('fuel_prices'),
                      lambda row: (row['load_area'],
                                   row['fuel'],
                                   year_to_period[int(row['year'])]))
    for (load_area, fuel, period), rows in groups:
        years = [int(row['year']) for row in rows]
        assert years == period_to_years[period], \
            (years, period_to_years[period])
    write_v2_table(
        'fuel_cost',
        ['load_zone', 'fuel', 'period', 'fuel_cost'],
        ({'load_zone': load_area,
          'fuel': fuel,
          'period': period,
          'fuel_cost': sum(float(row['fuel_price'])
                           for row in rows) / len(rows)}
         for (load_area, fuel, period), rows in groups))

    write_file(os.path.join(v2_inputs, 'financials.dat'), """\
param base_financial_year := 2015;
param interest_rate := .07;
param discount_rate := .05;
param distribution_loss_rate := 0.1;
""")

    write_file(os.path.join(v2_inputs, 'modules'), """\
project.no_commit
fuel_cost
local_td
""")

    v2_outputs = os.path.join('tmp', 'v2_outputs')
    import switch_mod.solve
    switch_mod.solve.main(['--inputs=%s' % v2_inputs,
                           '--outputs=%s' % v2_outputs])

    # Check that we got some output.
    assert os.path.exists(os.path.join(v2_outputs, 'DispatchProj.tab'))

    v1_dispatch = list(csv.DictReader(
        open(os.path.join('v1_outputs/generator_and_storage_dispatch_0.txt')),
        delimiter='\t'))
    assert_eq(len(v1_dispatch), 1)
    assert_eq(v1_dispatch[0]['power'], '5.06')

    v2_dispatch = list(csv.DictReader(
        open(os.path.join(v2_outputs, 'DispatchProj.tab')),
        delimiter='\t'))
    assert_eq(len(v2_dispatch), 1)
    assert_eq('%.4f' % float(v2_dispatch[0]['DispatchProj']), '5.0646')


if __name__ == '__main__':
    main()
