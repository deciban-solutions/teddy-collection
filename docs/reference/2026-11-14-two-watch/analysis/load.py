import json
S='<scratch>/twowatch'
K=json.load(open('/tmp/claude-1000/watch/scoring_keys.json'))
P=['brit','adrien','teddy','marco','james','andrew']
JUDGE={p:i+1 for i,p in enumerate(P)}
OCC={'black_tie':2,'suit':20,'biz_casual':150,'dinner':40,'weekend':100,'active':30,'swim':10,'scuba':0,'travel':12}
def load():
    out={}
    for s in (1,2,3):
        d=json.load(open(f'{S}/scoring/scorer{s}/scores.json'))
        pk=K[f'scorer{s}']; wk=K[f'scorer{s}_watches']
        out[s]={'pairs':{pk[c]:v for c,v in d['pairs'].items()},'watches':{wk[c]:v for c,v in d['watches'].items()}}
    return out
