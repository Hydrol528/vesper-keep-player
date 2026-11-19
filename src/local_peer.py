"""Fail-closed Windows loopback connection ownership. No process memory access."""
import ctypes,os,socket,struct,time,re
from pathlib import Path
from ctypes import wintypes
from dataclasses import dataclass
def steam_roots():
 if os.name!='nt':return []
 import winreg
 roots=[]
 for hive,key,value in ((winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam','SteamPath'),(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\WOW6432Node\Valve\Steam','InstallPath')):
  try:
   with winreg.OpenKey(hive,key) as item:roots.append(Path(winreg.QueryValueEx(item,value)[0]))
  except OSError:pass
 return roots

def trusted_installations():
 roots=steam_roots();libraries=list(roots)
 for root in roots:
  try:
   data=(root/'steamapps'/'libraryfolders.vdf').read_text(encoding='utf-8')
   libraries += [Path(value.replace('\\\\','\\')) for value in re.findall(r'"path"\s+"([^"\r\n]+)"',data)]
  except (OSError,UnicodeError):pass
 return {os.path.normcase(os.path.realpath(root/'steamapps'/'common'/'VRChat'/'VRChat.exe')) for root in libraries if (root/'steamapps'/'common'/'VRChat'/'VRChat.exe').is_file()}

@dataclass(frozen=True)
class PeerIdentity:
 pid:int
 image:str
 created:int

def connection_owner(peer,local):
 if os.name!='nt' or peer[0]!='127.0.0.1' or local[0]!='127.0.0.1':return None
 try:
  api=ctypes.WinDLL('iphlpapi',use_last_error=True)
  get=api.GetExtendedTcpTable;get.argtypes=[ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD),wintypes.BOOL,wintypes.ULONG,ctypes.c_int,wintypes.ULONG];get.restype=wintypes.DWORD
  size=wintypes.DWORD();code=get(None,ctypes.byref(size),False,2,5,0)
  if code!=122 or size.value>16*1024*1024:return None
  for _ in range(10):
   buf=ctypes.create_string_buffer(size.value);code=get(buf,ctypes.byref(size),False,2,5,0)
   if code==122:time.sleep(.05);continue
   if code:return None
   raw=buf.raw;count=struct.unpack_from('<I',raw)[0]
   if 4+count*24>len(raw):return None
   matches=[]
   for n in range(count):
    state,la,lp,ra,rp,pid=struct.unpack_from('<6I',raw,4+n*24)
    address=lambda v:socket.inet_ntoa(struct.pack('<I',v))
    if state==5 and (address(la),socket.ntohs(lp&65535))==peer and (address(ra),socket.ntohs(rp&65535))==local:matches.append(pid)
   if not matches:time.sleep(.05);continue
   if len(matches)!=1:return None
   return process_identity(matches[0])
  return None
 except (OSError,ValueError,struct.error):return None

def process_identity(pid):
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
 kernel.CloseHandle.argtypes=[wintypes.HANDLE]
 kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
 kernel.GetProcessTimes.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
 handle=kernel.OpenProcess(0x1000,False,pid)
 if not handle:return None
 try:
  path=ctypes.create_unicode_buffer(32768);length=wintypes.DWORD(len(path))
  times=[wintypes.FILETIME() for _ in range(4)]
  if not kernel.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(length)) or not kernel.GetProcessTimes(handle,*[ctypes.byref(t) for t in times]):return None
  return PeerIdentity(pid,os.path.normcase(os.path.realpath(path.value)),times[0].dwHighDateTime<<32|times[0].dwLowDateTime)
 finally:kernel.CloseHandle(handle)

def trusted_vrchat(peer,local):
 identity=connection_owner(peer,local)
 return identity if identity and identity.image in trusted_installations() else None
