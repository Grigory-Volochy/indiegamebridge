"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

function readCookie(name: string): string {
    const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
    return match ? decodeURIComponent(match[1]) : "";
}

export function OptOutButton() {
    const router = useRouter();
    const [pending, setPending] = useState(false);

    async function handleOptOut() {
        setPending(true);
        await fetch("/auth/optout/", {
            method: "POST",
            credentials: "include",
            headers: { "X-CSRFToken": readCookie("csrftoken") },
        });
        router.replace("/optout?status=done");
    }

    return (
        <button
            type="button"
            onClick={handleOptOut}
            disabled={pending}
            className="flex items-center justify-center gap-3 px-6 py-3 bg-red-600 text-white font-medium rounded hover:bg-red-700 border border-red-600 hover:border-red-700 w-full disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
        >
            Opt Out
        </button>
    );
}
