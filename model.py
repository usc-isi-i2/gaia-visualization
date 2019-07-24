from rdflib.plugins.stores.sparqlstore import SPARQLStore
from source_context import LTFSourceContext
from rdflib import URIRef, Literal
from rdflib.namespace import Namespace, RDF, SKOS, split_uri
from collections import namedtuple, Counter
import pickle
from setting import wikidata_endpoint, groundtruth_url
import requests
import debug
import json
import os
import tmp
import time_person_label
import re

wikidata_sparql = SPARQLStore(wikidata_endpoint)
AIDA = Namespace('https://tac.nist.gov/tracks/SM-KBP/2019/ontologies/InterchangeOntology#')
WDT = Namespace('http://www.wikidata.org/prop/direct/')
namespaces = {
    'aida': AIDA,
    'rdf': RDF,
    'skos': SKOS,
    'wdt': WDT
}
types = namedtuple('AIDATypes', ['Entity', 'Events', 'Relation'])(AIDA.Entity, AIDA.Event, AIDA.Relation)


class Model:
    def __init__(self, sparql, repo, graph):
        self.__sparql = sparql
        self.__repo = repo
        self.__graph = graph
        pkl_file = 'pkl/' + repo
        if graph:
            pkl_file = pkl_file + '-' + re.sub('[^0-9a-zA-Z]+', '-', graph)
        pkl_file = pkl_file + '.pkl'
        if not os.path.isfile(pkl_file):
            tmp.run(sparql, graph, pkl_file, namespaces, AIDA)
            time_person_label.run(sparql, graph, pkl_file, namespaces)
        self.__pickled = pickle.load(open(pkl_file, 'rb'))

    @property
    def graph(self):
        return self.__graph

    @property
    def repo(self):
        return self.__repo

    @property
    def sparql(self):
        return self.__sparql

    @property
    def pickled(self):
        return self.__pickled

    def get_cluster(self, uri):
        if Cluster.ask(self.__sparql, self.__graph, uri):
            return Cluster(self, uri)
        return None

    def get_cluster_list(self, type_=None, limit=10, offset=0, sortby='size'):
        open_clause = close_clause = ''
        if self.__graph:
            open_clause = 'GRAPH <%s> {' % self.__graph
            close_clause = '}'
        query = """
    SELECT ?cluster ?label (COUNT(?member) AS ?memberN)
    WHERE {
        %s
        ?cluster aida:prototype ?prototype .
        ?prototype a ?type .
        label_string
        ?membership aida:cluster ?cluster ;
                  aida:clusterMember ?member .
        MINUS {?cluster aida:prototype ?member}
        %s
    }
    GROUP BY ?cluster ?label
    ORDER BY order_by
    """ % (open_clause, close_clause)
        if type_ == AIDA.Entity:
            query = query.replace('?type', type_.n3())
            query = query.replace('label_string', 'OPTIONAL {?prototype aida:hasName ?label} .')
            query = query.replace('order_by', 'DESC(?memberN)')
        if type_ == AIDA.Event or type_ == AIDA.Relation:
            query = query.replace('?type', type_.n3())
            query = query.replace('label_string',
                                  '?s rdf:subject ?prototype ; rdf:predicate rdf:type ; rdf:object ?label .')
            if sortby == 'type':
                query = query.replace('order_by', '?label DESC(?memberN)')
            else:
                query = query.replace('order_by', 'DESC(?memberN) ?label')
        if limit:
            query += " LIMIT " + str(limit)
        if offset:
            query += " OFFSET " + str(offset)
        print(query)

        results = self.__sparql.query(query, namespaces)
        result_gen = (x for x in results if x.cluster)
        for r in result_gen:
            l = r.label
            u = r.cluster
            c = r.memberN
            if isinstance(l, URIRef):
                _, l = split_uri(l)
            if 'http://www.isi.edu/gaia' in u:
                href = u.replace('http://www.isi.edu/gaia', '/cluster')
                href = href.replace('/entities', '/entities/' + self.repo)
                href = href.replace('/events', '/events/' + self.repo)
                href = href.replace('/relations', '/relations/' + self.repo)
            else:
                href = u.replace('http://www.columbia.edu', '/cluster/' + self.repo)
            if self.graph:
                href = href + '?g=' + self.graph
            yield ClusterSummary(u, href, l, c)

    def recover_doc_online(self, doc_id):
        import json
        query_label_location = """
        SELECT DISTINCT ?label ?start ?end ?justificationType WHERE {
            ?justification a aida:TextJustification ;
                           skos:prefLabel ?label ;
                           aida:source ?source ;
                           aida:startOffset ?start ;
                           aida:endOffsetInclusive ?end ;
                           aida:privateData ?privateData .
            ?privateData aida:system <http://www.rpi.edu> ; aida:jsonContent ?justificationType
        }
        ORDER BY ?start 
        """

        doc_recover = ''
        lend = 0
        for label, start, end, j in self.__sparql.query(query_label_location, namespaces, {'source': Literal(doc_id)}):
            doc_recover += ' ' * (int(start)-lend)
            if json.loads(j).get('justificationType') == 'pronominal_mention':
                doc_recover += '<span style="color: red"><b>' + label + '</b></span>'
            else:
                doc_recover += '<u>' + label + '</u>'
            lend = int(end)
        return doc_recover


class Cluster:
    def __init__(self, model, uri):
        self.model = model
        self.uri = URIRef(uri)
        self.__prototype = None
        self.__type = None
        self.__members = []
        self.__forward = None
        self.__backward = None
        self.__targets = None
        self.__selected_targets = None
        self.__target_wiki = None
        self.__freebases = None
        self.__qids = Counter()
        self.__selected_qnodes = None
        self.__q_urls = {}
        self.__groundtruth = None
        self.__debug_info = None
        self.__all_labels = None

        if model.graph:
            self.__open_clause = 'GRAPH <%s> {' % self.model.graph
            self.__close_clause = '}'
        else:
            self.__open_clause = self.__close_clause = ''

    @property
    def href(self):
        res = self.uri.replace('http://www.isi.edu/gaia', '/cluster').replace('http://www.columbia.edu', '/cluster')
        res = res.replace('/entities/', '/entities/' + self.model.repo + '/')
        res = res.replace('/events/', '/events/' + self.model.repo + '/')
        if self.model.graph:
            res = res + '?g=' + self.model.graph
        return res

    @property
    def label(self):
        if self.uri in self.model.pickled and 'label' in self.model.pickled[self.uri]:
            return self.model.pickled[self.uri]['label']
        return self.prototype.label

    @property
    def all_labels(self):
        if not self.__all_labels:
            self.__all_labels = Counter()
            for m in self.members:
                for l, c in m.all_labels:
                    if l in self.__all_labels:
                        self.__all_labels[l] += c
                    else:
                        self.__all_labels[l] = c
        return self.__all_labels.most_common()

    @property
    def prototype(self):
        if not self.__prototype:
            self._init_cluster_prototype()
        return self.__prototype

    @property
    def type(self):
        if self.uri in self.model.pickled and 'type' in self.model.pickled[self.uri]:
            return self.model.pickled[self.uri]['type']
        if not self.__type:
            self._init_cluster_prototype()
        return self.__type

    @property
    def members(self):
        if not self.__members:
            self._init_cluster_members()
        return self.__members

    @property
    def targets(self):
        if self.__targets is None:
            self._init_cluster_members()
        return self.__targets.most_common()

    @property
    def selected_targets(self):
        if self.__selected_targets is None:
            self.__selected_targets = self.debug_info.selected_targets
        return self.__selected_targets

    def get_target_stats(self, target):
        return self.debug_info.target_statistics[target]

    @property
    def target_wiki(self):
        if self.__target_wiki is None:
            self._init_cluster_members()
        return self.__target_wiki

    @property
    def freebases(self):
        if self.__freebases is None:
            self._init_cluster_members()
        return self.__freebases.most_common()

    @property
    def targetsSize(self):
        return len(self.targets)

    @property
    def qids(self):
        if not self.__qids:
            self._init_qnodes()
        return self.__qids.most_common()

    @property
    def selected_qnodes(self):
        if not self.__selected_qnodes:
            self.__selected_qnodes = self.debug_info.selected_qnodes
        return self.__selected_qnodes

    def get_qnode_stats(self, qurl):
        if qurl in self.debug_info.qnode_statistics:
            return self.debug_info.qnode_statistics[qurl]
        else:
            return None

    @property
    def q_urls(self):
        if not self.__q_urls:
            self._init_qnodes()
        return self.__q_urls

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

    def neighborhood(self, hop=1):
        if hop == 1 and self.prototype.type != AIDA.Relation:
            hood = self.neighbors
            # for neighbor in [x for x in self.neighbors if x.subject.proto]
            for neighbor in self.neighbors:
                if neighbor.subject.prototype.type == AIDA.Relation:
                    hood |= neighbor.subject.neighbors
            return hood
        if hop <= 1:
            return self.neighbors
        hood = set()
        for neighbor in self.neighbors:
            hood |= neighbor.subject.neighborhood(hop-1)
            hood |= neighbor.object.neighborhood(hop-1)
        return hood

    @property
    def img(self):
        import os.path
        _, name = split_uri(self.uri)
        svgpath = 'static/img/' + name + '.svg'
        if os.path.isfile(svgpath):
            return name

        from graph import SuperEdgeBasedGraph
        graph = SuperEdgeBasedGraph(self.model, self.neighborhood(), self, self.uri)
        path = graph.dot()
        return graph.name

    @classmethod
    def ask(cls, sparql, graph, uri):
        if graph:
            open_clause = 'GRAPH <%s> {' % graph
            close_clause = '}'
        else:
            open_clause = close_clause = ''
        query = "ASK { %s ?cluster a aida:SameAsCluster %s}" % (open_clause, close_clause)
        for ans in sparql.query(query, namespaces, {'cluster': URIRef(uri)}):
            return ans
        return False

    @property
    def groundtruth(self):
        if self.__groundtruth is None:
            self._init_groundtruth()
        return self.__groundtruth

    @property
    def has_debug(self):
        return debug.has_debug(self.model.repo, self.model.graph)

    @property
    def debug_info(self):
        if self.__debug_info is None:
            if debug.has_debug(self.model.repo, self.model.graph):
                self._init_debug_info()
            else:
                self.__debug_info = False
        return self.__debug_info

    def _init_cluster_prototype(self):
        query = """
SELECT ?prototype (MIN(?label) AS ?mlabel) ?type ?category
WHERE {
    %s
    ?cluster aida:prototype ?prototype .
    ?prototype a ?type .
    OPTIONAL { ?prototype aida:hasName ?label } .
    OPTIONAL { ?statement a rdf:Statement ;
               rdf:subject ?prototype ;
               rdf:predicate rdf:type ;
               rdf:object ?category ; }
    %s
}
GROUP BY ?prototype ?type ?category """ % (self.__open_clause, self.__close_clause)
        for prototype, label, type_, cate in self.model.sparql.query(query, namespaces, {'cluster': self.uri}):
            if not label and cate:
                _, label = split_uri(cate)
            self.__prototype = ClusterMember(self.model, prototype, label, type_)
            self.__type = cate

    def _init_cluster_members(self):
        self.__targets = Counter()
        self.__target_wiki = {}
        self.__freebases = Counter()
        query = """
SELECT ?member (MIN(?label) AS ?mlabel) ?type
WHERE {
    %s
    ?membership aida:cluster ?cluster ;
                aida:clusterMember ?member .
    MINUS {?cluster aida:prototype ?member}
    %s
    OPTIONAL { ?member aida:hasName ?label } .
    OPTIONAL {?statement a rdf:Statement ;
              rdf:subject ?member ;
              rdf:predicate rdf:type ;
              rdf:object ?type }.
     
}
GROUP BY ?member ?type """ % (self.__open_clause, self.__close_clause)
        for member, label, type_ in self.model.sparql.query(query, namespaces, {'cluster': self.uri}):
            m = ClusterMember(model=self.model,
                              uri=str(member),
                              label=label,
                              type_=type_,
                              debug_info=self.debug_info.members[str(member)]['raw_object'])
            self.__members.append(m)
            for target in m.targets.keys():
                self.__targets[target] += 1
            for freebase in m.freebases.keys():
                self.__freebases[freebase] += 1

        query = '''
SELECT ?qnode ?qnodeLabel 
WHERE 
{
    ?qnode wdt:P1566 ?target .
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
} '''
        for target in self.__targets.keys():
            target_t = target[target.index(':')+1:]
            for qnode, qnodeLabel in wikidata_sparql.query(query, namespaces, {'target': Literal(target_t)}):
                url = str(qnode)
                qnode = url[url.rfind('/')+1:]
                self.__target_wiki[target] = {}
                self.__target_wiki[target]['qnode'] = qnode
                self.__target_wiki[target]['url'] = url
                self.__target_wiki[target]['label'] = str(qnodeLabel)

    def _init_qnodes(self):
        for fbid, count in self.freebases:
            if ":NIL" not in fbid:
                fbid = '/' + fbid.replace('.', '/')
                query = """
                    SELECT ?qid ?label WHERE {
                      ?qid wdt:P646 ?freebase .  
                      ?qid rdfs:label ?label filter (lang(?label) = "en") .
                    }
                    LIMIT 1
                """
                for qid, label in wikidata_sparql.query(query, namespaces, {'freebase': Literal(fbid)}):
                    qnodeURL = str(qid)
                    qid = qnodeURL.rsplit('/', 1)[1]
                    self.__qids[qid] = count
                    if qid not in self.__q_urls:
                        self.__q_urls[qid] = qnodeURL

    def _init_groundtruth(self):
        # query to find cluster of the missing member
        query = '''
            SELECT ?cluster 
            WHERE {
                %s
                ?membership aida:cluster ?cluster ;
                aida:clusterMember ?member .
                %s
            }
        ''' % (self.__open_clause, self.__close_clause)

        member_set = set([str(m.uri) for m in self.members])
        gt_set = set()
        for m in member_set:
            if self.model.graph:
                res = requests.get(groundtruth_url + '/' + self.model.repo + '?g=' + self.model.graph + '&e=' + m)
            else:
                res = requests.get(groundtruth_url + '/' + self.model.repo + '?e=' + m)
            if res.status_code == 404:
                self.__groundtruth = False
                return
            if len(res.json()) > 0:
                gt_set = set(res.json())
                break

        if len(gt_set) > 0:
            hit = member_set.intersection(gt_set)
            miss = member_set.difference(gt_set)
            missing = gt_set.difference(member_set)
            missing_dict = {}

            if missing:
                for m in missing:
                    for c, in self.model.sparql.query(query, namespaces, {'member': URIRef(m)}):
                        missing_dict[m] = str(c).replace('http://www.isi.edu/gaia/entities/', '')

            self.__groundtruth = Groundtruth(gt_set, hit, miss, missing_dict)

        else:
            self.__groundtruth = False

    def _init_debug_info(self):
        info = debug.get_debug_for_cluster(self.model.repo, self.model.graph, str(self.uri))
        if info:
            self.__debug_info = DebugInfo(info)
        else:
            self.__debug_info = False

    def _init_forward_clusters(self):
        query = """
SELECT ?p ?o ?cnt
WHERE {
    %s
  ?s aida:prototype ?proto1 .
  ?o aida:prototype ?proto2 .
  ?se rdf:subject ?proto1 ;
      rdf:predicate ?p ;
      rdf:object ?proto2 ;
      aida:confidence/aida:confidenceValue ?conf .
  BIND(ROUND(1/(2*(1-?conf))) as ?cnt)
  %s
} """ % (self.__open_clause, self.__close_clause)
        for p, o, cnt in self.model.sparql.query(query, namespaces, {'s': self.uri}):
            self.__forward.add(SuperEdge(self, Cluster(self.model, o), p, int(float(str(cnt)))))

    def _init_backward_clusters(self):
        query = """
SELECT ?s ?p ?cnt
WHERE {
    %s
  ?s aida:prototype ?proto1 .
  ?o aida:prototype ?proto2 .
  ?se rdf:subject ?proto1 ;
      rdf:predicate ?p ;
      rdf:object ?proto2 ;
      aida:confidence/aida:confidenceValue ?conf .
  BIND(ROUND(1/(2*(1-?conf))) as ?cnt)
    %s
} """ % (self.__open_clause, self.__close_clause)
        for s, p, cnt in self.model.sparql.query(query, namespaces, {'o': self.uri}):
            self.__backward.add(SuperEdge(Cluster(self.model, s), self, p, int(float(str(cnt)))))

    def _query_for_size(self):
        if self.uri in self.model.pickled and 'size' in self.model.pickled[self.uri]:
            return self.model.pickled[self.uri]['size']
        query = """
SELECT (COUNT(?member) AS ?size)
WHERE {
    %s
    ?membership aida:cluster ?cluster ;
                aida:clusterMember ?member .
    MINUS {?cluster aida:prototype ?member}
    %s
}  """ % (self.__open_clause, self.__close_clause)
        for size, in self.model.sparql.query(query, namespaces, {'cluster': self.uri}):
            return int(size)
        return 0

    def __hash__(self):
        return self.uri.__hash__()

    def __eq__(self, other):
        return isinstance(other, Cluster) and str(self.uri) == str(other.uri)


class SuperEdge:
    def __init__(self, s: Cluster, o: Cluster, p: URIRef, n: int):
        self.subject = s
        self.predicate = p
        self.object = o
        self.count = n

    def __hash__(self):
        return hash((self.subject.uri, self.predicate, self.object.uri))

    def __eq__(self, other):
        return isinstance(other, SuperEdge) and str(self.subject.uri) == str(other.subject.uri) and str(
            self.predicate) == str(other.predicate) and str(self.object.uri) == str(other.object.uri)


class ClusterMember:
    def __init__(self, model, uri, label=None, type_=None, debug_info=None):
        self.model = model
        self.uri = URIRef(uri)
        self.__id = None
        self.__label = label
        self.__all_labels = None
        self.__type = type_
        self.__targets = None
        self.__freebases = None
        self.__qids = None
        self.__q_labels = None
        self.__q_aliases = None
        self.__q_urls = None
        self.__source = None
        self.__context_pos = []
        self.__context_extractor = None
        self.__cluster: Cluster = None
        self.__debug_info = debug_info

        if model.graph:
            self.__open_clause = 'GRAPH <%s> {' % self.model.graph
            self.__close_clause = '}'
        else:
            self.__open_clause = self.__close_clause = ''

    @property
    def id(self):
        if not self.__id:
            self.__id = self.uri.replace('http://www.isi.edu/gaia/entities/', '').replace('http://www.columbia.edu/entities/', '')
        return self.__id

    @property
    def label(self):
        if not self.__label:
            self._init_member()
        return self.__label

    @property
    def all_labels(self):
        if not self.__all_labels:
            self.__all_labels = Counter()
            query = """
                SELECT ?label (COUNT(?label) AS ?n)
                WHERE {
                  ?member aida:justifiedBy/skos:prefLabel ?label .
                }
                GROUP BY ?label
                ORDER BY DESC(?n)
            """
            for label, n in self.model.sparql.query(query, namespaces, {'member': self.uri}):
                if label:
                    label = " ".join(label.split())  # remove double spaces
                    self.__all_labels[label] = int(n)

            query = """
                SELECT ?label (COUNT(?label) AS ?n)
                    WHERE {
                      ?member aida:hasName ?label .
                    }
                    GROUP BY ?label
                    ORDER BY DESC(?n)
                """
            for label, n in self.model.sparql.query(query, namespaces, {'member': self.uri}):
                if label:
                    label = " ".join(label.split())  # remove double spaces
                    if label in self.__all_labels:
                        self.__all_labels[label] += int(n)
                    else:
                        self.__all_labels[label] = int(n)

        return self.__all_labels.most_common()

    @property
    def type(self):
        if not self.__type:
            self._init_member()
        return self.__type

    @property
    def type_text(self):
        _, text = split_uri(self.type)
        return text

    @property
    def targets(self):
        if self.__targets is None:
            self._init_member()
        return self.__targets

    @property
    def freebases(self):
        if self.__freebases is None:
            self._init_member()
        return self.__freebases

    @property
    def qids(self):
        if self.__qids is None and self.freebases:
            self._init_qnode()
        return self.__qids

    @property
    def q_urls(self):
        if self.__qids is None and self.freebases:
            self._init_qnode()
        return self.__q_urls

    @property
    def q_labels(self):
        if self.__q_labels is None and self.freebases:
            self._init_qnode()
        return self.__q_labels

    @property
    def q_aliases(self):
        if self.__q_aliases is None and self.freebases:
            self._init_qnode()
        return self.__q_aliases

    def _init_qnode(self):
        self.__qids = {}  # qid to score
        self.__q_urls = {}
        self.__q_labels = {}
        self.__q_aliases = {}

        for fbid, score in self.freebases.items():
            if ":NIL" not in fbid:
                fbid = '/' + fbid[fbid.find(':')+1:].replace('.', '/')
                query = """
                    SELECT ?qid ?label WHERE {
                      ?qid wdt:P646 ?freebase .
                      ?qid rdfs:label ?label filter (lang(?label) = "en") .
                    }
                    LIMIT 1
                """
                for q_url, label in wikidata_sparql.query(query, namespaces, {'freebase': Literal(fbid)}):
                    qid = str(q_url).rsplit('/', 1)[1]
                    self.__qids[qid] = score
                    self.__q_urls[qid] = str(q_url)
                    self.__q_labels[qid] = str(label)

                query = """
                    SELECT ?qid ?alias WHERE {
                      ?qid wdt:P646 ?freebase .
                      ?qid skos:altLabel ?alias filter (lang(?alias) = "en") .
                    }
                """
                aliases = []
                qid = None
                for q_url, alias in wikidata_sparql.query(query, namespaces, {'freebase': Literal(fbid)}):
                    qid = str(q_url).rsplit('/', 1)[1]
                    aliases.append(str(alias))
                self.__q_aliases[qid] = ', '.join(aliases)

    @property
    def context_extractor(self):
        if self.__context_extractor is None:
            self.__context_extractor = LTFSourceContext(self.source)
        return self.__context_extractor

    @property
    def roles(self):
        query = """
        SELECT ?pred ?obj ?objtype (MIN(?objlbl) AS ?objlabel)
        WHERE {
            ?statement rdf:subject ?event ;
                       rdf:predicate ?pred ;
                       rdf:object ?obj .
            ?objstate rdf:subject ?obj ;
                      rdf:predicate rdf:type ;
                      rdf:object ?objtype .
            OPTIONAL { ?obj aida:hasName ?objlbl }
        }
        GROUP BY ?pred ?obj ?objtype
        """
        for pred, obj, obj_type, obj_lbl in self.model.sparql.query(query, namespaces, {'event': self.uri}):
            if not obj_lbl:
                _, obj_lbl = split_uri(obj_type)
            # _, pred = split_uri(pred)
            ind = pred.find('_')
            pred = pred[ind+1:]
            yield pred, ClusterMember(self.model, obj, obj_lbl, obj_type)

    @property
    def events_by_role(self):
      query = """
      SELECT ?pred ?event ?event_type (MIN(?lbl) AS ?label)
      WHERE {
          ?event a aida:Event .
          ?statement rdf:subject ?event ;
                    rdf:predicate ?pred ;
                    rdf:object ?obj .
          ?event_state rdf:subject ?event ;
                    rdf:predicate rdf:type ;
                    rdf:object ?event_type .
          OPTIONAL { ?event aida:justifiedBy/skos:prefLabel ?lbl }
      }
      GROUP BY ?pred ?event ?event_type
      """
      for pred, event, event_type, event_lbl in self.model.sparql.query(query, namespaces, {'obj': self.uri}):
          if not event_lbl:
              _, event_lbl = split_uri(event_type)
          ind = pred.find('_')
          pred = pred[ind+1:]
          yield pred, ClusterMember(self.model, event, event_lbl, event_type)

    @property
    def entity_relations(self):
        query = """
        SELECT ?relation ?pred2 ?obj2 ?relation_type (min(?lbl) as ?label)
        WHERE {
            ?relation a aida:Relation .
            ?s1 rdf:subject ?relation ;
                        rdf:predicate ?pred ;
                        rdf:object ?obj .
            ?s2 rdf:subject ?relation ;
                        rdf:predicate rdf:type ;
                        rdf:object ?relation_type .
            ?s3 rdf:subject ?relation ;
                        rdf:predicate ?pred2 ;
                        rdf:object ?obj2 .
            OPTIONAL {?obj2 aida:hasName ?lbl}
            filter(?s3 != ?s2 && ?s3 != ?s1)
        }
        groupby ?relation ?pred2 ?obj2 ?relation_type
          """
        for relation, pred, obj, relation_type, label in self.model.sparql.query(query, namespaces, {'obj': self.uri}):
            _, relation_type = split_uri(relation_type)
            ind = pred.find('_')
            pred = pred[ind + 1:]
            yield relation_type, obj, label

    @property
    def cluster(self):
        if self.__cluster is None:
            query = "SELECT ?cluster WHERE { %s ?membership aida:cluster ?cluster ; aida:clusterMember ?member . MINUS {?cluster aida:prototype ?member} %s}" % (self.__open_clause, self.__close_clause)
            for cluster, in self.model.sparql.query(query, namespaces, {'member': self.uri}):
                self.__cluster = self.model.get_cluster(cluster)
        return self.__cluster

    def _init_member(self):
        query = """
SELECT ?label ?type
WHERE {
  OPTIONAL { ?member aida:hasName ?label }
  OPTIONAL { ?member aida:justifiedBy ?justification .
    ?justification skos:prefLabel ?label }
  ?statement rdf:subject ?member ;
             rdf:predicate rdf:type ;
             rdf:object ?type .
}
LIMIT 1 """
        for label, type_ in self.model.sparql.query(query, namespaces, {'member': self.uri}):
            if not label:
                _, label = split_uri(type_)
            self.__label = label
            self.__type = type_

        self.__targets = {}
        if self.__debug_info:
            if self.__debug_info['targets']:
                for i in range(0, len(self.__debug_info['targets'])):
                    target = self.__debug_info['targets'][i]
                    score = self.__debug_info['target_scores'][i]
                    self.__targets[target] = score
        else:
            query = """
                SELECT ?target
                WHERE {
                  ?member aida:link/aida:linkTarget ?target 
                } """
            for target, in self.model.sparql.query(query, namespaces, {'member': self.uri}):
                self.__targets[str(target)] = 0

        self.__freebases = {}
        if self.__debug_info:
            if self.__debug_info['fbid']:
                for i in range(0, len(self.__debug_info['fbid'])):
                    fbid = self.__debug_info['fbid'][i]
                    score = self.__debug_info['fbid_score_avg'][i]
                    self.__freebases[fbid] = score
        else:
            query = """
                SELECT DISTINCT ?fbid {
                   ?member aida:privateData [
                        aida:jsonContent ?fbid ;
                        aida:system <http://www.rpi.edu/EDL_Freebase>
                    ]
                }
            """

            for j_fbid, in self.model.sparql.query(query, namespaces, {'member': self.uri}):
                fbids = json.loads(j_fbid).get('freebase_link').keys()
                for fbid in fbids:
                    self.__freebases[fbid] = 0

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
        for source, start, end in self.model.sparql.query(query, namespaces, {'member': self.uri}):
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


class Groundtruth:
    def __init__(self, members, hit, miss, missing):
        self.__members = members
        self.__hit = hit
        self.__miss = miss
        self.__missing = missing

    @property
    def members(self):
        return self.__members

    @property
    def members_count(self):
        return len(self.__members)

    @property
    def hit(self):
        return self.__hit

    @property
    def hit_count(self):
        return len(self.__hit)

    @property
    def miss(self):
        return self.__miss

    @property
    def miss_count(self):
        return len(self.__miss)

    @property
    def missing(self):
        return self.__missing

    @property
    def missing_count(self):
        return len(self.__missing)


class DebugInfo:
    def __init__(self, info):
        self.__info = info

    @property
    def members(self):
        return self.__info['all_records']

    def print_member(self, uri):
        m = self.members[uri]
        return json.dumps(m, indent=4, sort_keys=True, ensure_ascii=False)

    @property
    def attractives(self):
        return self.__info['attractive_records']

    @property
    def type(self):
        return self.__info['type']

    @property
    def selected_targets(self):
        return self.__info['kb_id']  # list of targets

    @property
    def selected_qnodes(self):
        return self.__info['wd_id']  # list of qnodes

    @property
    def target_statistics(self):
        return self.__info['kb_statistics']

    @property
    def qnode_statistics(self):
        return self.__info['wd_statistics']

