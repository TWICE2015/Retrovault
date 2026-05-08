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

  /**
   * @param {Request} request
   */
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname === '/list' && request.method === 'GET') {
      return this.handleList(url);
    }
    if (request.headers.get('Upgrade')?.toLowerCase() === 'websocket') {
      return this.acceptWebSocket(request);
    }
    return new Response('Netplay: WebSocket /socket.io/* or GET /list', { status: 404 });
  }

  /**
   * @param {URL} url
   */
  handleList(url) {
    const gameId = url.searchParams.get('game_id') || 'default';
    const openRooms = {};
    for (const sessionId of Object.keys(this.rooms)) {
      const room = this.rooms[sessionId];
      if (!room) continue;
      const n = Object.keys(room.players).length;
      if (n >= room.maxPlayers) continue;
      if (String(room.gameId) !== String(gameId)) continue;
      const ownerPlayerId = Object.keys(room.players).find(
        (pid) => room.players[pid].socketId === room.owner,
      );
      const playerName = ownerPlayerId
        ? String(room.players[ownerPlayerId].player_name || 'Unknown')
        : 'Unknown';
      openRooms[sessionId] = {
        room_name: room.roomName,
        current: n,
        max: room.maxPlayers,
        player_name: playerName,
        hasPassword: !!room.password,
      };
    }
    return new Response(JSON.stringify(openRooms), {
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 'no-store',
      },
    });
  }

  /**
   * @param {Request} request
   */
  acceptWebSocket(request) {
    const pair = new WebSocketPair();
    const [client, server] = Object.values(pair);
    this.state.acceptWebSocket(server);

    const eioSid = this.randomId(20);
    this.conns.set(eioSid, { ws: server, roomSessionId: null, playerId: null });

    const handshake = JSON.stringify({
      sid: eioSid,
      upgrades: [],
      pingInterval: 25000,
      pingTimeout: 20000,
      maxPayload: 1000000,
    });
    server.send(`0${handshake}`);

    server.addEventListener('message', (event) => {
      try {
        const data = typeof event.data === 'string' ? event.data : '';
        this.onEngineMessage(eioSid, data);
      } catch (_) {
        try {
          server.close(1011, 'protocol error');
        } catch (_) {}
      }
    });
    server.addEventListener('close', () => this.onDisconnect(eioSid));
    server.addEventListener('error', () => this.onDisconnect(eioSid));

    this.schedulePing(eioSid);

    return new Response(null, { status: 101, webSocket: client });
  }

  /** @param {string} eioSid */
  schedulePing(eioSid) {
    const prev = this.pingTimers.get(eioSid);
    if (prev) clearTimeout(prev);
    const t = setTimeout(() => {
      const rec = this.conns.get(eioSid);
      if (!rec || rec.ws.readyState !== WebSocket.OPEN) return;
      try {
        rec.ws.send('2');
      } catch (_) {}
      this.schedulePing(eioSid);
    }, 25000);
    this.pingTimers.set(eioSid, t);
  }

  /** @param {string} eioSid */
  onDisconnect(eioSid) {
    const t = this.pingTimers.get(eioSid);
    if (t) clearTimeout(t);
    this.pingTimers.delete(eioSid);
    this.leaveRoomInternal(eioSid, true);
    this.conns.delete(eioSid);
  }

  /**
   * @param {string} socketId
   * @param {boolean} _isDisconnect
   */
  leaveRoomInternal(socketId, _isDisconnect) {
    const rec = this.conns.get(socketId);
    const sessionId = rec?.roomSessionId;
    const playerId = rec?.playerId;
    if (!sessionId || !playerId) {
      if (rec) {
        rec.roomSessionId = null;
        rec.playerId = null;
      }
      return;
    }
    const room = this.rooms[sessionId];
    if (!room) {
      if (rec) {
        rec.roomSessionId = null;
        rec.playerId = null;
      }
      return;
    }
    delete room.players[playerId];
    room.peers = room.peers.filter((p) => p.source !== socketId && p.target !== socketId);
    this.broadcastRoomSio(sessionId, `2${JSON.stringify(['users-updated', room.players])}`);
    if (Object.keys(room.players).length === 0) {
      delete this.rooms[sessionId];
    } else if (socketId === room.owner) {
      const remainingPlayers = Object.keys(room.players);
      if (remainingPlayers.length > 0) {
        const newOwnerId = room.players[remainingPlayers[0]].socketId;
        room.owner = newOwnerId;
        room.peers = room.peers.map((peer) => {
          if (peer.source === socketId) return { source: newOwnerId, target: peer.target };
          return peer;
        });
        if (room.peers.length > 0) {
          const targetWs = this.conns.get(newOwnerId)?.ws;
          if (targetWs && targetWs.readyState === WebSocket.OPEN) {
            const inner = `2${JSON.stringify([
              'webrtc-signal',
              { target: room.peers[0].target, requestRenegotiate: true },
            ])}`;
            targetWs.send(`4${inner}`);
          }
        }
        this.broadcastRoomSio(sessionId, `2${JSON.stringify(['users-updated', room.players])}`);
      }
    }
    if (rec) {
      rec.roomSessionId = null;
      rec.playerId = null;
    }
  }

  /**
   * @param {string} sessionId
   * @param {string} sioPacket
   */
  broadcastRoomSio(sessionId, sioPacket) {
    const room = this.rooms[sessionId];
    if (!room) return;
    const frame = `4${sioPacket}`;
    for (const pid of Object.keys(room.players)) {
      const sid = String(room.players[pid].socketId || '');
      const ws = this.conns.get(sid)?.ws;
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(frame);
        } catch (_) {}
      }
    }
  }

  /**
   * @param {string} sessionId
   * @param {string} fromEioSid
   * @param {string} sioPacket
   */
  broadcastRoomOthersSio(sessionId, fromEioSid, sioPacket) {
    const room = this.rooms[sessionId];
    if (!room) return;
    const frame = `4${sioPacket}`;
    for (const pid of Object.keys(room.players)) {
      const sid = String(room.players[pid].socketId || '');
      if (sid === fromEioSid) continue;
      const ws = this.conns.get(sid)?.ws;
      if (ws && ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(frame);
        } catch (_) {}
      }
    }
  }

  /**
   * @param {string} eioSid
   * @param {number | null} ackId
   * @param {unknown} err
   * @param {unknown} [second]
   */
  sendAck(eioSid, ackId, err, second) {
    if (ackId == null) return;
    const ws = this.conns.get(eioSid)?.ws;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    let payload;
    if (err != null) payload = [err];
    else if (second !== undefined) payload = [null, second];
    else payload = [null];
    const inner = `3${ackId}${JSON.stringify(payload)}`;
    try {
      ws.send(`4${inner}`);
    } catch (_) {}
  }

  /**
   * Decode Socket.IO-protocol packet string (v5) — same rules as socket.io-parser decodeString.
   * @param {string} str
   */
  decodeSioPacket(str) {
    let i = 0;
    const type = Number(str.charAt(i++));
    if (type < 0 || type > 6 || Number.isNaN(type)) throw new Error('bad sio type');
    if (type === 5 || type === 6) {
      throw new Error('binary socket.io packets not supported');
    }
    let nsp = '/';
    if (str.charAt(i) === '/') {
      const start = i;
      while (i < str.length && str.charAt(i) !== ',') i++;
      nsp = str.substring(start, i);
      if (str.charAt(i) === ',') i++;
    }
    let id = null;
    if (i < str.length) {
      const c = str.charAt(i);
      if (c >= '0' && c <= '9') {
        const start = i;
        while (i < str.length) {
          const ch = str.charAt(i);
          if (ch < '0' || ch > '9') break;
          i++;
        }
        id = Number(str.substring(start, i));
      }
    }
    let data;
    if (i < str.length) {
      data = JSON.parse(str.substring(i));
    }
    return { type, id, data, nsp };
  }

  /**
   * @param {string} eioSid
   * @param {string} raw
   */
  onEngineMessage(eioSid, raw) {
    if (!raw || typeof raw !== 'string') return;
    const engType = raw.charAt(0);
    const payload = raw.slice(1);
    if (engType === '3') return; // pong
    if (engType === '5') return; // upgrade (unused)
    if (engType === '4') {
      this.onSocketIoPacket(eioSid, payload);
      return;
    }
  }

  /**
   * @param {string} eioSid
   * @param {string} sioStr
   */
  onSocketIoPacket(eioSid, sioStr) {
    const pkt = this.decodeSioPacket(sioStr);
    if (pkt.type === 0) {
      const ws = this.conns.get(eioSid)?.ws;
      if (ws && ws.readyState === WebSocket.OPEN) ws.send('40');
      return;
    }
    if (pkt.type === 1) {
      this.leaveRoomInternal(eioSid, false);
      return;
    }
    if (pkt.type === 2) {
      const data = pkt.data;
      if (!Array.isArray(data) || !data.length) return;
      const eventName = data[0];
      const args = data.slice(1);
      this.dispatchEvent(eioSid, String(eventName), args, pkt.id);
    }
  }

  /**
   * @param {string} eioSid
   * @param {string} name
   * @param {unknown[]} args
   * @param {number | null} ackId
   */
  dispatchEvent(eioSid, name, args, ackId) {
    if (name === 'open-room') this.handleOpenRoom(eioSid, args, ackId);
    else if (name === 'join-room') this.handleJoinRoom(eioSid, args, ackId);
    else if (name === 'leave-room') {
      this.leaveRoomInternal(eioSid, false);
      const ws = this.conns.get(eioSid)?.ws;
      try {
        ws?.send('41');
      } catch (_) {}
    } else if (name === 'webrtc-signal') this.handleWebRtcSignal(eioSid, args);
    else if (name === 'data-message') this.handleDataMessage(eioSid, args);
    else if (name === 'snapshot') this.handleSnapshot(eioSid, args);
    else if (name === 'input') this.handleInput(eioSid, args);
  }

  /**
   * @param {string} eioSid
   * @param {unknown[]} args
   * @param {number | null} ackId
   */
  handleOpenRoom(eioSid, args, ackId) {
    const data = /** @type {Record<string, unknown>} */ (args[0] || {});
    const extra = /** @type {Record<string, unknown>} */ (data.extra || {});
    const sessionId = extra.sessionid != null ? String(extra.sessionid) : '';
    const playerId = extra.userid != null
      ? String(extra.userid)
      : extra.playerId != null
        ? String(extra.playerId)
        : '';
    if (!sessionId || !playerId) {
      this.sendAck(eioSid, ackId, 'Invalid data: sessionId and playerId required');
      return;
    }
    if (this.rooms[sessionId]) {
      this.sendAck(eioSid, ackId, 'Room already exists');
      return;
    }
    const maxPlayers = typeof data.maxPlayers === 'number' ? data.maxPlayers : 4;
    const roomName = extra.room_name != null ? String(extra.room_name) : `Room ${sessionId}`;
    const gameId = extra.game_id != null ? String(extra.game_id) : 'default';
    const playerName = extra.player_name != null ? String(extra.player_name) : 'Unknown';
    const roomPassword = extra.room_password != null ? String(extra.room_password) : 'none';
    let finalDomain = extra.domain;
    if (finalDomain === undefined || finalDomain === null) finalDomain = 'unknown';

    const room = this._makeRoom();
    room.owner = eioSid;
    room.roomName = roomName;
    room.gameId = gameId;
    room.domain = String(finalDomain);
    room.password = /** @type {string | null} */ (data.password) || null;
    room.maxPlayers = maxPlayers;
    room.players[playerId] = { ...extra, socketId: eioSid, player_name: playerName, room_password: roomPassword };

    this.rooms[sessionId] = room;
    const rec = this.conns.get(eioSid);
    if (rec) {
      rec.roomSessionId = sessionId;
      rec.playerId = playerId;
    }
    this.broadcastRoomSio(sessionId, `2${JSON.stringify(['users-updated', room.players])}`);
    this.sendAck(eioSid, ackId, null);
  }

  /**
   * @param {string} eioSid
   * @param {unknown[]} args
   * @param {number | null} ackId
   */
  handleJoinRoom(eioSid, args, ackId) {
    const data = /** @type {Record<string, unknown>} */ (args[0] || {});
    const extra = /** @type {Record<string, unknown>} */ (data.extra || {});
    const sessionId = extra.sessionid != null ? String(extra.sessionid) : '';
    const playerId = extra.userid != null ? String(extra.userid) : '';
    const playerName = extra.player_name != null ? String(extra.player_name) : 'Unknown';
    if (!sessionId || !playerId) {
      this.sendAck(eioSid, ackId, 'Invalid data: sessionId and playerId required');
      return;
    }
    const room = this.rooms[sessionId];
    if (!room) {
      this.sendAck(eioSid, ackId, 'Room not found');
      return;
    }
    const roomPassword = /** @type {string | null} */ (data.password) || null;
    if (room.password && room.password !== roomPassword) {
      this.sendAck(eioSid, ackId, 'Incorrect password');
      return;
    }
    if (Object.keys(room.players).length >= room.maxPlayers) {
      this.sendAck(eioSid, ackId, 'Room full');
      return;
    }
    room.players[playerId] = { ...extra, socketId: eioSid, player_name: playerName };
    const rec = this.conns.get(eioSid);
    if (rec) {
      rec.roomSessionId = sessionId;
      rec.playerId = playerId;
    }
    this.broadcastRoomSio(sessionId, `2${JSON.stringify(['users-updated', room.players])}`);
    this.sendAck(eioSid, ackId, null, room.players);
  }

  /**
   * @param {string} eioSid
   * @param {unknown[]} args
   */
  handleWebRtcSignal(eioSid, args) {
    const data = /** @type {Record<string, unknown>} */ (args[0] || {});
    const target = data.target != null ? String(data.target) : '';
    const candidate = data.candidate;
    const offer = data.offer;
    const answer = data.answer;
    const requestRenegotiate = !!data.requestRenegotiate;
    try {
      if (!target && !requestRenegotiate) return;
      if (requestRenegotiate) {
        const targetWs = this.conns.get(target)?.ws;
        if (targetWs && targetWs.readyState === WebSocket.OPEN) {
          const inner = `2${JSON.stringify([
            'webrtc-signal',
            { sender: eioSid, requestRenegotiate: true },
          ])}`;
          targetWs.send(`4${inner}`);
        }
      } else {
        const targetWs = this.conns.get(target)?.ws;
        if (targetWs && targetWs.readyState === WebSocket.OPEN) {
          const inner = `2${JSON.stringify([
            'webrtc-signal',
            { sender: eioSid, candidate, offer, answer },
          ])}`;
          targetWs.send(`4${inner}`);
        }
      }
    } catch (_) {}
  }

  /**
   * @param {string} eioSid
   * @param {unknown[]} args
   */
  handleDataMessage(eioSid, args) {
    const rec = this.conns.get(eioSid);
    const sessionId = rec?.roomSessionId;
    if (!sessionId) return;
    const inner = `2${JSON.stringify(['data-message', args[0]])}`;
    this.broadcastRoomOthersSio(sessionId, eioSid, inner);
  }

  /**
   * @param {string} eioSid
   * @param {unknown[]} args
   */
  handleSnapshot(eioSid, args) {
    const rec = this.conns.get(eioSid);
    const sessionId = rec?.roomSessionId;
    if (!sessionId) return;
    const inner = `2${JSON.stringify(['snapshot', args[0]])}`;
    this.broadcastRoomOthersSio(sessionId, eioSid, inner);
  }

  /**
   * @param {string} eioSid
   * @param {unknown[]} args
   */
  handleInput(eioSid, args) {
    const rec = this.conns.get(eioSid);
    const sessionId = rec?.roomSessionId;
    if (!sessionId) return;
    const inner = `2${JSON.stringify(['input', args[0]])}`;
    this.broadcastRoomOthersSio(sessionId, eioSid, inner);
  }
}
