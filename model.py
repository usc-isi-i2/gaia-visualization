from rdflib.plugins.stores.sparqlstore import SPARQLStore
from source_context import SourceContext
from rdflib import URIRef, Literal
from rdflib.namespace import Namespace, RDF
from collections import namedtuple
endpoint = 'http://gaiadev01.isi.edu:3030/rpi0901aif80d2/query'
sparql = SPARQLStore(endpoint)
AIDA = Namespace('https://tac.nist.gov/tracks/SM-KBP/2018/ontologies/InterchangeOntology#')
namespaces = {
    'aida': AIDA,
    'rdf': RDF,
}

types = namedtuple('AIDATypes', ['Entity', 'Events'])(AIDA.Entity, AIDA.Event)


def get_cluster(uri):
    if Cluster.ask(uri):
        return Cluster(uri)
    return None


class Cluster:
    def __init__(self, uri):
        self.uri = URIRef(uri)
        self.__prototype = None
        self.__type = None
        self.__members = []
        self.__forward = None
        self.__backward = None

    @property
    def href(self):
        return self.uri.replace('http://www.isi.edu/gaia', '/cluster')

    @property
    def label(self):
        return self.prototype.label

    @property
    def prototype(self):
        if not self.__prototype:
            self._init_cluster_prototype()
        return self.__prototype

    @property
    def type(self):
        if not self.__type:
            self._init_cluster_prototype()
        return self.__type

    @property
    def members(self):
        if not self.__members:
            self._init_cluster_members()
        return self.__members

    @property
    def size(self):
        if self.__members:
            return len(self.__members)
        return self._query_for_size()

    @property
    def forward(self):
        if self.__forward is None:
            self.__forward = set()
            self._init_forward_clusters()
        return self.__forward

    @property
    def backward(self):
        if self.__backward is None:
            self.__backward = set()
            self._init_backward_clusters()
        return self.__backward

    @property
    def neighbors(self):
        return self.forward | self.backward

    def neighborhood(self, hop=2):
        if hop <= 1:
            return self.neighbors
        hood = set()
        for neighbor in self.neighbors:
            hood |= neighbor.subject.neighborhood(hop-1)
            hood |= neighbor.object.neighborhood(hop-1)
        return hood

    @property
    def img(self):
        from graph import SuperEdgeBasedGraph
        graph = SuperEdgeBasedGraph(self.neighborhood(), self, self.uri)
        path = graph.dot()
        return graph.name

    @classmethod
    def ask(cls, uri):
        query = "ASK { ?cluster a aida:SameAsCluster }"
        for ans in sparql.query(query, namespaces, {'cluster': URIRef(uri)}):
            return ans
        return False

    def _init_cluster_prototype(self):
        query = """
SELECT ?prototype ?label ?type ?category
WHERE {
  ?cluster aida:prototype ?prototype .
  ?prototype a ?type ;
             aida:hasName ?label .
  ?statement a rdf:Statement ;
             rdf:subject ?prototype ;
             rdf:predicate rdf:type ;
             rdf:object ?category ;
} """
        for prototype, label, type_, cate in sparql.query(query, namespaces, {'cluster': self.uri}):
            self.__prototype = ClusterMember(prototype, label, type_)
            self.__type = cate

    def _init_cluster_members(self):
        query = """
SELECT ?member ?label ?type
WHERE {
  ?membership aida:cluster ?cluster ;
              aida:clusterMember ?member .
  ?member aida:hasName ?label .
  ?statement a rdf:Statement ;
             rdf:subject ?member ;
             rdf:predicate rdf:type ;
             rdf:object ?type .
} """
        for member, label, type_ in sparql.query(query, namespaces, {'cluster': self.uri}):
            self.__members.append(ClusterMember(member, label, type_))

    def _init_forward_clusters(self):
        query = """
SELECT ?p ?o ?cnt
WHERE {
  ?s aida:prototype ?proto1 .
  ?o aida:prototype ?proto2 .
  ?se rdf:subject ?proto1 ;
      rdf:predicate ?p ;
      rdf:object ?proto2 ;
      aida:count ?cnt .
} """
        for p, o, cnt in sparql.query(query, namespaces, {'s': self.uri}):
            self.__forward.add(SuperEdge(self, Cluster(o), p, int(cnt)))

    def _init_backward_clusters(self):
        query = """
SELECT ?s ?p ?cnt
WHERE {
  ?s aida:prototype ?proto1 .
  ?o aida:prototype ?proto2 .
  ?se rdf:subject ?proto1 ;
      rdf:predicate ?p ;
      rdf:object ?proto2 ;
      aida:count ?cnt .
} """
        for s, p, cnt in sparql.query(query, namespaces, {'o': self.uri}):
            self.__backward.add(SuperEdge(Cluster(s), self, p, int(cnt)))

    def _query_for_size(self):
        query = """
SELECT (COUNT(?member) AS ?size)
WHERE {
  ?membership aida:cluster ?cluster ;
              aida:clusterMember ?member .
}  """
        for size, in sparql.query(query, namespaces, {'cluster': self.uri}):
            return int(size)
        return 0

    def __hash__(self):
        return self.uri.__hash__()


class SuperEdge:
    def __init__(self, s: Cluster, o: Cluster, p: URIRef, n: int):
        self.subject = s
        self.predicate = p
        self.object = o
        self.count = n

    def __hash__(self):
        return hash((self.subject.uri, self.predicate, self.object.uri))

    def __eq__(self, other):
        return isinstance(other, SuperEdge) and str(self.subject) == str(other.subject) and str(self.predicate) == str(
            other.predicate) and str(self.object) == str(other.object)


class ClusterMember:
    def __init__(self, uri, label=None, type_=None):
        self.uri = URIRef(uri)
        self.__label = label
        self.__type = type_
        self.__source = None
        self.__context_pos = []
        self.__context_extractor = None

    @property
    def label(self):
        if not self.__label:
            self._init_member()
        return self.__label

    @property
    def type(self):
        if not self.__type:
            self._init_member()
        return self.__type

    @property
    def context_extractor(self):
        if self.__context_extractor is None:
            self.__context_extractor = SourceContext(self.source)
        return self.__context_extractor

    def _init_member(self):
        query = """
SELECT ?label ?type
WHERE {
  ?member aida:hasName ?label .
  ?statement rdf:subject ?member ;
             rdf:predicate rdf:type ;
             rdf:object ?type .
} """
        for label, type_ in sparql.query(query, namespaces, {'member': self.uri}):
            self.__label = label
            self.__type = type_

    def _init_source(self):
        query = """
SELECT DISTINCT ?source ?start ?end
WHERE {
  ?member aida:justifiedBy ?justification .
  ?justification aida:source ?source ;
                 aida:startOffset ?start ;
                 aida:endOffsetInclusive ?end .
}
ORDER BY ?start """
        for source, start, end in sparql.query(query, namespaces, {'member': self.uri}):
            self.__source = str(source)
            self.__context_pos.append((int(start), int(end)))

    @property
    def source(self):
        if not self.__source:
            self._init_source()
        return self.__source

    @property
    def mention(self):
        if self.context_extractor.doc_exists():
            for start, end in self.__context_pos:
                res = self.context_extractor.query_context(start, end)
                if not res:
                    continue
                yield res

    def __hash__(self):
        return self.uri.__hash__()


ClusterSummary = namedtuple('ClusterSummary', ['uri', 'href', 'label', 'count'])


def get_cluster_list(type_=None):
    query = """
SELECT ?cluster ?label (COUNT(?member) AS ?memberN)
WHERE {
  ?cluster aida:prototype ?prototype .
  ?prototype a ?type ;
             aida:hasName ?label .
  ?membership aida:cluster ?cluster ;
              aida:clusterMember ?member .
}
GROUP BY ?cluster ?label
ORDER BY DESC(?memberN)
LIMIT 10 """
    if type_ in {AIDA.Entity, AIDA.Event}:
        query = query.replace('?type', type_.n3())
    return [ClusterSummary(u, u.replace('http://www.isi.edu/gaia', '/cluster'), l, c)
            for u, l, c in sparql.query(query, namespaces)]


if __name__ == '__main__':
    cluster = get_cluster('http://www.isi.edu/gaia/entities/a38267dd-499f-45bd-aa22-7b474781f193-cluster')
    print(cluster.label, cluster.uri, cluster.type, cluster.prototype.type)
    print(cluster.size)
