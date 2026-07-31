/**
 * Resolves the backend API base URL dynamically at runtime.
 *
 * Cloudflare Tunnel & Production Deployment Aware:
 * 1. If process.env.NEXT_PUBLIC_API_BASE_URL is explicitly set (e.g. https://scripts-rail-chapel-income.trycloudflare.com),
 *    returns that exact HTTPS tunnel URL.
 * 2. In browser environments (typeof window !== "undefined"):
 *    - If accessed over local LAN IP or hostname (192.168.x.x, 10.x.x.x, .local),
 *      dynamically uses the browser's hostname (http://192.168.x.x:8000) for zero-config LAN testing.
 * 3. Default fallback for SSR or local development: "http://localhost:8000".
 */
export function getApiBaseUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim().replace(/\/+$/, "");
  if (envUrl && envUrl.length > 0) {
    return envUrl;
  }

  if (typeof window !== "undefined" && window.location && window.location.hostname) {
    const hostname = window.location.hostname;
    const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
    const isLanIp = /^192\.168\.|^10\.|^172\.(1[6-9]|2\d|3[01])\.|.+\.local$/i.test(hostname);

    if (isLanIp) {
      const protocol = window.location.protocol;
      return `${protocol}//${hostname}:8000`;
    }

    if (isLocalhost) {
      return "http://localhost:8000";
    }
  }

  return "http://localhost:8000";
}

/**
 * Dynamic string wrapper for API_BASE_URL so legacy string references evaluate getApiBaseUrl() at runtime.
 */
export const API_BASE_URL = {
  toString(): string {
    return getApiBaseUrl();
  },
  valueOf(): string {
    return getApiBaseUrl();
  },
};
