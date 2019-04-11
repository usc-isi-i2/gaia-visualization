from rdflib import URIRef
import pickle
from model import sparql, namespaces
from model import pickled
from setting import named_graph

open_clause = close_clause = ''
if named_graph:
    open_clause = 'GRAPH <%s> {' % named_graph
    close_clause = '}'


def query_justification_lbl(uri):
    query = """
    SELECT ?lbl 
    WHERE {
        %s
        ?ms aida:cluster ?cluster ;
            aida:clusterMember/aida:justifiedBy/skos:prefLabel ?lbl .
        %s
    }
    GROUP BY ?lbl
    ORDER BY DESC(COUNT(?lbl))
    LIMIT 1
    """ % (open_clause, close_clause)
    for lbl, in sparql.query(query, namespaces, {'cluster': URIRef(uri)}):
        return lbl


def query_justification_label_for_cluster_by_type(typ, prefix=''):
    for uri, cluster in pickled.items():
        if cluster['label'] == typ and cluster['type'] == 'https://tac.nist.gov/tracks/SM-KBP/2018/ontologies/SeedlingOntology#' + typ:
            label = query_justification_lbl(uri)
            if label:
                cluster['label'] = prefix + label


query_justification_label_for_cluster_by_type('Person', '[P]')
query_justification_label_for_cluster_by_type('Time', '[T]')
query_justification_label_for_cluster_by_type('Facility', '[F]')
query_justification_label_for_cluster_by_type('Money', '[M]')
query_justification_label_for_cluster_by_type('Location', '[L]')
query_justification_label_for_cluster_by_type('Weapon', '[W]')
query_justification_label_for_cluster_by_type('Organization', '[O]')
query_justification_label_for_cluster_by_type('Vehicle', '[V]')


pickle.dump(pickled, open('cluster.pkl', 'wb'))

