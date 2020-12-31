import json
import logging
import os
import pathlib
import typing as T

import click
import structlog  # type: ignore

LOGGER = structlog.get_logger()


def open_cmor_tables(
    cmor_tables_dir: T.Union[str, "os.PathLike[str]"]
) -> T.List[T.Dict[str, T.Any]]:
    cmor_tables_dir = pathlib.Path(cmor_tables_dir)
    cmor_table_paths = [
        cmor_tables_dir / "CDS_coordinate.json",
        cmor_tables_dir / "CDS_variable.json",
    ]
    cmor_objects = []
    for path in cmor_table_paths:
        with open(path) as fp:
            cmor_objects.append(json.load(fp))
    return cmor_objects


def cmor_to_cdm(cmor_objects: T.List[T.Dict[str, T.Any]]) -> T.Dict[str, T.Any]:
    axis_entry: T.Dict[str, T.Dict[str, str]]
    variable_entry: T.Dict[str, T.Dict[str, str]]
    cdm_coords: T.Dict[str, T.Any] = {}
    cdm_data_vars = {}
    for cmor_object in cmor_objects:
        axis_entry = cmor_object.get("axis_entry", {})
        variable_entry = cmor_object.get("variable_entry", {})

        for _, coord in sorted(
            axis_entry.items(), key=lambda x: x[1].get("out_name", x[0])
        ):
            cdm_coord = {
                k: v
                for k, v in coord.items()
                if v and k in {"standard_name", "long_name"}
            }
            if coord.get("units", "") and "since" not in coord["units"]:
                cdm_coord["units"] = coord["units"]
            if coord.get("stored_direction", "") not in {"increasing", ""}:
                cdm_coord["stored_direction"] = coord["stored_direction"]
            cdm_coords[coord["out_name"]] = cdm_coord

        for coord in sorted(variable_entry.values(), key=lambda x: x["out_name"]):
            cdm_data_var = {
                k: v
                for k, v in coord.items()
                if v and k in {"standard_name", "long_name", "units"}
            }
            cdm_data_vars[coord["out_name"]] = cdm_data_var

    cdm = {
        "attrs": ["title", "history", "institution", "source", "comment", "references"],
        "coords": cdm_coords,
        "data_vars": cdm_data_vars,
    }
    return cdm


@click.command()
@click.argument("cmor_tables_dir", type=click.Path(exists=True))
def cmor_to_cdm_cli(cmor_tables_dir: str) -> None:
    logging.basicConfig(level=logging.INFO)
    structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())
    cmor_objects = open_cmor_tables(cmor_tables_dir)
    cdm_objects = cmor_to_cdm(cmor_objects)
    print(json.dumps(cdm_objects, separators=(",", ":"), indent=1, sort_keys=True))
