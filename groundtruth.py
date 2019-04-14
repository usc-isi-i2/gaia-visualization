import json_lines
import os
import re

# a list of lists
groundtruth = {}
prefix = 'http://www.isi.edu/gaia/entities/'


def has_gt(repo, graph):
    gtid = repo
    if graph:
        gtid = gtid + repo + '-' + re.sub('[^0-9a-zA-Z]+', '-', graph)
    file = 'gt/' + gtid + 'jl'
    return os.path.isfile(file)


# returns a list of members in the gt cluster
def search_cluster(repo, graph, entity_uri):
    gtid = repo
    if graph:
        gtid = gtid + repo + '-' + re.sub('[^0-9a-zA-Z]+', '-', graph)

    if gtid not in groundtruth:
        file = 'gt/' + gtid + 'jl'
        groundtruth[gtid] = []
        with open(file, 'r') as f:
            for line in json_lines.reader(f):
                groundtruth[gtid].append(line)

    for cluster in groundtruth[gtid]:
        if entity_uri in cluster:
            return cluster
    return []


def get_all():
    return groundtruth
