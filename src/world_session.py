"""Fail-closed session boundary for the explicitly launched local Keep test.
Reads only that test's log; no VRChat modifications or process injection.
"""
from pathlib import Path
import json,os,re
from local_peer import PeerIdentity
from local_peer import process_identity
TEST_LOG=Path(__file__).resolve().parent/'vrchat-private-menu-test.log'
CLIENT_BINDING=Path(__file__).resolve().parent/'world-session-client.json'
BUNDLE='Loaded asset bundle: VesperJellyfinTabReview'
APPROVED_BUNDLES=(BUNDLE,'Loaded asset bundle: VesperJellyfinInteractionTest','Loaded asset bundle: VesperPrivateCatalogueTest','Loaded asset bundle: VesperSharedCatalogueReview')
KEEP_WORLD='wrld_670af2b5-cb63-4c7e-af6e-9a0478bbf13a'
RELEASE_BUNDLE='Loaded asset bundle: VesperKeep_Refinement_Review'
FINISHED='[Behaviour] Finished entering world.'
BOUNDARIES=('[Behaviour] Destination requested:','[Behaviour] Unloading scenes','[Behaviour] Entering Room:','[Behaviour] OnLeftRoom','[Behaviour] OnDisconnected','[Behaviour] Joining or Creating Room:')
def discover_client_log(peer):
 # Read the normal log created with this exact Windows process, not another client.
 home=os.environ.get('USERPROFILE','')
 if not home:return None
 root=Path(home)/'AppData'/'LocalLow'/'VRChat'/'VRChat'
 started=peer.created/10000000-11644473600
 matches=[]
 try:
  for path in root.glob('output_log_*.txt'):
   stat=path.stat()
   if -3<=getattr(stat,'st_birthtime',stat.st_ctime)-started<=30:matches.append(path)
 except OSError:return None
 return matches[0] if len(matches)==1 else None

def test_bundle_position(text):
 position=max(text.rfind(value) for value in APPROVED_BUNDLES)
 if position<0:return -1
 destinations=list(re.finditer(r'(?m)^.*\[Behaviour\] Destination requested: ([^\r\n]+)',text[:position]))
 return position if destinations and destinations[-1].group(1).strip().startswith('local:') else -1

def release_bundle_position(text):
 position=text.rfind(RELEASE_BUNDLE)
 if position<0:return -1
 destinations=list(re.finditer(r'(?m)^.*\[Behaviour\] Destination requested: ([^\r\n]+)',text[:position]))
 if not destinations:return -1
 destination=destinations[-1].group(1).strip()
 return position if destination==KEEP_WORLD or destination.startswith(KEEP_WORLD+':') else -1

class WorldSessionGuard:
 def __init__(self,peer,path=TEST_LOG,identity_for=process_identity,expected_peer=None):
  self.peer=peer;self.path=Path(path);self.identity_for=identity_for;self.valid=False;self.offset=0;self.file_id=None;self.fragment=''
  if peer is None:return
  try:
   if expected_peer is None:
    try:
     binding=json.loads(CLIENT_BINDING.read_text(encoding='utf-8'));bound=PeerIdentity(**binding.get('peer',binding))
    except (OSError,ValueError,TypeError):binding={};bound=None
    if bound==peer:
     expected_peer=bound
     if binding.get('log'):self.path=Path(binding['log'])
    else:
     discovered=discover_client_log(peer)
     if discovered is None:return
     self.path=discovered;expected_peer=peer
   if expected_peer!=peer:return
   with self.path.open('rb') as f:
    stat=self.path.stat()
    if stat.st_size>32*1024*1024:return
    raw=f.read();self.offset=len(raw);self.file_id=(stat.st_dev,stat.st_ino)
   text=raw.decode('utf-8',errors='replace');bundle=max(test_bundle_position(text),release_bundle_position(text));finished=text.rfind(FINISHED)
   boundary=max(text.rfind(marker) for marker in BOUNDARIES)
   self.valid=peer is not None and bundle>=0 and finished>bundle and boundary<bundle and identity_for(peer.pid)==peer
   self.fragment=text.rsplit('\n',1)[-1]
  except (OSError,ValueError):pass
 def current(self):
  if not self.valid:return False
  try:
   if self.identity_for(self.peer.pid)!=self.peer:self.valid=False;return False
   stat=self.path.stat()
   if (stat.st_dev,stat.st_ino)!=self.file_id or stat.st_size<self.offset or stat.st_size-self.offset>4*1024*1024:self.valid=False;return False
   with self.path.open('rb') as f:f.seek(self.offset);raw=f.read(4*1024*1024+1)
   text=self.fragment+raw.decode('utf-8',errors='replace');self.offset+=len(raw);self.fragment=text.rsplit('\n',1)[-1]
   if any(marker in text for marker in BOUNDARIES):self.valid=False
  except (OSError,ValueError):self.valid=False
  return self.valid
