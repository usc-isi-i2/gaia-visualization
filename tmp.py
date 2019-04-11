from model import sparql, namespaces, AIDA
from rdflib.namespace import split_uri
from collections import defaultdict
import pickle
from setting import named_graph


data = defaultdict(dict)

open_clause = close_clause = ''
if named_graph:
    open_clause = 'GRAPH <%s> {' % named_graph
    close_clause = '}'

query = """
SELECT ?cluster (COUNT(?member) AS ?size)
WHERE {
    %s
        ?membership aida:cluster ?cluster ;
                    aida:clusterMember ?member .
    %s
}
GROUP BY ?cluster """ % (open_clause, close_clause)

for cluster, size in sparql.query(query, namespaces):
    cluster = str(cluster)
    data[cluster]['size'] = int(size)

# Entity
query = """
SELECT ?cluster ?label ?category
WHERE {
    %s
        ?cluster aida:prototype ?prototype .
        ?prototype a aida:Entity .
        OPTIONAL { ?prototype aida:hasName ?label }
        OPTIONAL { ?statement rdf:subject ?prototype ;
                              rdf:predicate rdf:type ;
                              rdf:object ?category . }
     %s
} """ % (open_clause, close_clause)

for cluster, label, type_ in sparql.query(query, namespaces):
    if not label and type_:
        _, label = split_uri(type_)
    cluster = str(cluster)
    data[cluster]['label'] = str(label) if label else cluster
    data[cluster]['type'] = str(type_)

# Event
query = """
SELECT ?cluster ?category
WHERE {
    %s
        ?cluster aida:prototype ?prototype .
        ?prototype a aida:Event .
        ?statement rdf:subject ?prototype ;
                   rdf:predicate rdf:type ;
                   rdf:object ?category .
    %s
} """ % (open_clause, close_clause)

for cluster, type_ in sparql.query(query, namespaces):
    _, label = split_uri(type_)
    cluster = str(cluster)
    data[cluster]['label'] = str(label)
    data[cluster]['type'] = str(type_)

# Relation
query = """
SELECT ?cluster ?type
WHERE {
    %s
        ?cluster aida:prototype ?prototype .
        ?prototype a aida:Relation .
        ?statement rdf:subject ?prototype ;
                   rdf:predicate rdf:type ;
                   rdf:object ?type .
    %s
} """ % (open_clause, close_clause)

for cluster, type_ in sparql.query(query, namespaces):
    _, label = split_uri(type_)
    cluster = str(cluster)
    data[cluster]['label'] = str(label)
    data[cluster]['type'] = str(AIDA.Relation)

pickle.dump(data, open('cluster.pkl', 'wb'))
