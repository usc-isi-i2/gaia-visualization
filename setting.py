repo = 'gaia0404ta1-testing'
gt_file = 'groundtruth.jl'
# debug_file = 'gaia0404ta1-test.jl'
port = '5050'

endpoint = 'http://gaiadev01.isi.edu:7200/repositories'
endpoint_repo = endpoint + '/' + repo
named_graph = 'http://www.isi.edu/clusters1'
wikidata_endpoint = "http://sitaware.isi.edu:8080/bigdata/namespace/wdq/sparql"
# wikidata_endpoint = 'https://query.wikidata.org/bigdata/namespace/wdq/sparql'
groundtruth_url = 'http://gaiadev01.isi.edu:' + port + '/groundtruth'
debug_url = 'http://gaiadev01.isi.edu:' + port + '/cluster/entity/debug'

# for importing clusters
import_endpoint = 'http://gaiadev01.isi.edu:7200/repositories'
repositories = ['gaia0304ta1-test', 'gaia0404ta1-test', 'gaia0404ta1-testing']
# upload_folder = '/nas/home/jchen/gaia-visual-uploads'
upload_folder = '/Users/jenniferchen/Documents/AIDA/clusters_upload'

username = 'admin'
password = 'gaia@isi'

