
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


def remove_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path)


# Convert from US dollars to UK pounds.
# Approximate exchange rate.
# TODO: We should probably avoid using US dollar costs as our inputs.
def usd_to_ukp(cost):
    return cost / 1.5


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
        location = row[5]
        # Omit generators in Northern Ireland, since we are modelling the
        # National Grid of Britain only.
        if location == 'Northern Ireland':
            continue
        if row[2] not in ('CCGT', 'Coal', 'Nuclear'):
            continue

        # The Killingholme A and B plants are the only case where the name
        # field in the table isn't unique.
        name = row[1]
        if name == 'Killingholme':
            name += ' ' + row[0]
        name = name.replace(' ', '_')

        yield {'name': name,
               'gen_type': row[2],
               'capacity_limit_mw': '.', # Unlimited
               'capacity_mw': int(row[3]),
               'build_year': row[4]}


def run_model(allow_existing, allow_new):
    inputs_dir = 'inputs'
    remove_dir(inputs_dir)
    os.mkdir(inputs_dir)
    remove_dir('outputs')

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

    # Generate list of time series.
    fh = open(os.path.join(inputs_dir, 'timeseries.tab'), 'w')
    out = csv.DictWriter(fh, 'TIMESERIES,ts_period,ts_duration_of_tp,ts_num_tps,ts_scale_to_period'.split(','), dialect=AmplTab)
    out.writeheader()
    # Use 12 time series: one per month.
    # For each time series, use 12 time points, spaced 2 hours apart.
    for month in xrange(1, 12 + 1):
        out.writerow(dict(TIMESERIES='2020_%02d' % month,
                          ts_period=2020,
                          ts_duration_of_tp=2,
                          ts_num_tps=12,
                          # TODO: take into account that months are non-equal
                          ts_scale_to_period=365.25 / 12 * 10))

    # Generate time points list.
    fh = open(os.path.join(inputs_dir, 'timepoints.tab'), 'w')
    out = csv.DictWriter(fh, 'timepoint_id,timestamp,timeseries'.split(','), dialect=AmplTab)
    out.writeheader()
    for month in xrange(1, 12 + 1):
        for hour in xrange(0, 24, 2):
            out.writerow(dict(timepoint_id='%02d-%02d' % (month, hour),
                              timestamp='%02d-%02d' % (month, hour),
                              timeseries='2020_%02d' % (month)))

    # Read historical load (demand) data.
    fh = open(os.path.join(inputs_dir, 'loads.tab'), 'w')
    out = csv.DictWriter(fh, 'LOAD_ZONE,TIMEPOINT,lz_demand_mw'.split(','), dialect=AmplTab)
    out.writeheader()
    month_list = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    month_map = dict((name, num + 1) for num, name in enumerate(month_list))
    # TODO: Adjust for time zone shift (GMT vs. BST), which sometimes
    # produces less or more than 48 settlement periods per day.
    for row in csv.DictReader(open('demand_2015.csv')):
        date_parts = row['SETTLEMENT_DATE'].split('-')
        # Use first day of each month.
        # TODO: Use better sampling.
        if date_parts[0] == '01':
            period = int(row['SETTLEMENT_PERIOD']) - 1
            if period % 4 == 0:
                assert period < 48, period
                hour = period / 2
                month = month_map[date_parts[1]]
                out.writerow(dict(LOAD_ZONE='LZ',
                                  TIMEPOINT='%02d-%02d' % (month, hour),
                                  lz_demand_mw=int(row['ND'])))
    fh.close()

    # Financial parameters

    write_file(os.path.join(inputs_dir, 'financials.dat'), """\
param base_financial_year := 2015;
param interest_rate := .07;
param discount_rate := .05;
""")

    write_input('load_zones', """\
LOAD_ZONE,cost_multipliers,ccs_distance_km,dbid
LZ,1,0,3
""")

    # Possible generators

    gen_techs = dict((name, {'generation_technology': name})
                     for name in ['CCGT', 'Coal', 'Nuclear'])

    # From Switch WECC docs, Oct 2013, Table 2-4
    gen_techs['Coal'].update(dict(
        # Coal Steam Turbine
        g_overnight_cost_per_watt=usd_to_ukp(3.04),
        g_fixed_o_m=usd_to_ukp(24000),
        g_variable_o_m=usd_to_ukp(3.9),
        g_energy_source='Coal',
    ))
    gen_techs['CCGT'].update(dict(
        g_overnight_cost_per_watt=usd_to_ukp(1.29),
        g_fixed_o_m=usd_to_ukp(7000),
        g_variable_o_m=usd_to_ukp(3.9),
        g_energy_source='NaturalGas',
    ))
    gen_techs['Nuclear'].update(dict(
        g_overnight_cost_per_watt=usd_to_ukp(6.41),
        g_fixed_o_m=usd_to_ukp(133000),
        g_variable_o_m=usd_to_ukp(0),
        g_energy_source='Uranium',
    ))

    # From Switch WECC docs, Oct 2013, Table 2-5
    gen_techs['Coal'].update(dict(
        g_full_load_heat_rate=9.0,
        g_max_age=40,
        g_forced_outage_rate=0.06,
        g_scheduled_outage_rate=0.10,
    ))
    gen_techs['CCGT'].update(dict(
        g_full_load_heat_rate=6.7,
        g_max_age=20,
        g_forced_outage_rate=0.04,
        g_scheduled_outage_rate=0.06,
    ))
    gen_techs['Nuclear'].update(dict(
        g_full_load_heat_rate=9.7,
        g_max_age=40,
        g_forced_outage_rate=0.04,
        g_scheduled_outage_rate=0.06,
    ))

    for gen_tech in gen_techs.values():
        gen_tech.update(dict(
            g_min_build_capacity=0,
            g_is_resource_limited=0,
            g_is_variable=0,
            g_is_baseload=0,
            g_is_flexible_baseload=0,
            g_is_cogen=0,
            g_competes_for_space=0,
        ))
    gen_techs['Coal'].update(dict(g_is_flexible_baseload=1))
    gen_techs['Nuclear'].update(dict(g_is_baseload=1))

    fh = open(os.path.join(inputs_dir, 'generator_info.tab'), 'w')
    fields = 'generation_technology,g_max_age,g_min_build_capacity,g_scheduled_outage_rate,g_forced_outage_rate,g_is_resource_limited,g_is_variable,g_is_baseload,g_is_flexible_baseload,g_is_cogen,g_competes_for_space,g_variable_o_m,g_energy_source,g_full_load_heat_rate'.split(',')
    out = csv.DictWriter(fh, fields, dialect=AmplTab)
    out.writeheader()
    for gen_tech in gen_techs.values():
        out.writerow(dict((key, gen_tech[key]) for key in fields))
    fh.close()

    generators = []
    new_generators = []
    if allow_existing:
        generators.extend(get_generators())
    if allow_new:
        for gen_type in ('CCGT', 'Coal', 'Nuclear'):
            new_generators.append(
                {'gen_type': gen_type,
                 'name': 'P_%s' % gen_type,
                 'capacity_limit_mw': '.',
                 # Workaround: Switch doesn't like it if there are no
                 # existing projects, so use a very small existing
                 # capacity.
                 'capacity_mw': 1e-9})
    generators.extend(new_generators)

    print 'Total generator capacity: %d MW' % \
        sum(gen['capacity_mw'] for gen in generators)

    fh = open(os.path.join(inputs_dir, 'project_info.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    out.writerow('PROJECT,proj_gen_tech,proj_load_zone,proj_capacity_limit_mw,proj_connect_cost_per_mw'.split(','))
    for gen in generators:
        out.writerow([gen['name'],
                      gen['gen_type'],
                      'LZ',
                      gen['capacity_limit_mw'],
                      0]) # TODO
    fh.flush()

    fh = open(os.path.join(inputs_dir, 'proj_existing_builds.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    out.writerow('PROJECT,build_year,proj_existing_cap'.split(','))
    for gen in generators:
        out.writerow([gen['name'],
                      2000, # TODO: gen['build_year'],
                      gen['capacity_mw']])
    fh.flush()

    fh = open(os.path.join(inputs_dir, 'proj_build_costs.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    out.writerow('PROJECT,build_year,proj_overnight_cost,proj_fixed_om'.split(','))
    for gen in generators:
        out.writerow([
            gen['name'],
            2000, # TODO: gen['build_year'],
            gen_techs[gen['gen_type']]['g_overnight_cost_per_watt'] * 1e6,
            gen_techs[gen['gen_type']]['g_fixed_o_m']])
    fh.flush()

    fh = open(os.path.join(inputs_dir, 'gen_new_build_costs.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    out.writerow('generation_technology,investment_period,g_overnight_cost,g_fixed_o_m'.split(','))
    for gen in new_generators:
        out.writerow([
            gen['gen_type'],
            2020,
            gen_techs[gen['gen_type']]['g_overnight_cost_per_watt'] * 1e6,
            gen_techs[gen['gen_type']]['g_fixed_o_m']])
    fh.flush()

    # Fuel cost and CO2 intensity.  Cost can vary by load zone; CO2
    # intensity does not.
    fh = open(os.path.join(inputs_dir, 'fuel_cost.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    # Prices from:
    # https://www.ofgem.gov.uk/sites/default/files/docs/2015/09/wholesale_energy_markets_in_2015_final_0.pdf
    out.writerows([
        ['load_zone', 'fuel', 'period', 'fuel_cost'],
        # Wholesale gas cost: approx 0.50ukp per therm in 2015,
        # which is 0.50 / 0.1 = 5 ukp per MMBTU.
        # (1 therm = 0.10 MMBTU.)
        ['LZ', 'NaturalGas', 2020, 5],
        # CO2:
        # Based on https://www.eia.gov/environment/emissions/co2_vol_mass.cfm:
        #   2100.82 kg CO2 / short ton of coal
        #     = 2100.82 kg CO2 / 0.90718474 tonne of coal
        #   also 95.35 kg CO2 / MMBTU
        #   So MMBTU per tonne = (2100.82 / 0.90718474) / 95.35
        # Coal price: roughly $65 per tonne in 2015.
        ['LZ', 'Coal', 2020,
         usd_to_ukp(65 / ((2100.82 / 0.90718474) / 95.35))],
        # Uranium price for US projected for 2015.
        # From http://www.energy.ca.gov/2007publications/CEC-200-2007-011/CEC-200-2007-011-SD.PDF
        ['LZ', 'Uranium', 2020, usd_to_ukp(2.58)],
    ])
    fh.close()

    fh = open(os.path.join(inputs_dir, 'fuels.tab'), 'w')
    out = csv.writer(fh, dialect=AmplTab)
    # CO2 intensity in metric tons of CO2 per MMBTU.
    # From https://www.eia.gov/environment/emissions/co2_vol_mass.cfm
    out.writerows([['fuel', 'co2_intensity'],
                   ['NaturalGas', 53.07e-3],
                   ['Coal', 95.35e-3],
                   ['Uranium', 0],
                   ])
    fh.close()

    write_input('non_fuel_energy_sources', """\
energy_source
Solar
Geothermal
""")
    write_input('variable_capacity_factors', """\
PROJECT,timepoint,proj_max_capacity_factor
""")

    write_file(os.path.join(inputs_dir, 'modules'), """\
project.no_commit
fuel_cost
""")

    switch_mod.solve.main([])

    # Check that we got some output.
    assert os.path.exists(os.path.join('outputs', 'DispatchProj.tab'))

    generator_to_type = dict((gen['name'], gen['gen_type'])
                             for gen in generators)
    totals = {}
    for row in csv.DictReader(open(os.path.join('outputs',
                                                'DispatchProj.tab')),
                              dialect=AmplTab):
        gen_tech = generator_to_type[row['PROJ_DISPATCH_POINTS_1']]
        totals.setdefault(gen_tech, 0)
        totals[gen_tech] += \
            float(row['DispatchProj']) * 2 * (365.25 / 12) / 1e6
    for gen_tech, total in sorted(totals.iteritems()):
        print 'Total generation for %s: %.2f TWh' % (gen_tech, total)
    print 'Total generation: %.2f TWh' % sum(totals.itervalues())


def main():
    print '\nNew builds only (from scratch):'
    run_model(allow_existing=False, allow_new=True)
    print '\nExisting generators only:'
    run_model(allow_existing=True, allow_new=False)


main()
