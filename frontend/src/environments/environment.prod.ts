// Build de production (Docker) : appels relatifs, proxifiés par nginx vers
// les conteneurs api (HTTP) et ws (WebSocket) — voir frontend/nginx.conf.
const hoteWs = typeof window !== 'undefined'
  ? `${window.location.protocol === 'https:' ? 'wss://' : 'ws://'}${window.location.host}`
  : '';

export const environment = {
  production: true,
  apiUrl: '/api',
  wsUrl: `${hoteWs}/ws`,
};
