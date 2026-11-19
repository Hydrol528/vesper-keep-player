"""Find one running, registered VRChat process currently in the Keep. No memory reads."""
import ctypes,os
from ctypes import wintypes
from local_peer import process_identity,trusted_installations
from world_session import WorldSessionGuard

def process_ids():
 if os.name!='nt':return []
 api=ctypes.WinDLL('psapi',use_last_error=True)
 values=(wintypes.DWORD*8192)();used=wintypes.DWORD()
 if not api.EnumProcesses(values,ctypes.sizeof(values),ctypes.byref(used)) or used.value>=ctypes.sizeof(values):return []
 return list(values[:used.value//ctypes.sizeof(wintypes.DWORD)])

def current_keep_peer(ids=None,identity_for=process_identity,installations=None,guard_for=WorldSessionGuard):
 allowed=trusted_installations() if installations is None else installations
 matches=[]
 for pid in process_ids() if ids is None else ids:
  try:
   peer=identity_for(pid)
   if peer and peer.image in allowed and guard_for(peer).current():matches.append(peer)
  except (OSError,ValueError):pass
 return matches[0] if len(matches)==1 else None
