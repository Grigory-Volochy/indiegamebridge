import { cookies } from "next/headers";

export type CurrentUser = {
    id: number;
    username: string;
    display_name: string;
    email: string;
};

export async function getCurrentUser(): Promise<CurrentUser | null> {
    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    const cookieHeader = (await cookies()).toString();
    if (!cookieHeader) {
        return null;
    }

    // Fail soft: a backend outage or a 4xx shouldn't take down pages that
    // happen to call this. The page just renders in logged-out state.
    try {
        const response = await fetch(`${apiBase}/auth/me/`, {
            headers: { cookie: cookieHeader },
            cache: "no-store",
        });
        if (!response.ok) {
            return null;
        }
        return await response.json();
    } catch {
        return null;
    }
}
