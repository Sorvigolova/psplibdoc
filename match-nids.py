#!/usr/bin/python3

# When a NID randomization has been detected, try to match to the closest function in the previous firmware
# Usage example: ./match-nids.py PSPLibDoc/kd/ata.xml 620.PBP/F0/kd/ata.prx 630.PBP/F0/kd/ata.prx

from collections import defaultdict
import Levenshtein
import psp_libdoc
import re
import subprocess
import sys

# Run prxtool on a .prx file
def run_prxtool(binary_path):
    return subprocess.check_output(["prxtool", "-w", binary_path], stderr=subprocess.DEVNULL).decode('ascii')

# Get the raw disassembly (without addresses) of the functions of a .prx file
def get_raw_functions(binary_path):
    data = run_prxtool(binary_path)
    funs = defaultdict(str)
    cur_fun = None
    names = []
    for line in data.split('\n'):
        if 'Subroutine' in line:
            m = re.match(r"; Subroutine ([^ ]*) .*", line)
            names = [m.groups()[0]]
            alias_pos = line.find("Aliases: ")
            if alias_pos != -1:
                alias_str = line[alias_pos + len("Aliases: "):]
                names += alias_str.split(", ")
        elif line.startswith('\t0x'):
            m = re.match(r"\t0x[0-9A-F]{8}: 0x([0-9A-F]{8})", line)
            data = m.groups()[0]
            for n in names:
                funs[n] += data
        elif '; Imported from' in line:
            break
    return funs

# Match the functions of two module (versions) by repeatedly finding the closest pairs
def match_module_pair(path1, path2):
    # Find the functions of both modules, ignoring unexported functions
    funs1 = {k: v for k, v in get_raw_functions(path1).items() if not (k.startswith('sub_') or k.startswith('loc_') or k.startswith('module_'))}
    funs2 = {k: v for k, v in get_raw_functions(path2).items() if not (k.startswith('sub_') or k.startswith('loc_') or k.startswith('module_'))}
    distances = defaultdict(dict)
    print('computing distances...')
    for (f1, c1) in funs1.items():
        lib1 = f1[:-8]
        for (f2, c2) in funs2.items():
            lib2 = f2[:-8]
            if lib1 != lib2:
                continue
            distances[f1][f2] = Levenshtein.distance(c1, c2)

    print('associating functions...')
    result = {}
    while len(funs1) > 0 and len(funs2) > 0:
        closest_pair = None
        min_dist = None
        for (f1, c1) in funs1.items():
            lib1 = f1[:-8]
            for (f2, c2) in funs2.items():
                lib2 = f2[:-8]
                # Only match functions belonging to the same library
                if lib1 != lib2:
                    continue
                cur_dist = distances[f1][f2]
                if min_dist is None or cur_dist < min_dist:
                    min_dist = cur_dist
                    closest_pair = (f1, f2)
        if closest_pair is None: # could happen if the two remaining functions are in different libraries
            break
        #print(closest_pair, min_dist)
        del funs1[closest_pair[0]]
        del funs2[closest_pair[1]]
        result[closest_pair[0]] = closest_pair[1]
    # Return a dictionary of (name of function in path1) -> (name of function in path2)
    return result

# Match pairs of NIDs for a sequence of versions of modules
def match_modules(paths):
    results = []
    for (path1, path2) in zip(paths, paths[1:]):
        print("check", path1, path2)
        results.append(match_module_pair(path1, path2))
        print(results[-1])

    checked = set()
    nid_matches = {}
    for j in range(len(results)):
        for k in results[j]:
            if k not in checked:
                firstk = k
                for i in range(j, len(results)):
                    checked.add(k)
                    print(k, '->', end=' ')
                    if k not in results[i]:
                        break
                    k = results[i][k]
                    checked.add(k)
                    nid_matches[k] = firstk
                print(k)
    return nid_matches

# Return the "real" name associated to an unobfuscated name (LibraryName_12345678), if it exists in the psplibdoc
def check_entry(entries, funname):
    lib = '_'.join(funname.split('_')[:-1])
    nid = funname.split('_')[-1]
    for e in entries:
        if e.nid == nid and e.libraryName == lib:
            if not e.name.endswith(e.nid):
                return e.name
            else:
                return None
    assert(False)

# Include automated deductions in a given libdoc file
def fix_psplibdoc(libdoc, modules):
    # nid_matches contains a (obfuscated NID) -> (unobfuscated NID) mapping
    nid_matches = match_modules(modules)

    entries = psp_libdoc.loadPSPLibdoc(libdoc)
    out_entries = []
    for e in entries:
        funname = e.libraryName + '_' + e.nid
        if e.name.endswith(e.nid) and funname in nid_matches:
            # Check if the unobfuscated NID does have an associated name
            prev_name = check_entry(entries, nid_matches[funname])
            if prev_name is not None:
                print(funname, '->', prev_name)
                e = e._replace(name = prev_name, source = "previous version (automated)")
        out_entries.append(e)

    psp_libdoc.updatePSPLibdoc(out_entries, libdoc)

if __name__ == '__main__':
    fix_psplibdoc(sys.argv[1], sys.argv[2:])

