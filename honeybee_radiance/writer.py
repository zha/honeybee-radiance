# coding=utf-8
"""Methods to write to rad."""
from ladybug.futil import write_to_file_by_name, preparedir
from honeybee.config import folders
from honeybee.boundarycondition import Surface
from honeybee_radiance_folder.folder import ModelFolder
import honeybee_radiance_folder.config as folder_config

from .geometry import Polygon
from .modifier.material import BSDF
from .lib.modifiers import black

import os
import json
import shutil


def shade_to_rad(shade, blk=False, minimal=False):
    """Generate a RAD string representation of a Shade.

    Note that the resulting string does not include modifier definitions. Nor
    does it include any states for dynamic geometry.

    Args:
        shade: A honeybee Shade for which a RAD representation will be returned.
        blk: Boolean to note whether the "blacked out" version of the Shade should
            be output, which is useful for direct studies and isolation studies
            to understand the contribution of individual apertures.
        minimal: Boolean to note whether the radiance string should be written
            in a minimal format (with spaces instead of line breaks). Default: False.
    """
    rad_prop = shade.properties.radiance
    modifier = rad_prop.modifier_blk if blk else rad_prop.modifier
    rad_poly = Polygon(shade.identifier, shade.vertices, modifier)
    return rad_poly.to_radiance(minimal, False, False)


def door_to_rad(door, blk=False, minimal=False):
    """Generate a RAD string representation of a Door.

    Note that the resulting string does not include modifier definitions. Nor
    does it include any states for dynamic geometry. However, it does include
    any of the shades assigned to the Door.

    Args:
        door: A honeybee Door for which a RAD representation will be returned.
        blk: Boolean to note whether the "blacked out" version of the Door should
            be output, which is useful for direct studies and isolation studies
            to understand the contribution of individual apertures.
        minimal: Boolean to note whether the radiance string should be written
            in a minimal format (with spaces instead of line breaks). Default: False.
    """
    rad_prop = door.properties.radiance
    modifier = rad_prop.modifier_blk if blk else rad_prop.modifier
    rad_poly = Polygon(door.identifier, door.vertices, modifier)
    door_strs = [rad_poly.to_radiance(minimal, False, False)]
    for shd in door.shades:
        door_strs.append(shade_to_rad(shd, blk, minimal))
    return '\n\n'.join(door_strs)


def aperture_to_rad(aperture, blk=False, minimal=False):
    """Generate a RAD string representation of an Aperture.

    Note that the resulting string does not include modifier definitions. Nor
    does it include any states for dynamic geometry. However, it does include
    the shade geometry assigned to the Aperture.

    Args:
        aperture: A honeybee Aperture for which a RAD representation will be returned.
        blk: Boolean to note whether the "blacked out" version of the Aperture should
            be output, which is useful for direct studies and isolation studies
            to understand the contribution of individual apertures.
        minimal: Boolean to note whether the radiance string should be written
            in a minimal format (with spaces instead of line breaks). Default: False.
    """
    rad_prop = aperture.properties.radiance
    modifier = rad_prop.modifier_blk if blk else rad_prop.modifier
    rad_poly = Polygon(aperture.identifier, aperture.vertices, modifier)
    ap_strs = [rad_poly.to_radiance(minimal, False, False)]
    for shd in aperture.shades:
        ap_strs.append(shade_to_rad(shd, blk, minimal))
    return '\n\n'.join(ap_strs)


def face_to_rad(face, blk=False, minimal=False):
    """Get Face as a Radiance string.

    Note that the resulting string does not include modifier definitions. Nor
    does it include any states for dynamic geometry. However, it does include
    any of the shades assigned to the Face along with the Apertures and Doors
    in the Face.

    Args:
        face: A honeybee Face for which a RAD representation will be returned.
        blk: Boolean to note whether the "blacked out" version of the Face should
            be output, which is useful for direct studies and isolation studies
            to understand the contribution of individual apertures.
        minimal: Boolean to note whether the radiance string should be written
            in a minimal format (with spaces instead of line breaks). Default: False.
    """
    rad_prop = face.properties.radiance
    modifier = rad_prop.modifier_blk if blk else rad_prop.modifier
    rad_poly = Polygon(face.identifier, face.punched_vertices, modifier)
    face_strs = [rad_poly.to_radiance(minimal, False, False)]
    for shd in face.shades:
        face_strs.append(shade_to_rad(shd, blk, minimal))
    for dr in face.doors:
        face_strs.append(door_to_rad(dr, blk, minimal))
    for ap in face.apertures:
        face_strs.append(aperture_to_rad(ap, blk, minimal))
    return '\n\n'.join(face_strs)


def room_to_rad(room, blk=False, minimal=False):
    """Generate a RAD string representation of a Room.

    This method will write all geometry associated with a Room including all
    Faces, Apertures, Doors, and Shades. However, it does not include modifiers
    for this geometry. Nor does it include any states for dynamic geometry and
    will only write the default state for each dynamic object.

    Args:
        room: A honeybee Room for which a RAD representation will be returned.
        blk: Boolean to note whether the "blacked out" version of the geometry
            should be output, which is useful for direct studies and isolation
            studies to understand the contribution of individual apertures.
        minimal: Boolean to note whether the radiance string should be written
            in a minimal format (with spaces instead of line breaks). Default: False.
    """
    room_strs = []
    for face in room.faces:
        room_strs.append(face_to_rad(face, blk, minimal))
    for shd in room.shades:
        room_strs.append(shade_to_rad(shd, blk, minimal))
    return '\n\n'.join(room_strs)


def model_to_rad(model, blk=False, minimal=False):
    r"""Generate a RAD string representation of a Model.

    The resulting strings will include all geometry (Rooms, Faces, Shades, Apertures,
    Doors) and all modifiers. However, it does not include any states for dynamic
    geometry and will only write the default state for each dynamic object. To
    correctly account for dynamic objects, the model_to_rad_folder should be used.

    Note that this method will also ensure that any Faces, Apertures, or Doors
    with Surface boundary condition only have one of such objects in the output
    string.

    Args:
        model: A honeybee Model for which a RAD representation will be returned.
        blk: Boolean to note whether the "blacked out" version of the geometry
            should be output, which is useful for direct studies and isolation
            studies to understand the contribution of individual apertures.
        minimal: Boolean to note whether the radiance string should be written
            in a minimal format (with spaces instead of line breaks). Default: False.

    Returns:
        A tuple of two strings.

        -   model_str: A radiance string that contains all geometry of the Model.

        -   modifier_str: A radiance string that contains all of the modifiers
            in the model. These will be modifier_blk if blk is True.
    """
    # write all modifiers into the file
    modifier_str = ['#   ============== MODIFIERS ==============\n']
    rad_prop = model.properties.radiance
    modifiers = rad_prop.blk_modifiers if blk else rad_prop.modifiers
    if not blk:
        # must be imported here to avoid circular imports
        from .lib.modifiersets import generic_modifier_set_visible
        modifiers = set(modifiers + generic_modifier_set_visible.modifiers_unique)
    for mod in modifiers:
        modifier_str.append(mod.to_radiance(minimal))

    # write all Faces into the file
    model_str = ['#   ================ MODEL ================\n']
    faces = model.faces
    interior_faces = set()
    if len(faces) != 0:
        model_str.append('#   ================ FACES ================\n')
        for face in faces:
            if isinstance(face.boundary_condition, Surface):
                if face.identifier in interior_faces:
                    continue
                interior_faces.add(face.boundary_condition.boundary_condition_object)
            model_str.append(face_to_rad(face, blk, minimal))

    # write all orphaned Apertures into the file
    apertures = model.orphaned_apertures
    interior_aps = set()
    if len(apertures) != 0:
        model_str.append('#   ============== APERTURES ==============\n')
        for ap in apertures:
            if isinstance(ap.boundary_condition, Surface):
                if ap.identifier in interior_aps:
                    continue
                interior_aps.add(ap.boundary_condition.boundary_condition_object)
            model_str.append(aperture_to_rad(ap, blk, minimal))

    # write all orphaned Doors into the file
    doors = model.orphaned_doors
    interior_drs = set()
    if len(doors) != 0:
        model_str.append('#   ================ DOORS ================\n')
        for dr in doors:
            if isinstance(dr.boundary_condition, Surface):
                if dr.identifier in interior_drs:
                    continue
                interior_drs.add(dr.boundary_condition.boundary_condition_object)
            model_str.append(door_to_rad(dr, blk, minimal))

    # write all Room shades into the file
    rooms = model.rooms
    if len(rooms) != 0:
        model_str.append('#   ============== ROOM SHADES ==============\n')
        for room in rooms:
            for shd in room.shades:
                model_str.append(shade_to_rad(shd, blk, minimal))

    # write all orphaned Shades into the file
    shades = model.orphaned_shades
    if len(shades) != 0:
        model_str.append('#   ============= CONTEXT SHADES =============\n')
        for shd in shades:
            model_str.append(shade_to_rad(shd, blk, minimal))

    return '\n\n'.join(model_str), '\n\n'.join(modifier_str)


def model_to_rad_folder(model, folder=None, config_file=None, minimal=False):
    r"""Write a honeybee model to a rad folder.

    The rad files in the resulting folders will include all geometry (Rooms, Faces,
    Shades, Apertures, Doors), all modifiers, and all states of dynamic objects.
    It also includes any SensorGrids and Views that are assigned to the model's
    radiance properties.

    Args:
        model: A honeybee Model for which radiance folder will be written.
        folder: An optional folder to be used as the root of the model's
            Radiance folder. If None, the files will be written into a sub-directory
            of the honeybee-core default_simulation_folder. This sub-directory
            is specifically: default_simulation_folder/[MODEL IDENTIFIER]/Radiance
        config_file: An optional config file path to modify the default folder
            names. If None, ``folder.cfg`` in ``honeybee-radiance-folder``
            will be used. (Default: None).
        minimal: Boolean to note whether the radiance strings should be written
            in a minimal format (with spaces instead of line breaks). Default: False.
    """
    # prepare the folder for simulation
    model_id = model.identifier
    if folder is None:
        folder = os.path.join(folders.default_simulation_folder, model_id, 'Radiance')
    if not os.path.isdir(folder):
        preparedir(folder)  # create the directory if it's not there
    model_folder = ModelFolder(folder, 'model', config_file)
    model_folder.write(folder_type=-1, cfg=folder_config.minimal, overwrite=True)

    # gather and write static apertures to the folder
    aps, aps_blk = model.properties.radiance.subfaces_by_blk()
    mods, mods_blk, mod_combs, mod_names = _collect_modifiers(aps, aps_blk, True)
    _write_static_files(
        folder, model_folder.aperture_folder(full=True), 'aperture',
        aps, aps_blk, mods, mods_blk, mod_combs, mod_names, False, minimal)

    # gather and write static faces
    faces, faces_blk = model.properties.radiance.faces_by_blk()
    f_mods, f_mods_blk, mod_combs, mod_names = _collect_modifiers(faces, faces_blk)
    _write_static_files(
        folder, model_folder.scene_folder(full=True), 'envelope',
        faces, faces_blk, f_mods, f_mods_blk, mod_combs, mod_names, True, minimal)

    # gather and write static shades
    shades, shades_blk = model.properties.radiance.shades_by_blk()
    s_mods, s_mods_blk, mod_combs, mod_names = _collect_modifiers(shades, shades_blk)
    _write_static_files(
        folder, model_folder.scene_folder(full=True), 'shades',
        shades, shades_blk, s_mods, s_mods_blk, mod_combs, mod_names, False, minimal)

    # write dynamic sub-face groups (apertures and doors)
    ext_dict = {}
    out_subfolder = model_folder.aperture_group_folder(full=True)
    dyn_subface = model.properties.radiance.dynamic_subface_groups
    if len(dyn_subface) != 0:
        preparedir(out_subfolder)
        for group in dyn_subface:
            if group.is_indoor:
                # TODO: Implement dynamic interior apertures once the radiance folder
                # structure is clear about how the "light path" should be input
                raise NotImplementedError('Dynamic interior apertures are not currently'
                                          ' supported by Model.to.rad_folder.')
            else:
                st_d = _write_dynamic_subface_files(folder, out_subfolder, group, minimal)
                _write_mtx_files(folder, out_subfolder, group, st_d, minimal)
                ext_dict[group.identifier] = st_d
        _write_dynamic_json(folder, out_subfolder, ext_dict)

    # write dynamic shade groups
    out_dict = {}
    in_dict = {}
    out_subfolder = model_folder.dynamic_scene_folder(full=True, indoor=False)
    in_subfolder = model_folder.dynamic_scene_folder(full=True, indoor=True)
    dyn_shade = model.properties.radiance.dynamic_shade_groups
    if len(dyn_shade) != 0:
        preparedir(out_subfolder)
        indoor_created = False
        for group in dyn_shade:
            if group.is_indoor:
                if not indoor_created:
                    preparedir(in_subfolder)
                    indoor_created = True
                st_d = _write_dynamic_shade_files(folder, in_subfolder, group, minimal)
                in_dict[group.identifier] = st_d
            else:
                st_d = _write_dynamic_shade_files(folder, out_subfolder, group, minimal)
                out_dict[group.identifier] = st_d
        _write_dynamic_json(folder, out_subfolder, out_dict)
        if indoor_created:
            _write_dynamic_json(folder, in_subfolder, in_dict)

    # copy all bsdfs into the bsdf folder
    bsdf_folder = model_folder.bsdf_folder(full=True)
    bsdf_mods = model.properties.radiance.bsdf_modifiers
    if len(bsdf_mods) != 0:
        preparedir(bsdf_folder)
        for bdf_mod in bsdf_mods:
            bsdf_name = os.path.split(bdf_mod.bsdf_file)[-1]
            new_bsdf_path = os.path.join(bsdf_folder, bsdf_name)
            shutil.copy(bdf_mod.bsdf_file, new_bsdf_path)

    # write the assigned sensor grids and views into the correct folder
    grid_dir = model_folder.grid_folder(full=True)
    grids = model.properties.radiance.sensor_grids
    if len(grids) != 0:
        preparedir(grid_dir)
        model.properties.radiance.check_duplicate_sensor_grid_display_names()
        for grid in grids:
            grid.to_file(grid_dir)
            info_file = os.path.join(grid_dir, '{}.json'.format(grid.identifier))
            with open(info_file, 'w') as fp:
                json.dump(grid.info_dict(model), fp, indent=4)
    view_dir = model_folder.view_folder(full=True)
    views = model.properties.radiance.views
    if len(views) != 0:
        preparedir(view_dir)
        model.properties.radiance.check_duplicate_view_display_names()
        for view in views:
            view.to_file(view_dir)
            info_file = os.path.join(view_dir, '{}.json'.format(view.identifier))
            with open(info_file, 'w') as fp:
                json.dump(view.info_dict(model), fp, indent=4)

    return folder


def _write_dynamic_shade_files(folder, sub_folder, group, minimal=False):
    """Write out the files that need to go into any dynamic model folder.

    Args:
        folder: The model folder location on this machine.
        sub_folder: The sub-folder for the three files (relative to the model folder).
        group: A DynamicShadeGroup object to be written into files.
        minimal: Boolean noting whether radiance strings should be written minimally.

    Returns:
        A list of dictionaries to be written into the states.json file.
    """
    # destination folder for all of the radiance files
    dest = os.path.join(folder, sub_folder)

    # loop through all states and write out the .rad files for them
    states_list = group.states_json_list
    for state_i, file_names in enumerate(states_list):
        default_str = group.to_radiance(state_i, direct=False, minimal=minimal)
        direct_str = group.to_radiance(state_i, direct=True, minimal=minimal)
        write_to_file_by_name(dest, file_names['default'].replace('./', ''), default_str)
        write_to_file_by_name(dest, file_names['direct'].replace('./', ''), direct_str)
    return states_list


def _write_dynamic_subface_files(folder, sub_folder, group, minimal=False):
    """Write out the files that need to go into any dynamic model folder.

    Args:
        folder: The model folder location on this machine.
        sub_folder: The sub-folder for the three files (relative to the model folder).
        group: A DynamicSubFaceGroup object to be written into files.
        minimal: Boolean noting whether radiance strings should be written minimally.

    Returns:
        A list of dictionaries to be written into the states.json file.
    """
    # destination folder for all of the radiance files
    dest = os.path.join(folder, sub_folder)

    # loop through all states and write out the .rad files for them
    states_list = group.states_json_list
    for state_i, file_names in enumerate(states_list):
        default_str = group.to_radiance(state_i, direct=False, minimal=minimal)
        direct_str = group.to_radiance(state_i, direct=True, minimal=minimal)
        write_to_file_by_name(dest, file_names['default'].replace('./', ''), default_str)
        write_to_file_by_name(dest, file_names['direct'].replace('./', ''), direct_str)

    # write out the black representation of the aperture
    black_str = group.blk_to_radiance(minimal)
    write_to_file_by_name(dest, file_names['black'].replace('./', ''), black_str)
    return states_list


def _write_mtx_files(folder, sub_folder, group, states_json_list, minimal=False):
    """Write out the mtx files needed for 3-phase simulation into a model folder.

    Args:
        folder: The model folder location on this machine.
        sub_folder: The sub-folder for the three files (relative to the model folder).
        group: A DynamicSubFaceGroup object to be written into files.
        states_json_list: A list to be written into the states.json file.
        minimal: Boolean noting whether radiance strings should be written minimally.

    Returns:
        A list of dictionaries to be written into the states.json file.
    """
    dest = os.path.join(folder, sub_folder)  # destination folder for radiance files

    # check if all of the states of all of the vmtx and dmtx geometry are default
    one_mtx = all(st.mtxs_default for obj in group.dynamic_objects
                  for st in obj.properties.radiance._states)
    if one_mtx:  # if they're all default, we can use one file
        mtx_file = './{}..mtx.rad'.format(group.identifier)

    # loop through all states and write out the .rad files for them
    tmxt_valid = False
    for state_i, st_dict in enumerate(states_json_list):
        tmtx_bsdf = group.tmxt_bsdf(state_i)
        if tmtx_bsdf is not None:  # it's a valid state for 3-phase
            tmxt_valid = True
            # add the tmxt to the states_json_list
            bsdf_name = os.path.split(tmtx_bsdf.bsdf_file)[-1]
            states_json_list[state_i]['tmtx'] = bsdf_name

            # add the vmtx and the dmtx to the states_json_list
            if one_mtx:
                states_json_list[state_i]['vmtx'] = mtx_file
                states_json_list[state_i]['dmtx'] = mtx_file
            else:
                states_json_list[state_i]['vmtx'] = \
                    './{}..vmtx..{}.rad'.format(group.identifier, str(state_i))
                states_json_list[state_i]['dmtx'] = \
                    './{}..dmtx..{}.rad'.format(group.identifier, str(state_i))
                vmtx_str = group.vmtx_to_radiance(state_i, minimal)
                dmtx_str = group.dmtx_to_radiance(state_i, minimal)
                write_to_file_by_name(
                    dest, states_json_list[state_i]['vmtx'].replace('./', ''), vmtx_str)
                write_to_file_by_name(
                    dest, states_json_list[state_i]['dmtx'].replace('./', ''), dmtx_str)

    # write the single mtx file if everything is default
    if one_mtx and tmxt_valid:
        mtx_str = group.vmtx_to_radiance(0, minimal)
        write_to_file_by_name(dest, mtx_file, mtx_str)


def _write_dynamic_json(folder, sub_folder, json_dict):
    """Write out the files that need to go into any dynamic model folder.

    Args:
        folder: The model folder location on this machine.
        sub_folder: The sub-folder for the three files (relative to the model folder).
        json_dict: A dictionary to be written into the states.json file.
    """
    if json_dict != {}:
        dest_file = os.path.join(folder, sub_folder, 'states.json')
        with open(dest_file, 'w') as fp:
            json.dump(json_dict, fp, indent=4)


def _write_static_files(
        folder, sub_folder, file_id, geometry, geometry_blk, modifiers, modifiers_blk,
        mod_combs, mod_names, punched_verts=False, minimal=False):
    """Write out the three files that need to go into any static radiance model folder.

    This includes a .rad, .mat, and .blk file for the folder.
    This method will also catch any cases of BSDF modifiers and copy the XML files
    to the bsdf folder of the model folder.

    Args:
        folder: The model folder location on this machine.
        sub_folder: The sub-folder for the three files (relative to the model folder).
        file_id: An identifier to be used for the names of each of the files.
        geometry: A list of geometry objects all with default blk modifiers.
        geometry_blk: A list of geometry objects with overridden blk modifiers.
        modifiers: A list of modifiers to write.
        modifiers_blk: A list of modifier_blk to write.
        mod_combs: Dictionary of modifiers from _unique_modifier_blk_combinations method.
        mod_names: Modifier names from the _unique_modifier_blk_combinations method.
        punched_verts: Boolean noting whether punched geometry should be written
        minimal: Boolean noting whether radiance strings should be written minimally.
    """
    if len(geometry) != 0 or len(geometry_blk) != 0:
        # write the strings for the geometry
        face_strs = []
        if punched_verts:
            for face in geometry:
                modifier = face.properties.radiance.modifier
                rad_poly = Polygon(face.identifier, face.punched_vertices, modifier)
                face_strs.append(rad_poly.to_radiance(minimal, False, False))
            for face, mod_name in zip(geometry_blk, mod_names):
                modifier = mod_combs[mod_name][0]
                rad_poly = Polygon(face.identifier, face.punched_vertices, modifier)
                face_strs.append(rad_poly.to_radiance(minimal, False, False))
        else:
            for face in geometry:
                modifier = face.properties.radiance.modifier
                rad_poly = Polygon(face.identifier, face.vertices, modifier)
                face_strs.append(rad_poly.to_radiance(minimal, False, False))
            for face, mod_name in zip(geometry_blk, mod_names):
                modifier = mod_combs[mod_name][0]
                rad_poly = Polygon(face.identifier, face.vertices, modifier)
                face_strs.append(rad_poly.to_radiance(minimal, False, False))

        # write the strings for the modifiers
        mod_strs = []
        mod_blk_strs = []
        for mod in modifiers:
            if isinstance(mod, BSDF):
                _process_bsdf_modifier(mod, mod_strs, minimal)
            else:
                mod_strs.append(mod.to_radiance(minimal))
        for mod in modifiers_blk:
            if isinstance(mod, BSDF):
                _process_bsdf_modifier(mod, mod_strs, minimal)
            else:
                mod_blk_strs.append(mod.to_radiance(minimal))

        # write the three files for the model sub-folder
        dest = os.path.join(folder, sub_folder)
        write_to_file_by_name(dest, '{}.rad'.format(file_id), '\n\n'.join(face_strs))
        write_to_file_by_name(dest, '{}.mat'.format(file_id), '\n\n'.join(mod_strs))
        write_to_file_by_name(dest, '{}.blk'.format(file_id), '\n\n'.join(mod_blk_strs))


def _unique_modifiers(geometry_objects):
    """Get a list of unique modifiers across an array of geometry objects.

    Args:
        geometry_objects: An array of geometry objects (Faces, Apertures,
            Doors, Shades) for which unique modifiers will be determined.

    Returns:
        A list of all unique modifiers across the input geometry_objects
    """
    modifiers = []
    for obj in geometry_objects:
        mod = obj.properties.radiance.modifier
        if not _instance_in_array(mod, modifiers):
            modifiers.append(mod)
    return list(set(modifiers))


def _unique_modifier_blk_combinations(geometry_objects):
    """Get lists of unique modifier/modifier_blk combinations across geometry objects.

    Args:
        geometry_objects: An array of geometry objects (Faces, Apertures,
            Doors, Shades) for which unique combinations of modifier and
            modifier_blk will be determined.

    Returns:
        A tuple with two objects.

        -   modifier_combs: A dictionary of modifiers with identifiers of
            modifiers as keys and tuples with two modifiers as values. Each
            item in the dictionary represents a unique combination of modifier
            and modifer_blk found in the objects. Both modifiers in the pair
            have the same identifier (making them write-able into a radiance
            folder). The first item in the tuple is the true modifier while
            the second one is the modifier_blk.

        -   modifier_names: A list of modifier names with one name for each of
            the input geometry_objects. These names can be looked up in the
            modifier_combs dictionary to get the modifier combination for a
            given geometry object
    """
    modifier_combs = {}
    modifier_names = []
    for obj in geometry_objects:
        mod = obj.properties.radiance.modifier
        mod_blk = obj.properties.radiance.modifier_blk
        comb_name = '{}_{}'.format(mod.identifier, mod_blk.identifier)
        modifier_names.append(comb_name)
        try:  # test to see if the combination already exists
            modifier_combs[comb_name]
        except KeyError:  # new combination of modifier and modifier_blk
            new_mod = mod.duplicate()
            new_mod.identifier = comb_name
            new_mod_blk = mod_blk.duplicate()
            new_mod_blk.identifier = comb_name
            modifier_combs[comb_name] = (new_mod, new_mod_blk)
    return modifier_combs, modifier_names


def _collect_modifiers(geo, geo_blk, aperture=False):
    """Collect all modifier and modifier_blk across geometry."""
    mods = _unique_modifiers(geo)
    mods_blk = []
    for mod in mods:
        if mod.is_opaque or aperture:  # static transparent apertures still use black
            mod_blk = black.duplicate()
            mod_blk.identifier = mod.identifier
            mods_blk.append(mod_blk)
        else:
            mods_blk.append(mod)
    mod_combs, mod_names = _unique_modifier_blk_combinations(geo_blk)
    mods.extend([mod_comb[0] for mod_comb in mod_combs.values()])
    mods_blk.extend([mod_comb[1] for mod_comb in mod_combs.values()])
    return mods, mods_blk, mod_combs, mod_names


def _process_bsdf_modifier(modifier, mod_strs, minimal):
    """Process a BSDF modifier for a radiance model folder."""
    bsdf_name = os.path.split(modifier.bsdf_file)[-1]
    mod_dup = modifier.duplicate()  # duplicate to avoid editing the original
    # we must edit the hidden _bsdf_file property since the file has not yet been copied
    mod_dup._bsdf_file = os.path.join('model', 'bsdf', bsdf_name)
    mod_strs.append(mod_dup.to_radiance(minimal))


def _instance_in_array(object_instance, object_array):
    """Check if a specific object instance is already in an array.

    This can be much faster than  `if object_instance in object_array`
    when you expect to be testing a lot of the same instance of an object for
    inclusion in an array since the builtin method uses an == operator to
    test inclusion.
    """
    for val in object_array:
        if val is object_instance:
            return True
    return False
