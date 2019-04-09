repo = 'gaia0404ta1-test'
gt_file = 'groundtruth.jl'
debug_file = 'clusters-debug-gaia0404.jl'
port = '5055'

endpoint = 'http://gaiadev01.isi.edu:7200/repositories/' + repo
wikidata_endpoint = "http://sitaware.isi.edu:8080/bigdata/namespace/wdq/sparql"
groundtruth_url = 'http://gaiadev01.isi.edu:' + port + '/groundtruth'
debug_url = 'http://gaiadev01.isi.edu:' + port + '/cluster/entity/debug'
