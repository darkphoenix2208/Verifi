const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function _buildWsUrl(path: string): string {
  const url = new URL(API_BASE_URL);
  const wsProtocol = url.protocol === "https:" ? "wss:" : "ws:";
  return `${wsProtocol}//${url.host}${path}`;
}

// --- Core Banking live transaction stream ---
export function getTransactionsWsUrl(): string {
  return _buildWsUrl("/api/transactions/live");
}

export function connectTransactionsSocket(): WebSocket {
  return new WebSocket(getTransactionsWsUrl());
}

// --- Crypto Radar (real mempool) ---
export function getCryptoRadarWsUrl(): string {
  return _buildWsUrl("/api/ws/crypto/radar");
}

export function connectCryptoRadarSocket(): WebSocket {
  return new WebSocket(getCryptoRadarWsUrl());
}

// --- Crypto Radar (demo mode) ---
export function getCryptoRadarDemoWsUrl(): string {
  return _buildWsUrl("/api/ws/crypto/radar/demo");
}

export function connectCryptoRadarDemoSocket(): WebSocket {
  return new WebSocket(getCryptoRadarDemoWsUrl());
}
