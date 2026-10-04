"""Verify a complete builder-owned copper inventory before in-memory replacement.

This helper never saves a PCB. Caller retains returned detached SWIG items until
all board operations finish, guards new anchors/geometry, refills ground,
then saves a trial or accepted board and refreshes its own report fields.
"""
import pcbnew

def replace_owned_routes(board,existing,old,ident,vec,report,prefix):
    owned=[];ids=[];vids=[];index=0
    for route in old['paths']:
        layer={'F.Cu':pcbnew.F_Cu,'In2.Cu':pcbnew.In2_Cu,'B.Cu':pcbnew.B_Cu}[route['layer']]
        for a,c in zip(route['points'],route['points'][1:]):
            key=ident('track',index);index+=1;t=existing[key];ids.append(key)
            assert not isinstance(t,pcbnew.PCB_VIA) and t.GetStart()==vec(a) and t.GetEnd()==vec(c) and t.GetLayer()==layer and t.GetWidth()==pcbnew.FromMM(route['width_mm']) and t.GetNetname()==route.get('net',old['net']),key
            owned.append(t)
    for i,xy in enumerate(old['via_positions']):
        key=ident('via',i);v=existing[key];vids.append(key)
        diameter=old.get('via_diameters_mm',[old['via_diameter_mm']]*len(old['via_positions']))[i]
        net=old.get('via_net_names',[old['net']]*len(old['via_positions']))[i]
        assert isinstance(v,pcbnew.PCB_VIA) and v.GetPosition()==vec(xy) and v.GetNetname()==net and v.GetWidth(pcbnew.F_Cu)==pcbnew.FromMM(diameter) and v.GetDrillValue()==pcbnew.FromMM(old['via_drill_mm']) and v.TopLayer()==pcbnew.F_Cu and v.BottomLayer()==pcbnew.B_Cu and v.GetViaType()==pcbnew.VIATYPE_THROUGH,key
        owned.append(v)
    assert report[prefix+'_track_ids']==ids and report[prefix+'_via_ids']==vids,'Previous manifest must match complete owned inventory'
    # Validate the entire old inventory before removing anything in memory.
    for t in owned:board.Remove(t)
    removed=set(ids+vids)
    # Dropping detached wrappers early made later FindNet return an untyped
    # SwigPyObject in a native trial. Keep them alive through caller board work.
    return {key:t for key,t in existing.items()if key not in removed},owned
