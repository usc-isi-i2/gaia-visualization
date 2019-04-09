import json_lines
import setting

clusters_debug = {}
debugs = []


def init_debug_from_file():
    with open(setting.debug_file, 'r') as f:
        for line in json_lines.reader(f):
            debugs.append(line)


def get_debug_for_cluster(cluster_uri):
    if cluster_uri in clusters_debug:
        return clusters_debug[cluster_uri]
    entity_uri = cluster_uri.replace('-cluster', '')
    for debug in debugs:
        if entity_uri in debug['all_records']:
            clusters_debug[cluster_uri] = debug
            return debug
    return None  # not found


init_debug_from_file()
