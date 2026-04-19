const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export function getTransactionsWsUrl(): string {
  const url = new URL(API_BASE_URL);
  const wsProtocol = url.protocol === "https:" ? "wss:" : "ws:";
  return `${wsProtocol}//${url.host}/api/transactions/live`;
}

export function connectTransactionsSocket(): WebSocket {
  return new WebSocket(getTransactionsWsUrl());
}
