"""Session-selected Jellyfin endpoints. Never follow redirects with credentials."""
import ipaddress, urllib.parse, urllib.request
class ServerAddressError(ValueError): pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs): raise ServerAddressError('Jellyfin redirected this request. Enter its final server address.')
def normalize_server(value):
 if not isinstance(value,str) or not value or len(value)>2048 or any(ord(c)<33 for c in value):raise ServerAddressError('Enter your Jellyfin server address, including http:// or https://')
 try:
  p=urllib.parse.urlsplit(value);port=p.port
 except ValueError:raise ServerAddressError('Invalid Jellyfin server address')
 if p.scheme not in ('http','https') or not p.hostname or p.username is not None or p.password is not None or p.query or p.fragment:raise ServerAddressError('Use a server address without passwords, query parameters, or fragments')
 try:ip=ipaddress.ip_address(p.hostname)
 except ValueError:ip=None
 if ip and (ip.is_link_local or ip.is_multicast or ip.is_unspecified):raise ServerAddressError('Unsupported server address')
 if p.scheme=='http' and not (p.hostname=='localhost' or (ip and (ip.is_private or ip.is_loopback))):raise ServerAddressError('Use HTTPS for a server outside your local network')
 path=p.path.rstrip('/')
 if path.endswith('/web') or '/web/' in path or any(x in ('.','..') for x in path.split('/')) or '%' in path:raise ServerAddressError('Enter the server base address, without /web or a page path')
 return urllib.parse.urlunsplit((p.scheme,p.netloc.lower(),path,'',''))
def server_url(session):
 if not session.get('server'):raise ServerAddressError('Connect your Jellyfin server first')
 return normalize_server(session['server'])
def approval_url(server):return normalize_server(server)+'/web/#/quickconnect'
def open_request(request,timeout=20):return urllib.request.build_opener(NoRedirect).open(request,timeout=timeout)
