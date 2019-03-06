from rdflib.namespace import split_uri
from typing import List
from model import SuperEdge, get_cluster, AIDA
import uuid
import subprocess
import pickle

SVG = 'SVG'
PNG = 'PNG'
clusters = pickle.load(open('cluster.pkl', 'rb'))


class Graph:
    def __init__(self, name=None):
        self.nodes = []
        self.edges = []
        self.name = name if name else uuid.uuid4().hex

    @staticmethod
    def generate(node_strings, edge_strings):
        dot = [
            'digraph G {',
            '  node[style="filled"]',
        ]
        dot.extend(node_strings)
        dot.extend(edge_strings)
        dot.append('}')
        return '\n'.join(dot)

    def to_draw(self):
        node_strings = [x.to_draw() for x in self.nodes]
        edge_string = [x.to_draw() for x in self.edges]
        return self.generate(node_strings, edge_string)

    def dot(self, format=SVG, path='static/img/'):
        prefix = path + self.name
        dotpath = prefix + '.dot'
        with open(dotpath, 'w') as f:
            f.write(self.to_draw())
        imgpath = prefix+'.'+format.lower()
        e = subprocess.call(
            ['dot', '-T' + format.lower(), '-o', imgpath, dotpath, '-Ksfdp', '-Goverlap=prism', '-Goverlap_scaling=5',
             '-Gsep=+20'])
        print(e)
        return imgpath


class Element:
    def __init__(self, id_, config=None):
        self.id = id_
        self.config = config if config else dict()

    def update(self, new_config):
        self.config.update(new_config)

    def to_draw(self):
        if self.config:
            config = ' '.join(['{}="{}"'.format(k, v) for k, v in self.config.items()])
            return '{} [{}]'.format(self.id, config)
        return self.id

    def set_color(self, color):
        self.config['color'] = color

    @staticmethod
    def text_justify(words, max_width):
        words = words.split()
        res, cur, num_of_letters = [], [], 0
        max_ = 0
        for w in words:
            if num_of_letters + len(w) + len(cur) > max_width:
                res.append(' '.join(cur))
                max_ = max(max_, num_of_letters)
                cur, num_of_letters = [], 0
            cur.append(w)
            num_of_letters += len(w)
        return res + [' '.join(cur).center(max_)]

    def __hash__(self):
        return self.id.__hash__()

    def __eq__(self, other):
        return isinstance(other, Element) and self.id == other.id

    def __repr__(self):
        return self.id


class Node(Element):
    def __init__(self, id_, config):
        super().__init__('"{}"'.format(id_), config)

    def set_color(self, color):
        super().set_color(color)
        self.config['fillcolor'] = color


class Edge(Element):
    def __init__(self, from_, to, config):
        if isinstance(from_, Node):
            from_ = from_.id
        if isinstance(to, Node):
            to = to.id
        id_ = '"{}" -> "{}"'.format(from_, to)
        super().__init__(id_, config)


type_color_map = {
    # Entity
    'Facility': '#7f7f7f',
    'GeopoliticalEntity': '#e377c2',
    'Location': '#8c564b',
    'Organization': '#9467bd',
    'Person': '#1f77b4',
    'FillerType': '#ff7f0e',
    # Event
    'Relation': '#ff7f0e'
}


class ClusterNode(Node):
    def __init__(self, uri, count, label=None, config=None, type_=None):
        super().__init__(uri, config)
        if type_:
            self.set_color(type_)
        if label:
            self.config['label'] = self.node_label_justify(label, count)
        else:
            self.config['label'] = ''

    def set_color(self, type_):
        if isinstance(type_, str) and type_.startswith('http'):
            _, type_ = split_uri(type_)
        color = type_color_map.get(type_, '#17becf')
        super().set_color(color)

    def node_label_justify(self, label, count, max_width=20):
        words = label + " (×{})".format(count)
        return "\\n".join(self.text_justify(words, max_width))


class ClusterEdge(Edge):
    def __init__(self, sub, obj, pred, count, config=None):
        super().__init__(sub, obj, config)
        if pred and pred.startswith('http'):
            ind = pred.find('_')
            pred = pred[ind+1:]
            # _, pred = split_uri(pred)
        self.pred = pred
        self.config['label'] = self.edge_label_justify(pred, count)
        # self.config['label'] = pred
        self.set_color('#d62728')
        self.config['arrowsize'] = '0.7'

    def edge_label_justify(self, label, count, max_width=20):
        words = label + " (×{})".format(count)
        return "\\n".join(self.text_justify(words, max_width))

    def __hash__(self):
        return hash((self.id, self.pred))

    def __eq__(self, other):
        return isinstance(other, ClusterEdge) and self.id == other.id and self.pred == other.pred


class ClusterGraph(Graph):
    def __init__(self, clusters: List[ClusterNode], super_edges: List[ClusterEdge], name=None):
        super().__init__(name=name)
        self.nodes = clusters
        self.edges = super_edges


class SuperEdgeBasedGraph(ClusterGraph):
    def __init__(self, superedges: List[SuperEdge], base=None, name=None):
        nodes = {base} if base else set()
        edges = set()
        for se in superedges:
            sub, obj, pred = se.subject, se.object, se.predicate
            nodes.add(sub)
            nodes.add(obj)
            edges.add(ClusterEdge(sub.uri, obj.uri, pred, se.count))
        if isinstance(name, str) and name.startswith('http'):
            _, name = split_uri(name)
        # super().__init__([self._cluster_node_from_cluster(c) for c in nodes], edges, name)
        super().__init__([self._cluster_node_from_pickle(c.uri) for c in nodes], edges, name)

    @staticmethod
    def _cluster_node_from_cluster(cluster):
        return ClusterNode(cluster.uri, cluster.size, cluster.label, type_=cluster.prototype.type)

    @staticmethod
    def _cluster_node_from_pickle(uri):
        try:
            c = clusters[str(uri)]
            if c['type'] != AIDA.Relation:
                return ClusterNode(uri, c['size'], c['label'], type_=c['type'])
            else:
                return ClusterNode(uri, c['size'], '', type_=c['type'])
        except KeyError:
            print("Failed to hit the cluster cache with uri: ", uri)
            return SuperEdgeBasedGraph._cluster_node_from_cluster(get_cluster(uri))



if __name__ == '__main__':
    cluster = get_cluster('http://www.isi.edu/gaia/entities/4242167c-60ee-4ea5-9efa-105d41ce8306-cluster')
    # cluster = get_cluster('http://www.isi.edu/gaia/assertions/bdc5d9d1-5167-4d93-b2c1-d0b3e62bf12c-cluster')
    neighborhood = cluster.neighborhood()
    graph = SuperEdgeBasedGraph(neighborhood, cluster, cluster.uri)
    dot_string = graph.dot()
