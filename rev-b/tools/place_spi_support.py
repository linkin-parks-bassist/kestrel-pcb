#!/usr/bin/env python3
"""Guarded SPI support placement and unrouted translator orientation correction."""
import argparse
import json
from pathlib import Path
import pcbnew
from build_hp_ground import ident as hp_ident
ROOT=Path(__file__).resolve().parents[1]
def vec(p):return pcbnew.VECTOR2I(pcbnew.FromMM(100+p[0]),pcbnew.FromMM(100-p[1]))
def at(fp,pose):return fp.GetPosition()==vec(pose) and abs((fp.GetOrientationDegrees()-pose[2]+180)%360-180)<.001

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--trial-output',type=Path);parser.add_argument('--board',type=Path);args=parser.parse_args()
    path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(args.board or path));d=json.loads((ROOT/'electrical/spi-support-placement.json').read_text());fps={f.GetReference():f for f in b.GetFootprints()}
    conn=b.GetConnectivity();conn.Build(b)
    for ref,pose in d['poses'].items():
        f=fps[ref];assert f.GetLayer()==pcbnew.F_Cu
        if pcbnew.ToMM(f.GetPosition().x)<190 and not at(f,pose):
            assert ref in d.get('previous_poses',{}) and at(f,d['previous_poses'][ref]),ref
            assert all(all(item.m_Uuid.AsString()==p.m_Uuid.AsString()for item in conn.GetConnectedItems(p))for p in f.Pads()),f'{ref} already routed'
    conn=b.GetConnectivity();conn.Build(b)
    for ref,pose in d['major_poses'].items():
        f=fps[ref];assert f.GetLayer()==pcbnew.F_Cu
        if not at(f,pose):
            assert at(f,d['original_major_poses'][ref]),ref
            assert all(all(item.m_Uuid.AsString()==p.m_Uuid.AsString() for item in conn.GetConnectedItems(p)) for p in f.Pads()),f'{ref} already routed'
    for ref,pose in (d['poses']|d['major_poses']).items():fps[ref].SetPosition(vec(pose));fps[ref].SetOrientationDegrees(pose[2])
    z=next(z for z in b.Zones()if z.m_Uuid.AsString()==hp_ident('zone',0));assert pcbnew.ZONE_FILLER(b).Fill(b.Zones()) and z.HasFilledPolysForLayer(pcbnew.In1_Cu)
    pcbnew.SaveBoard(str(args.trial_output or path),b)
    if not args.trial_output:
        major_path=ROOT/'electrical/placement-draft.json';major=json.loads(major_path.read_text());major['poses'].update(d['major_poses']);major_path.write_text(json.dumps(major,indent=2)+'\n')
        p=ROOT/'generated/pcb-import-review.json';r=json.loads(p.read_text());r['provisional_spi_support_references']=list(d['poses']);p.write_text(json.dumps(r,indent=2)+'\n')
    print('Placed sixteen provisional SPI support parts; U801 at 180 degrees with B-side facing FPGA; routing and qualification unfinished.')
if __name__=='__main__':main()
