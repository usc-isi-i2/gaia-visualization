from model import namespaces
from setting import repo
import json


def count_query(sparql, query):
    for count, in sparql.query(query, namespaces):
        return int(count)


class ReportMemory(dict):
    file = 'report.json'

    def __init__(self, update=False):
        super().__init__()
        if not update:
            try:
                self.update(json.load(open(self.file)))
            except FileNotFoundError:
                pass

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        json.dump(self, open(self.file, 'w'))


class Report:
    name = repo

    def __init__(self, update=False):
        self.mem = ReportMemory(update)

    @staticmethod
    def __num_of_entities(type_):
        query = '''
        SELECT (COUNT(?e) AS ?eN)
        WHERE {
          ?e a ?type .
          FILTER NOT EXISTS { ?cluster aida:prototype ?e }
        } '''.replace('?type', type_)
        return count_query(query)

    @property
    def num_of_entities(self):
        name = 'num_of_entities'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities('aida:Entity')
        return self.mem[name]

    @property
    def num_of_events(self):
        name = 'num_of_events'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities('aida:Event')
        return self.mem[name]

    @property
    def num_of_relations(self):
        name = 'num_of_relation'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities('aida:Relation')
        return self.mem[name]

    @property
    def total_cluster(self):
        query = '''
        SELECT (COUNT(?c) AS ?cN)
        WHERE {
          ?c a aida:SameAsCluster .
        } '''
        return count_query(query)

    @property
    def map_of_entity_types(self):
        name = 'map_of_entity_types'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities_by_type('aida:Entity')
        return self.mem[name]

    @property
    def map_of_event_types(self):
        name = 'map_of_event_types'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities_by_type('aida:Event')
        return self.mem[name]

    @property
    def map_of_relation_types(self):
        name = 'map_of_relation_type'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities_by_type('aida:Relation')
        return self.mem[name]

    @staticmethod
    def __num_of_entities_by_type(sparql, type_, cluster=False):
        filter_ = '?cluster aida:prototype ?e' if cluster else 'FILTER NOT EXISTS { ?cluster aida:prototype ?e }'
        query = '''
        SELECT ?cate (COUNT(?e) AS ?eN)
        WHERE {
          ?e a ?type .
          ?s rdf:subject ?e ;
             rdf:predicate rdf:type ;
             rdf:object ?cate .
          filter
        }
        GROUP BY ?cate
        '''.replace('?type', type_).replace('filter', filter_)
        d = {}
        for cate, count in sparql.query(query, namespaces):
            cate = cate.replace('https://tac.nist.gov/tracks/SM-KBP/2018/ontologies/SeedlingOntology#', '')
            d[cate] = int(count)
        return d

    @property
    def num_of_entity_clusters(self):
        name = 'num_of_entity_clusters'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entity_clusters('aida:Entity')
        return self.mem[name]

    @property
    def num_of_event_clusters(self):
        name = 'num_of_event_clusters'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entity_clusters('aida:Event')
        return self.mem[name]

    @property
    def num_of_relation_clusters(self):
        name = 'num_of_relation_clusters'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entity_clusters('aida:Relation')
        return self.mem[name]

    @staticmethod
    def __num_of_entity_clusters(type_):
        query = '''
        SELECT (COUNT(?c) AS ?cN)
        WHERE {
          ?c aida:prototype ?p .
          ?p a ?type .
        } '''.replace('?type', type_)
        return count_query(query)

    @property
    def map_of_entity_cluster_types(self):
        name = 'map_of_entity_cluster_types'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities_by_type('aida:Entity', True)
        return self.mem[name]

    @property
    def map_of_event_cluster_types(self):
        name = 'map_of_event_cluster_types'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities_by_type('aida:Event', True)
        return self.mem[name]

    @property
    def map_of_relation_cluster_types(self):
        name = 'map_of_relation_cluster_types'
        if name not in self.mem:
            self.mem[name] = self.__num_of_entities_by_type('aida:Relation', True)
        return self.mem[name]

    @property
    def num_of_self_connect_entity(self):
        query = '''
        PREFIX aida: <https://tac.nist.gov/tracks/SM-KBP/2018/ontologies/InterchangeOntology#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

        SELECT ?relation ?entity
        WHERE {
          ?cr aida:prototype ?relation .
          ?relation a aida:Relation .
          ?ce aida:prototype ?entity .
          ?s1 rdf:subject ?relation ;
              rdf:object ?entity .
          ?s2 rdf:subject ?relation ;
              rdf:object ?entity .
          ?s3 rdf:subject ?relation ;
              rdf:predicate rdf:type ;
              rdf:object ?rp .
          FILTER(?s1!=?s2)
        }
        '''
        pass
