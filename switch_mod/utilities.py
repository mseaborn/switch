# Copyright 2015 The Switch Authors. All rights reserved.
# Licensed under the Apache License, Version 2, which is in the LICENSE file.

"""
Utility functions for SWITCH-pyomo.
"""

import os
import types
import importlib
import sys
import __main__ as main
from pyomo.environ import *

# This stores full names of modules that are dynamically loaded to
# define a Switch model.
_full_module_names = {}

# Check whether this is an interactive session (determined by whether
# __main__ has a __file__ attribute). Scripts can check this value to
# determine what level of output to display.
interactive_session = not hasattr(main, '__file__')


def define_AbstractModel(*module_list):
    """

    Construct a Pyomo AbstractModel using the Switch modules or packages
    in the given list and return the model. The following utility methods
    are attached to the model as class methods to simplify their use:
    min_data_check(), load_inputs(), save_results().

    This is implemented as calling define_components() for each module
    that has that function defined, then calling
    define_dynamic_components() for each module that has that function
    defined. This division into two stages give some modules an
    opportunity to have dynamic constraints or objective functions. For
    example, financials.define_components() defines empty lists that
    will be used to calculate overall system costs. Other modules such
    as transmission.build and project.build that have components that
    contribute to system costs insert the names of those components into
    these lists. The total system costs equation is defined in
    financials.define_dynamic_components() as the sum of elements in
    those lists. This division into multiple stages allows a user of
    Switch to include additional modules such as demand response or
    storage without rewriting the core equations for system costs. The
    two primary use cases for dynamic components so far are load-zone
    level energy balancing and overall system costs.

    SYNOPSIS:
    >>> from switch_mod.utilities import define_AbstractModel
    >>> model = define_AbstractModel(
    ...     'switch_mod', 'project.no_commit', 'fuel_cost')

    """
    # Load modules
    module_list_full_names = _load_modules(*module_list)
    model = AbstractModel()
    # Add the list of modules to the model
    model.module_list = module_list_full_names
    # Bind some utility functions to the model as class objects
    _add_min_data_check(model)
    model.load_inputs = types.MethodType(load_inputs, model)
    model.save_results = types.MethodType(save_results, model)
    # Define the model components
    _define_components(model, model.module_list)
    _define_dynamic_components(model, model.module_list)
    return model


def load_inputs(model, inputs_dir="inputs"):
    """

    Load input data for an AbstractModel using the modules in the given
    list and return a DataPortal object suitable for creating a model
    instance. This is implemented as calling the load_inputs() function
    of each module, if the module has that function.

    SYNOPSIS:
    >>> from switch_mod.utilities import define_AbstractModel
    >>> model = define_AbstractModel(
    ...     'switch_mod', 'project.no_commit', 'fuel_cost')
    >>> instance = model.load_inputs(inputs_dir='test_dat')

    """
    data = DataPortal(model=model)
    # Attach an augmented load data function to the data portal object
    data.load_aug = types.MethodType(load_aug, data)
    _load_inputs(model, inputs_dir, model.module_list, data)
    instance = model.create(data)
    return instance


def save_results(model, results, instance, outdir):
    """

    Export results in a modular fashion.

    """
    # Ensure the output directory exists. Don't worry about race
    # conditions.
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    # Try to load the results and export.
    if instance.load(results):
        if interactive_session:
            print "Model solved successfully."
        _save_results(model, instance, outdir, model.module_list)
        return True
    else:
        if interactive_session:
            print ("ERROR: unable to load solver results. " +
                   "Problem may be infeasible.")
        return False


def load_aug(switch_data, optional=False, **kwds):
    """
    This is a wrapper for DataPortal.load() that allows more robust
    processing and error reporting of input files.

    If the argument "optional" is set to True, this will not attempt
    to load an input file that is missing or empty.

    In the future, this will also support individual columns being
    optional as well.

    The name of this function is bad and will likely be changed when
    I think of something better.

    """
    path = kwds['filename']
    # Skip if the file is missing
    if optional and not os.path.isfile(path):
        return
    # Parse header and first row
    with open(path) as infile:
        headers = infile.readline().strip().split('\t')
        dat1 = infile.readline().strip().split('\t')
    # Skip if the file is empty or has no data in the first row.
    if optional and (headers == [''] or dat1 == ['']):
        return
    # Check to see if expected column names are in the file.
    if 'select' in kwds:
        for col in kwds['select']:
            if col not in headers:
                raise InputError(
                    'Column {} not found in file {}.'
                    .format(col, path))
    switch_data.load(**kwds)


def min_data_check(model, *mandatory_model_components):
    """

    This function checks that an instance of Pyomo abstract model has
    mandatory components defined. If a user attempts to create an
    instance without defining all of the necessary data, this will
    produce fatal errors with clear messages stating specifically what
    components have missing data. This function is attached to an
    abstract model by the _add_min_data_check() function. See
    _add_min_data_check() documentation for usage examples.

    Without this check, I would get fatal errors if I forgot to specify data
    for a component that didn't have a default value, but the error message
    was obscure and gave me a line number with the first snippet of code
    that tried to reference the component with missing data. It took me a
    little bit of time to figure out what was causing that failure, and I'm
    a skilled programmer. I would like this model to be accessible to non-
    programmers as well, so I felt it was important to use the BuildCheck
    Pyomo function to validate data during construction of a model instance.

    I found that BuildCheck's message listed the name of the check that
    failed, but did not provide mechanisms for printing a specific error
    message. I tried printing to the screen, but that output tended to be
    obscured or hidden. I've settled on raising a ValueError for now with a
    clear and specific message. I could also use logging.error() or related
    logger methods, and rely on BuildCheck to throw an error, but I've
    already implemented this, and those other methods don't offer any clear
    advantages that I can see.

    """
    model.__num_min_data_checks += 1
    new_data_check_name = "min_data_check_" + str(model.__num_min_data_checks)
    setattr(model, new_data_check_name, BuildCheck(
        rule=lambda m: check_mandatory_components(
            m, *mandatory_model_components)))


def _add_min_data_check(model):
    """

    Bind the min_data_check() method to an instance of a Pyomo AbstractModel
    object if it has not already been added. Also add a counter to keep
    track of what to name the next check that is added.

    >>> from switch_mod.utilities import _add_min_data_check
    >>> mod = AbstractModel()
    >>> _add_min_data_check(mod)
    >>> mod.set_A = Set(initialize=[1,2])
    >>> mod.paramA_full = Param(mod.set_A, initialize={1:'a',2:'b'})
    >>> mod.paramA_empty = Param(mod.set_A)
    >>> mod.min_data_check('set_A', 'paramA_full')
    >>> instance_pass = mod.create()
    >>> mod.min_data_check('set_A', 'paramA_empty')
    >>> try:
    ...     instance_fail = mod.create()
    ... except ValueError as e:
    ...     print e  # doctest: +NORMALIZE_WHITESPACE
    ERROR: Constructing component 'min_data_check_2' from data=None failed:
        ValueError: Values are not provided for every element of the
        mandatory parameter 'paramA_empty'
    Values are not provided for every element of the mandatory parameter
    'paramA_empty'


    """
    if getattr(model, 'min_data_check', None) is None:
        model.__num_min_data_checks = 0
        model.min_data_check = types.MethodType(min_data_check, model)


def check_mandatory_components(model, *mandatory_model_components):
    """
    Checks whether mandatory elements of a Pyomo model are populated,
    and returns a clear error message if they don't exist.

    Typically, this method is not used directly. Instead, the
    min_data_check() method will set up a BuildCheck that uses this
    function.

    If an argument is a set, it must have non-zero length.

    If an argument is an indexed parameter, it must have a value for
    every index in the indexed set. Do not use this for indexed params
    that have default values. If the set indexing a param is not
    mandatory and is empty, then the indexed parameter may be empty as
    well.

    If an argument is a simple parameter, it must have a value.

    This does not work with indexed sets.

    EXAMPLE:
    >>> from pyomo.environ import *
    >>> import switch_mod.utilities as utilities
    >>> mod = ConcreteModel()
    >>> mod.set_A = Set(initialize=[1,2])
    >>> mod.paramA_full = Param(mod.set_A, initialize={1:'a',2:'b'})
    >>> mod.paramA_empty = Param(mod.set_A)
    >>> mod.set_B = Set()
    >>> mod.paramB_empty = Param(mod.set_B)
    >>> mod.paramC = Param(initialize=1)
    >>> mod.paramD = Param()
    >>> utilities.check_mandatory_components(mod, 'set_A', 'paramA_full')
    True
    >>> utilities.check_mandatory_components(mod, 'paramB_empty')
    True
    >>> utilities.check_mandatory_components(mod, 'paramC')
    True
    >>> utilities.check_mandatory_components(\
        mod, 'set_A', 'paramA_empty') # doctest: +NORMALIZE_WHITESPACE
    Traceback (most recent call last):
        ...
    ValueError: Values are not provided for every element of the
    mandatory parameter 'paramA_empty'
    >>> utilities.check_mandatory_components(mod, 'set_A', 'set_B')
    Traceback (most recent call last):
        ...
    ValueError: No data is defined for the mandatory set 'set_B'.
    >>> utilities.check_mandatory_components(mod, 'paramC', 'paramD')
    Traceback (most recent call last):
        ...
    ValueError: Value not provided for mandatory parameter 'paramD'

    # Demonstration of incorporating this funciton into Pyomo's BuildCheck()
    >>> mod.min_dat_pass = BuildCheck(\
            rule=lambda m: utilities.check_mandatory_components(\
                m, 'set_A', 'paramA_full','paramB_empty', 'paramC'))
    """

    for component_name in mandatory_model_components:
        obj = getattr(model, component_name)
        o_class = type(obj).__name__
        if o_class == 'SimpleSet' or o_class == 'OrderedSimpleSet':
            if len(obj) == 0:
                raise ValueError(
                    "No data is defined for the mandatory set '{}'.".
                    format(component_name))
        elif o_class == 'IndexedParam':
            if len(obj) != len(obj._index):
                raise ValueError(
                    ("Values are not provided for every element of " +
                     "the mandatory parameter '{}'").format(component_name))
        elif o_class == 'IndexedSet':
            if len(obj) != len(obj._index):
                raise ValueError(
                    ("Sets are not defined for every index of " +
                     "the mandatory indexed set '{}'").format(component_name))
        elif o_class == 'SimpleParam':
            if obj.value is None:
                raise ValueError(
                    "Value not provided for mandatory parameter '{}'".
                    format(component_name))
        else:
            raise ValueError(
                "Error! Object type {} not recognized for model element '{}'.".
                format(o_class, component_name))
    return True


def _load_modules(*module_list):
    """

    An internal function to recursively load switch modules that define
    components of an abstract model.

    SYNOPSIS:
    >>> from switch_mod.utilities import _load_modules
    >>> full_module_names = _load_modules(
    ...     'switch_mod', 'project.no_commit', 'fuel_cost')

    This will first attempt to load each listed modules from the
    switch_mod package, and will look for them in the broader system
    path if the first attempt fails. If any listed module is a package
    that includes a list named core_modules in __init__.py that contains
    full formed module names, those modules will be loaded recursively
    by this function.

    This function returns the full names of each loaded modules,
    including the "switch_mod." package prefix. After this function
    is called, each loaded module will be accessible via sys.modules

    """
    # Traverse the list of switch modules and load each one.
    full_names = []
    for m in module_list:
        # Skip loading if it was already loaded
        if m in _full_module_names:
            full_names.append(_full_module_names[m])
            continue
        # First try to load this module from the switch package
        try:
            module = importlib.import_module('.' + m, package='switch_mod')
            full_names.append(module.__name__)
        # If that doesn't work, try from the general python path
        except ImportError:
            module = importlib.import_module(m)
            full_names.append(module.__name__)
        # If this has a list of core_modules, load them.
        if hasattr(module, 'core_modules'):
            _load_modules(*module.core_modules)
        # Add this to the list of known loaded modules
        _full_module_names[m] = module.__name__
    return full_names


def _define_components(model, module_list):
    """
    A private function to allow recurve calling of defining standard
    components from modules or packages.
    """
    for m in module_list:
        module = sys.modules[m]
        if hasattr(module, 'define_components'):
            module.define_components(model)
        if hasattr(module, 'core_modules'):
            _define_components(model, module.core_modules)


def _define_dynamic_components(model, module_list):
    """
    A private function to allow recurve calling of defining dynamic
    components from modules or packages.
    """
    for m in module_list:
        module = sys.modules[m]
        if hasattr(module, 'define_dynamic_components'):
            module.define_dynamic_components(model)
        if hasattr(module, 'core_modules'):
            _define_dynamic_components(model, module.core_modules)


def _load_inputs(model, inputs_dir, module_list, data):
    """
    A private function to allow recurve calling of loading data from
    modules or packages.
    """
    for m in module_list:
        module = sys.modules[m]
        if hasattr(module, 'load_inputs'):
            module.load_inputs(model, data, inputs_dir)
        if hasattr(module, 'core_modules'):
            _load_inputs(model, inputs_dir, module.core_modules, data)


def _save_results(model, instance, outdir, module_list):
    """
    A private function to allow recurve calling of saving results from
    modules or packages.
    """
    for m in module_list:
        module = sys.modules[m]
        if hasattr(module, 'save_results'):
            module.save_results(model, instance, outdir)
        if hasattr(module, 'core_modules'):
            _save_results(model, instance, outdir, module.core_modules)


class InputError(Exception):
    """Exception raised for errors in the input.

    Attributes:
        expression -- input expression in which the error occurred
        message -- explanation of the error
    """

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def approx_equal(a, b, tolerance=0.01):
    return abs(a-b) <= (abs(a) + abs(b)) / 2.0 * tolerance
