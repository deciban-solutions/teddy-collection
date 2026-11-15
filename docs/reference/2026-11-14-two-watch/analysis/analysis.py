import json,itertools,random,statistics as st,sys
sys.path.insert(0,'.')
from load import load,P,JUDGE,OCC
from features import pair_features
D=load()
S3=(1,2,3)
def kt(x,y):
    # Kendall tau-b, x,y dict picker->value, higher=better for both
    c=d=tx=ty=0
    for a,b in itertools.combinations(P,2):
        dx=x[a]-x[b]; dy=y[a]-y[b]
        if dx==0 and dy==0: continue
        if dx==0: tx+=1; continue
        if dy==0: ty+=1; continue
        if dx*dy>0: c+=1
        else: d+=1
    den=((c+d+tx)*(c+d+ty))**0.5
    return (c-d)/den if den else 0.0
judge={p:7-JUDGE[p] for p in P}   # higher = better
crit={}
pc=['differentiation','coherence_expert','anchor_strength','tension_point','gap_test','wear_balance','makes_sense_together','beaten_path','daily_driver','sensible_spice','everyday_livability']
for c in pc: crit['S:'+c]={p:st.mean(D[s]['pairs'][p][c] for s in S3) for p in P}
crit['S:expert_rank(inv)']={p:7-st.mean(D[s]['pairs'][p]['expert_rank'] for s in S3) for p in P}
tot=sum(OCC.values())
def cov(p,s,occs=None):
    occs=occs or OCC
    w=D[s]['watches']
    num=sum(OCC[o]*max(w[p+'_A']['occasion_fit'][o],w[p+'_B']['occasion_fit'][o]) for o in occs)
    return num/(2*sum(OCC[o] for o in occs)) if sum(OCC[o] for o in occs) else 0
crit['C:coverage_weighted']={p:st.mean(cov(p,s) for s in S3) for p in P}
crit['C:coverage_unweighted']={p:st.mean(sum(max(D[s]['watches'][p+'_A']['occasion_fit'][o],D[s]['watches'][p+'_B']['occasion_fit'][o]) for o in OCC if o!='scuba')/16 for s in S3) for p in P}
crit['C:n_occasions_fully_covered']={p:st.mean(sum(1 for o in OCC if o!='scuba' and max(D[s]['watches'][p+'_A']['occasion_fit'][o],D[s]['watches'][p+'_B']['occasion_fit'][o])==2) for s in S3) for p in P}
wc=['robustness','wearability','useful_complications','practicality','horological_merit','design_integrity','value']
for c in wc:
    crit['W:min_'+c]={p:st.mean(min(D[s]['watches'][p+'_A'][c],D[s]['watches'][p+'_B'][c]) for s in S3) for p in P}
    crit['W:sum_'+c]={p:st.mean(D[s]['watches'][p+'_A'][c]+D[s]['watches'][p+'_B'][c] for s in S3) for p in P}
crit['W:register_gap']={p:st.mean(abs(D[s]['watches'][p+'_A']['register']-D[s]['watches'][p+'_B']['register']) for s in S3) for p in P}
crit['W:min_register(sportiest)']={p:-st.mean(min(D[s]['watches'][p+'_A']['register'],D[s]['watches'][p+'_B']['register']) for s in S3) for p in P}
crit['W:max_register(dressiest)']={p:st.mean(max(D[s]['watches'][p+'_A']['register'],D[s]['watches'][p+'_B']['register']) for s in S3) for p in P}
F={p:pair_features(p) for p in P}
for f in F['brit']:
    crit['F:'+f]={p:F[p][f] for p in P}
    crit['F:-'+f]={p:-F[p][f] for p in P}
# --- single-criterion fit
single=sorted(((kt(v,judge),k) for k,v in crit.items()),reverse=True)
# --- exact reproduction: lexicographic, up to 3 criteria
def strict_order_ok(keys):
    vals={p:tuple(round(crit[k][p],6) for k in keys) for p in P}
    order=sorted(P,key=lambda p:vals[p],reverse=True)
    if len(set(vals.values()))<6: return False
    return order==P
pool=[k for k in crit if not k.startswith('F:-') or True]
lex={1:[],2:[],3:[]}
for r in (1,2,3):
    for combo in itertools.permutations(pool,r):
        # skip using a criterion and its negation together
        base=[c.replace('F:-','F:') for c in combo]
        if len(set(base))<r: continue
        if strict_order_ok(combo): lex[r].append(combo)
# lexicographic minimality: keep combos whose prefix alone doesn't already work
def minimal(lst):
    s=set(lst); return [c for c in lst if not any(c[:i] in s for i in range(1,len(c)))]
# --- weighted linear: z-score each criterion, sample Dirichlet weights for subsets of 2 and 3
def z(v):
    m=st.mean(v.values()); sd=st.pstdev(v.values()) or 1
    return {p:(v[p]-m)/sd for p in P}
Z={k:z(v) for k,v in crit.items()}
rnd=random.Random(7)
def lin_frac(keys,n=400):
    ok=0
    for _ in range(n):
        w=[rnd.gammavariate(1,1) for _ in keys]
        sc={p:sum(wi*Z[k][p] for wi,k in zip(w,keys)) for p in P}
        if len(set(round(v,9) for v in sc.values()))<6: continue
        order=sorted(P,key=lambda p:sc[p],reverse=True)
        ok+= order==P
    return ok/n
cand=[k for _,k in single[:40]]
lin2=[]
for a,b in itertools.combinations(cand,2):
    if a.replace('F:-','F:')==b.replace('F:-','F:'): continue
    f=lin_frac((a,b)); 
    if f>0: lin2.append((f,a,b))
lin2.sort(reverse=True)
# --- null baseline: how often do random 1-5 integer criteria reproduce exact order lexicographically with r=1..3 from a pool of same size?
def null_rate(npool=len(pool),trials=60):
    hits={1:0,2:0,3:0}
    for t in range(trials):
        R={i:{p:rnd.randint(1,5) for p in P} for i in range(40)}
        found={1:False,2:False,3:False}
        for r in (1,2,3):
            for combo in itertools.permutations(range(40),r):
                vals={p:tuple(R[i][p] for i in combo) for p in P}
                if len(set(vals.values()))==6 and sorted(P,key=lambda p:vals[p],reverse=True)==P: found[r]=True; break
        for r in found: hits[r]+=found[r]
    return {r:hits[r]/trials for r in hits}
res=dict(single=single,lex={r:minimal(v) for r,v in lex.items()},lin2=lin2[:30],crit=crit)
json.dump(res,open('results.json','w'),indent=1,default=list)
print('== single-criterion Kendall tau-b vs judges (top 25)')
for t,k in single[:25]: print(f'{t:+.2f}  {k}   ', ' '.join(f'{p[:3]}={crit[k][p]:.2f}' for p in P))
print('== bottom 8'); 
for t,k in single[-8:]: print(f'{t:+.2f}  {k}')
for r in (1,2,3): print(f'== exact lexicographic rules, length {r}: {len(minimal(lex[r]))} minimal'); [print('  ',c) for c in minimal(lex[r])[:25]]
print('== weighted 2-criterion combos reproducing exact order (fraction of random weightings)')
for f,a,b in lin2[:20]: print(f'  {f:.2f} {a} + {b}')
print('pool size',len(pool))
import collections
nr=null_rate(trials=40)
print('== null: P(at least one exact lexicographic rule of length r exists among 40 random 1-5 criteria):',nr)

