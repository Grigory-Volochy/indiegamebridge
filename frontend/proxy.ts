import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const ACCESS_COOKIE = "ig_access";
const REFRESH_COOKIE = "ig_refresh";
const CSRF_COOKIE = "csrftoken";

const API_BASE = process.env.API_BASE_URL ?? "http://localhost:8000";
const FRONTEND_URL = process.env.FRONTEND_URL ?? "http://localhost:3000";

function extractCookieNameValue(setCookie: string): { name: string; value: string } | null {
    const firstSegment = setCookie.split(";")[0];
    const eq = firstSegment.indexOf("=");
    if (eq <= 0) return null;
    return { name: firstSegment.slice(0, eq).trim(), value: firstSegment.slice(eq + 1).trim() };
}

function rebuildCookieHeader(original: string, overrides: Map<string, string>): string {
    const parts = original ? original.split(";").map((p) => p.trim()).filter(Boolean) : [];
    const seen = new Set<string>();
    const merged: string[] = [];
    for (const part of parts) {
        const eq = part.indexOf("=");
        if (eq <= 0) continue;
        const name = part.slice(0, eq);
        seen.add(name);
        if (overrides.has(name)) {
            merged.push(`${name}=${overrides.get(name)}`);
        } else {
            merged.push(part);
        }
    }
    for (const [name, value] of overrides) {
        if (!seen.has(name)) merged.push(`${name}=${value}`);
    }
    return merged.join("; ");
}

export async function proxy(request: NextRequest) {
    // Skip our own auth endpoints to avoid recursion: refreshing on a refresh
    // request would consume the rotated token twice, and finalize-login is the
    // view that issues fresh cookies in the first place. Also skip allauth's
    // OAuth dance for the same reason.
    if (request.nextUrl.pathname.startsWith("/auth/") || request.nextUrl.pathname.startsWith("/accounts/")) {
        return NextResponse.next();
    }

    // Access token still present (or user has neither) - nothing to do.
    if (request.cookies.has(ACCESS_COOKIE)) {
        return NextResponse.next();
    }
    const refresh = request.cookies.get(REFRESH_COOKIE);
    if (!refresh) {
        return NextResponse.next();
    }

    const csrf = request.cookies.get(CSRF_COOKIE);
    const upstreamCookies = [`${REFRESH_COOKIE}=${refresh.value}`];
    if (csrf) upstreamCookies.push(`${CSRF_COOKIE}=${csrf.value}`);

    // TODO: race condition - if multiple tabs hit this at the same moment the access cookie expires, the first refresh
    // consumes the refresh token (BLACKLIST_AFTER_ROTATION) and the rest get 401 here, rendering logged-out until re-login.
    // Fix later via single-flight refresh (shared cache lock by refresh-token JTI) or a brief blacklist grace window on the backend.
    const refreshResp = await fetch(`${API_BASE}/auth/token/refresh/`, {
        method: "POST",
        headers: {
            cookie: upstreamCookies.join("; "),
            ...(csrf ? { "X-CSRFToken": csrf.value } : {}),
            // CSRF middleware accepts requests whose Origin matches CSRF_TRUSTED_ORIGINS.
            origin: FRONTEND_URL,
        },
    });

    if (!refreshResp.ok) {
        // Refresh failed (expired/blacklisted). Wipe the stale refresh cookie and let the downstream render in logged-out state; user re-logs in.
        const response = NextResponse.next();
        response.cookies.delete(REFRESH_COOKIE);
        return response;
    }

    const setCookieHeaders = refreshResp.headers.getSetCookie();
    const overrides = new Map<string, string>();
    for (const sc of setCookieHeaders) {
        const parsed = extractCookieNameValue(sc);
        if (parsed) overrides.set(parsed.name, parsed.value);
    }

    // Override the Cookie header for downstream rendering so getCurrentUser() sees the freshly minted access token within the same request cycle.
    const newCookieHeader = rebuildCookieHeader(request.headers.get("cookie") ?? "", overrides);
    const requestHeaders = new Headers(request.headers);
    requestHeaders.set("cookie", newCookieHeader);

    const response = NextResponse.next({ request: { headers: requestHeaders } });

    // Forward Set-Cookie from Django to the browser so subsequent requests carry the rotated tokens.
    for (const sc of setCookieHeaders) {
        response.headers.append("set-cookie", sc);
    }
    return response;
}

export const config = {
    matcher: [
        // Run on every page/api request except Next internals and static files.
        "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)",
    ],
};
