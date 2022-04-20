"""Functions for post-processing EN 17037 daylight outputs."""
import json
import os
import re

from .annual import filter_schedule_by_hours, _process_input_folder


def _metrics(values, occ_pattern, threshold, total_hours):
    """Calculate annual metrics for a sensor.

    Args:
        values: Hourly illuminance values as numbers.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        threshold: Threshold value for daylight autonomy.
        total_occupied_hours: An integer for the total number of occupied hours,
            which can be used to avoid having to sum occ pattern each time.

    Returns:
        daylight autonomy
    """
    def _percentage(in_v, occ_hours):
        return round(100.0 * in_v / occ_hours, 2)

    da = 0
    for is_occ, value in zip(occ_pattern, values):
        if is_occ == 0:
            continue
        if value > threshold:
            da += 1

    return _percentage(da, total_hours)


def metrics_to_files(
    ill_file, occ_pattern, output_folder, grid_name=None, total_hours=None
):
    """Compute annual EN 17037 metrics for an ill file and write the results to a folder.

    This function generates 6 different files for daylight autonomy based on the varying
    level of reccomendation in EN 17037.

    Args:
        ill_file: Path to an ill file generated by Radiance. The ill file should be
            tab separated and shot NOT have a header. The results for each sensor point
            should be available in a row and and each column should be the illuminance
            value for a sun_up_hour. The number of columns should match the number of
            sun up hours.
        occ_pattern: A list of 0 and 1 values for hours of occupancy.
        output_folder: An output folder where the results will be written to. The folder
            will be created if not exist.
        grid_name: An optional name for grid name which will be used to name the output
            files. If None the name of the input file will be used.
        total_hours: An integer for the total number of occupied hours in the
            occupancy schedule. If None, it will be assumed that all of the
            occupied hours are sun-up hours and are already accounted for
            in the the occ_pattern.
    """
    if not os.path.isdir(output_folder):
        os.makedirs(output_folder)

    recommendations = {
        'minimum': {
            'minimum': 100,
            'medium': 300,
            'high': 500
        }
        ,
        'target': {
            'minimum': 300,
            'medium': 500,
            'high': 750
        }
    }

    grid_name = grid_name or os.path.split(ill_file)[-1][-4:]

    for target_type, thresholds in recommendations.items():
        type_folder = os.path.join(output_folder, target_type)
        if not os.path.isdir(type_folder):
            os.makedirs(type_folder)

        for level, threshold in thresholds.items():
            level_folder = os.path.join(type_folder, level)
            if not os.path.isdir(level_folder):
                os.makedirs(level_folder)
        
            da_file = os.path.join(
                level_folder, 'da', '%s.da' % grid_name).replace('\\', '/')
            folder = os.path.dirname(da_file)
            if not os.path.isdir(folder):
                os.makedirs(folder)
            sda_file = os.path.join(
                level_folder, 'sda', '%s.sda' % grid_name).replace('\\', '/')
            folder = os.path.dirname(sda_file)
            if not os.path.isdir(folder):
                os.makedirs(folder)

            da = []
            with open(ill_file) as results, open(da_file, 'w') as daf:
                for pt_res in results:
                    values = (float(res) for res in pt_res.split())
                    #assert False, [float(res) for res in pt_res.split()]
                    dar = _metrics(values, occ_pattern, threshold, total_hours)
                    daf.write(str(dar) + '\n')
                    da.append(dar)

            space_target = 50 if target_type == 'target' else 95
            pass_fail = [int(val > space_target) for val in da]

            sda = sum(pass_fail) / len(pass_fail)
            with open(sda_file, 'w') as sdaf:
                sdaf.write(str(sda))


# TODO - support a list of schedules/schedule folder to match the input grids
def en17037_to_folder(
    results_folder, schedule, grids_filter='*', sub_folder='metrics'
        ):
    """Compute annual EN 17037 metrics in a folder and write them in a subfolder.

    This folder is an output folder of annual daylight recipe. Folder should include
    grids_info.json and sun-up-hours.txt - the script uses the list in grids_info.json
    to find the result files for each sensor grid.

    Args:
        results_folder: Results folder.
        schedule: An annual schedule for 8760 hours of the year as a list of values. This
            should be a daylight hours schedule.
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

    if total_occ != 4380:
        raise ValueError('There are %s occupied hours in the schedule. According to '
            'EN 17037 the schedule must consist of the daylight hours which is defined '
            'as the half of the year with the largest quantity of daylight' % total_occ)

    metrics_folder = os.path.join(results_folder, sub_folder)
    if not os.path.isdir(metrics_folder):
        os.makedirs(metrics_folder)
    assert False, sum(occ_pattern)
    for grid in grids:
        ill_file = os.path.join(results_folder, '%s.ill' % grid['full_id'])
        metrics_to_files(
            ill_file, occ_pattern, metrics_folder, grid['full_id'], total_occ
        )

    # copy info.json to all results folders
    # for folder_name in ['da', 'cda', 'udi_lower', 'udi', 'udi_upper']:
    #     grid_info = os.path.join(metrics_folder, folder_name, 'grids_info.json')
    #     with open(grid_info, 'w') as outf:
    #         json.dump(grids, outf)

    # create info for available results. This file will be used by honeybee-vtk for
    # results visualization
    config_file = os.path.join(metrics_folder, 'config.json')

    cfg = _annual_daylight_en17037_config()

    with open(config_file, 'w') as outf:
        json.dump(cfg, outf)

    return metrics_folder


def _annual_daylight_en17037_config():
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
