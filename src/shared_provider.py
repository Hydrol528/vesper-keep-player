"""Local provider transport. Only sanitized catalogue/poster bytes leave this process.
No Jellyfin session, password, token or source URL is accepted by this interface.
"""
import json, secrets, urllib.request, urllib.parse
from shared_catalogue import SharedCatalogues, ShareDenied

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

class SharedProvider:
    def __init__(self,base,*,allow_local_test=False):
        u=urllib.parse.urlsplit(base)
        local=allow_local_test and u.scheme=='http' and u.hostname=='127.0.0.1'
        if (u.scheme!='https' and not local) or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
            raise ValueError('Use the HTTPS catalogue relay address')
        self.base=base.rstrip('/');self.opener=urllib.request.build_opener(NoRedirect())
        self.path=None;self.control=None
    def _call(self,path,body=None,method=None,kind='application/json',private=True,timeout=8):
        headers={'Content-Type':kind}
        if private and self.control:headers['Authorization']='Bearer '+self.control
        data=body if isinstance(body,bytes) else json.dumps(body).encode() if body is not None else None
        request=urllib.request.Request(self.base+path,data=data,headers=headers,method=method)
        with self.opener.open(request,timeout=timeout) as response:
            payload=response.read(1024*1024+1)
            if len(payload)>1024*1024:raise ShareDenied('Relay response too large')
            return json.loads(payload)
    def publish(self,catalogue,posters,instance):
        # Project a fresh allowlist before any network operation.
        clean=SharedCatalogues._catalogue(catalogue)
        if self.path:self.disconnect()
        # Free hosting can take about a minute to wake; do this before creating a lease.
        health=self._call('/health',private=False,timeout=65)
        if health.get('ready') is not True:raise ShareDenied('Catalogue service is not ready')
        grant=self._call('/shared/publish',{'provider':secrets.token_urlsafe(24),'instance':instance,'catalogue':clean},private=False)
        path=grant.get('path','');control=grant.get('control','')
        import re
        if not re.fullmatch(r'/shared/[A-Za-z0-9_-]{32}',path) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',control):
            raise ShareDenied('Invalid relay connection')
        self.path=path;self.control=control
        try:self._call(path+'/posters',posters,'PUT','image/png')
        except Exception:
            self.disconnect();raise
        return self.base+path
    def heartbeat(self):
        if not self.path:raise ShareDenied('Not connected')
        self._call(self.path+'/heartbeat',{})
    def selection(self):
        if not self.path:raise ShareDenied('Not connected')
        return self._call(self.path+'/selection')['index']
    def lock(self,locked):
        if not self.path:raise ShareDenied('Not connected')
        self._call(self.path+'/lock',{'locked':locked})
    def disconnect(self):
        path=self.path
        try:
            if path:self._call(path+'/disconnect',{})
        finally:self.path=None;self.control=None
