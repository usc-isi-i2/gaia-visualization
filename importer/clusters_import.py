import sys
import json_lines
from . import queries
import requests
from . import namespaces as ns

prefix = ''.join(['PREFIX %s: <%s>\n' % (abbr, full) for abbr, full in ns.namespaces.items()])

class Cluster:
    def __init__(self, members_list):
        self.__uri = '%s-cluster' % members_list[0]
        self.__prototype_uri = '%s-prototype' % members_list[0]
        self.__members = members_list

    def to_string(self):
        return self.__uri + " [" + ",".join(self.__members) + "]"

    def uri(self):
        return self.__uri

    def prototype_uri(self):
        return self.__prototype_uri

    def members(self):
        return self.__members


def update_sparql(endpoint, q, user, pwd):
    req = requests.post(endpoint + '/statements', params={'update': q}, auth=(user, pwd))
    print(req, req.content)
    return req.status_code


def upload_data(endpoint, triple_list, nt_prefix, user, pwd):
    data = nt_prefix + '\n'.join(triple_list)
    with open("queries.txt", 'w') as f:
        f.write(data)
    r = requests.post(endpoint, data=data, headers={'Content-Type': 'text/turtle'}, auth=(user, pwd))
    print('  response ', r.content)
    return r.status_code


def wrap_cluster(cluster_uri, prototype_uri, system_uri, prototype_type):
    cluster = '''
        <%s> a               aida:SameAsCluster ;
             aida:prototype  <%s> ;
             aida:system     <%s> .
        <%s> a %s .
        ''' % (cluster_uri, prototype_uri, system_uri, prototype_uri, prototype_type)
    return cluster.strip('\n')


def wrap_membership(cluster_uri, member_uri, system_uri):
    membership = '''
    [] a aida:ClusterMembership ;
       aida:cluster <%s> ;
       aida:clusterMember <%s> ;
       aida:confidence [
            a aida:Confidence ;
            aida:confidenceValue  "1.0"^^xsd:double ;
            aida:system <%s> ] ;
       aida:system <%s> .
    ''' % (cluster_uri, member_uri, system_uri, system_uri)
    return membership.strip('\n')


# Create new named graph by copying the default
# Because creating empty graph is not supported
def create_graph(endpoint, graph_uri, user, pwd):
    print('Creating graph ' + graph_uri)
    query = '''
        COPY DEFAULT TO <uri>
    '''
    query = query.replace('uri', graph_uri)
    status_code = update_sparql(endpoint, query, user, pwd)
    return status_code


def delete_clusters(endpoint, graph_uri, user, pwd):
    print("Delete clusters")
    query_del_cluster = queries.delete_ori_cluster(graph_uri)
    update_sparql(endpoint, query_del_cluster, user, pwd)
    print("Delete cluster membership")
    query_del_members = queries.delete_ori_clusterMember(graph_uri)
    status_code = update_sparql(endpoint, query_del_members, user, pwd)
    return status_code


def add_entity_clusters(endpoint, graph_uri, user, pwd, clusters, system_uri):
    endpoint = endpoint + '/rdf-graphs/service?graph=' + graph_uri
    res = []
    for cluster in clusters:
        res.append(wrap_cluster(cluster.uri(), cluster.prototype_uri(), system_uri, "aida:Entity"))
        memberships = '\n'.join([wrap_membership(cluster.uri(), m, system_uri) for m in cluster.members()])
        res.append(memberships)

    print("Add entities")
    nt_prefix = ''.join(['@prefix %s: <%s> .\n' % (abbr, full) for abbr, full in ns.namespaces.items()])
    status_code = upload_data(endpoint, res, nt_prefix, user, pwd)
    return status_code


def run_insert_proto(endpoint, graph_uri, user, pwd):
    print("start inserting prototype name")
    insert_name = queries.proto_name(graph_uri)
    status_code = update_sparql(endpoint, prefix + insert_name, user, pwd)
    if status_code > 300:
        return status_code

    print("start inserting prototype type(category)")
    insert_type = queries.proto_type(graph_uri)
    status_code = update_sparql(endpoint, prefix + insert_type, user, pwd)
    if status_code > 300:
        return status_code

    print("start inserting prototype justification")
    insert_justi = queries.proto_justi(graph_uri)
    status_code = update_sparql(endpoint, prefix + insert_justi, user, pwd)
    if status_code > 300:
        return status_code

    print("start inserting prototype type-assertion justification")
    insert_type_justi = queries.proto_type_assertion_justi(graph_uri)
    status_code = update_sparql(endpoint, prefix + insert_type_justi, user, pwd)
    print("Done. ")
    return status_code


def run_super_edge(endpoint, graph_uri, user, pwd):
    print("start inserting superEdge")
    insert_se = queries.super_edge(graph_uri)
    status_code = update_sparql(endpoint, prefix + insert_se, user, pwd)
    if status_code > 300:
        return status_code

    print("start inserting superEdge justifications")
    insert_se_justi = queries.super_edge_justif(graph_uri)
    status_code = update_sparql(endpoint, prefix + insert_se_justi, user, pwd)
    print("Done. ")
    return status_code


def create_clusters(endpoint, repository, graph_uri, clusters_file, system_uri, username, password):

    endpoint = endpoint + '/' + repository

    # 1. create graph
    status_code = create_graph(endpoint, graph_uri, username, password)
    if status_code > 300:
        return "Failed creating graph: status code: " + status_code

    # 1. get clusters from file
    clusters = []
    with open(clusters_file, 'r') as f:
        for line in json_lines.reader(f):
            clusters.append(Cluster(line))

    print(len(clusters))

    # 2. delete membership and clusters from graph
    status_code = delete_clusters(endpoint, graph_uri, username, password)
    if status_code > 300:
        return "Failed deleting membership and clusters: status code: " + status_code

    # 3. add entities
    status_code = add_entity_clusters(endpoint, graph_uri, username, password, clusters, system_uri)
    if status_code > 300:
        return "Failed adding clusters: status code: " + status_code

    # 4. insert prototypes
    status_code = run_insert_proto(endpoint, graph_uri, username, password)
    if status_code > 300:
        return "Failed creating prototypes: status code: " + status_code

    # 5.  insert super edge
    status_code = run_super_edge(endpoint, graph_uri, username, password)
    if status_code > 300:
        return "Failed inserting super edge: status code: " + status_code

    return 'success'


if __name__ == '__main__':

    endpoint = 'http://gaiadev01.isi.edu:7200/repositories'

    # repository = 'gaia0304ta1-test'
    # clusters_file = 'clusters-20190403.jl'  # gaia0304ta1-test

    # repository = 'gaia0404ta1-test'
    # clusters_file = 'clusters-baseline-20190408-001.jl'  # gaia0404ta1-test

    repository = 'gaia0404ta1-testing'
    clusters_file = 'clusters-baseline-20190408-001.jl'  # gaia0404ta1-test

    graph_uri = 'http://www.isi.edu/clusters1'

    system_uri = 'http://www.isi.edu'
    username = sys.argv[1]
    password = sys.argv[2]

    create_clusters(endpoint, repository, graph_uri, clusters_file, system_uri, username, password)
