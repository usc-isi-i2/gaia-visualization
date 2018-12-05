import json
from collections import Counter

with open('entity_with_attr.jl') as f:
    objs = json.load(f)

for obj in objs:
    cluster = obj['entities']
    for e in cluster:
        if e[0] and e[0][0] == '{':
            e[0] = json.loads(e[0])['translation'][0]

for obj in objs:
    cluster = obj['entities']
    print('Cluster size: ', len(cluster))
    print('Cluster type: ', cluster[0][1])

    for link in {e[2] for e in cluster if e[2].startswith('LDC2015E42:m')}:
        print(link)
        for w, n in Counter([e[0] for e in cluster if e[2] == link]).most_common():
            print('  {}: {}'.format(w, n))
    print('others')
    for w, n in Counter([e[0] for e in cluster if not e[2].startswith('LDC2015E42:m')]).most_common():
        print('  {}: {}'.format(w, n))
    print('\n\n\n')
    print('===========================================')
