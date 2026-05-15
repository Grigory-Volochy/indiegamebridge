import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Log in — IndieGameBridge",
    robots: { index: false, follow: false },
};

export default function LoginPage() {
    return (
        <main className="flex-1 px-6">
            <div className="max-w-md mx-auto py-24 text-center">
                <h1 className="text-2xl font-bold mb-4">Log in</h1>
                <p className="text-gray-600">
                    Authentication is coming soon. You&apos;ll be able to sign in with Twitch to search streamers and view their profiles.
                </p>
            </div>
        </main>
    );
}
