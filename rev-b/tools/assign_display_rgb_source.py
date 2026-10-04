#!/usr/bin/env python3
"""Guarded remap of four unrouted RGB data bits to free right-side GPIOs."""
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--board',type=Path);p.add_argument('--trial-output',type=Path);args=p.parse_args();path=ROOT/'electrical/kestrel-revb.kicad_pcb';b=pcbnew.LoadBoard(str(args.board or path));f=next(f for f in b.GetFootprints()if f.GetReference()=='U701');pads={p.GetNumber():p for p in f.Pads()};xml=ET.parse(ROOT/'generated/revb-netlist.xml');expected={node.attrib['pin']:n.attrib['name']for n in xml.findall('.//nets/net')for node in n.findall('node')if node.attrib['ref']=='U701'}
 old={'55':'unconnected-(U701C-GPIO26-Pad55)','93':'/MCU_LCD_R3','57':'unconnected-(U701C-GPIO28-Pad57)','95':'/MCU_LCD_R5','60':'unconnected-(U701C-GPIO30-Pad60)','98':'/MCU_LCD_R7','63':'unconnected-(U701C-GPIO32-Pad63)','90':'/MCU_LCD_G6'}
 assert {n:expected[n]for n in old}=={'55':'/MCU_LCD_R3','93':'unconnected-(U701E-GPIO50-Pad93)','57':'/MCU_LCD_R5','95':'unconnected-(U701E-GPIO52-Pad95)','60':'/MCU_LCD_R7','98':'unconnected-(U701E-GPIO54-Pad98)','63':'/MCU_LCD_G6','90':'unconnected-(U701D-GPIO48-Pad90)'}
 if all(pads[n].GetNetname()==expected[n]for n in old):print('Verified current RGB GPIO26/28/30/32 allocation');return
 conn=b.GetConnectivity();conn.Build(b)
 for n,net in old.items():
  assert pads[n].GetNetname()==net,n
  assert all(x.m_Uuid.AsString()==pads[n].m_Uuid.AsString()for x in conn.GetConnectedItems(pads[n])),f'Pad{n} already routed'
 for n in old:
  net=b.FindNet(expected[n])
  if net is None:net=pcbnew.NETINFO_ITEM(b,expected[n]);b.Add(net)
  pads[n].SetNet(net)
 b.RemoveUnusedNets(None);pcbnew.SaveBoard(str(args.trial_output or path),b);print('Assigned R3/R5/R7/G6 to GPIO26/28/30/32; only eight unrouted pad nets changed')
if __name__=='__main__':main()
