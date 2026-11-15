import json
K=["black_tie","suit","biz_casual","dinner","weekend","active","swim","scuba","travel"]
F=["register","robustness","wearability","useful_complications","practicality","horological_merit","design_integrity","value"]
W={
"PAIR-U-1":([4,2,2,3,3,5,4,3],[2,2,1,2,1,0,0,0,1]),
"PAIR-U-2":([2,3,4,4,3,3,4,3],[0,1,2,1,2,1,1,0,1]),
"PAIR-V-1":([2,4,3,4,4,4,4,3],[0,1,2,1,2,2,1,0,1]),
"PAIR-V-2":([3,4,5,3,5,4,4,4],[1,2,2,2,2,2,2,0,1]),
"PAIR-W-1":([2,5,4,3,4,4,4,3],[0,1,2,1,2,2,2,0,1]),
"PAIR-W-2":([3,3,4,3,5,5,4,4],[1,2,2,2,2,1,1,0,1]),
"PAIR-X-1":([3,3,2,3,3,3,4,2],[1,2,2,2,1,0,0,0,1]),
"PAIR-X-2":([3,3,5,3,5,5,4,4],[1,2,2,2,2,1,1,0,1]),
"PAIR-Y-1":([1,5,5,3,4,2,4,5],[0,0,1,1,2,2,2,0,1]),
"PAIR-Y-2":([4,1,4,5,4,4,4,4],[1,2,2,2,1,0,0,0,2]),
"PAIR-Z-1":([3,3,4,3,5,5,4,4],[1,2,2,2,2,1,1,0,1]),
"PAIR-Z-2":([4,2,3,3,3,5,3,3],[1,2,2,2,1,0,0,0,1]),
}
P=["differentiation","coherence_expert","anchor_strength","tension_point","gap_test","wear_balance","makes_sense_together","beaten_path","daily_driver","sensible_spice","everyday_livability","expert_rank"]
PV={
"PAIR-U":([4,2,2,4,4,3,2,2,2,3,2,6],"A 44 mm, 15 mm-thick gold perpetual calendar on alligator is too large and delicate for a 17 cm wrist and an office life, and it sits idle outside formal evenings. The 38 mm hand-wound Gallet chronograph on fabric is a charming daily piece, but it has to be wound and it is fragile for active days. The pair differs a lot, but it has no grab-and-go anchor, and the two do not read as one collector's plan."),
"PAIR-V":([3,3,5,3,2,3,4,5,5,3,5,3],"The 38 mm Aqua Terra is close to the ideal single anchor: it goes from a suit to the pool and wears superbly. The IWC Pilot chronograph adds timing and a sportier blue dial, but both are steel-on-bracelet sports watches, so removing the IWC leaves almost no gap. It is very livable and conventional, but somewhat redundant, and nothing in it suits formal evenings."),
"PAIR-W":([3,4,4,4,3,3,4,4,5,3,5,2],"A 200 m SeaQ diver and a Spring Drive Evolution 9 make a coherent German-versus-Japanese pairing of high-craft steel watches, and between them they cover water, office and dinner well. Both are roughly 40 mm time-and-date watches on steel bracelets, so the differences are mainly dial colour and the bezel. It is a very livable pair with excellent movements, but it has no real dress register and no travel complication."),
"PAIR-X":([4,3,4,4,3,4,4,3,5,3,4,4],"The 37 mm Lake Suwa is an excellent, comfortable daily anchor, and the copper-dial Datora on leather adds warmth, a chronograph and a dressier register. The Datora is 15.35 mm thick, which is a poor fit under a cuff, and its triple calendar needs resetting by hand, so the spice comes with some friction. The two differ in strap, dial and complication, but the Datora is the weak link on value and wearability."),
"PAIR-Y":([5,4,3,5,5,5,5,4,3,4,4,1],"This is the textbook two-watch split: a compact 39 mm, 10.5 mm Doxa diver for weekends, sport and swimming, and a cream-dial Grand Seiko GMT on crocodile for the office, dinners and the 12 travel days. The two are similar in size but opposite in register, so each owns its days and removing either opens a real gap. The weaknesses are that neither is a do-everything watch (the GS is only splash resistant), and the Doxa movement is modest, but the coverage, the clear choice each morning and the value are the best of the six."),
"PAIR-Z":([3,4,4,3,3,4,3,2,5,2,4,5],"Both are enthusiasts' movements: the 9SA5 Hi-Beat and the PanoMaticInverse's dial-side bridges reflect a coherent appreciation of mechanics. The Grand Seiko covers most days on its bracelet, and the Glashuette Original covers suits and dinners, but both have light, silvery dials, neither suits the water, and the pair has little energy or colour. It is refined but conservative, and less complete for active or travel days."),
}
out={"watches":{k:{**dict(zip(F,v)),"occasion_fit":dict(zip(K,o))} for k,(v,o) in W.items()},
     "pairs":{k:{**dict(zip(P,v)),"rationale":r} for k,(v,r) in PV.items()}}
p="<scratch>/twowatch/scoring/scorer3/scores.json"
json.dump(out,open(p,"w"),indent=1)
d=json.load(open(p))
assert len(d["watches"])==12 and len(d["pairs"])==6
for k,w in d["watches"].items():
    for f in F: assert isinstance(w[f],int) and 1<=w[f]<=5,(k,f)
    assert set(w["occasion_fit"])==set(K)
    for o in K: assert w["occasion_fit"][o] in (0,1,2)
for k,pp in d["pairs"].items():
    for f in P[:-1]: assert isinstance(pp[f],int) and 1<=pp[f]<=5
    assert pp["rationale"]
assert sorted(pp["expert_rank"] for pp in d["pairs"].values())==[1,2,3,4,5,6]
print("valid", sorted(d["pairs"],key=lambda k:d["pairs"][k]["expert_rank"]))
