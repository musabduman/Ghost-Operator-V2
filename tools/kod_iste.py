import http.server
import socketserver
import os

port = 8000
os.chdir(r'C:\Users\dum4n\FallingSandGame')
Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(('', port), Handler) as httpd:
    print(f'Serving at http://localhost:{port}')
    httpd.serve_forever()