#!/usr/bin/env python3
"""Check input-part poses and jack datums; no enclosure/fault qualification."""
import json,math
import pcbnew
from place_fpga_bypass import ROOT
from build_hp_ground import ident as hp_ident

def main():
    b=pcbnew.LoadBoard(str(ROOT/'electrical/kestrel-revb.kicad_pcb'));f={f.GetReference():f for f in b.GetFootprints()}
    d=json.loads((ROOT/'electrical/input-power-placement.json').read_text())
    assert set(d['poses'])=={'F401','Q401','R401','D401','C401','C402','TP401','TP402','TP403'}
    def vec(xy):return pcbnew.VECTOR2I(*(pcbnew.FromMM(v)for v in xy))
    for r,(x,y,a)in d['poses'].items():
        assert (f[r].GetPosition()-vec([100+x,100-y])).EuclideanNorm()<=2,r
        assert f[r].GetOrientationDegrees()==a and f[r].GetLayer()==pcbnew.F_Cu,r
    j=f['J401'];assert j.GetPosition()==vec([46,58])and j.GetOrientationDegrees()==0 and j.GetLayer()==pcbnew.B_Cu
    pads={r:{p.GetNumber():p for p in fp.Pads()}for r,fp in f.items()}
    for n,xy in {'1':[46,58],'2':[46,52],'3':[50.7,55]}.items():
        p=pads['J401'][n];assert p.GetPosition()==vec(xy)
        assert p.GetDrillSize()==vec([1.6,1.6])and p.GetSize()==vec([2.6,2.6])
    expected={'/GND':{'J401.1','R401.2','D401.2','C401.2','C402.2','TP403.1'},
              '/Centre-negative 9 V input/9V_RAW':{'J401.2','F401.1','TP401.1'},
              '/Centre-negative 9 V input/9V_FUSED':{'F401.2','Q401.5','Q401.6','Q401.7','Q401.8'},
              '/9V_PROTECTED':{'Q401.1','Q401.2','Q401.3','D401.1','C401.1','C402.1','TP402.1'},
              '/Centre-negative 9 V input/INPUT_GATE':{'Q401.4','R401.1'}}
    for net,names in expected.items():
        for name in names:
            r,n=name.split('.');assert pads[r][n].GetNetname()==net,name
    assert pads['J401']['3'].GetNetname()=='unconnected-(J401-Pad3)'
    # Retain the Fab shape: the nominal front face hangs 2.7 mm beyond the PCB rear edge.
    assert any(isinstance(g,pcbnew.PCB_SHAPE)and g.GetLayer()==pcbnew.B_Fab and g.GetStart()==vec([50.5,44.3])and g.GetEnd()==vec([41.5,44.3])for g in j.GraphicalItems())
    conn=b.GetConnectivity();conn.Build(b)
    pending=[pads['J401']['1']];seen=set()
    while pending:
        item=pending.pop();uid=item.m_Uuid.AsString()
        if uid in seen:continue
        seen.add(uid);pending.extend(conn.GetConnectedItems(item))
    assert hp_ident('zone',0)in seen,'Jack ground does not reach filled plane'
    result={'status':'PASS ten input-part poses, independent pad nets, underside jack drills/Fab front datum and filled-plane ground',
            'placed_references':sorted(d['poses'])+['J401'],
            'jack_pcb_mm':[46,58],'jack_front_pcb_y_mm':44.3,
            'nominal_height_review':{'pcb_top_z_mm':23.6,'reference_panel_bottom_z_mm':32.62,'topside_body_top_z_mm':34.6,'topside_overlap_mm':1.98,'underside_body_bottom_z_mm':11},
            'limits':['Input copper and both buck feeds are checked by check_input_power_local.py; fault/current/thermal, lead fit and return performance remain unqualified.',
                      'Fab datum is not manufacturer 3D fit. Rear-wall plug insertion, opening/support, body tolerances, solder access and all-component assembly remain unqualified.']}
    (ROOT/'generated/input-power-placement-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS ten input-part poses and pad nets; underside jack datums/plane ground checked; enclosure/protection unfinished.')
if __name__=='__main__':main()
