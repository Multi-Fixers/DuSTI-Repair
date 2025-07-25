from utils import *
import subprocess
import os
import json
import time
import copy
import multiprocessing
import google.generativeai as genai
from dotenv import load_dotenv

def process_context_file_path(file_path):
    return file_path.replace("buggy/", "")


def preprocess_bug(
    buggy_line_numbers, buggy_lines, fix_line_numbers, contexts, file_path, bug_type
):
    bug_input = ""
    start_added = False
    end_added = False

    for context in contexts:
        context_line_numbers = context["linenumbers"]
        context_lines = context["context"]

        same_file = file_path == process_context_file_path(context["file_path"])

        for i in range(len(context_line_numbers)):
            if bug_type != "insert":
                if same_file and context_line_numbers[i] in buggy_line_numbers:
                    if not start_added:
                        bug_input += "// Bug starts here\n"
                        start_added = True
                        # for l in buggy_lines:
                        #     bug_input += l + "\n"

                elif same_file and context_line_numbers[i] > buggy_line_numbers[-1]:
                    if not end_added:
                        bug_input += "// Bug ends here\n"
                        end_added = True
                    bug_input += context_lines[i] + "\n"
                else:
                    bug_input += context_lines[i] + "\n"

            else:
                if (
                    same_file
                    and not start_added
                    and context_line_numbers[i] >= buggy_line_numbers[0]
                ):
                    bug_input += "// Bug starts here\n" + "// Bug ends here\n"
                    start_added = True
                bug_input += context_lines[i] + "\n"

    return bug_input


def process_fix(fix_text: str) -> list[str]:
    if not isinstance(fix_text, str):
        return ""  # Return empty list for invalid input

    start_marker = "// Fix starts here //"
    end_marker = "// Fix ends here //"
    start_index = fix_text.find(start_marker)
    end_index = fix_text.find(end_marker)

    if start_index == -1 or end_index == -1 or start_index >= end_index:
        return ""  # Return empty list if markers are not found or in the wrong order

    # Extract the fix lines, removing leading/trailing whitespace
    fix_lines = fix_text[
        start_index + len(start_marker) : end_index
    ].strip()  # .split('\n')
    # return [line.strip() for line in fix_lines] #remove empty lines
    return fix_lines


def generate_fixes(loc, file_path, _):  # bug_input
    bug_input = preprocess_bug(
        loc["buggy_line_numbers"],
        loc["buggy_lines"],
        loc["fix_line_numbers"],
        loc["context"],
        file_path,
        loc["type"],
    )
    
    # print("Bug input:", bug_input)

    buggy_lines = " ".join(loc["buggy_lines"])
    prompt = f"""
    You are an expert software developer tasked with automatically correcting code bugs. You will be given a code snippet separated into its context and the specific bug marked by `// Bug starts here //` and `// Bug ends here //` markers. Your task is to provide the *shortest possible correct code replacement* for the bug that, when inserted *directly* between these markers within the context, will fix the bug. The replacement should ensure that the resulting code is syntactically correct and semantically sound within the given context.

    **Input Format:**

    Context:
    context line 1
    context line 2
    // Bug starts here //
    // Bug ends here //
    context line 3
    context line 4
    Bug:
    bug line 1
    bug line 2


    * The `Context` section provides the surrounding code with the bug markers.
    * The `Bug` section contains the code that is marked as buggy. If the bug is a missing code section, the `Bug` section will be empty.

    **Output Format:**

    Your response *must* contain *only* the corrected code snippet that, when placed directly between the `// Bug starts here //` and `// Bug ends here //` markers in the `Context`, will resolve the bug without introducing repeated or incorrect code. Enclose this replacement code within `// Fix starts here //` and `// Fix ends here //` markers. Do *not* include any context lines, comments, or explanations. The replacement code should be syntactically correct and follow the original code's style. If no fix is possible, respond with "// Fix starts here // // Fix ends here //".

    **Examples:**

    **Example 1:**

    Input:

    Context:
    int x = 10;
    int y = 20;
    // Bug starts here //
    // Bug ends here //
    printf("Sum: %d", sum);
    return 0;
    Bug:
    int sum = x - y;


    Output:

    // Fix starts here //
    int sum = x + y;
    // Fix ends here //


    **Example 2:**

    Input:

    Context:
    // Bug starts here //
    // Bug ends here //
    printf("i = %d", i);
    }}
    return 0;
    Bug:
    for (int i = 0; i < 5; i--) {{


    Output:

    // Fix starts here //
    for (int i = 0; i < 5; i++) {{
    // Fix ends here //


    **Example 3:**

    Input:

    Context:
    int arr[5] = {{1, 2, 3, 4, 5}};
    // Bug starts here //
    // Bug ends here //
    for (i = 0; i < 5; i++) {{
    printf("%d ", arr[i]);
    }}
    Bug:


    Output:

    // Fix starts here //
    int i;
    // Fix ends here //


    **Input:**

    Context:
    {bug_input}
    Bug:
    {buggy_lines}
        """

    try:
        # print(f"Prompt: {prompt}")
        response = model.generate_content(
            prompt,
            generation_config={
                "candidate_count": 3,
                "temperature": 1.2,  # Adjust for more or less randomness
                # "top_p": 0.9,
                # "top_k": 40,
            },
            stream=False,  # Set to False to get all candidates at once
        )

        all_fixes = []
        if hasattr(response, "candidates") and response.candidates:
            for candidate in response.candidates:
                if (
                    hasattr(candidate, "content")
                    and candidate.content
                    and hasattr(candidate.content, "parts")
                    and candidate.content.parts
                ):
                    response_text = candidate.content.parts[0].text
                    print(f"Response: {response_text}")
                    fix = process_fix(response_text)
                    all_fixes.append(fix)
            if loc.get("type") == "delete":  # Safely access 'loc' as a dictionary
                all_fixes.append("")
        else:
            print("No candidates found in the response.")
            return [[""]]

        fix_set = set(all_fixes)
        all_fixes = [[line.strip() for line in fix.split("\n")] for fix in fix_set]
        return all_fixes

    except Exception as e:
        print(f"An error occurred during generation: {e}")
        return None


def apply_patch(file_path, buggy_line_numbers, fix, bug_type):
    with open(file_path, "r") as f:
        lines = f.readlines()

    if bug_type != "insert":
        bug_start_line = buggy_line_numbers[0]
        bug_end_line = buggy_line_numbers[-1]

        lines = (
            lines[: bug_start_line - 1]
            + fix
            + ["\n" * len(buggy_line_numbers)]
            + lines[bug_end_line:]
        )

    else:
        bug_start_line = buggy_line_numbers[0]
        lines = (
            lines[: bug_start_line - 1]
            + fix
            + ["\n"]
            + [lines[bug_start_line - 1].replace("\n", "")]
            + lines[bug_start_line:]
        )

    with open(file_path, "w") as f:
        f.writelines(lines)


def validate_patch(workspace):
    try:
        print("Compiling project")
        compile_command = ["defects4j", "compile", "-w", workspace]
        compile_result = subprocess.run(compile_command, capture_output=True, text=True)

        if compile_result.returncode != 0:
            # print(compile_result.stderr)
            return "Compilation error"

        print("Running test cases")
        test_command = ["defects4j", "test", "-w", workspace]
        test_result = subprocess.run(test_command, capture_output=True, text=True)

        if "Failing tests:" in test_result.stdout:
            failing_tests_count = int(
                test_result.stdout.split("Failing tests:")[1].split()[0]
            )
            if failing_tests_count > 0:
                return f"Testcase failure: {failing_tests_count}"

        return "Plausible patch"

    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr or e}")
        return f"An error occurred: {e.stderr or e}"


def legacy_modify_contexts(locations, loc_ranks, loc, fix, reduced):
    new_locations = copy.deepcopy(locations)
    new_loc_ranks = copy.deepcopy(loc_ranks)
    tgt_file = map_file_path(loc["file_path"])

    for index in range(len(new_locations)):
        nxt_loc = new_locations[index]
        if reduced and nxt_loc != loc:
            for context in nxt_loc["context"]:
                file = process_context_file_path(context["file_path"])
                if file == tgt_file:
                    cxt_line_no = context["linenumbers"]
                    bug_line_no = loc["buggy_line_numbers"]
                    common_lines = set(cxt_line_no) & set(bug_line_no)

                    if common_lines:
                        new_loc_ranks[index] += 1
                        
        elif nxt_loc == loc:
            if loc["type"] == "insert":
                nxt_loc["type"] = "replace"
                nxt_loc["buggy_lines"] = fix
                for context in nxt_loc["context"]:
                    file = process_context_file_path(context["file_path"])
                    if file == tgt_file:
                        cxt_line_no = context["linenumbers"]
                        cxt_lines = context["context"]
                        bug_line_no = loc["buggy_line_numbers"][0]
                        
                        if bug_line_no in cxt_line_no:
                            bug_index = cxt_line_no.index(bug_line_no)

                            if bug_line_no + 1 in cxt_line_no:
                                cxt_lines[bug_index + 1] = (
                                    cxt_lines[bug_index].replace("\n", "")
                                    + " "
                                    + cxt_lines[bug_index + 1]
                                )

                            else:
                                cxt_line_no.insert(bug_index + 1, bug_line_no + 1)
                                cxt_lines.insert(bug_index, "")

            else:
                nxt_loc["buggy_lines"] = fix

    return new_locations, new_loc_ranks


def modify_contexts(locations, loc_ranks, loc, fix):
    new_locations = copy.deepcopy(locations)
    new_loc_ranks = copy.deepcopy(loc_ranks)
    tgt_file = map_file_path(loc["file_path"])

    for index in range(len(new_locations)):
        nxt_loc = new_locations[index]
        if nxt_loc != loc:
            for context in nxt_loc["context"]:
                file = process_context_file_path(context["file_path"])
                if file == tgt_file:
                    cxt_line_no = context["linenumbers"]
                    bug_line_no = loc["buggy_line_numbers"]
                    common_lines = set(cxt_line_no) & set(bug_line_no)

                    if common_lines:
                        new_loc_ranks[index] += 1
                        new_cxt_line_no = []
                        new_cxt_lines = []
                        cxt_lines = context["context"]

                        bug_start_line = bug_line_no[0]
                        bug_end_line = bug_line_no[-1]
                        fixes_added = False

                        for i in range(len(cxt_line_no)):
                            line_num = cxt_line_no[i]
                            if bug_start_line <= line_num <= bug_end_line + 1:
                                if not fixes_added:
                                    new_cxt_lines.append(" ".join(fix))
                                    new_cxt_line_no.append(bug_start_line)
                                    fixes_added = True

                                    if loc["type"] == "insert":
                                        new_cxt_line_no.append(bug_start_line + 1)
                                        new_cxt_lines.append(
                                            cxt_lines[i].replace("\n", "")
                                            + " "
                                            + cxt_lines[i + 1]
                                        )

                                if bug_start_line < line_num <= bug_end_line:
                                    new_cxt_line_no.append(line_num)
                                    new_cxt_lines.append("")

                                elif (
                                    loc["type"] != "insert"
                                    and line_num == bug_end_line + 1
                                ):
                                    new_cxt_line_no.append(bug_end_line + 1)
                                    new_cxt_lines.append(cxt_lines[i])

                            else:
                                new_cxt_line_no.append(cxt_line_no[i])
                                new_cxt_lines.append(cxt_lines[i])

                        context["linenumbers"] = new_cxt_line_no
                        context["context"] = new_cxt_lines

        elif loc["type"] == "insert":
            nxt_loc["type"] = "replace"
            nxt_loc["buggy_lines"] = fix
            for context in nxt_loc["context"]:
                file = process_context_file_path(context["file_path"])
                if file == tgt_file:
                    cxt_line_no = context["linenumbers"]
                    cxt_lines = context["context"]
                    bug_line_no = loc["buggy_line_numbers"][0]
                    
                    if bug_line_no in cxt_line_no:
                        bug_index = cxt_line_no.index(bug_line_no)

                        if bug_line_no + 1 in cxt_line_no:
                            cxt_lines[bug_index + 1] = (
                                cxt_lines[bug_index].replace("\n", "")
                                + " "
                                + cxt_lines[bug_index + 1]
                            )

                        else:
                            cxt_line_no.insert(bug_index + 1, bug_line_no + 1)
                            cxt_lines.insert(bug_index, "")

        else:
            nxt_loc["buggy_lines"] = fix

    return new_locations, new_loc_ranks


def generate_fix_trace(fix_locs, locations):
    fix_trace = []

    for index in range(len(fix_locs)):
        new_loc = fix_locs[index]
        initial_loc = locations[index]

        if "patch" in new_loc:
            fix_trace.append(
                {
                    "file_path": new_loc["file_path"].split("/buggy/")[1],
                    "buggy_line numbers": new_loc["buggy_line_numbers"],
                    "fix_type": initial_loc["type"],
                    "fix": new_loc["patch"],
                    "developer_fix": new_loc["fix_lines"],
                }
            )

    return fix_trace


def legacy_iterative_inference(
    iter_path,
    tmp_workspace,
    tmp_bug_workspace,
    locations,
    loc_ranks,
    backup_folder,
    max_iter,
    beam_size,
    i,
):
    global backup_index
    backup_index += 1
    if i > max_iter:
        print("Max iteration reached")
        return "No plausible patch found", "", ""

    print(f"Iteration {i}/{max_iter}")
    print("Iter path:", iter_path)
    loc_trace = [item["type"] for item in locations]
    print("Location trace:", loc_trace)

    # mocked
    res = validate_patch(tmp_bug_workspace)

    if res == "Compilation error":
        failing_tests = -1

    elif res.startswith("Testcase failure"):
        failing_tests = int(res.split(": ")[1])

    else:
        print("Error runing test cases")
        return "Error runing test cases", "", ""
    print(f"Failing tests = {failing_tests}")

    all_patches = []
    l_index = 1

    for _ in range(len(locations)):
        cur_index = loc_ranks.index(max(loc_ranks))
        loc = locations[cur_index]
        print(f"Processing location {l_index}/{len(locations)}")
        file_names = loc["file_path"].split("/")[-1].split(".")
        file_path = map_file_path(loc["file_path"])
        backup_path = (
            backup_folder
            + "/"
            + file_names[0]
            + str(backup_index)
            + "."
            + file_names[1]
        )

        fixes = generate_fixes(loc, file_path, beam_size)

        f_index = 0

        for fix in fixes:
            f_index += 1
            print(f"Testing fix {f_index}/{len(fixes)}")

            copy_file(file_path, backup_path)
            apply_patch(file_path, loc["buggy_line_numbers"], fix, loc["type"])
            res = validate_patch(tmp_bug_workspace)
            if res == "Plausible patch":
                print("Pluasible patch generated")
                loc["patch"] = fix
                return res, locations, iter_path + f"Iteration {i} with loc {cur_index + 1}/{len(locations)}. "

            elif res.startswith("Testcase failure"):
                tmp_fails = int(res.split(": ")[1])
                print(f"Failing tests changed to {tmp_fails} from {failing_tests}")
                
            elif res == "Compilation error":
                print("Compilation error")

            print("Fix reverted")
            revert_file(backup_path, file_path)
            all_patches.append((loc, fix))

        l_index += 1

    for index, (loc, fix) in enumerate(all_patches):
        print("\nCreating new iteration branch")
        copy_file(file_path, backup_path)
        apply_patch(file_path, loc["buggy_line_numbers"], fix, loc["type"])
        reduced = False
        
        res = validate_patch(tmp_bug_workspace)
        if res.startswith("Testcase failure"):
            tmp_fails = int(res.split(": ")[1])
            print(f"Failing tests changed to {tmp_fails} from {failing_tests}")
            
            if tmp_fails < failing_tests or (failing_tests == -1 and tmp_fails > 0):
                print("Location ranks updated")
                reduced = True
                
        new_locations, new_loc_ranks = legacy_modify_contexts(locations, loc_ranks, loc, fix, reduced)
        new_locations[locations.index(loc)]["patch"] = fix

        res, fix_locs, res_iter_path = legacy_iterative_inference(
            iter_path + f"Iteration {i} with loc {locations.index(loc) + 1}/{len(new_locations)}. ",
            tmp_workspace,
            tmp_bug_workspace,
            new_locations,
            new_loc_ranks,
            backup_folder,
            max_iter,
            beam_size,
            i + 1,
        )

        if res == "Plausible patch":
            return res, fix_locs, res_iter_path
        revert_file(backup_path, file_path)

    return "No plausible patch found", "", ""

def iterative_inference(
    iter_path,
    tmp_workspace,
    tmp_bug_workspace,
    locations,
    loc_ranks,
    backup_folder,
    max_iter,
    beam_size,
    i,
): 
    global backup_index
    backup_index += 1
    if i > max_iter:
        print("Max iteration reached")
        return "No plausible patch found", "", ""

    print(f"\nIteration {i}/{max_iter}")
    print("Iter path:", iter_path)
    loc_trace = [item["type"] for item in locations]
    print("Location trace:", loc_trace)
    reduced = False

    # mocked
    res = validate_patch(tmp_bug_workspace)

    if res == "Compilation error":
        failing_tests = -1

    elif res.startswith("Testcase failure"):
        failing_tests = int(res.split(": ")[1])

    else:
        print("Error runing test cases")
        return "Error runing test cases", "", ""
    print(f"Failing tests = {failing_tests}")
    # failing_tests = 1

    all_patches = []
    l_index = 1

    for loc_ind in range(len(locations)):
        cur_index = loc_ranks.index(max(loc_ranks))
        loc = locations[cur_index]
        print(f"Processing location {l_index}/{len(locations)}")
        file_names = loc["file_path"].split("/")[-1].split(".")
        file_path = map_file_path(loc["file_path"])
        backup_path = (
            backup_folder
            + "/"
            + file_names[0]
            + str(backup_index)
            + "."
            + file_names[1]
        )

        fixes = generate_fixes(loc, file_path, beam_size)
        print("Fixes:", fixes)

        f_index = 0

        for fix in fixes:
            f_index += 1
            print(f"Testing fix {f_index}/{len(fixes)}")

            copy_file(file_path, backup_path)
            apply_patch(file_path, loc["buggy_line_numbers"], fix, loc["type"])
            res = validate_patch(tmp_bug_workspace)
            if res == "Plausible patch":
                print("Pluasible patch generated")
                loc["patch"] = fix
                if reduced:
                    final_iter_path = f"Iteration {i} reduced failing tests with loc {cur_index + 1}. " 
                else:
                    final_iter_path = f"Iteration {i} with loc {cur_index + 1}/{len(locations)}. "
                    
                return (
                    res,
                    locations,
                    iter_path
                    + final_iter_path
                )

            elif res.startswith("Testcase failure"):
                tmp_fails = int(res.split(": ")[1])
                print(f"Failing tests changed to {tmp_fails} from {failing_tests}")

                if tmp_fails < failing_tests or (failing_tests == -1 and tmp_fails > 0):
                    print("Fix carried forward")
                    iter_path += f"Iteration {i} reduced failing tests with loc {cur_index + 1}. "
                    loc["patch"] = fix
                    failing_tests = tmp_fails
                    locations, loc_ranks = modify_contexts(
                        locations, loc_ranks, loc, fix
                    )
                    reduced = True
                    continue

            elif res == "Compilation error":
                print("Compilation error")

            print("Fix reverted")
            revert_file(backup_path, file_path)
            all_patches.append((loc, fix))

        l_index += 1
        loc_ranks[cur_index] = -100

    for j in range(len(loc_ranks)):
        loc_ranks[j] += 100

    if reduced:
        print("Not branching as failing tests reduced")
        res, fix_locs, res_iter_path = iterative_inference(
            iter_path,
            tmp_workspace,
            tmp_bug_workspace,
            locations,
            loc_ranks,
            backup_folder,
            max_iter,
            beam_size,
            i + 1,
        )
        return res, fix_locs, res_iter_path

    else:
        print("Branching as failing tests not reduced")
        for index, (loc, fix) in enumerate(all_patches):
            copy_file(file_path, backup_path)
            apply_patch(file_path, loc["buggy_line_numbers"], fix, loc["type"])
            new_locations, new_loc_ranks = modify_contexts(
                locations, loc_ranks, loc, fix
            )
            new_locations[locations.index(loc)]["patch"] = fix

            res, fix_locs, res_iter_path = iterative_inference(
                iter_path
                + f"Iteration {i} with loc {locations.index(loc) + 1}/{len(new_locations)}. ",
                tmp_workspace,
                tmp_bug_workspace,
                new_locations,
                new_loc_ranks,
                backup_folder,
                max_iter,
                beam_size,
                i + 1,
            )

            if res == "Plausible patch":
                return res, fix_locs, res_iter_path
            revert_file(backup_path, file_path)

    return "No plausible patch found", "", ""


def run_with_timeout(func, args=(), timeout_seconds=3600):
    def wrapper(queue, *args):
        try:
            result = func(*args)
            queue.put(result)
        except Exception as e:
            queue.put(e)

    queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=wrapper, args=(queue, *args))

    start_time = time.time()
    process.start()
    print("Process started")
    print("time started")
    process.join(timeout_seconds)
    print("time ended")
    end_time = time.time()
    duration = end_time - start_time

    print("alive test")
    if process.is_alive():
        print("process alive")
        process.terminate()
        process.join()
        print("Process timed out")
        return None, None, None, duration
    else:
        print("completed")
        result = queue.get()
        print("result got")
        if isinstance(result, Exception):
            print("Error in process:", result)
            return None, None, None, duration
        else:
            print("in else")
            if isinstance(result, tuple):
                return *result, duration
            else:
                return result, None, None, duration


def generate_patches(
    tmp_workspace,
    checkout,
    locations_folder,
    backup_folder,
    max_iter,
    beam_size,
    workspace,
    results_path,
    timeout_seconds,
    legacy_iter,
):
    global backup_index, status
    projects = get_projects()
    
    if not os.path.exists(tmp_workspace):
        os.makedirs(tmp_workspace)
        
    if not os.path.exists(results_path):
        os.makedirs(results_path)
        
    if os.path.exists(os.path.join(results_path,"summary_results.json")):
        with open(os.path.join(results_path, "summary_results.json"), "r") as f:
            fixed_bugs = json.load(f)
            
    else:
        fixed_bugs = {
            "meta": {
                "last": "",
                "tot_tested": 0,
                "tot_skipped": 0,
                "tot_no_cxt": 0,
                "tot_fixed": 0,
            },
            "skipped": {},
            "no_cxt": {},
            "fixed": {},
        }

    for project in projects:
        bugs = get_bugs(project)
        if project in status:
            last_bug = status[project]
            bugs = bugs[bugs.index(last_bug)+1:]
        
        print("Bugs:", bugs)
        for bug in bugs:
            backup_index = 0
            print(f"\nProcessing bug {bug} in project {project}")

            buggy_workspace = os.path.join(workspace, project, bug)
            tmp_bug_workspace = os.path.join(tmp_workspace, project, bug)

            if checkout:
                checkout_defects4j(tmp_bug_workspace, project, bug, False)
            else:
                copy_folder_contents(buggy_workspace, tmp_bug_workspace)

            backup_bug_folder = os.path.join(backup_folder, project, bug)
            if not os.path.exists(backup_bug_folder):
                os.makedirs(backup_bug_folder)

            locations_path = os.path.join(locations_folder, project, f"fl_{bug}.json")
            if not os.path.exists(locations_path):
                print("No fault locations found")
                add_to_json(fixed_bugs["no_cxt"], project, bug)
                fixed_bugs["meta"]["tot_no_cxt"] += 1
                continue

            try:
                with open(locations_path, "r") as f:
                    locations = json.load(f)
            except:
                print("Error reading fault locations")
                add_to_json(fixed_bugs["no_cxt"], project, bug)
                fixed_bugs["meta"]["tot_no_cxt"] += 1
                continue
            
            max_locs = 3 if legacy_iter else 4
            if len(locations) > max_locs:
                print(f"Skipping due to having more than {max_locs} fault locations")
                add_to_json(fixed_bugs["skipped"], project, bug)
                fixed_bugs["meta"]["tot_skipped"] += 1
                continue

            no_cxt = False
            for loc in locations:
                if "context" not in loc:
                    no_cxt = True
                elif not loc["context"]:
                    no_cxt = True

            if no_cxt:
                print("Skipping due to no context found")
                add_to_json(fixed_bugs["no_cxt"], project, bug)
                fixed_bugs["meta"]["tot_no_cxt"] += 1
                continue

            # return locations, tmp_bug_workspace

            fixed_bugs["meta"]["tot_tested"] += 1
            loc_ranks = [0 for _ in range(len(locations))]

            args = (
                "",
                tmp_workspace,
                tmp_bug_workspace,
                locations,
                loc_ranks,
                backup_bug_folder,
                max_iter,
                beam_size,
                1,
            )

            if legacy_iter:
                iter_method = legacy_iterative_inference
            else:
                iter_method = iterative_inference

            start_time = time.time()
            res, fix_locs, iter_path = iter_method(
                "",
                tmp_workspace,
                tmp_bug_workspace,
                locations,
                loc_ranks,
                backup_bug_folder,
                max_iter,
                beam_size,
                1,
            )
            end_time = time.time()
            duration = end_time - start_time

            # res, fix_locs, iter_path, duration = run_with_timeout(iter_method, args, timeout_seconds)

            if res == "Plausible patch":
                # save_to_json(results_path, "fix_locs.json", fix_locs)
                add_to_json(fixed_bugs["fixed"], project, bug)
                fixed_bugs["meta"]["tot_fixed"] += 1
                fix_trace = generate_fix_trace(fix_locs, locations)

                res_folder = os.path.join(results_path, project)

                if not os.path.exists(res_folder):
                    os.makedirs(res_folder)
                patch_output = {
                    "patch": fix_trace,
                    "iter_path": iter_path,
                    "time_cost": duration,
                }
                save_to_json(res_folder, f"{project}_{bug}.json", patch_output)

                # if project in fixed_bugs:
                #     fixed_bugs[project][bug] = {"patch":fix_trace, "iter_path": iter_path, "time_cost": duration}
                # else:
                #     fixed_bugs[project] = {bug: {"patch":fix_trace, "iter_path": iter_path, "time_cost": duration}}

            fixed_bugs["meta"]["last"] = project + bug
            save_to_json(results_path, "summary_results.json", fixed_bugs)
            remove_folder(backup_bug_folder)
            # remove_folder(tmp_bug_workspace)

        fixed_bugs["meta"]["last"] = project + bug
        save_to_json(results_path, "summary_results.json", fixed_bugs)
        remove_folder(backup_bug_folder)
        print(f"Fixed bugs: {fixed_bugs}")


if __name__ == "__main__":
    tmp_workspace = "./workspace"
    checkout = True
    backup_folder = "./backup"
    locations_folder = "../Fault_Localization/fault_locations"
    max_iter = 3
    beam_size = 4
    timeout_seconds = 3600
    workspace = ""
    legacy_iter = False
    results_path = "./results"

    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    genai.configure(api_key=api_key)  # Initialize Gemini with the API key
    model = genai.GenerativeModel("gemini-2.0-flash")  # Use the Gemini Pro model
    
    backup_index = 0
    generate_patches(
        tmp_workspace,
        checkout,
        locations_folder,
        backup_folder,
        max_iter,
        beam_size,
        workspace,
        results_path,
        timeout_seconds,
        legacy_iter
    )   
