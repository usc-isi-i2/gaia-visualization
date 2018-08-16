from rdflib.plugins.stores.sparqlstore import SPARQLStore
from source_context import SourceContext
from rdflib import URIRef, Literal
from rdflib.namespace import Namespace, SKOS, RDF
from collections import namedtuple
endpoint = 'http://kg2018a.isi.edu:3030/all_clusters/sparql'
sparql = SPARQLStore(endpoint)
context = SourceContext()
AIDA = Namespace('http://darpa.mil/aida/interchangeOntology#')
namespaces = {
    'aida': AIDA,
    'skos': SKOS,
    'rdf': RDF,
    'xij': Namespace('http://isi.edu/xij-rule-set#')
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
             a ?category ;
             skos:prefLabel ?label .
  FILTER (?type NOT IN (aida:Entity, aida:Event) && ?category IN (aida:Entity, aida:Event))
} """
        for prototype, label, type_, cate in sparql.query(query, namespaces, {'cluster': self.uri}):
            self.__prototype = ClusterMember(prototype, label, type_)
            self.__type = cate

    def _init_cluster_members(self):
        query = """
SELECT ?member ?label ?type
WHERE {
  ?member xij:inCluster ?cluster ;
          skos:prefLabel ?label ;
          a ?type
  FILTER (?type NOT IN (aida:Entity, aida:Event))
} """
        for member, label, type_ in sparql.query(query, namespaces, {'cluster': self.uri}):
            self.__members.append(ClusterMember(member, label, type_))

    def _init_forward_clusters(self):
        query = """
SELECT ?p ?o ?cnt
WHERE {
  ?se rdf:subject ?s ;
      rdf:predicate ?p ;
      rdf:object ?o ;
      aida:edgeCount ?cnt .
}
        """
        for p, o, cnt in sparql.query(query, namespaces, {'s': self.uri}):
            self.__forward.add(SuperEdge(self, Cluster(o), p, int(cnt)))

    def _init_backward_clusters(self):
        query = """
SELECT ?s ?p ?cnt
WHERE {
  ?se rdf:subject ?s ;
      rdf:predicate ?p ;
      rdf:object ?o ;
      aida:edgeCount ?cnt .
}
        """
        for s, p, cnt in sparql.query(query, namespaces, {'o': self.uri}):
            self.__backward.add(SuperEdge(Cluster(s), self, p, int(cnt)))

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

    def _init_member(self):
        query = """
SELECT ?prototype ?type ?label
WHERE {
  ?member a ?type ;
          skos:prefLabel ?label
  FILTER (?type NOT IN (aida:Entity, aida:Event))
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
ORDER BY ?start
"""
        for source, start, end in sparql.query(query, namespaces, {'member': self.uri}):
            self.__source = str(source)
            self.__context_pos.append((int(start), int(end)))

    @property
    def source_url(self):
        if self.source in context.map:
            return context.map[self.source]['URL']

    @property
    def source(self):
        if not self.__source:
            self._init_source()
        return self.__source

    @property
    def mention(self):
        for start, end in self.__context_pos:
            res = context.get_some_context(self.source, start, end, 100)
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
             skos:prefLabel ?label .
  ?member xij:inCluster ?cluster .
}
GROUP BY ?cluster ?label
ORDER BY DESC(?memberN)
LIMIT 10 """
    # bind = {'type': type_} if type_ in {AIDA.Entity, AIDA.Event} else {}
    # return {ClusterSummary(u, u.replace('http://www.isi.edu/gaia', '/cluster'), l, c)
    #         for u, l, c in sparql.query(query, namespaces, bind)}
    if type_ in {AIDA.Entity, AIDA.Event}:
        query = query.replace('?type', type_.n3())
    return [ClusterSummary(u, u.replace('http://www.isi.edu/gaia', '/cluster'), l, c)
            for u, l, c in sparql.query(query, namespaces)]
