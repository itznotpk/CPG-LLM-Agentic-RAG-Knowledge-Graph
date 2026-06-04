import json, sys
fn = sys.argv[1]
with open(fn,encoding='utf-8') as f:
    for i,line in enumerate(f):
        r = json.loads(line)
        e=r['edge']; x=r['extracted']
        ev = (e.get('evidence') or '').replace('\n',' ')[:220]
        v = x.get('threshold_value')
        v2 = x.get('threshold_value2')
        vstr = f"{v}-{v2}" if v2 else f"{v}"
        print(f"{i:3d} | {e['relation'][:8]:8} | op={x.get('threshold_op'):>4} val={vstr} unit={x.get('threshold_unit')} | param={x.get('threshold_param')}")
        print(f"     subj={e['subject'][:35]} | obj={e['object'][:45]}")
        print(f"     ev: {ev}")
