import json
K=["black_tie","suit","biz_casual","dinner","weekend","active","swim","scuba","travel"]
def w(r,rb,wr,uc,p,hm,di,v,occ):
    return dict(register=r,robustness=rb,wearability=wr,useful_complications=uc,practicality=p,horological_merit=hm,design_integrity=di,value=v,occasion_fit=dict(zip(K,occ)))
W={
"PAIR-U-1":w(2,4,3,4,4,3,4,3,[0,1,2,1,2,2,1,0,1]),
"PAIR-U-2":w(3,4,5,3,5,4,4,4,[1,2,2,2,2,1,2,0,1]),
"PAIR-V-1":w(3,2,2,3,2,3,3,2,[1,2,2,2,1,0,0,0,1]),
"PAIR-V-2":w(3,4,5,3,5,5,4,4,[1,2,2,2,2,1,1,0,1]),
"PAIR-W-1":w(3,4,4,3,5,5,4,4,[1,2,2,2,2,1,1,0,1]),
"PAIR-W-2":w(2,5,4,3,4,4,4,3,[0,1,2,1,2,2,2,0,1]),
"PAIR-X-1":w(4,2,3,3,3,5,3,3,[1,2,2,2,1,0,0,0,1]),
"PAIR-X-2":w(3,4,4,3,5,5,4,4,[1,2,2,2,2,1,1,0,1]),
"PAIR-Y-1":w(2,3,4,3,3,4,5,4,[0,1,2,1,2,2,1,0,1]),
"PAIR-Y-2":w(5,2,2,2,3,5,4,2,[2,2,1,2,0,0,0,0,0]),
"PAIR-Z-1":w(1,5,5,3,4,2,5,4,[0,0,1,1,2,2,2,0,1]),
"PAIR-Z-2":w(4,2,4,5,4,4,5,5,[2,2,2,2,1,0,0,0,2]),
}
PK=["differentiation","coherence_expert","anchor_strength","tension_point","gap_test","wear_balance","makes_sense_together","beaten_path","daily_driver","sensible_spice","everyday_livability","expert_rank"]
def p(vals,rat): d=dict(zip(PK,vals)); d["rationale"]=rat; return d
P={
"PAIR-U":p([3,3,5,2,2,3,4,5,5,3,5,3],"Two steel-bracelet sport watches: a blue pilot chronograph and a 38 mm Aqua Terra. The Aqua Terra alone covers nearly every wear-day, including suit and swim, so the IWC is mostly a weekend alternative with a useful chronograph. Highly conventional and very livable, but somewhat redundant and with no dress or travel (GMT) coverage."),
"PAIR-V":p([4,2,5,3,2,2,3,3,5,3,4,5],"The 37 mm Lake Suwa is an excellent all-rounder and anchors the pair alone. The thick 42 mm copper triple-calendar chronograph on alligator is a dressy-ish occasional piece whose calendar needs resetting and which the GS already out-dresses in most settings. Weak collection logic and limited gap: the Breitling's niche is thin."),
"PAIR-W":p([3,4,5,3,3,3,4,4,5,3,5,2],"A Spring Drive White Birch for office and dinner plus a 200 m SeaQ diver for weekends, activity and water. Shared values of quiet craftsmanship, with a Japan/Germany contrast. Both are ~40 mm steel bracelets, so differentiation is moderate, and neither covers black tie or travel as well as a GMT/dress option would, but daily livability is excellent."),
"PAIR-X":p([3,4,5,4,2,3,3,2,5,2,4,4],"An enthusiast's horology pair: the asymmetric PanoMaticInverse on blue alligator and the Hi-Beat White Birch. Coherent in mechanical interest, but both have pale silver/white dials and sit in a similar dressy-to-versatile register; nothing sporty or water-ready besides the GS. The GS carries almost all days, so the GO is a showpiece rather than an indispensable second watch."),
"PAIR-Y":p([5,3,3,4,4,2,3,1,3,4,2,6],"Maximal contrast: a 38 mm hand-wound vintage-styled Gallet chronograph on fabric and a 44 mm Armor Gold perpetual calendar on alligator. The gold perpetual suits only formal days for this wearer and is large and delicate, while the Gallet has no date and needs winding, so neither is a true grab-and-go daily anchor. Interesting, but the poorest fit to a 'serve me every day' brief."),
"PAIR-Z":p([5,4,3,5,5,5,5,4,4,5,4,1],"A clear tool/dress split: the slim 39 mm Doxa diver on beads-of-rice for weekends, activity and water, and a cream Elegance GMT on crocodile for office, suits, dinners, black tie and travel. Each owns a distinct set of days with almost no overlap, the GMT addresses travel directly, and the orange-accented Doxa supplies spice. The trade-off is that neither alone covers everything (GS splash-resistant, Doxa casual), but as a two-watch system it is the most complete and the cheapest."),
}
out=dict(watches=W,pairs=P)
path="<scratch>/twowatch/scoring/scorer2/scores.json"
json.dump(out,open(path,"w"),indent=1)
d=json.load(open(path))
assert set(d["watches"])=={f"PAIR-{c}-{i}" for c in "UVWXYZ" for i in (1,2)}
for k,v in d["watches"].items():
    for f in ["register","robustness","wearability","useful_complications","practicality","horological_merit","design_integrity","value"]:
        assert isinstance(v[f],int) and 1<=v[f]<=5,(k,f)
    assert set(v["occasion_fit"])==set(K) and all(isinstance(x,int) and 0<=x<=2 for x in v["occasion_fit"].values())
assert set(d["pairs"])=={f"PAIR-{c}" for c in "UVWXYZ"}
for k,v in d["pairs"].items():
    for f in PK[:-1]: assert isinstance(v[f],int) and 1<=v[f]<=5,(k,f)
    assert v["rationale"]
assert sorted(v["expert_rank"] for v in d["pairs"].values())==[1,2,3,4,5,6]
print("valid", sorted(d["pairs"],key=lambda k:d["pairs"][k]["expert_rank"]))
