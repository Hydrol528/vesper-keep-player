"""Explicitly ticked provider visit lifetime; no background process starts on import.
The caller supplies the existing native world-session guard, never a browser flag.
"""
class SharedVisit:
    def __init__(self,provider,guard,play,clock):
        self.provider=provider;self.guard=guard;self.play=play;self.clock=clock
        self.active=False;self.next_heartbeat=0;self.next_poll=0
    def connect(self,catalogue,posters,instance):
        if not self.guard.current():raise PermissionError('Join the Keep before sharing')
        url=self.provider.publish(catalogue,posters,instance)
        self.active=True;self.next_heartbeat=self.clock()+10
        if not self.guard.current():
            self.stop();raise PermissionError('The visit ended')
        return url
    def stop(self):
        self.active=False
        self.provider.disconnect()
    def tick(self):
        if not self.active:return
        if not self.guard.current():self.stop();return
        try:
            if self.clock()>=self.next_heartbeat:
                self.provider.heartbeat();self.next_heartbeat=self.clock()+10
            if self.clock()<self.next_poll:return
            self.next_poll=self.clock()+2
            index=self.provider.selection()
            if index is not None:
                if not self.guard.current():self.stop();return
                self.play(index)
        except Exception:
            # Stop renewing after connection errors; the relay lease also expires.
            self.stop();raise
