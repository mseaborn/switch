# Copyright 2016 The Switch Authors. All rights reserved.
# Licensed under the Apache License, Version 2, which is in the LICENSE file.

import os


def write_file(filename, data):
    fh = open(filename, "w")
    try:
        fh.write(data)
    finally:
        fh.close()


def write_example(inputs_dir):
    def write_input(name, data):
        write_file(os.path.join(inputs_dir, '%s.tab' % name),
                   data.replace(',', '\t'))

    # Time definitions
    #  * Investment periods, multi-year
    #    -- new infrastructure is built at start of investment period?

    write_input('periods', """\
INVESTMENT_PERIOD,period_start,period_end
2014,2014,2017
""")
    # ts_scale_to_period = 365.25 * 4 = 1461.0 occurrences per invest period.
    write_input('timeseries', """\
TIMESERIES,ts_period,ts_duration_of_tp,ts_num_tps,ts_scale_to_period
2014_series,2014,24,1,1461.0
""")
    write_input('timepoints', """\
timepoint_id,timeseries
2016011600,2014_series
""")

    # Financial parameters

    write_file(os.path.join(inputs_dir, 'financials.dat'), """\
param base_financial_year := 2015;
param interest_rate := .07;
param discount_rate := .05;
""")

    # Load (demand) and its organisation into zones

    write_input('load_zones', """\
LOAD_ZONE
S10
""")
    write_input('loads', """\
LOAD_ZONE,TIMEPOINT,lz_demand_mw
S10,2016011600,6.2
""")

    # Possible generators

    write_input('generator_info', """\
generation_technology,g_max_age,g_min_build_capacity,g_scheduled_outage_rate,g_forced_outage_rate,g_is_resource_limited,g_is_variable,g_is_baseload,g_is_flexible_baseload,g_is_cogen,g_competes_for_space,g_variable_o_m,g_energy_source,g_full_load_heat_rate
NaturalGas-CombinedCycle,20,0,0.04,0.06,0,0,0,0,0,0,3.4131,NaturalGas,6.705
""")
    write_input('project_info', """\
PROJECT,proj_dbid,proj_gen_tech,proj_load_zone,proj_connect_cost_per_mw,proj_capacity_limit_mw,proj_variable_om
SIN_MonteRosa,34,NaturalGas-CombinedCycle,S10,57566.6,.,3.4131
""")
    # Already-built projects.
    write_input('proj_existing_builds', """\
PROJECT,build_year,proj_existing_cap
SIN_MonteRosa,1998,10
""")

    # Fuel cost and CO2 intensity.  Cost can vary by load zone; CO2
    # intensity does not.
    write_input('fuel_cost', """\
load_zone,fuel,period,fuel_cost
S10,NaturalGas,2014,4
""")
    write_input('fuels', """\
fuel,co2_intensity,upstream_co2_intensity
NaturalGas,0.05306,0
""")

    write_input('non_fuel_energy_sources', """\
energy_source
""")
    write_input('proj_build_costs', """\
PROJECT,build_year,proj_overnight_cost,proj_fixed_om
SIN_MonteRosa,1998,1143900,5868.3
""")
    write_input('variable_capacity_factors', """\
PROJECT,timepoint,proj_max_capacity_factor
""")

    write_file(os.path.join(inputs_dir, 'modules'), """\
project.no_commit
fuel_cost
""")


def main():
    inputs_dir = 'inputs'
    if not os.path.exists(inputs_dir):
        os.mkdir(inputs_dir)

    write_example(inputs_dir)

    import switch_mod.solve
    switch_mod.solve.main([])

    # Check that we got some output.
    assert os.path.exists(os.path.join('outputs', 'DispatchProj.tab'))


if __name__ == '__main__':
    main()
