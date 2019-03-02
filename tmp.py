from model import sparql, namespaces, AIDA
from rdflib.namespace import split_uri
from collections import defaultdict
import pickle


data = defaultdict(dict)

query = """
SELECT ?cluster (COUNT(?member) AS ?size)
WHERE {
  ?membership aida:cluster ?cluster ;
              aida:clusterMember ?member .
}
GROUP BY ?cluster """
for cluster, size in sparql.query(query, namespaces):
    cluster = str(cluster)
    data[cluster]['size'] = int(size)

# Entity
query = """
SELECT ?cluster ?label ?category
WHERE {
  ?cluster aida:prototype ?prototype .
  ?prototype a aida:Entity .
  OPTIONAL { ?prototype aida:hasName ?label }
  ?statement rdf:subject ?prototype ;
             rdf:predicate rdf:type ;
             rdf:object ?category .
} """
for cluster, label, type_ in sparql.query(query, namespaces):
    if not label:
        _, label = split_uri(type_)
    cluster = str(cluster)
    data[cluster]['label'] = str(label)
    data[cluster]['type'] = str(type_)

# Event
query = """
SELECT ?cluster ?category
WHERE {
  ?cluster aida:prototype ?prototype .
  ?prototype a aida:Event .
  ?statement rdf:subject ?prototype ;
             rdf:predicate rdf:type ;
             rdf:object ?category .
} """
for cluster, type_ in sparql.query(query, namespaces):
    _, label = split_uri(type_)
    cluster = str(cluster)
    data[cluster]['label'] = str(label)
    data[cluster]['type'] = str(type_)

# Relation
query = """
SELECT ?cluster ?type
WHERE {
  ?cluster aida:prototype ?prototype .
  ?prototype a aida:Relation .
  ?statement rdf:subject ?prototype ;
             rdf:predicate rdf:type ;
             rdf:object ?type .
} """
for cluster, type_ in sparql.query(query, namespaces):
    _, label = split_uri(type_)
    cluster = str(cluster)
    data[cluster]['label'] = str(label)
    data[cluster]['type'] = str(AIDA.Relation)

pickle.dump(data, open('cluster.pkl', 'wb'))
