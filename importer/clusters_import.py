import sys
import os
kg_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../gaia-knowledge-graph/update_kg')
sys.path.append(kg_path)
from Updater import Updater
import setting


def create_clusters(endpoint, repo, graph):

    endpoint = endpoint + '/' + repo
    data_dir = setting.store_data + '/' + repo
    up = Updater(endpoint, repo, data_dir, graph, True)
    up.run_load_jl()
    up.run_system()
    up.run_entity_nt()
    up.run_event_nt()
    up.run_relation_nt()
    up.run_insert_proto()
    up.run_super_edge()

    return 'success'
