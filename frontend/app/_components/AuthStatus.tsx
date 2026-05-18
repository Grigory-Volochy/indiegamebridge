"use client";

import { useRouter } from "next/navigation";
import { Fragment } from "react/jsx-runtime";

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

    async function handleLogout() {
        await fetch("/auth/logout/", {
            method: "POST",
            credentials: "include",
            headers: { "X-CSRFToken": readCookie("csrftoken") },
        });
        router.refresh();
    }

    return (
        <div className="flex gap-x-8 gap-y-2 flex-col md:flex-row lg:flex-row items-end">
            {!user
                ? <a href="/login" className="underline hover:opacity-80 cursor-pointer text-blue-500 hover:text-white">Log in</a>
                : <Fragment>
                        <span className="opacity-80">Hi, {user.display_name}</span>
                        <button type="button" onClick={handleLogout} className="text-white cursor-pointer hover:underline">Log out</button>
                    </Fragment>
            }
        </div>
    );
}
