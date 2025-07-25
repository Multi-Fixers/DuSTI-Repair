import subprocess
import os
import json
import shutil

def get_projects():
    result = subprocess.run(["defects4j", "pids"], capture_output=True, text=True)
    return result.stdout.splitlines()

def get_bugs(project_name):
    result = subprocess.run(['defects4j', 'bids', '-p', project_name], capture_output=True, text=True)
    bugs = [f"{bug_id}b" for bug_id in result.stdout.splitlines()]
    

def checkout_defects4j(workspace_path, project_name, bug_id, fix_checkout):
    buggy_workspace = workspace_path
    fixed_workspace = ""

    if fix_checkout:
        buggy_workspace = os.path.join(workspace_path, "buggy")
        fixed_workspace = os.path.join(workspace_path, "fixed")
        fix_id = bug_id.replace("b", "f") if "b" in bug_id else bug_id.replace("f", "b")
        subprocess.run(
            [
                "defects4j",
                "checkout",
                "-p",
                project_name,
                "-v",
                fix_id,
                "-w",
                fixed_workspace,
            ],
            check=True,
        )

    subprocess.run(
        [
            "defects4j",
            "checkout",
            "-p",
            project_name,
            "-v",
            bug_id,
            "-w",
            buggy_workspace,
        ],
        check=True,
    )
    return buggy_workspace, fixed_workspace


def save_to_file(path, file_name, text):
    with open(os.path.join(path, file_name), "w") as f:
        f.write(text)

def read_json(path, file_name):
    with open(os.path.join(path, file_name), "r") as f:
        data = json.load(f)
    return data

def save_to_json(path, file_name, data):
    with open(os.path.join(path, file_name), "w") as f:
        json.dump(data, f)


def copy_folder_contents(source_folder, destination_folder):
    try:
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        for item in os.listdir(source_folder):
            source_item = os.path.join(source_folder, item)
            destination_item = os.path.join(destination_folder, item)

            if os.path.isfile(source_item):
                shutil.copy2(source_item, destination_item)  # copy2 preserves metadata
            elif os.path.isdir(source_item):
                shutil.copytree(source_item, destination_item, dirs_exist_ok=True)
    except FileNotFoundError:
        print(f"Error: Source folder '{source_folder}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def remove_folder(folder_path):
    try:
        shutil.rmtree(folder_path)
    except FileNotFoundError:
        print(f"Error: Folder '{folder_path}' not found.")
    except OSError as e:
        print(f"Error removing folder '{folder_path}': {e}")


def copy_file(source_path, destination_path):
    try:
        shutil.copy2(source_path, destination_path)
    except FileNotFoundError:
        print(f"Error: Source file '{source_path}' not found.")
    except Exception as e:
        print(f"An error occurred: {e}")


def add_to_json(obj, project, bug):
    if project not in obj:
        obj[project] = [bug]
    else:
        obj[project].append(bug)


def revert_file(source_file, dest_file):
    with open(source_file, "r") as src:
        lines = src.readlines()

    with open(dest_file, "w") as dest:
        dest.writelines(lines)


def map_file_path(file_path):
    return file_path.replace("buggy/", "")
