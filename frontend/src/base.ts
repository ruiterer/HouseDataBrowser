// Runtime prefix detection (D-022 point 7): one build must work both
// directly on its own port ("/") and behind the hub proxy prefix
// ("/t/housedata/..."). The hub strips the prefix server-side, so only
// browser-facing URLs (router paths, API calls) need it.
const KNOWN_ROUTES = ["/dashboard", "/schema"];

function detectBase(): string {
  let path = window.location.pathname;
  for (const route of KNOWN_ROUTES) {
    if (path.endsWith(route)) {
      path = path.slice(0, path.length - route.length);
      break;
    }
  }
  return path.replace(/\/+$/, "");
}

/** URL prefix the app is served under ("" when served at the root). */
export const BASE = detectBase();

/** Basename for the router ("/" when served at the root). */
export const ROUTER_BASENAME = BASE || "/";

/** Prefix an absolute-style API path ("/api/...") with the runtime base. */
export function apiUrl(path: string): string {
  return BASE + path;
}
