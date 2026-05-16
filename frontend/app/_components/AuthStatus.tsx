"use client";

import { useRouter } from "next/navigation";

export type AuthStatusProps = {
    user: {
        twitch_id: number;
        username: string;
        display_name: string;
        email: string;
    } | null;
};

function readCookie(name: string): string {
    const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : "";
}

export function AuthStatus({ user }: AuthStatusProps) {
    const router = useRouter();

    if (!user) {
        return (
            <a href="/login" className="text-sm underline hover:opacity-80">
                Log in
            </a>
        );
    }

    async function handleLogout() {
        await fetch("/auth/logout/", {
            method: "POST",
            credentials: "include",
            headers: { "X-CSRFToken": readCookie("csrftoken") },
        });
        router.refresh();
    }

    return (
        <div className="text-sm flex items-center gap-3">
            <span className="opacity-80">Hi, {user.display_name}</span>
            <button
                type="button"
                onClick={handleLogout}
                className="underline hover:opacity-80 cursor-pointer"
            >
                Log out
            </button>
        </div>
    );
}
