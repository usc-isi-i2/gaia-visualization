from model import sparql, namespaces
from collections import defaultdict
import pickle


data = defaultdict(dict)

query = """
SELECT ?cluster (COUNT(?member) AS ?size)
WHERE {
  ?member xij:inCluster ?cluster
}
GROUP BY ?cluster
"""
for cluster, size in sparql.query(query, initNs=namespaces):
    data[cluster]['size'] = size


query = """
SELECT ?cluster ?label ?type 
WHERE {
  ?cluster nist:prototype ?prototype .
  ?prototype a ?type ;
             aida:hasName ?label .
  FILTER (?type NOT IN (aida:Entity, aida:Event))
}
"""
for cluster, label, type_ in sparql.query(query, initNs=namespaces):
    data[cluster]['label'] = label
    data[cluster]['type'] = type_

pickle.dump(data, open('cluster.pkl', 'wb'))
