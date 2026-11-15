# Objective, spec-derived pair features (no scorer judgement). Values from specs_master.json.
WATCH={
 # bracelet, wr_m (splash=0), diver(200m+bezel), precious, auto(1)/manual(0), thickness, diameter, price_k, complication_level(0 time/date,1 GMT/day-date,2 chrono,3 chrono+calendar/perpetual), mainstream_brand(1 per big-volume brand list)
 'brit_A':dict(bracelet=1,wr=100,diver=0,precious=0,auto=1,thick=11.7,dia=40.0,price=10.2,comp=0,brand='Grand Seiko'),
 'brit_B':dict(bracelet=1,wr=200,diver=1,precious=0,auto=1,thick=12.15,dia=39.5,price=11.6,comp=0,brand='Glashütte Original'),
 'adrien_A':dict(bracelet=1,wr=150,diver=0,precious=0,auto=1,thick=12.24,dia=38.0,price=7.1,comp=0,brand='Omega'),
 'adrien_B':dict(bracelet=1,wr=100,diver=0,precious=0,auto=1,thick=14.5,dia=41.0,price=8.7,comp=2,brand='IWC'),
 'teddy_A':dict(bracelet=1,wr=100,diver=0,precious=0,auto=1,thick=11.4,dia=37.0,price=10.2,comp=0,brand='Grand Seiko'),
 'teddy_B':dict(bracelet=0,wr=100,diver=0,precious=0,auto=1,thick=15.35,dia=42.0,price=15.5,comp=3,brand='Breitling'),
 'marco_A':dict(bracelet=0,wr=50,diver=0,precious=0,auto=1,thick=12.3,dia=42.0,price=15.3,comp=0,brand='Glashütte Original'),
 'marco_B':dict(bracelet=1,wr=100,diver=0,precious=0,auto=1,thick=11.7,dia=40.0,price=10.2,comp=0,brand='Grand Seiko'),
 'james_A':dict(bracelet=0,wr=0,diver=0,precious=0,auto=1,thick=13.7,dia=39.5,price=5.4,comp=1,brand='Grand Seiko'),
 'james_B':dict(bracelet=1,wr=200,diver=1,precious=0,auto=1,thick=10.6,dia=39.0,price=1.79,comp=0,brand='Doxa'),
 'andrew_A':dict(bracelet=0,wr=100,diver=0,precious=0,auto=0,thick=12.5,dia=38.0,price=6.7,comp=2,brand='Gallet'),
 'andrew_B':dict(bracelet=0,wr=50,diver=0,precious=1,auto=1,thick=14.9,dia=44.4,price=52.0,comp=3,brand='IWC'),
}
# Brand tiers: 'big' = brands with large retail presence (Omega, IWC, Breitling, Grand Seiko); 'mid' = GO; 'niche' = Doxa, Gallet.
TIER={'Omega':3,'IWC':3,'Breitling':3,'Grand Seiko':3,'Glashütte Original':2,'Doxa':1,'Gallet':1}
def pair_features(p):
    a,b=WATCH[p+'_A'],WATCH[p+'_B']
    return {
     'n_bracelet':a['bracelet']+b['bracelet'],
     'min_wr':min(a['wr'],b['wr']),
     'max_wr':max(a['wr'],b['wr']),
     'has_diver':max(a['diver'],b['diver']),
     'n_wr100':(a['wr']>=100)+(b['wr']>=100),
     'any_precious':max(a['precious'],b['precious']),
     'all_auto':min(a['auto'],b['auto']),
     'max_thick':max(a['thick'],b['thick']),
     'max_dia':max(a['dia'],b['dia']),
     'sum_price':a['price']+b['price'],
     'min_price':min(a['price'],b['price']),
     'max_comp':max(a['comp'],b['comp']),
     'sum_comp':a['comp']+b['comp'],
     'min_brand_tier':min(TIER[a['brand']],TIER[b['brand']]),
     'sum_brand_tier':TIER[a['brand']]+TIER[b['brand']],
     'n_simple_steel_sport':sum(1 for w in (a,b) if w['bracelet'] and w['wr']>=100 and w['comp']<=2 and not w['precious']),
    }
