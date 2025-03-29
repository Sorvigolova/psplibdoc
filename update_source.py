#! /usr/bin/env python3

# Check if the "SOURCE" field is properly filled

import psp_libdoc
import glob
from collections import defaultdict

# For each NID with a confirmed name, holds the (name, module, library) tuples
all_nids = defaultdict(set)
# List of (NID, name, module, library) tuples with non-matching or unknown NID
all_unk_nids = []

# Browse all the export files
filelist = glob.glob('PSPLibDoc/**/*.xml', recursive=True)
for (idx, file) in enumerate(filelist):
    print('checking', file)
    entries = psp_libdoc.loadPSPLibdoc(file)
    # Get the version and module name from the path
    version = file.split('/')[1]
    moduleName = file.split('/')[-1].split('.')[0] + '.prx'
    updated_entries = []
    for e in entries:
        # Check if the specified names match their NID
        if e.name.endswith(e.nid): # no name specified, check that there is no source
            if e.source != '':
                print("source set for", e.name, e.nid, ":", e.source)
                e = e._replace(source = '')
                updated_entries.append(e)
        elif psp_libdoc.compute_nid(e.name) == e.nid: # NIDs matches, specifying 'matching' as the source
            if e.source != 'matching':
                e = e._replace(source = 'matching')
                updated_entries.append(e)
        elif e.source != 'previous version (automated)' and e.source != 'previous version' and e.source != 'unknown':
            print('wrong', e.name, e.nid, e.source)
            e = e._replace(source = "unknown")
            updated_entries.append(e)

    psp_libdoc.updatePSPLibdoc(updated_entries, file)

