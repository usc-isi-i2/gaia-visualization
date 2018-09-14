from flask import Flask, render_template, abort
from model import get_cluster, get_cluster_list, types
from report import Report

app = Flask(__name__, static_folder='static')


@app.route('/')
def hello_world():
    return render_template('index.html',
                           entities=get_cluster_list(types.Entity),
                           events=get_cluster_list(types.Events))


@app.route('/js/<path>')
def static_js(path):
    return app.send_static_file('js/'+path)


@app.route('/img/<path>')
def static_img(path):
    return app.send_static_file('img/'+path)


@app.route('/css/<path>')
def static_css(path):
    return app.send_static_file('css/'+path)


@app.route('/viz/<name>')
def show_bidirection_viz(name):
    return render_template('viz.html', name=name)


@app.route('/sviz/<name>')
def show_viz(name):
    return render_template('sviz.html', name=name)


@app.route('/cluster/entities/<uri>')
@app.route('/entities/<uri>')
def show_entity_cluster(uri):
    uri = 'http://www.isi.edu/gaia/entities/' + uri
    return show_cluster(uri)


@app.route('/cluster/events/<uri>')
@app.route('/events/<uri>')
def show_event_cluster(uri):
    uri = 'http://www.isi.edu/gaia/events/' + uri
    return show_cluster(uri)


def show_cluster(uri):
    cluster = get_cluster(uri)
    if not cluster:
        abort(404)
    return render_template('cluster.html', cluster=cluster)


@app.route('/report')
def show_report():
    report = Report()
    return render_template('report.html', report=report)


if __name__ == '__main__':
    # app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    app.debug = True
    app.run(host='0.0.0.0', port=5005)
