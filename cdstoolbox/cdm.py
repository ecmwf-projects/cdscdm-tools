import logging

import cfunits
import click
import structlog
import xarray as xr


LOGGER = structlog.get_logger()

CDM_VARIABLES = {
    "air_temperature": {"units": "K", "long_name": "temperature",},
}

CDM_GLOBAL_ATTRIBUTES = [
    "title",
    "history",
    "institution",
    "source",
    "comment",
    "references",
]


class CommonDataModelError(Exception):
    pass


def check_coordinates(coords, log=LOGGER):
    pass


def check_dataset_attrs(attrs, log=LOGGER):
    conventions = attrs.get("Conventions")
    if conventions is None:
        log.warning("missing required 'Conventions' global attribute")
    elif conventions not in ["CF-1.8", "CF-1,7", "CF-1.6"]:
        log.warning("invalid 'Conventions' value", conventions=conventions)

    for attr_name in CDM_GLOBAL_ATTRIBUTES:
        if attr_name not in attrs:
            log.warning(f"missing recommended global attribute '{attr_name}'")


def check_variable_attrs(attrs, log=LOGGER):
    standard_name = attrs.get("standard_name")
    units = attrs.get("units")

    expected_attrs = CDM_VARIABLES.get(standard_name, {})
    expected_units = expected_attrs.get("units")

    if standard_name is not None:
        log = log.bind(standard_name=standard_name)

    if "long_name" not in attrs:
        log.warning("missing recommended attribute 'long_name'")

    if "units" not in attrs:
        log.warning("missing recommended attribute 'units'")
    else:
        cf_units = cfunits.Units(units)
        if not cf_units.isvalid:
            log.warning("'units' attribute not valid", units=units)
        elif expected_units is not None:
            expected_cf_units = cfunits.Units(expected_units)
            log = log.bind(units=units, expected_units=expected_units)
            if not cf_units.equivalent(expected_cf_units):
                log.warning("'units' attribute not equivalent to the expected")
            elif not cf_units.equals(expected_cf_units):
                log.warning("'units' attribute not equal to the expected")


def check_variable(data_var, data_var_name=None, log=LOGGER):
    log = log.bind(data_var_name=data_var_name)
    check_variable_attrs(data_var.attrs, log=log)


def check_dataset(dataset, log=LOGGER):
    data_vars = list(dataset.data_vars)
    if len(data_vars) > 1:
        log.error("file must have at most one variable", data_vars=data_vars)
    check_dataset_attrs(dataset.attrs)
    for data_var_name, data_var in dataset.data_vars.items():
        check_variable(data_var, data_var_name=data_var_name)


def open_netcdf_dataset(file_path):
    return xr.open_dataset(file_path, engine="netcdf4")


def check_file(file_path, log=LOGGER):
    try:
        dataset = open_netcdf_dataset(file_path)
    except OSError:
        raise CommonDataModelError("Cannot open file as netCDF4 data")
    check_dataset(dataset)


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
def check_file_cli(file_path):
    logging.basicConfig(level=logging.INFO)
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())
    check_file(file_path)
