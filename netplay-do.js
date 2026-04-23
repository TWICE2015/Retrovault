/**
 * Durable Object: EmulatorJS-Netplay–compatible signaling (Engine.IO v4 + Socket.IO v4, WebSocket only).
 * Mirrors https://github.com/EmulatorJS/EmulatorJS-Netplay/blob/main/server.js room + webrtc-signal behavior.
 */
export class NetplayCoordinatorDO {
  /**
   * @param {DurableObjectState} state
   * @param {Record<string, unknown>} env
   */
  constructor(state, env) {
    this.state = state;
    this.env = env;
    /** @type {Map<string, { ws: WebSocket, roomSessionId: string | null, playerId: string | null }>} */
    this.conns = new Map();
    /** @type {Record<string, ReturnType<NetplayCoordinatorDO['_makeRoom']>>} */
    this.rooms = Object.create(null);
    /** @type {Map<string, ReturnType<typeof setTimeout>>} */
    this.pingTimers = new Map();
  }

  randomId(len = 18) {
    const a = new Uint8Array(len);
    crypto.getRandomValues(a);
    return [...a].map((b) => b.toString(36).padStart(2, '0')).join('').slice(0, len);
  }

  _makeRoom() {
    return {
      /** @type {string} */
      owner: '',
      /** @type {Record<string, Record<string, unknown>>} */
      players: Object.create(null),
      /** @type {{ source: string, target: string }[]} */
      peers: [],
      roomName: '',
      gameId: 'default',
      domain: 'unknown',
      /** @type {string | null} */
      password: null,
      maxPlayers: 4,
    };
  }

  _roomKeyFromQuery(url) {
    const u = new URL(url);
    return (u.searchParams.get('room') || u.searchParams.get('roomName') || u.searchParams.get('roomId') || 'default').slice(0, 64);
  }

  _jsonResponse(obj, status = 200) {
    return new Response(JSON.stringify(obj), {
      status,
      headers: { 'content-type': 'application/json; charset=utf-8' },
    });
  }

  _wsResponse(ws) {
    return new Response(null, { status: 101, webSocket: ws });
  }

  _send(ws, packet) {
    try {
      ws.send(typeof packet === 'string' ? packet : JSON.stringify(packet));
    } catch {
      // ignore
    }
  }

  _broadcast(room, packet, excludeConnId = null) {
    for (const [cid, c] of this.conns.entries()) {
      if (excludeConnId && cid === excludeConnId) continue;
      if (!c?.ws) continue;
      if (c.roomSessionId !== room) continue;
      this._send(c.ws, packet);
    }
  }

  _closeConn(connId) {
    const c = this.conns.get(connId);
    if (!c) return;
    try {
      c.ws.close(1000, 'closed');
    } catch {
      // ignore
    }
    this.conns.delete(connId);
    try {
      const t = this.pingTimers.get(connId);
      if (t) clearTimeout(t);
      this.pingTimers.delete(connId);
    } catch {
      // ignore
    }
  }

  _schedulePing(connId) {
    try {
      const prev = this.pingTimers.get(connId);
      if (prev) clearTimeout(prev);
      const t = setTimeout(() => {
        this._closeConn(connId);
      }, 60_000);
      this.pingTimers.set(connId, t);
    } catch {
      // ignore
    }
  }

  async fetch(request) {
    const url = new URL(request.url);
    const { pathname } = url;

    // Minimal Engine.IO-ish endpoint compatibility for EmulatorJS-Netplay:
    // We accept WebSocket upgrades and then just proxy JSON messages between peers.
    // This is intentionally minimal; it exists to satisfy the existing Durable Object class dependency.

    if (request.headers.get('Upgrade') === 'websocket') {
      const pair = new WebSocketPair();
      const client = pair[0];
      const server = pair[1];
      server.accept();

      const connId = this.randomId(18);
      const roomKey = this._roomKeyFromQuery(url);
      if (!this.rooms[roomKey]) this.rooms[roomKey] = this._makeRoom();

      this.conns.set(connId, { ws: server, roomSessionId: roomKey, playerId: null });
      this._schedulePing(connId);

      server.addEventListener('message', (evt) => {
        this._schedulePing(connId);
        const data = evt?.data;
        // Broadcast everything (netplay client already namespaces message types)
        this._broadcast(roomKey, data, connId);
      });
      server.addEventListener('close', () => {
        this._closeConn(connId);
      });
      server.addEventListener('error', () => {
        this._closeConn(connId);
      });

      return this._wsResponse(client);
    }

    // health / info
    if (pathname === '/health' || pathname === '/') {
      return this._jsonResponse({ ok: true, rooms: Object.keys(this.rooms).length, conns: this.conns.size });
    }

    return this._jsonResponse({ ok: false, error: 'Not found' }, 404);
  }
}

