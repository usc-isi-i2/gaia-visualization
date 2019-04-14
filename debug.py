import json_lines
import re
import os

debugs = {}


def has_debug(repo, graph):
    did = repo
    if graph:
        did = repo + '-' + re.sub('[^0-9a-zA-Z]+', '-', graph)

    debug_file = 'debug/' + did + '.jl'
    return os.path.isfile(debug_file)


def get_debug_for_cluster(repo, graph, cluster_uri):

    did = repo
    if graph:
        did = repo + '-' + re.sub('[^0-9a-zA-Z]+', '-', graph)

    # get debug file for repo/graph if hasn't been loaded
    if did not in debugs:
        debugs[did] = []
        debug_file = 'debug/' + did + '.jl'
        if os.path.isfile(debug_file):
            with open(debug_file, 'r') as f:
                for line in json_lines.reader(f):
                    debugs[did].append(line)
        else:
            return None

    entity_uri = cluster_uri.replace('-cluster', '')
    for debug in debugs[did]:
        if entity_uri in debug['all_records']:
            return debug
    return None  # not found

