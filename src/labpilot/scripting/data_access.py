import os
from pathlib import Path
from typing import List, Type
import json
from labpilot.analysis import View
import tqdm
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import numpy as np

import logging

logger = logging.getLogger(__name__)

from labpilot import config
from labpilot.data_management.measurement_information import RecordingInfos
from labpilot.MainLoopHandler import ScriptingLoopHandler
import labpilot.DataReceiver as dr


def list_recording_folders(base_path: str | Path) -> List[Path]:
    """Returns the list of all folders containing recording data. The search is performed recursively

    Args:
        base_path (str): Path from where to start the search
    """
    recording_folders: List[Path] = []
    rec_folders = [Path(base_path)]
    while len(rec_folders) > 0:
        # Pop
        current_folder = rec_folders.pop()

        # Check if it has an info.json file AND contains subfolders
        sub_dirs = os.walk(current_folder).__next__()
        info_file = current_folder / "info.json"
        if info_file.exists() and len(sub_dirs[1]) > 0:
            # load the json to see if it has the correct key
            with open(info_file, "r") as f:
                data = json.load(f)
                if "__type__" in data and data["__type__"] == RecordingInfos.__name__:
                    recording_folders.append(current_folder)
                    continue

        # If we reach here, it means this is NOT a recording folder. Therefore, we add all sub directories
        rec_folders += [Path(os.path.join(sub_dirs[0], d)) for d in sub_dirs[1]]

    return recording_folders


def list_experiment_folders(base_path: str | Path) -> List[Path]:
    """Given a basepath, returns all recording folders present in this base path

    Note:
        The search is recursive. Therefore, it will return all recording folders without accounting for the different measurements/experiments
    """
    experiment_folders: List[Path] = []
    rec_folders = [base_path]
    while len(rec_folders) > 0:
        # Pop
        current_folder = rec_folders.pop()

        # Check if it has an info.json
        sub_dirs = os.walk(current_folder).__next__()
        if (
            os.path.exists(os.path.join(current_folder, "info.json"))
            and len(sub_dirs[1]) > 0
        ):
            # This is an experiment folder!
            exp_path = os.path.dirname(current_folder)
            if exp_path not in experiment_folders:
                experiment_folders.append(Path(exp_path))
        else:
            # List sub dirs
            for d in sub_dirs[1]:
                if d == "Simulation_checks":
                    continue
                rec_folders.insert(0, os.path.join(sub_dirs[0], d))

    return experiment_folders


def read_data(
    path_template: str,
    zip_save: bool = False,
    delete_detail_outputs: bool = True,
) -> np.ndarray:
    """From a recording, aggregate all data from all outputs to create a single file with everything

    Args:
        path_template (str): Path to one of the "output_%1.npy" file to aggregate
        zip_delete (bool, optional): If `True`, will ZIP all "output_%1.npy" files into a single ZIP file and delete the original files. If `False`, the ZIP file will be deleted if it exists
        delete_detail_outputs (bool, optional): If `True`, all detail output files (output_xx.npy) will be deleted after the aggragation if it was successful


    Returns:
        np.ndarray: Description
    """
    direct_file = os.path.join(os.path.dirname(path_template), "data.npy")
    zip_file = os.path.join(os.path.dirname(path_template), "originals.zip")

    data = dr.LiveDataReader.read_reader_data(os.path.dirname(path_template))

    # List all files with the format output_%1.py
    all_files = list(Path(os.path.dirname(path_template)).glob("output_*.npy"))

    # Find all output_*.npy files
    if zip_save and not os.path.exists(zip_file):
        # Zip all output_%1.npy files into a single zip file and deletes them

        # Create ZIP archive
        with ZipFile(zip_file, "w", compression=ZIP_DEFLATED) as zipf:
            for file in tqdm.tqdm(all_files, desc="ZIP creation"):
                zipf.write(file, arcname=file.name)
    elif not zip_save and os.path.exists(zip_file):
        # If we don't save as ZIP, but the ZIP file exists, removes it
        os.remove(zip_file)
        logger.warning(f"Removed ZIP file: {zip_file}")

    if len(all_files) > 0 and delete_detail_outputs:
        # Delete original files
        for file in tqdm.tqdm(all_files, desc="detail files suppression"):
            file.unlink()

    return data


def begin_scripting_with(config_path: str | Path):
    # Load the configuration
    config.read(config_path)
    config.simulation = True
    config.use_gui = False

    # Begin the loop
    ScriptingLoopHandler.main().start()


def get_view[T: View](type: Type[T]) -> T:
    return ScriptingLoopHandler.main().get_view(type)
