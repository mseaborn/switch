# Copyright 2015 The Switch Authors. All rights reserved.
# Licensed under the Apache License, Version 2, which is in the LICENSE file.

"""

Defines model components to describe generation projects build-outs for
the SWITCH-Pyomo model.

SYNOPSIS
>>> from switch_mod.utilities import define_AbstractModel
>>> model = define_AbstractModel(
...     'timescales', 'financials', 'load_zones', 'fuels',
...     'gen_tech', 'project.build')
>>> instance = model.load_inputs(inputs_dir='test_dat')

"""

import os
from pyomo.environ import *
from switch_mod.financials import capital_recovery_factor as crf


def define_components(mod):
    """

    Adds components to a Pyomo abstract model object to describe
    generation and storage projects. Unless otherwise stated, all power
    capacity is specified in units of MW and all sets and parameters
    are mandatory.

    PROJECTS is the set of generation and storage projects that have
    been built or could potentially be built. A project is a combination
    of generation technology, load zone and location. A particular
    build-out of a project should also include the year in which
    construction was complete and additional capacity came online.
    Members of this set are abbreviated as proj or prj in parameter
    names and indexes. Use of p instead of prj is discouraged because p
    is reserved for period.

    proj_dbid[prj] is an external database id for each project. This is
    an optional parameter than defaults to the project index.

    proj_gen_tech[prj] describes what kind of generation technology a
    projects is using.

    proj_load_zone[prj] is the load zone this project is built in.

    VARIABLE_PROJECTS is a subset of PROJECTS that only includes
    variable generators such as wind or solar that have exogenous
    constraints on their energy production.

    BASELOAD_PROJECTS is a subset of PROJECTS that only includes
    baseload generators such as coal or geothermal.

    LZ_PROJECTS[lz in LOAD_ZONES] is an indexed set that lists all
    projects within each load zone.

    PROJECTS_CAP_LIMITED is the subset of PROJECTS that are capacity
    limited. Most of these will be generator types that are resource
    limited like wind, solar or geothermal, but this can be specified
    for any project. Some existing or proposed projects may have upper
    bounds on increasing capacity or replacing capacity as it is retired
    based on permits or local air quality regulations.

    proj_capacity_limit_mw[proj] is defined for generation technologies
    that are resource limited and do not compete for land area. This
    describes the maximum possible capacity of a project in units of
    megawatts.

    proj_full_load_heat_rate[proj] is the full load heat rate in units
    of MMBTU/MWh that describes the thermal efficiency of a project when
    runnign at full load. This optional parameter overrides the generic
    heat rate of a generation technology. In the future, we may expand
    this to be indexed by fuel source as well if we need to support a
    multi-fuel generator whose heat rate depends on fuel source.

    proj_energy_source[proj] is the primary energy source for a project.
    This is derived from the generation technology description and
    assumes one energy source per generation technology. This parameter
    may be altered in the future to support generators that use multiple
    energy sources.

    -- CONSTRUCTION --

    PROJECT_BUILDYEARS is a two-dimensional set of projects and the
    years in which construction or expansion occured or can occur. You
    can think of a project as a physical site that can be built out over
    time. BuildYear is the year in which construction is completed and
    new capacity comes online, not the year when constrution begins.
    BuildYear will be in the past for existing projects and will be the
    first year of an investment period for new projects. Investment
    decisions are made for each project/invest period combination. This
    set is derived from other parameters for all new construction. This
    set also includes entries for existing projects that have already
    been built; information for legacy projects come from other files
    and their build years will usually not correspond to the set of
    investment periods. There are two recommended options for
    abbreviating this set for denoting indexes: typically this should be
    written out as (proj, build_year) for clarity, but when brevity is
    more important (prj, b) is acceptable.

    NEW_PROJ_BUILDYEARS is a subset of PROJECT_BUILDYEARS that only
    includes projects that have not yet been constructed. This is
    derived by joining the set of PROJECTS with the set of
    NEW_GENERATION_BUILDYEARS using generation technology.

    EXISTING_PROJ_BUILDYEARS is a subset of PROJECT_BUILDYEARS that
    only includes existing projects.

    proj_existing_cap[(proj, build_year) in EXISTING_PROJ_BUILDYEARS] is
    a parameter that describes how much capacity was built in the past
    for existing projects.

    BuildProj[proj, build_year] is a decision variable that describes
    how much capacity of a project to install in a given period. This also
    stores the amount of capacity that was installed in existing projects
    that are still online.

    ProjCapacity[proj, period] is an expression that returns the total
    capacity online in a given period. This is the sum of installed capacity
    minus all retirements.

    Max_Build_Potential[proj] is a constraint defined for each project
    that enforces maximum capacity limits for resource-limited projects.

        ProjCapacity <= proj_capacity_limit_mw

    proj_end_year[(proj, build_year) in PROJECT_BUILDYEARS] is the last
    investment period in the simulation that a given project build will
    be operated. It can either indicate retirement or the end of the
    simulation. This is derived from g_max_age.

    --- OPERATIONS ---

    PROJECT_BUILDS_OPERATIONAL_PERIODS[proj, build_year] is an indexed
    set that describes which periods a given project build will be
    operational.

    PROJECT_PERIOD_ONLINE_BUILD_YRS[proj, period] is a complementary
    indexed set that identify which build years will still be online
    for the given project in the given period. For some project-period
    combinations, this will be an empty set.

    PROJECT_OPERATIONAL_PERIODS describes periods in which projects
    could be operational. Unlike the related sets above, it is not
    indexed. Instead it is specified as a set of (proj, period)
    combinations useful for indexing other model components.


    --- COSTS ---

    proj_connect_cost_per_mw[prj] is the cost of grid upgrades to support a
    new project, in dollars per peak MW. These costs include new
    transmission lines to a substation, substation upgrades and any
    other grid upgrades that are needed to deliver power from the
    interconnect point to the load center or from the load center to the
    broader transmission network.

    The following cost components are defined for each project and build
    year. These parameters will always be available, but will typically
    be populated by the generic costs specified in generator costs
    inputs file and the load zone cost adjustment multipliers from
    load_zones inputs file.

    proj_overnight_cost[proj, build_year] is the overnight capital cost per
    MW of capacity for building a project in the given period. By
    "installed in the given period", I mean that it comes online at the
    beginning of the given period and construction starts before that.

    proj_fixed_om[proj, build_year] is the annual fixed Operations and
    Maintenance costs (O&M) per MW of capacity for given project that
    was installed in the given period.

    -- Derived cost parameters --

    proj_capital_cost_annual[proj, build_year] is the annualized loan
    payments for a project's capital and connection costs in units of
    $/MW per year. This is specified in non-discounted real dollars in a
    future period, not real dollars in net present value.

    Proj_Fixed_Costs_Annual[proj, period] is the total annual fixed
    costs (capital as well as fixed operations & maintenance) incurred
    by a project in a period. This reflects all of the builds are
    operational in the given period. This is an expression that reflect
    decision variables.

    Total_Proj_Fixed_Costs_Annual[period] is the sum of
    Proj_Fixed_Costs_Annual[proj, period] for all projects that could be
    online in the target period. This aggregation is performed for the
    benefit of the objective function.

    --- DELAYED IMPLEMENATION ---

    The following components are not implemented at this time.

    proj_energy_capacity_overnight_cost[proj, period] defaults to the
    generic costs of the energy component of a storage technology. It
    can be overridden if different projects have different cost
    components. For new CAES projects, this could easily be overridden
    based on whether an empty gas well was nearby that could be reused,
    whether the local geological conditions made it easy or difficult to
    drill and construct underground storage, or whether an above-ground
    pressurized vessel would be needed. For new battery projects, a
    generic cost would be completely sufficient.

    proj_replacement_id[prj] is defined for projects that could replace
    existing generators.

    LOCATIONS_WITH_COMPETITION is the set of locations that have limited
    land area where multiple projects can compete for space. Members of
    this set are abbreviated as either loc or a lowercase L "l" in
    parameter names and indexes.

    loc_area_km2[l] describes the land area available for development
    at a particular location in units of square kilometers.

    proj_location[prj] is only defined for projects that compete with each
    other for limited land space at a given location. It refers to a
    member of the set LOCATIONS_WITH_COMPETITION. For example, if solar
    thermal and solar PV projects were competing for the same parcel of
    land, they would need the same location id.

    proj_land_footprint_mw_km2[prj] describes the land footprint of a project
    in units of megawatts per square kilometer.

    Max_Build_Location[location] is a constraint defined for each project
    that enforces maximum capacity limits for resource-limited locations.

        sum(BuildProj/proj_land_footprint_mw_km2) <= loc_area_km2

    ccs_pipeline_cost_per_mw[proj, build_year] is the normalize cost of
    a ccs pipeline sized relative to a project's emissions intensity.

    ProjCommitToMinBuild[proj, build_year] is a binary decision variable
    that is only defined for generation technologies that have minimum
    build requirements as specified by g_min_build_capacity[g].

    Enforce_Min_Build[proj, build_year] is a constraint that forces
    project build-outs to meet the minimum build requirements for
    generation technologies that have those requirements. This is
    defined as a pair of constraints that force BuildProj to be 0 when
    ProjCommitToMinBuild is 0, and force BuildProj to be greater than
    g_min_build_capacity when ProjCommitToMinBuild is 1. The value used
    for max_reasonable_build_capacity can be set to something like three
    times the sum of the peak demand of all load zones in a given
    period, or just to the maximum possible floating point value. When
    ProjCommitToMinBuild is 1, the upper constraint should be non-binding.

        ProjCommitToMinBuild * g_min_build_capacity <= BuildProj ...
            <= ProjCommitToMinBuild * max_reasonable_build_capacity

    Decommission[proj, build_year, period] is a decision variable that
    allows early retirement of portions of projects. Any portion of a
    project that is decomisssioned early will not incur fixed O&M
    costs and cannot be brought back into service in later periods.

    NameplateCapacity[proj, build_year, period] is an expression that
    describes the amount of capacity available from a particular project
    build in a given period. This takes into account any decomissioning
    that occured.

        NameplateCapacity = BuildProj - sum(Decommission)

    """

    mod.PROJECTS = Set()
    mod.proj_dbid = Param(mod.PROJECTS, default=lambda m, proj: proj)
    mod.proj_gen_tech = Param(mod.PROJECTS, within=mod.GENERATION_TECHNOLOGIES)
    mod.proj_load_zone = Param(mod.PROJECTS, within=mod.LOAD_ZONES)
    mod.min_data_check('PROJECTS', 'proj_gen_tech', 'proj_load_zone')
    mod.VARIABLE_PROJECTS = Set(
        initialize=mod.PROJECTS,
        filter=lambda m, proj: (
            m.g_is_variable[m.proj_gen_tech[proj]]))
    mod.BASELOAD_PROJECTS = Set(
        initialize=mod.PROJECTS,
        filter=lambda m, proj: (
            m.g_is_baseload[m.proj_gen_tech[proj]]))
    mod.LZ_PROJECTS = Set(
        mod.LOAD_ZONES,
        initialize=lambda m, lz: set(
            p for p in m.PROJECTS if m.proj_load_zone[p] == lz))
    mod.PROJECTS_CAP_LIMITED = Set(within=mod.PROJECTS)
    mod.proj_capacity_limit_mw = Param(
        mod.PROJECTS_CAP_LIMITED,
        within=PositiveReals)
    # Add PROJECTS_LOCATION_LIMITED & associated stuff later
    mod.FUEL_BASED_PROJECTS = Set(
        initialize=lambda m: set(
            p for p in m.PROJECTS if m.g_uses_fuel[m.proj_gen_tech[p]]))
    mod.proj_fuel = Param(
        mod.FUEL_BASED_PROJECTS,
        within=mod.FUELS,
        initialize=lambda m, proj: set(
            set(m.G_ENERGY_SOURCES[m.proj_gen_tech[proj]]) &
            set(m.FUELS)).pop())
    mod.NON_FUEL_BASED_PROJECTS = Set(
        initialize=lambda m: set(
            p for p in m.PROJECTS if not m.g_uses_fuel[m.proj_gen_tech[p]]))
    mod.proj_non_fuel_energy_source = Param(
        mod.NON_FUEL_BASED_PROJECTS,
        within=mod.NON_FUEL_ENERGY_SOURCES,
        initialize=lambda m, proj: set(
            set(m.G_ENERGY_SOURCES[m.proj_gen_tech[proj]]) &
            set(m.NON_FUEL_ENERGY_SOURCES)).pop())
    mod.proj_energy_source = Param(
        mod.PROJECTS,
        within=mod.ENERGY_SOURCES,
        initialize=lambda m, proj: set(
            m.G_ENERGY_SOURCES[m.proj_gen_tech[proj]]).pop())
    # For now, I've only implemented support for each project having a
    # single fuel type. Throw an error if that is not the case, which
    # can prompt us to expand the model to support that.
    mod.thermal_generators_use_single_fuel = BuildCheck(
        mod.FUEL_BASED_PROJECTS,
        rule=lambda m, proj: len(set(
            set(m.G_ENERGY_SOURCES[m.proj_gen_tech[proj]]) &
            set(m.FUELS))) == 1)

    # proj_full_load_heat_rate defaults to g_full_load_heat_rate if it
    # is available. Throw an error if no data was given for
    # proj_full_load_heat_rate or g_full_load_heat_rate.
    def proj_full_load_heat_rate_default_rule(m, pr):
        g = m.proj_gen_tech[pr]
        if g in m.g_full_load_heat_rate:
            return m.g_full_load_heat_rate[g]
        else:
            raise ValueError(
                ("Project {} uses a fuel, but there is no heat rate " +
                 "specified for this project or its generation technology " +
                 "{}.").format(pr, m.proj_gen_tech[pr]))
    mod.proj_full_load_heat_rate = Param(
        mod.FUEL_BASED_PROJECTS,
        within=PositiveReals,
        default=proj_full_load_heat_rate_default_rule)

    def init_proj_buildyears(m):
        project_buildyears = set()
        for proj in m.PROJECTS:
            g = m.proj_gen_tech[proj]
            build_years = [
                b for (gen, b) in m.NEW_GENERATION_BUILDYEARS if gen == g]
            for b in build_years:
                project_buildyears.add((proj, b))
        return project_buildyears
    mod.NEW_PROJ_BUILDYEARS = Set(
        dimen=2,
        initialize=init_proj_buildyears)
    mod.EXISTING_PROJ_BUILDYEARS = Set(
        dimen=2)
    mod.proj_existing_cap = Param(
        mod.EXISTING_PROJ_BUILDYEARS,
        within=PositiveReals)
    mod.min_data_check('proj_existing_cap')
    mod.PROJECT_BUILDYEARS = Set(
        dimen=2,
        initialize=lambda m: set(
            m.EXISTING_PROJ_BUILDYEARS | m.NEW_PROJ_BUILDYEARS))

    def init_proj_end_year(m, proj, build_year):
        g = m.proj_gen_tech[proj]
        max_age = m.g_max_age[g]
        earliest_study_year = m.period_start[m.PERIODS.first()]
        if build_year + max_age < earliest_study_year:
            return build_year + max_age
        for p in m.PERIODS:
            if build_year + max_age < m.period_end[p]:
                break
        return p
    mod.proj_end_year = Param(
        mod.PROJECT_BUILDYEARS,
        initialize=init_proj_end_year)
    mod.min_data_check('proj_end_year')

    mod.PROJECT_BUILDS_OPERATIONAL_PERIODS = Set(
        mod.PROJECT_BUILDYEARS,
        within=mod.PERIODS,
        ordered=True,
        initialize=lambda m, proj, bld_yr: set(
            p for p in m.PERIODS
            if bld_yr <= p <= m.proj_end_year[proj, bld_yr]))
    # The set of build years that could be online in the given period
    # for the given project.
    mod.PROJECT_PERIOD_ONLINE_BUILD_YRS = Set(
        mod.PROJECTS, mod.PERIODS,
        initialize=lambda m, proj, p: set(
            bld_yr for (prj, bld_yr) in m.PROJECT_BUILDYEARS
            if prj == proj and bld_yr <= p <= m.proj_end_year[proj, bld_yr]))

    def bounds_BuildProj(model, proj, bld_yr):
        if((proj, bld_yr) in model.EXISTING_PROJ_BUILDYEARS):
            return (model.proj_existing_cap[proj, bld_yr],
                    model.proj_existing_cap[proj, bld_yr])
        elif(proj in model.PROJECTS_CAP_LIMITED):
            # This does not replace Max_Build_Potential because
            # Max_Build_Potential applies across all build years.
            return (0, model.proj_capacity_limit_mw[proj])
        else:
            return (0, None)
    mod.BuildProj = Var(
        mod.PROJECT_BUILDYEARS,
        within=NonNegativeReals,
        bounds=bounds_BuildProj)

    # To Do: Subtract retirements after I write support for that.
    mod.ProjCapacity = Expression(
        mod.PROJECTS, mod.PERIODS,
        initialize=lambda m, proj, period: sum(
            m.BuildProj[proj, bld_yr]
            for bld_yr in m.PROJECT_PERIOD_ONLINE_BUILD_YRS[proj, period]))

    mod.Max_Build_Potential = Constraint(
        mod.PROJECTS_CAP_LIMITED, mod.PERIODS,
        rule=lambda m, proj, p: (
            m.proj_capacity_limit_mw[proj] >= m.ProjCapacity[proj, p]))

    # Costs
    mod.proj_connect_cost_per_mw = Param(mod.PROJECTS, within=NonNegativeReals)
    mod.min_data_check('proj_connect_cost_per_mw')
    mod.proj_overnight_cost = Param(
        mod.PROJECT_BUILDYEARS,
        within=NonNegativeReals,
        default=lambda m, proj, bld_yr: (
            m.g_overnight_cost[m.proj_gen_tech[proj], bld_yr] *
            m.lz_cost_multipliers[m.proj_load_zone[proj]]))
    mod.proj_fixed_om = Param(
        mod.PROJECT_BUILDYEARS,
        within=NonNegativeReals,
        default=lambda m, proj, bld_yr: (
            m.g_fixed_o_m[m.proj_gen_tech[proj], bld_yr] *
            m.lz_cost_multipliers[m.proj_load_zone[proj]]))
    # Derived annual costs
    mod.proj_capital_cost_annual = Param(
        mod.PROJECT_BUILDYEARS,
        initialize=lambda m, proj, bld_yr: (
            (m.proj_overnight_cost[proj, bld_yr] +
                m.proj_connect_cost_per_mw[proj]) *
            crf(m.interest_rate, m.g_max_age[m.proj_gen_tech[proj]])))

    mod.PROJECT_OPERATIONAL_PERIODS = Set(
        dimen=2,
        initialize=lambda m: set(
            (proj, p)
            for (proj, bld_yr) in m.PROJECT_BUILDYEARS
            for p in m.PROJECT_BUILDS_OPERATIONAL_PERIODS[proj, bld_yr]))
    mod.Proj_Fixed_Costs_Annual = Expression(
        mod.PROJECT_OPERATIONAL_PERIODS,
        initialize=lambda m, proj, p: sum(
            m.BuildProj[proj, bld_yr] *
            (m.proj_capital_cost_annual[proj, bld_yr] +
             m.proj_fixed_om[proj, bld_yr])
            for (prj, bld_yr) in m.PROJECT_BUILDYEARS
            if (p in m.PROJECT_BUILDS_OPERATIONAL_PERIODS[prj, bld_yr] and
                proj == prj)))
    # Summarize costs for the objective function. Units should be total
    # annual future costs in $base_year real dollars. The objective
    # function will convert these to base_year Net Present Value in
    # $base_year real dollars.
    mod.Total_Proj_Fixed_Costs_Annual = Expression(
        mod.PERIODS,
        initialize=lambda m, p: sum(
            m.Proj_Fixed_Costs_Annual[proj, p]
            for (proj, period) in m.PROJECT_OPERATIONAL_PERIODS
            if p == period))
    mod.cost_components_annual.append('Total_Proj_Fixed_Costs_Annual')


def load_inputs(mod, switch_data, inputs_dir):
    """

    Import project-specific data. The following files are expected in
    the input directory.

    all_projects.tab
        PROJECT, proj_dbid, proj_gen_tech, proj_load_zone,
        proj_connect_cost_per_mw

    existing_projects.tab
        PROJECT, build_year, proj_existing_cap

    cap_limited_projects is optional because some systems will not have
    capacity limited projects.

    cap_limited_projects.tab
        PROJECT, proj_capacity_limit_mw

    The following files are optional because they override generic
    values given by descriptions of generation technologies.

    proj_heat_rate.tab
        PROJECT, proj_heat_rate

    Note: Load-zone cost adjustments will not be applied to any costs
    specified in project_specific_costs.

    project_specific_costs.tab
        PROJECT, build_year, proj_overnight_cost, proj_fixed_om

    """
    switch_data.load_aug(
        filename=os.path.join(inputs_dir, 'all_projects.tab'),
        select=('PROJECT', 'proj_dbid', 'proj_gen_tech',
                'proj_load_zone', 'proj_connect_cost_per_mw'),
        index=mod.PROJECTS,
        param=(mod.proj_dbid, mod.proj_gen_tech,
               mod.proj_load_zone, mod.proj_connect_cost_per_mw))
    switch_data.load_aug(
        filename=os.path.join(inputs_dir, 'existing_projects.tab'),
        select=('PROJECT', 'build_year', 'proj_existing_cap'),
        index=mod.EXISTING_PROJ_BUILDYEARS,
        param=(mod.proj_existing_cap))
    switch_data.load_aug(
        optional=True,
        filename=os.path.join(inputs_dir, 'cap_limited_projects.tab'),
        select=('PROJECT', 'proj_capacity_limit_mw'),
        index=mod.PROJECTS_CAP_LIMITED,
        param=(mod.proj_capacity_limit_mw))
    switch_data.load_aug(
        optional=True,
        filename=os.path.join(inputs_dir, 'proj_heat_rate.tab'),
        select=('PROJECT', 'full_load_heat_rate'),
        param=(mod.proj_full_load_heat_rate))
    switch_data.load_aug(
        optional=True,
        filename=os.path.join(inputs_dir, 'project_specific_costs.tab'),
        select=('PROJECT', 'build_year',
                'proj_overnight_cost', 'proj_fixed_om'),
        param=(mod.proj_overnight_cost, mod.proj_fixed_om))
