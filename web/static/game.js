/* ================================================================== */
/*  Chess Web App — Vanilla JS client                                  */
/* ================================================================== */

'use strict';

// ---------------------------------------------------------------------------
// Piece Unicode glyphs
// ---------------------------------------------------------------------------
const GLYPHS = {
  WHITE: { KING:'♔', QUEEN:'♕', ROOK:'♖', BISHOP:'♗', KNIGHT:'♘', PAWN:'♙' },
  BLACK: { KING:'♚', QUEEN:'♛', ROOK:'♜', BISHOP:'♝', KNIGHT:'♞', PAWN:'♟' },
};

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------
const boardEl       = document.getElementById('board');
const statusEl      = document.getElementById('status-text');
const moveListEl    = document.getElementById('move-list');
const resignBtn     = document.getElementById('resign-btn');
const newGameBtn    = document.getElementById('new-game-btn');
const modeSelect    = document.getElementById('mode-select');
const evalSelect    = document.getElementById('eval-select');
const depthRange    = document.getElementById('depth-range');
const depthLabel    = document.getElementById('depth-label');
const promoOverlay  = document.getElementById('promo-overlay');
const promoChoices  = document.getElementById('promo-choices');

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let sessionId    = null;
let ws           = null;
let gameState    = null;   // latest state dict from server
let selected     = null;   // currently selected square index
let legalFrom    = {};     // from_sq → [Move, …]
let lastMove     = null;   // {from, to}
let promoResolve = null;   // Promise resolve for promotion dialog
let playerColor  = 'WHITE';// which side the human controls (for HvC)

// ---------------------------------------------------------------------------
// Board rendering
// ---------------------------------------------------------------------------
function renderBoard(state) {
  if (!state) return;

  const pieceMap = {};
  for (const p of state.board) {
    pieceMap[p.square] = p;
  }

  // Build legalFrom index
  legalFrom = {};
  for (const m of state.legal_moves) {
    if (!legalFrom[m.from]) legalFrom[m.from] = [];
    legalFrom[m.from].push(m);
  }

  boardEl.innerHTML = '';

  for (let sq = 0; sq < 64; sq++) {
    const row = Math.floor(sq / 8);
    const col = sq % 8;
    const isLight = (row + col) % 2 === 0;

    const sqEl = document.createElement('div');
    sqEl.className = 'sq ' + (isLight ? 'light' : 'dark');
    sqEl.dataset.sq = sq;

    // Rank label (leftmost column)
    if (col === 0) {
      const lbl = document.createElement('span');
      lbl.className = 'rank-label';
      lbl.textContent = String(8 - row);
      sqEl.appendChild(lbl);
    }
    // File label (bottom row)
    if (row === 7) {
      const lbl = document.createElement('span');
      lbl.className = 'file-label';
      lbl.textContent = 'abcdefgh'[col];
      sqEl.appendChild(lbl);
    }

    // Highlights
    if (selected === sq) sqEl.classList.add('selected');

    if (lastMove) {
      if (sq === lastMove.from || sq === lastMove.to) sqEl.classList.add('last-move');
    }

    // King in check
    if (state.in_check) {
      const kingSq = findKing(state, state.turn);
      if (sq === kingSq) sqEl.classList.add('in-check');
    }

    // Legal-move indicators
    if (selected !== null && legalFrom[selected]) {
      const targets = legalFrom[selected].map(m => m.to);
      if (targets.includes(sq)) {
        if (pieceMap[sq]) {
          sqEl.classList.add('capture-ring');
        } else {
          const dot = document.createElement('div');
          dot.className = 'move-dot';
          sqEl.appendChild(dot);
        }
      }
    }

    // Piece
    if (pieceMap[sq]) {
      const { color, type } = pieceMap[sq];
      const piece = document.createElement('span');
      piece.className = 'piece';
      piece.textContent = GLYPHS[color][type];
      sqEl.appendChild(piece);
    }

    sqEl.addEventListener('click', onSquareClick);
    boardEl.appendChild(sqEl);
  }
}

function findKing(state, color) {
  for (const p of state.board) {
    if (p.color === color && p.type === 'KING') return p.square;
  }
  return -1;
}

// ---------------------------------------------------------------------------
// Click handling
// ---------------------------------------------------------------------------
async function onSquareClick(evt) {
  if (!gameState || gameState.result !== 'ongoing') return;
  // Only allow clicks when it's the human's turn
  if (!isHumanTurn()) return;

  const sq = parseInt(evt.currentTarget.dataset.sq, 10);

  if (selected === null) {
    // Select a piece that belongs to current side
    const piece = getPieceAt(sq);
    if (piece && piece.color === gameState.turn) {
      selected = sq;
      renderBoard(gameState);
    }
    return;
  }

  // Already have a selection
  if (selected === sq) {
    // Deselect
    selected = null;
    renderBoard(gameState);
    return;
  }

  // Check if clicking own piece (re-select)
  const targetPiece = getPieceAt(sq);
  if (targetPiece && targetPiece.color === gameState.turn) {
    selected = sq;
    renderBoard(gameState);
    return;
  }

  // Try to find a legal move from selected → sq
  const moves = (legalFrom[selected] || []).filter(m => m.to === sq);
  if (moves.length === 0) {
    selected = null;
    renderBoard(gameState);
    return;
  }

  let chosenMove = moves[0];

  // Promotion?
  if (moves.some(m => m.promotion)) {
    const piece = getPieceAt(selected);
    const promoType = await askPromotion(piece.color);
    if (!promoType) { selected = null; renderBoard(gameState); return; }
    chosenMove = moves.find(m => m.promotion === promoType) || moves[0];
  }

  sendMove(selected, sq, chosenMove.promotion || null);
  selected = null;
}

function getPieceAt(sq) {
  if (!gameState) return null;
  return gameState.board.find(p => p.square === sq) || null;
}

function isHumanTurn() {
  if (!gameState) return false;
  if (gameState.result !== 'ongoing') return false;
  // In HvH both sides are always human
  const mode = sessionStorage.getItem('mode') || 'hvh';
  if (mode === 'hvh') return true;
  if (mode === 'cvc') return false;
  // HvC: human plays black? no — human is always White in hvc
  return gameState.turn === 'WHITE';
}

// ---------------------------------------------------------------------------
// Promotion dialog
// ---------------------------------------------------------------------------
function askPromotion(color) {
  return new Promise(resolve => {
    promoResolve = resolve;
    promoChoices.innerHTML = '';
    for (const type of ['QUEEN', 'ROOK', 'BISHOP', 'KNIGHT']) {
      const btn = document.createElement('button');
      btn.className = 'promo-btn';
      btn.textContent = GLYPHS[color][type];
      btn.title = type;
      btn.addEventListener('click', () => {
        closePromo();
        resolve(type);
      });
      promoChoices.appendChild(btn);
    }
    promoOverlay.classList.add('active');
  });
}

function closePromo() {
  promoOverlay.classList.remove('active');
  promoResolve = null;
}

promoOverlay.addEventListener('click', (e) => {
  if (e.target === promoOverlay) {
    closePromo();
    if (promoResolve) promoResolve(null);
  }
});

// ---------------------------------------------------------------------------
// WebSocket communication
// ---------------------------------------------------------------------------
function connectWS(sid) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const url   = `${proto}://${location.host}/ws/${sid}`;
  ws = new WebSocket(url);

  ws.onopen    = () => setStatus('Connected — game started.');
  ws.onclose   = () => setStatus('Connection closed.');
  ws.onerror   = () => setStatus('WebSocket error.');
  ws.onmessage = (evt) => handleMessage(JSON.parse(evt.data));
}

function handleMessage(msg) {
  switch (msg.type) {
    case 'state':
      gameState = msg.state;
      renderBoard(gameState);
      updateInfo(gameState);
      break;

    case 'ai_thinking':
      setStatus('AI is thinking…');
      break;

    case 'ai_move':
      lastMove = { from: msg.from_sq, to: msg.to_sq };
      setStatus(`AI played ${msg.uci || ''}`);
      break;

    case 'game_over':
      handleGameOver(msg);
      break;

    case 'error':
      setStatus('Error: ' + msg.message, true);
      break;

    case 'pong':
      break;

    default:
      console.warn('Unknown message type:', msg.type);
  }
}

function sendMove(fromSq, toSq, promotion) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  lastMove = { from: fromSq, to: toSq };
  ws.send(JSON.stringify({ type: 'move', from_sq: fromSq, to_sq: toSq, promotion }));
}

function sendResign() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const color = gameState?.turn?.toLowerCase() || 'white';
  ws.send(JSON.stringify({ type: 'resign', color }));
}

// ---------------------------------------------------------------------------
// Game lifecycle
// ---------------------------------------------------------------------------
async function startNewGame() {
  // Cleanup old WS
  if (ws) { ws.close(); ws = null; }

  const mode  = modeSelect.value;
  const ev    = evalSelect.value;
  const depth = parseInt(depthRange.value, 10);

  sessionStorage.setItem('mode', mode);

  const body = { mode, black_depth: depth };
  if (mode === 'cvc') {
    body.white_evaluator = 'positional';
    body.black_evaluator = ev;
    body.white_depth = depth;
  } else if (mode === 'hvc') {
    body.black_evaluator = ev;
  }

  try {
    const res = await fetch('/api/new_game', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    sessionId = data.session_id;

    selected  = null;
    lastMove  = null;
    gameState = null;
    moveListEl.innerHTML = '';

    resignBtn.style.display = mode === 'hvh' || mode === 'hvc' ? 'block' : 'none';

    connectWS(sessionId);
  } catch (err) {
    setStatus('Failed to start game: ' + err.message, true);
  }
}

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------
function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? '#e94560' : '';
}

function updateInfo(state) {
  const mode = sessionStorage.getItem('mode') || 'hvh';

  if (state.result === 'ongoing') {
    const turnText = state.turn === 'WHITE' ? 'White' : 'Black';
    const checkText = state.in_check ? ' (in check!)' : '';
    setStatus(`${turnText} to move${checkText}`);
  }

  // Append latest move to move list
  const history = state.move_history || [];
  if (history.length > 0) {
    const latest = history[history.length - 1];
    const moveNum = Math.ceil(history.length / 2);
    const li = document.createElement('li');
    li.textContent = history.length % 2 === 1
      ? `${moveNum}. ${latest}`
      : `${latest}`;
    moveListEl.appendChild(li);
    moveListEl.scrollTop = moveListEl.scrollHeight;
  }
}

function handleGameOver(msg) {
  let text = '';
  switch (msg.result) {
    case 'white': text = 'White wins!'; break;
    case 'black': text = 'Black wins!'; break;
    case 'draw':  text = `Draw (${msg.reason || 'agreed'})`; break;
    default:      text = 'Game over';
  }
  setStatus(text);
  resignBtn.style.display = 'none';
}

// ---------------------------------------------------------------------------
// Evaluator options (populated from server)
// ---------------------------------------------------------------------------
async function loadEvaluators() {
  try {
    const res  = await fetch('/api/evaluators');
    const data = await res.json();
    evalSelect.innerHTML = '';
    for (const name of data.evaluators) {
      const opt = document.createElement('option');
      opt.value = name;
      opt.textContent = name.charAt(0).toUpperCase() + name.slice(1);
      if (name === 'positional') opt.selected = true;
      evalSelect.appendChild(opt);
    }
  } catch (_) {
    // Fallback options if server not reachable yet
    evalSelect.innerHTML = '<option value="positional">Positional</option><option value="material">Material</option>';
  }
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------
newGameBtn.addEventListener('click', startNewGame);
resignBtn.addEventListener('click', sendResign);

depthRange.addEventListener('input', () => {
  depthLabel.textContent = depthRange.value;
});

modeSelect.addEventListener('change', () => {
  const mode = modeSelect.value;
  const aiOpts = document.getElementById('ai-options');
  if (aiOpts) aiOpts.style.display = mode === 'hvh' ? 'none' : 'flex';
});

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
(async function init() {
  await loadEvaluators();
  // Trigger initial visibility of AI options
  modeSelect.dispatchEvent(new Event('change'));
})();
