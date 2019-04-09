import json_lines
import setting

# a list of lists
groundtruth = []
prefix = 'http://www.isi.edu/gaia/entities/'


def init_groundtruth():
    with open(setting.gt_file, 'r') as f:
        for line in json_lines.reader(f):
            groundtruth.append(line)


# returns a list of members in the gt cluster
def search_cluster(entity_uri):
    for cluster in groundtruth:
        if entity_uri in cluster:
            return cluster
    return []


def get_all():
    return groundtruth


init_groundtruth()
