"use client";

import { useEffect } from "react";
import Link from "next/link";

export function OptOutSuccess() {
    // Strip ?status=done so a refresh shows the default opt-out view rather
    // than the success message again — we deliberately keep no client-side
    // flag so the success copy only renders during this one navigation.
    useEffect(() => {
        window.history.replaceState(null, "", "/optout");
    }, []);

    return (
        <main className="flex-1 px-6">
            <div className="max-w-md mx-auto py-24">
                <h1 className="text-2xl font-bold mb-6 text-center">Opt Out</h1>
                <p className="text-gray-600 mb-8 text-center">
                    We have verified your Twitch ID and we removed all data related to your Twitch ID. From now we exclude all the data collections related to your Twitch ID. The public page may still show your data for up to an hour due to cached data.
                </p>
                <Link
                    href="/"
                    className="block text-center text-blue-500 hover:text-blue-400 underline"
                >
                    Return to Home Page
                </Link>
            </div>
        </main>
    );
}
