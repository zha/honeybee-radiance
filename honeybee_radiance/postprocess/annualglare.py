"""Functions for post-processing imageless annual glare outputs.

Note: These functions will most likely be moved to a separate package in the near future.
"""
import json
import os

from .annual import filter_schedule_by_hours, _process_input_folder


def glare_autonomy_to_file(dgp_file, occ_pattern, output_folder, glare_threshold=0.4,
                           grid_name=None, total_hours=None):
    """Compute glare autonomy for an dgp file and write the results to a folder.

    This function generates 1 file for glare autonomy.

    Args:
        dgp_file: Path to an dgp file generated by Radiance. The dgp file should be
            tab separated and shot NOT have a header. The results for each sensor point
            should be available in a row and and each column should be the daylight
            glare probability value for a sun_up_hour. The number of columns should
            match the number of sun up hours.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        output_folder: An output folder where the results will be written to. The folder
            will be created if not exist.
        glare_threshold: A fractional number for the threshold of DGP above which
            conditions are considered to induce glare. Default: 0.4.
        grid_name: An optional name for grid name which will be used to name the output
            files. If None the name of the input file will be used.
        total_hours: An integer for the total number of occupied hours in the
            occupancy schedule. If None, it will be assumed that all of the
            occupied hours are sun-up hours and are already accounted for
            in the the occ_pattern.

    Returns:
        file.ga

    """
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    grid_name = grid_name or os.path.split(dgp_file)[-1][-4:]
    ga = os.path.join(output_folder, 'ga', '%s.ga' % grid_name).replace('\\', '/')

    folder = os.path.dirname(ga)
    if not os.path.isdir(folder):
        os.makedirs(folder)

    with open(dgp_file) as results, open(ga, 'w') as gaf:
        for pt_res in results:
            values = (float(res) for res in pt_res.split())
            gar = _glare_autonomy(values, occ_pattern, glare_threshold, total_hours)
            gaf.write(str(gar) + '\n')

    return ga


def glare_autonomy(dgp_file, occ_pattern, glare_threshold=0.4, total_hours=None):
    """Compute glare autonomy for a given result file.

    Args:
        dgp_file: Path to a dgp file generated by Radiance. The dgp file should be
            tab separated and shot NOT have a header. The results for each sensor point
            should be available in a row and and each column should be the DGP value for
            a sun_up_hour. The number of columns should match the number of sun up hours.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        glare_threshold: Threshold DGP level for glare autonomy. Default: 0.4.
        total_hours: An integer for the total number of occupied hours in the
            occupancy schedule. If None, it will be assumed that all of the
            occupied hours are sun-up hours and are already accounted for
            in the the occ_pattern.

    Returns:
        A list of glare autonomy values. Number of results in each list matches the
        number of lines in dgp input file.

    """
    ga = []
    total_occupied_hours = sum(occ_pattern) if total_hours is None else total_hours
    with open(dgp_file) as results:
        for pt_res in results:
            values = (float(res) for res in pt_res.split())
            ga_v = _glare_autonomy(
                values, occ_pattern, glare_threshold, total_occupied_hours
            )
            ga.append(ga_v)

    return ga


# TODO - support a list of schedules/schedule folder to match the input grids
def glare_autonomy_from_folder(results_folder, schedule=None, glare_threshold=0.4, 
                               grids_filter='*'):
    """Compute glare autonomy for a folder.

    This folder is an output folder of imageless annual glare recipe. Folder should
    include grids_info.json and sun-up-hours.txt - the script uses the list in
    grids_info.json to find the result files for each sensor grid.

    Args:
        results_folder: Results folder.
        schedule: An annual schedule for 8760 hours of the year as a list of values.
        glare_threshold: Threshold DGP level for glare autonomy. Default: 0.4.
        grids_filter: A pattern to filter the grids. By default all the grids will be
            processed.

    Returns:
        Tuple[List] - There will be a list for each input sensor grid. Number of results
        in each list matches the number of lines in ill input file.

    """
    ga = []

    grids, sun_up_hours = _process_input_folder(results_folder, grids_filter)
    occ_pattern, total_occ = \
        filter_schedule_by_hours(sun_up_hours=sun_up_hours, schedule=schedule)

    for grid in grids:
        dgp_file = os.path.join(results_folder, '%s.dgp' % grid['full_id'])
        ga_r = glare_autonomy(dgp_file, occ_pattern, glare_threshold, total_occ)
        ga.append(ga_r)

    return ga


def glare_autonomy_to_folder(
    results_folder, schedule=None, glare_threshold=0.4, grids_filter='*',
    sub_folder='metrics'
        ):
    """Compute annual glare autonomy in a folder and write them in a subfolder.

    This folder is an output folder of imageless annual glare recipe. Folder should
    include grids_info.json and sun-up-hours.txt - the script uses the list in
    grids_info.json to find the result files for each sensor grid.

    Args:
        results_folder: Results folder.
        schedule: An annual schedule for 8760 hours of the year as a list of values.
        glare_threshold: A fractional number for the threshold of DGP above which
            conditions are considered to induce glare. Default: 0.4.
        grids_filter: A pattern to filter the grids. By default all the grids will be
            processed.
        sub_folder: An optional relative path for subfolder to copy results files.
            Default: metrics

    Returns:
        str -- Path to results folder.

    """
    grids, sun_up_hours = _process_input_folder(results_folder, grids_filter)
    occ_pattern, total_occ = \
        filter_schedule_by_hours(sun_up_hours=sun_up_hours, schedule=schedule)

    metrics_folder = os.path.join(results_folder, sub_folder)
    if not os.path.isdir(metrics_folder):
        os.makedirs(metrics_folder)

    for grid in grids:
        dgp_file = os.path.join(results_folder, '%s.dgp' % grid['full_id'])
        glare_autonomy_to_file(
            dgp_file, occ_pattern, metrics_folder, glare_threshold,
            grid['full_id'], total_occ
        )

    # copy info.json to all results folders
    grid_info = os.path.join(metrics_folder, 'ga', 'grids_info.json')
    with open(grid_info, 'w') as outf:
        json.dump(grids, outf)

    # create info for available results. This file will be used by honeybee-vtk for
    # results visualization
    config_file = os.path.join(metrics_folder, 'config.json')

    cfg = _annual_glare_config()

    with open(config_file, 'w') as outf:
        json.dump(cfg, outf)

    return metrics_folder


def _glare_autonomy(values, occ_pattern, glare_threshold, total_hours):
    """Calculate annual glare autonomy for a sensor.

    Args:
        values: Hourly illuminance values as numbers.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        glare_threshold: A fractional number for the threshold of DGP above which
            conditions are considered to induce glare. Default: 0.4.
        total_hours: An integer for the total number of occupied hours, which can be used
            to avoid having to sum occ pattern each time.

    Returns:
        glare autonomy
    """
    def _percentage(in_v, occ_hours):
        return round(100.0 * in_v / occ_hours, 2)

    ga_above = 0
    # count hours above glare threshold
    for is_occ, value in zip(occ_pattern, values):
        if is_occ == 0:
            continue
        if value > glare_threshold:
            ga_above += 1

    # get the number of glare free hours
    ga = total_hours - ga_above

    return _percentage(ga, total_hours)


def _annual_glare_config():
    """Return vtk-config for imageless annual glare."""
    cfg = {
        "data": [
            {
                "identifier": "Glare Autonomy",
                "object_type": "grid",
                "unit": "Percentage",
                "path": "ga",
                "hide": False,
                "legend_parameters": {
                    "hide_legend": False,
                    "min": 0,
                    "max": 100,
                    "color_set": "original",
                    "label_parameters": {
                        "color": [34, 247, 10],
                        "size": 0,
                        "bold": True,
                    },
                },
            },
        ]
    }

    return cfg
