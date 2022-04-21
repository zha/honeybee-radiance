"""Functions for post-processing annual daylight outputs.

Note: These functions will most likely be moved to a separate package in the near future.
"""
import json
import os

from .annual import filter_schedule_by_hours, _process_input_folder


def _metrics(values, occ_pattern, threshold, min_t, max_t, total_hours):
    """Calculate annual metrics for a sensor.

    Args:
        values: Hourly illuminance values as numbers.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        threshold: Threshold value for daylight autonomy. Default: 300.
        min_t: Minimum threshold for useful daylight illuminance. Default: 100.
        max_t: Maximum threshold for useful daylight illuminance. Default: 3000.
        total_hours: An integer for the total number of occupied hours,
            which can be used to avoid having to sum occ pattern each time.

    Returns:
        Tuple -- daylight autonomy, continuous daylight autonomy, lower useful daylight
            illuminance, useful daylight illuminance, higher useful daylight illuminance
    """
    def _percentage(in_v, occ_hours):
        return round(100.0 * in_v / occ_hours, 2)

    da = 0
    cda = 0
    udi_lower = 0
    udi = 0
    udi_upper = 0

    for is_occ, value in zip(occ_pattern, values):
        if is_occ == 0:
            continue
        if value > threshold:
            da += 1
            cda += 1
        else:
            cda += value / threshold

        if min_t > value:
            udi_lower += 1
        elif value > max_t:
            udi_upper += 1
        else:
            udi += 1

    return _percentage(da, total_hours), _percentage(cda, total_hours), \
        _percentage(udi_lower, total_hours), _percentage(udi, total_hours), \
        _percentage(udi_upper, total_hours)


def metrics(ill_file, occ_pattern, threshold=300, min_t=100, max_t=3000,
            total_hours=None):
    """Compute annual metrics for a given result file.

    Args:
        ill_file: Path to an ill file generated by Radiance. The ill file should be
            tab separated and shot NOT have a header. The results for each sensor point
            should be available in a row and and each column should be the illuminance
            value for a sun_up_hour. The number of columns should match the number of
            sun up hours.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        threshold: Threshold illuminance level for daylight autonomy. Default: 300.
        min_t: Minimum threshold for useful daylight illuminance. Default: 100.
        max_t: Maximum threshold for useful daylight illuminance. Default: 3000.
        total_hours: An integer for the total number of occupied hours in the
            occupancy schedule. If None, it will be assumed that all of the
            occupied hours are sun-up hours and are already accounted for
            in the the occ_pattern.

    Returns:
        Tuple(List, List, List, List, List) -- 5 lists for daylight autonomy,
        continuous daylight automony, lower than useful daylight illuminance,
        useful daylight illuminance and higher than useful daylight illuminance.
        Number of results in each list matches the number of lines in ill input file.

    """
    da = []
    cda = []
    udi = []
    udi_lower = []
    udi_upper = []
    total_occupied_hours = sum(occ_pattern) if total_hours is None else total_hours
    with open(ill_file) as results:
        for pt_res in results:
            values = (float(res) for res in pt_res.split())
            da_v, cda_v, udi_lower_v, udi_v, udi_upper_v = _metrics(
                values, occ_pattern, threshold, min_t, max_t,
                total_occupied_hours
            )
            da.append(da_v)
            cda.append(cda_v)
            udi_lower.append(udi_lower_v)
            udi.append(udi_v)
            udi_upper.append(udi_upper_v)

    return da, cda, udi_lower, udi, udi_upper


def metrics_to_files(ill_file, occ_pattern, output_folder, threshold=300,
                     min_t=100, max_t=3000, grid_name=None, total_hours=None):
    """Compute annual metrics for an ill file and write the results to a folder.

    This function generates 5 different files or daylight autonomy, continuous daylight
    automony, lower than useful daylight illuminance, useful daylight illuminance and
    higher than useful daylight illuminance.

    Args:
        ill_file: Path to an ill file generated by Radiance. The ill file should be
            tab separated and shot NOT have a header. The results for each sensor point
            should be available in a row and and each column should be the illuminance
            value for a sun_up_hour. The number of columns should match the number of
            sun up hours.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        output_folder: An output folder where the results will be written to. The folder
            will be created if not exist.
        threshold: Threshold illuminance level for daylight autonomy. Default: 300.
        min_t: Minimum threshold for useful daylight illuminance. Default: 100.
        max_t: Maximum threshold for useful daylight illuminance. Default: 3000.
        grid_name: An optional name for grid name which will be used to name the output
            files. If None the name of the input file will be used.
        total_hours: An integer for the total number of occupied hours in the
            occupancy schedule. If None, it will be assumed that all of the
            occupied hours are sun-up hours and are already accounted for
            in the the occ_pattern.

    Returns:
        Tuple(file.da, file.cda, file.luid, file.uid, file.hudi)

    """
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    grid_name = grid_name or os.path.split(ill_file)[-1][-4:]
    da = os.path.join(output_folder, 'da', '%s.da' % grid_name).replace('\\', '/')
    cda = os.path.join(output_folder, 'cda', '%s.cda' % grid_name).replace('\\', '/')
    udi = os.path.join(output_folder, 'udi', '%s.udi' % grid_name).replace('\\', '/')
    udi_lower = \
        os.path.join(output_folder, 'udi_lower', '%s.udi' % grid_name).replace('\\', '/')
    udi_upper = \
        os.path.join(output_folder, 'udi_upper', '%s.udi' % grid_name).replace('\\', '/')

    for file_path in [da, cda, udi, udi_upper, udi_lower]:
        folder = os.path.dirname(file_path)
        if not os.path.isdir(folder):
            os.makedirs(folder)

    with open(ill_file) as results, open(da, 'w') as daf, open(cda, 'w') as cdaf, \
            open(udi, 'w') as udif, open(udi_lower, 'w') as udi_lowerf, \
            open(udi_upper, 'w') as udi_upperf:
        for pt_res in results:
            values = (float(res) for res in pt_res.split())
            dar, cdar, udi_lowerr, udir, udi_upperr = _metrics(
                values, occ_pattern, threshold, min_t, max_t, total_hours
            )
            daf.write(str(dar) + '\n')
            cdaf.write(str(cdar) + '\n')
            udi_lowerf.write(str(udi_lowerr) + '\n')
            udif.write(str(udir) + '\n')
            udi_upperf.write(str(udi_upperr) + '\n')

    return da, cda, udi_lower, udi, udi_upper


# TODO - support a list of schedules/schedule folder to match the input grids
def metrics_from_folder(results_folder, schedule=None, threshold=300,
                        min_t=100, max_t=3000, grids_filter='*'):
    """Compute annual metrics for a folder.

    This folder is an output folder of annual daylight recipe. Folder should include
    grids_info.json and sun-up-hours.txt - the script uses the list in grids_info.json
    to find the result files for each sensor grid.

    Args:
        results_folder: Results folder.
        schedule: An annual schedule for 8760 hours of the year as a list of values.
        threshold: Threshold illuminance level for daylight autonomy. Default: 300.
        min_t: Minimum threshold for useful daylight illuminance. Default: 100.
        max_t: Maximum threshold for useful daylight illuminance. Default: 3000.
        grids_filter: A pattern to filter the grids. By default all the grids will be
            processed.

    Returns:
        Tuple[Tuple] - There will be a tuple for each input sensor grid which is a
        Tuple(List, List, List, List, List) -- 5 lists for daylight autonomy,
        continuous daylight automony, lower than useful daylight illuminance,
        useful daylight illuminance and higher than useful daylight illuminance.
        Number of results in each list matches the number of lines in ill input file.

    """
    da = []
    cda = []
    udi = []
    udi_lower = []
    udi_upper = []

    grids, sun_up_hours = _process_input_folder(results_folder, grids_filter)
    occ_pattern, total_occ = \
        filter_schedule_by_hours(sun_up_hours=sun_up_hours, schedule=schedule)

    for grid in grids:
        ill_file = os.path.join(results_folder, '%s.ill' % grid['full_id'])
        da_r, cda_r, udi_lower_r, udi_r, udi_upper_r = \
            metrics(ill_file, occ_pattern, threshold, min_t, max_t, total_occ)
        da.append(da_r)
        cda.append(cda_r)
        udi_lower.append(udi_lower_r)
        udi.append(udi_r)
        udi_upper.append(udi_upper_r)

    return da, cda, udi_lower, udi, udi_upper


# TODO - support a list of schedules/schedule folder to match the input grids
def metrics_to_folder(
    results_folder, schedule=None, threshold=300, min_t=100, max_t=3000,
    grids_filter='*', sub_folder='metrics'
        ):
    """Compute annual metrics in a folder and write them in a subfolder.

    This folder is an output folder of annual daylight recipe. Folder should include
    grids_info.json and sun-up-hours.txt - the script uses the list in grids_info.json
    to find the result files for each sensor grid.

    Args:
        results_folder: Results folder.
        schedule: An annual schedule for 8760 hours of the year as a list of values.
        threshold: Threshold illuminance level for daylight autonomy. Default: 300.
        min_t: Minimum threshold for useful daylight illuminance. Default: 100.
        max_t: Maximum threshold for useful daylight illuminance. Default: 3000.
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
        ill_file = os.path.join(results_folder, '%s.ill' % grid['full_id'])
        metrics_to_files(
            ill_file, occ_pattern, metrics_folder, threshold, min_t,
            max_t, grid['full_id'], total_occ
        )

    # copy info.json to all results folders
    for folder_name in ['da', 'cda', 'udi_lower', 'udi', 'udi_upper']:
        grid_info = os.path.join(metrics_folder, folder_name, 'grids_info.json')
        with open(grid_info, 'w') as outf:
            json.dump(grids, outf)

    # create info for available results. This file will be used by honeybee-vtk for
    # results visualization
    config_file = os.path.join(metrics_folder, 'config.json')

    cfg = _annual_daylight_config()

    with open(config_file, 'w') as outf:
        json.dump(cfg, outf)

    return metrics_folder


def _annual_daylight_config():
    """Return vtk-config for annual daylight. """
    cfg = {
        "data": [
            {
                "identifier": "Useful Daylight Illuminance Lower",
                "object_type": "grid",
                "unit": "Percentage",
                "path": "udi_lower",
                "hide": False,
                "legend_parameters": {
                    "hide_legend": False,
                    "min": 0,
                    "max": 100,
                    "color_set": "nuanced",
                },
            },
            {
                "identifier": "Useful Daylight Illuminance Upper",
                "object_type": "grid",
                "unit": "Percentage",
                "path": "udi_upper",
                "hide": False,
                "legend_parameters": {
                    "hide_legend": False,
                    "min": 0,
                    "max": 100,
                    "color_set": "glare_study",
                    "label_parameters": {
                        "color": [34, 247, 10],
                        "size": 0,
                        "bold": True,
                    },
                },
            },
            {
                "identifier": "Useful Daylight Illuminance",
                "object_type": "grid",
                "unit": "Percentage",
                "path": "udi",
                "hide": False,
                "legend_parameters": {
                    "hide_legend": False,
                    "min": 0,
                    "max": 100,
                    "color_set": "annual_comfort",
                    "label_parameters": {
                        "color": [34, 247, 10],
                        "size": 0,
                        "bold": True,
                    },
                },
            },
            {
                "identifier": "Continuous Daylight Autonomy",
                "object_type": "grid",
                "unit": "Percentage",
                "path": "cda",
                "hide": False,
                "legend_parameters": {
                    "hide_legend": False,
                    "min": 0,
                    "max": 100,
                    "color_set": "annual_comfort",
                    "label_parameters": {
                        "color": [34, 247, 10],
                        "size": 0,
                        "bold": True,
                    },
                },
            },
            {
                "identifier": "Daylight Autonomy",
                "object_type": "grid",
                "unit": "Percentage",
                "path": "da",
                "hide": False,
                "legend_parameters": {
                    "hide_legend": False,
                    "min": 0,
                    "max": 100,
                    "color_set": "annual_comfort",
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
