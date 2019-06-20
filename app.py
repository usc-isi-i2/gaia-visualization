import os
from flask import Flask, render_template, abort, request, jsonify
# from model import get_cluster, get_cluster_list, types, recover_doc_online
from model import Model, types
# from setting import repo, port, repositories, upload_folder, import_endpoint
import setting
from setting import url_prefix
import groundtruth as gt
import debug
from importer import clusters_import
import requests
from rdflib.plugins.stores.sparqlstore import SPARQLStore
import tmp
import time_person_label


app = Flask(__name__, static_folder='static')
app.jinja_env.globals.update(str=str)  # allow str function to be used in template
app.jinja_env.globals.update(round=round)  # allow round function to be used in template
app.config['JSON_AS_ASCII'] = True


def generate_pkl(sparql, graph, file_path):
    tmp.run(sparql, graph, file_path)
    time_person_label.run(sparql, graph, file_path)


@app.route('/')
def index():
    repos = {}
    for repo in setting.repositories:
        repos[repo] = []
        endpoint = setting.endpoint + '/' + repo + '/rdf-graphs'
        res = requests.get(endpoint, headers={'Accept': 'application/sparql-results+json'},
                           auth=(setting.username, setting.password))
        result = res.json()['results']['bindings']
        for r in result:
            repos[repo].append(r['contextID']['value'])
    return render_template('index.html',
                           url_prefix=url_prefix,
                           repos=repos)


@app.route('/repo/<repo>')
def hello_world(repo):
    graph_uri = request.args.get('g', '')
    sparql = SPARQLStore(setting.endpoint + '/' + repo)
    model = Model(sparql, repo, graph_uri)
    return render_template('clusters.html',
                           url_prefix=url_prefix,
                           repo=repo,
                           graph=graph_uri,
                           entities=model.get_cluster_list(types.Entity),
                           events=model.get_cluster_list(types.Events))


@app.route('/js/<path>')
def static_js(path):
    return app.send_static_file('js/' + path)


@app.route('/img/<path>')
def static_img(path):
    return app.send_static_file('img/' + path)


@app.route('/css/<path>')
def static_css(path):
    return app.send_static_file('css/' + path)


@app.route('/viz/<name>')
def show_bidirection_viz(name):
    return render_template('viz.html', url_prefix=url_prefix, name=name)


@app.route('/sviz/<name>')
def show_viz(name):
    return render_template('sviz.html', url_prefix=url_prefix, name=name)


@app.route('/cluster/entities/<repo>/<uri>')
@app.route('/entities/<repo>/<uri>')
def show_entity_cluster(repo, uri):
    i = uri.find('?')
    if i > 0:
        uri = uri[:i]
    uri = 'http://www.isi.edu/gaia/entities/' + uri
    graph_uri = request.args.get('g', default=None)
    show_image = request.args.get('image', default=True)
    show_limit = request.args.get('limit', default=100)
    sparql = SPARQLStore(setting.endpoint + '/' + repo)
    model = Model(sparql, repo, graph_uri)
    return show_cluster(model, uri, show_image, show_limit)


@app.route('/list/<type_>/<repo>')
def show_entity_cluster_list(type_, repo):
    graph_uri = request.args.get('g', default=None)
    limit = request.args.get('limit', default=100, type=int)
    offset = request.args.get('offset', default=0, type=int)
    sortby = request.args.get('sortby', default='size')
    sparql = SPARQLStore(setting.endpoint + '/' + repo)
    model = Model(sparql, repo, graph_uri)
    if type_ == 'entity':
        return render_template('list.html',
                               url_prefix=url_prefix,
                               type_='entity',
                               repo=repo,
                               graph=graph_uri,
                               limit=limit,
                               offset=offset,
                               sortby=sortby,
                               clusters=model.get_cluster_list(types.Entity, limit, offset, sortby))
    elif type_ == 'event':
        return render_template('list.html',
                               url_prefix=url_prefix,
                               type_='event',
                               repo=repo,
                               graph=graph_uri,
                               limit=limit,
                               offset=offset,
                               sortby=sortby,
                               clusters=model.get_cluster_list(types.Events, limit, offset, sortby))
    else:
        abort(404)


@app.route('/cluster/events/<repo>/<uri>')
@app.route('/events/<repo>/<uri>')
def show_event_cluster(repo, uri):
    uri = 'http://www.isi.edu/gaia/events/' + uri
    graph_uri = request.args.get('g', default=None)
    show_image = request.args.get('image', default=True)
    show_limit = request.args.get('limit', default=100)
    sparql = SPARQLStore(setting.endpoint + '/' + repo)
    model = Model(sparql, repo, graph_uri)
    return show_cluster(model, uri, show_image, show_limit)


@app.route('/cluster/<repo>/AIDA/<path:uri>')
def show_columbia_cluster(repo, uri):
    graph_uri = request.args.get('g', default=None)
    uri = 'http://www.columbia.edu/AIDA/' + uri
    show_image = request.args.get('image', default=True)
    show_limit = request.args.get('limit', default=100)
    sparql = SPARQLStore(setting.endpoint + '/' + repo)
    model = Model(sparql, repo, graph_uri)
    return show_cluster(model, uri, show_image, show_limit)


def show_cluster(model: Model, uri, show_image=True, show_limit=100):
    cluster = model.get_cluster(uri)
    show_image = show_image not in {False, 'False', 'false', 'no', '0'}
    show_limit = show_limit not in {False, 'False', 'false', 'no', '0'} and (
            isinstance(show_limit, int) and show_limit) or (show_limit.isdigit() and int(show_limit))
    if not cluster:
        abort(404)
    print(cluster.href)
    return render_template('cluster.html',
                           url_prefix=url_prefix,
                           repo=model.repo,
                           graph=model.graph,
                           cluster=cluster,
                           show_image=show_image,
                           show_limit=show_limit)


@app.route('/report')
def show_report():
    update = request.args.get('update', default=False, type=bool)
    report = Report(update)
    return render_template('report.html', url_prefix=url_prefix, report=report)


@app.route('/doc/<doc_id>')
def show_doc_pronoun(doc_id):
    return render_template('doc.html', url_prefix=url_prefix, doc_id=doc_id, content=recover_doc_online(doc_id))


@app.route('/cluster/entities/gt/<repo>')
def show_entity_gt(repo):
    uri = request.args.get('e', default=None)
    graph_uri = request.args.get('g', default=None)
    sparql = SPARQLStore(setting.endpoint + '/' + repo)
    model = Model(sparql, repo, graph_uri)
    cluster = model.get_cluster(uri)
    return render_template('groundtruth.html', url_prefix=url_prefix, repo=repo, graph=graph_uri, cluster=cluster)


@app.route('/cluster/import')
def show_import():
    return render_template('importer.html', url_prefix=url_prefix, repos=setting.repositories)


@app.route('/import', methods=['POST'])
def import_clusters():
    repo = request.form['repo']
    graph_uri = request.form['graph_uri']
    entity_file = request.files['entity_file']
    event_file = request.files['event_file']

    if repo and graph_uri and entity_file and event_file:

        # create directory for upload
        data_dir = setting.store_data + '/' + repo
        if not os.path.isdir(data_dir):
            os.makedirs(data_dir)

        # upload file
        filename = 'entity-clusters.jl'
        file = os.path.join(data_dir, filename)
        entity_file.save(file)

        filename = 'event-clusters.jl'
        file = os.path.join(data_dir, filename)
        event_file.save(file)

        # to triple store
        res = clusters_import.create_clusters(setting.endpoint, repo, graph_uri)

        if res == 'success':
            return '''
            <!doctype html>
            <title>Imported</title>
            <h1>Imported</h1>
            '''
        else:
            return '''
            <!doctype html>
            <title>Import Failed</title>
            <h1>Import Failed</h1>
            <h2>%s<h2>
            ''' % res

    else:
        return '''
        <!doctype html>
        <title>Invalid</title>
        <h1>Invalid</h1>
        '''


@app.route('/groundtruth/<repo>', methods=['GET'])
def groundtruth(repo):
    graph = request.args.get('g', default=None)
    entity_uri = request.args.get('e', default=None)
    if entity_uri:
        if gt.has_gt(repo, graph):
            print("has gt")
            gt_cluster = gt.search_cluster(repo, graph, entity_uri)
            return jsonify(gt_cluster)
        else:
            print("no gt")
            return not_found()
    else:
        return jsonify(gt.get_all())


@app.route('/cluster/entities/debug/<repo>', methods=['GET'])
def debugger(repo):
    graph = request.args.get('g', default=None)
    cluster_uri = request.args.get('cluster')
    if cluster_uri:
        result = debug.get_debug_for_cluster(repo, graph, cluster_uri)
    else:
        return not_found()

    if result:
        return jsonify(result)
    else:
        return not_found()


@app.errorhandler(404)
def not_found(error=None):
    message = {
        'status': 404,
        'message': 'Not Found: ' + request.url,
    }
    resp = jsonify(message)
    resp.status_code = 404

    return resp


if __name__ == '__main__':
    # app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.debug = True
    app.run(host='0.0.0.0', port=setting.port)
