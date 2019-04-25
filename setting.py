port = '5000'
endpoint = 'http://gaiadev01.isi.edu:7200/repositories'
# wikidata_endpoint = "http://sitaware.isi.edu:8080/bigdata/namespace/wdq/sparql"
wikidata_endpoint = 'https://query.wikidata.org/sparql'
store_data = 'store_data'
repositories = ['gaia0304ta1-test', 'gaia0404ta1-test', 'gaia0404ta1-testing', 'jchen-test']
username = 'admin'
password = 'gaia@isi'

# deploy
# groundtruth_url = 'http://gaiadev01.isi.edu:' + port + '/groundtruth'

# testing
groundtruth_url = 'http://127.0.0.1:' + port + '/groundtruth'

