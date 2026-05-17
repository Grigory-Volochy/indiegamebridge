import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "Log in — IndieGameBridge",
    robots: { index: false, follow: false },
};

export type LoginPageContent = {
    title: string;
    prompt: string;
    twitch_login_btn: string;
    more_options_note: string;
};

function buildTwitchLoginUrl(rawNext: string | undefined): string {
    // Only forward a same-app path through the OAuth dance - never an absolute URL.
    const next = rawNext && rawNext.startsWith("/") && !rawNext.startsWith("//") ? rawNext : "/";
    const finalize = `/auth/finalize-login/?next=${encodeURIComponent(next)}`;
    return `/accounts/twitch/login/?process=login&next=${encodeURIComponent(finalize)}`;
}

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }>; }) {
    const { next } = await searchParams;
    const twitchLoginUrl = buildTwitchLoginUrl(next);

    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    const response = await fetch(`${apiBase}/pages/login/`);

    if (!response.ok) {
        throw new Error(`Failed to load login page content (status ${response.status})`);
    }

    const content: LoginPageContent = await response.json();

    return (
        <main className="flex-1 px-6">
            <div className="max-w-md mx-auto py-24">
                <h1 className="text-2xl font-bold mb-6 text-center">{content.title}</h1>
                <p className="text-gray-600 mb-8 text-center">{content.prompt}</p>
                <a
                    href={twitchLoginUrl}
                    className="flex items-center justify-center gap-3 px-6 py-3 bg-twitch-brand text-white font-medium rounded hover:bg-twitch-brand-dark border border-twitch-brand hover:border-twitch-brand-dark w-full"
                >
                    <svg
                        aria-hidden="true"
                        viewBox="0 0 24 24"
                        className="w-5 h-5 fill-current"
                    >
                        <path d="M4.265 0L1 3.265v17.47h5.47V24h3.265l3.265-3.265h5.47L24 14.47V0H4.265zm17.47 13.265L18.47 16.53h-5.47l-3.265 3.265V16.53H5.47V2.265h16.265v11zm-5.47-6.53h-2.265v6.53h2.265v-6.53zm-5.47 0H8.53v6.53h2.265v-6.53z" />
                    </svg>
                    <span>{content.twitch_login_btn}</span>
                </a>
                <p className="text-xs text-gray-500 mt-8 text-center">{content.more_options_note}</p>
            </div>
        </main>
    );
}
