# Copyright 2016 The Switch Authors. All rights reserved.
# Licensed under the Apache License, Version 2, which is in the LICENSE file.

import os
import subprocess


def write_file(filename, data):
    fh = open(filename, "w")
    try:
        fh.write(data)
    finally:
        fh.close()


def main():
    inputs_dir = 'inputs'
    if not os.path.exists(inputs_dir):
        os.mkdir(inputs_dir)

    def write_input(name, keys, data):
        line1, _ = data.split('\n', 1)
        num_fields = len(line1.split(','))
        assert keys <= num_fields
        header = 'ampl.tab %d %d\n' % (keys, num_fields - keys)
        data = '\n'.join(line for line in data.split('\n')
                         if not line.startswith('#'))
        write_file(os.path.join(inputs_dir, '%s.tab' % name),
                   header + data.replace(',', '\t'))

    # Time definitions
    #  * Investment periods, multi-year
    #    -- new infrastructure is built at start of investment period?

#     write_input('periods', """\
# INVESTMENT_PERIOD,period_start,period_end
# 2020,2017,2026
# """)

    # Financial parameters

#     write_file(os.path.join(inputs_dir, 'financials.dat'), """\
# param base_financial_year := 2015;
# param interest_rate := .07;
# param discount_rate := .05;
# """)
    write_file(os.path.join(inputs_dir, 'misc_params.dat'), """\
param scenario_id := 1;
param num_years_per_period := 2;
param present_year := 2013;
param enable_carbon_cap := 0;
""")

    # Load (demand) and its organisation into zones

    write_input('load_area', keys=1, data="""\
load_area,balancing_area,ccs_distance_km,present_day_existing_distribution_cost,present_day_max_coincident_demand_mwh_for_distribution,distribution_new_annual_payment_per_mw,existing_transmission_sunk_annual_payment,bio_gas_capacity_limit_mmbtu_per_hour,rps_compliance_entity
S10,SIN,0,0,0,0,0,0,0
""")

    write_input('regional_grid_companies', keys=1, data="""\
balancing_area,load_only_spinning_reserve_requirement,wind_spinning_reserve_requirement,solar_spinning_reserve_requirement,quickstart_requirement_relative_to_spinning_reserve_requirement
SIN,0.03,0.05,0.05,1
""")

    write_input('rps_compliance_entity_targets', keys=3, data="""\
rps_compliance_entity,rps_compliance_type,rps_compliance_year,rps_compliance_fraction
""")

    write_input('rps_areas_and_fuel_category', keys=2, data="""\
load_area,fuel_category,fuel_qualifies_for_rps
S10,fossilish,0
""")

    write_input('carbon_cap_targets', keys=1, data="""\
year,carbon_emissions_relative_to_base
""")

    write_input('transmission_lines', keys=2, data="""\
la_start,la_end,transmission_line_id,existing_transfer_capacity_mw,transmission_length_km,transmission_efficiency,new_transmission_builds_allowed,dc_line
""")
    # S11,S19,8290,5000,23.31,0.98506845,1,0

#     write_input('timeseries', """\
# TIMESERIES,ts_period,ts_duration_of_tp,ts_num_tps,ts_scale_to_period
# 2020_all,2020,24,1,3652.5
# """)
#     write_input('timepoints', """\
# timepoint_id,timestamp,timeseries
# 1,2025011512,2020_all
# """)

    # TODO: Fix hours_in_sample
    write_input('study_hours', keys=1, data="""\
hour,period,date,hours_in_sample,month_of_year,hour_of_day
2016011600,2014,20160116,240.0,1,0
""")

    write_input('la_hourly_demand', keys=2, data="""\
load_area,hour,load_mw,present_day_system_load
S10,2016011600,4.604178233,4.105696313
""")

    write_input('max_la_demand', keys=2, data="""\
load_area,period,max_load_mw
S10,2014,7.285715607
""")

    write_input('existing_plants', keys=3, data="""\
project_id,load_area,technology,plant_name,capacity_mw,heat_rate,cogen_thermal_demand_mmbtus_per_mwh,start_year,overnight_cost,connect_cost_per_mw,fixed_o_m,variable_o_m,ep_location_id
SIN_MonteRosa,S10,Gas_Combustion_Turbine,MonteRosa,54.5,9.035,0,1998,3536811.443,99048.565,100400.475,4.480182,0
""")

    write_input('existing_plant_intermittent_capacity_factor', keys=4, data="""\
project_id,load_area,technology,hour,capacity_factor
SIN_ALBANISA,S26,Wind_EP,2016011600,0.798091
""")
    write_input('hydro_monthly_limits_ep', keys=4, data="""\
project_id,load_area,technology,date,average_output_mw
SIN_HPA1,S16,Hydro_RoR_EP,20160116,0.0
""")
    write_input('hydro_monthly_limits_new', keys=4, data="""\
project_id,load_area,technology,date,average_output_cf
16,S16,Hydro_RoR_RPS,20160116,0.371
""")
    write_input('new_projects', keys=3, data="""\
project_id,load_area,technology,location_id,ep_project_replacement_id,capacity_limit,capacity_limit_conversion,heat_rate,cogen_thermal_demand,connect_cost_per_mw,overnight_cost,fixed_o_m,variable_o_m,overnight_cost_change
#1,S17,Central_PV,64,0,13,45,0,0,320960.6705,2067222.201,10621.2603,0,-0.036276106
""")
    write_input('new_projects_intermittent_capacity_factor', keys=4, data="""\
project_id,load_area,technology,hour,capacity_factor
#1,S17,Central_PV,2016011600,0
""")
    write_input('generator_info', keys=1, data="""\
technology,technology_id,min_build_year,fuel,construction_time_years,year_1_cost_fraction,year_2_cost_fraction,year_3_cost_fraction,year_4_cost_fraction,year_5_cost_fraction,year_6_cost_fraction,max_age_years,forced_outage_rate,scheduled_outage_rate,can_build_new,ccs,intermittent,resource_limited,baseload,flexible_baseload,dispatchable,cogen,min_build_capacity,competes_for_space,storage,storage_efficiency,max_store_rate,max_spinning_reserve_fraction_of_capacity,heat_rate_penalty_spinning_reserve,minimum_loading,deep_cycling_penalty
Gas_Combustion_Turbine,2,2030,Gas,2,0.25,0.75,0,0,0,0,20,0.0413,0.0318,0,0,0,0,0,0,1,0,0,0,0,0,0,0.3,0.087,0,0
#Battery_Storage,33,2013,Storage,3,0.8,0.1,0.1,0,0,0,15,0.02,0.0055,1,0,0,0,0,0,0,0,0,0,1,0.767,1,0,0,0,0
""")
    write_input('fuel_info', keys=1, data="""\
fuel,rps_fuel_category,biofuel,carbon_content,carbon_sequestered
Gas,fossilish,0,0.05306,0
""")
    write_input('fuel_prices', keys=3, data="""\
load_area,fuel,year,fuel_price
S10,Gas,2014,0.043478261
S10,Gas,2015,0.043478261
""")


#     write_input('loads', """\
# LOAD_ZONE,TIMEPOINT,lz_demand_mw
# South,1,6.2
# """)

    # Possible generators

#     write_input('generator_info', """\
# generation_technology,g_max_age,g_min_build_capacity,g_scheduled_outage_rate,g_forced_outage_rate,g_is_resource_limited,g_is_variable,g_is_baseload,g_is_flexible_baseload,g_is_cogen,g_competes_for_space,g_variable_o_m,g_energy_source,g_full_load_heat_rate
# NG_CC,20,0,0.04,0.06,0,0,0,0,0,0,3.4131,NaturalGas,6.705
# """)
#     write_input('project_info', """\
# PROJECT,proj_dbid,proj_gen_tech,proj_load_zone,proj_connect_cost_per_mw,proj_capacity_limit_mw,proj_variable_om
# S-NG_CC,34,NG_CC,South,57566.6,.,3.4131
# """)
#     # Already-built projects.
#     write_input('proj_existing_builds', """\
# PROJECT,build_year,proj_existing_cap
# S-NG_CC,2000,10
# """)

    # Fuel cost and CO2 intensity.  Cost can vary by load zone; CO2
    # intensity does not.
#     write_input('fuel_cost', """\
# load_zone,fuel,period,fuel_cost
# South,NaturalGas,2020,4
# """)
#     write_input('fuels', """\
# fuel,co2_intensity,upstream_co2_intensity
# NaturalGas,0.05306,0
# """)

#     write_input('non_fuel_energy_sources', """\
# energy_source
# """)
#     write_input('proj_build_costs', """\
# PROJECT,build_year,proj_overnight_cost,proj_fixed_om
# S-NG_CC,2000,1143900,5868.3
# """)
#     write_input('variable_capacity_factors', """\
# PROJECT,timepoint,proj_max_capacity_factor
# """)

#     write_file(os.path.join(inputs_dir, 'modules'), 'project.no_commit\n')

    subprocess.check_call(['./run_switch.sh'])

    # Check that we got some output.
    assert os.path.exists(os.path.join('outputs', 'DispatchProj.tab'))


main()
