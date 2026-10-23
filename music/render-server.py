
import http.server,sys,os
D=os.path.dirname(os.path.abspath(__file__))
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(s,*a,**k): super().__init__(*a,directory=D,**k)
    def do_POST(s):
        n=int(s.headers['content-length']); b=s.rfile.read(n)
        open(os.path.join(D,'music.wav' if s.path.startswith('/wav') else 'err.txt'),'wb').write(b)
        print('POST',s.path,n,flush=True); s.send_response(200); s.end_headers()
        if s.path.startswith('/wav') or s.path.startswith('/err'): os._exit(0)
http.server.ThreadingHTTPServer(('127.0.0.1',8765),H).serve_forever()
