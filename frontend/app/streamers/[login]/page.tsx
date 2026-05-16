import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getCurrentUser } from "../../_lib/auth";

export const metadata: Metadata = {
    robots: { index: false, follow: false },
};

export default async function StreamerProfilePage({ params }: { params: Promise<{ login: string }>; }) {
    const { login } = await params;
    const user = await getCurrentUser();
    if (!user) {
        redirect(`/login?next=${encodeURIComponent(`/streamers/${login}`)}`);
    }

    return (
        <main className="flex-1 px-6">
            <div className="max-w-2xl mx-auto py-16">
                <h1 className="text-2xl font-bold mb-4">Streamer: {login}</h1>
                <p className="text-gray-600">
                    Detailed streamer profile is coming soon. The data source and caching
                    strategy are still being decided.
                </p>
            </div>
        </main>
    );
}
