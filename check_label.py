#!/usr/bin/env python3
"""Verifica por CDP que LM Studio muestra la etiqueta esperada.

Uso:
  1) pkill -9 -x lm-studio
  2) /opt/LM-Studio/lm-studio --remote-debugging-port=9333 &
  3) python3 check_label.py "OPENVINO - "

Requiere el paquete `websocket-client` (pip install websocket-client).
"""
import json
import sys
import time
import urllib.request

import websocket


def target(port=9333):
    for _ in range(30):
        try:
            data = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3))
            for t in data:
                if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                    return t["webSocketDebuggerUrl"]
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit("no hay target CDP en :9333 (LM Studio arrancado con --remote-debugging-port?)")


class CDP:
    def __init__(self, port=9333):
        self.ws = websocket.create_connection(target(port), timeout=30,
                                              max_size=50 * 1024 * 1024,
                                              suppress_origin=True)
        self.i = 0

    def send(self, method, **params):
        self.i += 1
        self.ws.send(json.dumps({"id": self.i, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.i:
                if "error" in msg:
                    raise RuntimeError(msg["error"])
                return msg.get("result", {})

    def js(self, expr):
        r = self.send("Runtime.evaluate", expression=expr, returnByValue=True,
                      awaitPromise=True, userGesture=True)
        return r.get("result", {}).get("value")

    def close(self):
        self.ws.close()


def main():
    needle = sys.argv[1] if len(sys.argv) > 1 else "OPENVINO - "
    c = CDP()
    # abrir el selector de modelo si hace falta
    c.js("""(() => {const b=[...document.querySelectorAll('button,div[role=button]')]
        .find(x=>(x.innerText||'').includes('Select a model to load')); if(b){b.click();return 1;} return 0;})()""")
    time.sleep(2)
    raw = c.js("""JSON.stringify([...new Set([...document.querySelectorAll('*')]
        .filter(e=>e.children.length===0)
        .map(e=>(e.innerText||'').trim())
        .filter(t=>t && t.length<140 && t.includes(%s)))].slice(0,5))""" % json.dumps(needle))
    labels = json.loads(raw) if raw else []
    print("etiquetas encontradas:", labels)
    print("OK" if labels else "NO ENCONTRADA la etiqueta")
    c.close()


if __name__ == "__main__":
    main()
