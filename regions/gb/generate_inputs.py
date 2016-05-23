
import csv
import os
import re
import shutil

import switch_mod.solve


class AmplTab(object):
    delimiter = "\t"
    lineterminator = "\n"
    doublequote = False
    escapechar = "\\"
    quotechar = '"'
    quoting = csv.QUOTE_MINIMAL
    skipinitialspace = False


def write_file(filename, data):
    fh = open(filename, "w")
    try:
        fh.write(data)
    finally:
        fh.close()


def get_generators():
    reader = csv.reader(open('dukes5_10.csv'))

    # Find the heading row
    while True:
        row = next(reader)
        if row[0] == 'Company Name':
            break

    for row in reader:
        if row[0] == 'Total':
            break
        if row[2] not in ('CCGT', 'Coal'):
            continue
        yield {'name': row[1].replace(' ', '_'),
               'gen_type': row[2],
               'capacity_mw': int(row[3]),
               'build_year': row[4]}


def main():
    inputs_dir = 'inputs'
    if os.path.exists(inputs_dir):
        shutil.rmtree(inputs_dir)
    if not os.path.exists(inputs_dir):
        os.mkdir(inputs_dir)

    def write_input(name, data):
        write_file(os.path.join(inputs_dir, '%s.tab' % name),
                   data.replace(',', '\t'))

    # Time definitions
    #  * Investment periods, multi-year
    #    -- new infrastructure is built at start of investment period?

    write_input('periods', """\
INVESTMENT_PERIOD,period_start,period_end
2020,2017,2026
""")
    write_input('timeseries', """\
TIMESERIES,ts_period,ts_duration_of_tp,ts_num_tps,ts_scale_to_period
2020_all,2020,12,2,3652.5
""")
    write_input('timepoints', """\
timepoint_id,timestamp,timeseries
1,2025011512,2020_all
2,2025011600,2020_all
""")

    # Financial parameters

    write_file(os.path.join(inputs_dir, 'financials.dat'), """\
param base_financial_year := 2015;
param interest_rate := .07;
param discount_rate := .05;
""")

    # Load (demand) and its organisation into zones

    write_input('load_zones', """\
LOAD_ZONE,cost_multipliers,ccs_distance_km,dbid
LZ,1,0,3
""")
    write_input('loads', """\
LOAD_ZONE,TIMEPOINT,lz_demand_mw
LZ,1,6.2
LZ,2,0.5
""")

    # Possible generators

    write_input('generator_info', """\
generation_technology,g_max_age,g_min_build_capacity,g_scheduled_outage_rate,g_forced_outage_rate,g_is_resource_limited,g_is_variable,g_is_baseload,g_is_flexible_baseload,g_is_cogen,g_competes_for_space,g_variable_o_m,g_energy_source,g_full_load_heat_rate
CCGT,20,0,0.04,0.06,0,0,0,0,0,0,3.4131,NaturalGas,6.705
Coal,20,0,0.04,0.06,0,0,0,0,0,0,3.4131,NaturalGas,6.705
""")

    fh = open(os.path.join(inputs_dir, 'project_info.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    out.writerow('PROJECT,proj_gen_tech,proj_load_zone,proj_capacity_limit_mw,proj_connect_cost_per_mw'.split(','))
    for gen in get_generators():
        out.writerow([gen['name'],
                      gen['gen_type'],
                      'LZ',
                      gen['capacity_mw'],
                      0]) # TODO
    fh.flush()

    fh = open(os.path.join(inputs_dir, 'proj_existing_builds.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    out.writerow('PROJECT,build_year,proj_existing_cap'.split(','))
    for gen in get_generators():
        out.writerow([gen['name'],
                      2000, # TODO: gen['build_year'],
                      gen['capacity_mw']])
    fh.flush()

    fh = open(os.path.join(inputs_dir, 'proj_build_costs.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    out.writerow('PROJECT,build_year,proj_overnight_cost,proj_fixed_om'.split(','))
    for gen in get_generators():
        out.writerow([gen['name'],
                      2000, # TODO: gen['build_year'],
                      1, # TODO
                      1]) # TODO
    fh.flush()

    # Fuel cost and CO2 intensity.  Cost can vary by load zone; CO2
    # intensity does not.
    write_input('fuel_cost', """\
load_zone,fuel,period,fuel_cost
LZ,NaturalGas,2020,4
""")
    write_input('fuels', """\
fuel,co2_intensity,upstream_co2_intensity
NaturalGas,0.05306,0
""")

    write_input('non_fuel_energy_sources', """\
energy_source
Solar
Geothermal
""")
    write_input('variable_capacity_factors', """\
PROJECT,timepoint,proj_max_capacity_factor
""")

    write_file(os.path.join(inputs_dir, 'modules'), 'project.no_commit\n')

    switch_mod.solve.main(['-v'])

    # Check that we got some output.
    assert os.path.exists(os.path.join('outputs', 'DispatchProj.tab'))


main()
