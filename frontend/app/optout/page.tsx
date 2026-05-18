import type { Metadata } from "next";
import { getCurrentUser } from "../_lib/auth";
import { OptOutButton } from "./_components/OptOutButton";
import { OptOutSuccess } from "./_components/OptOutSuccess";
import { Fragment } from "react/jsx-runtime";
import Link from "next/link";

export const metadata: Metadata = {
    title: "Opt out — IndieGameBridge",
    robots: { index: false, follow: false },
};

export type OptOutPageContent = {
    title: string;
    return_home: string;
    not_logged_in: { prompt: string; login_btn: string };
    logged_in: { prompt: string; optout_btn: string };
    already_optout: string;
    success_optout: string;
};

function buildTwitchOptOutUrl(): string {
    // finalize-login with action=optout performs the opt-out (reads Twitch ID,
    // clears session) instead of minting JWT, then redirects to ?status=done.
    const finalize = `/auth/finalize-login/?action=optout&next=${encodeURIComponent("/optout?status=done")}`;
    return `/accounts/twitch/login/?process=login&next=${encodeURIComponent(finalize)}`;
}

export default async function OptOutPage({ searchParams }: { searchParams: Promise<{ status?: string; new?: string; }>; }) {
    const { status, new: isNewOptOut } = await searchParams;

    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    const [response, user] = await Promise.all([
        fetch(`${apiBase}/pages/optout/`),
        getCurrentUser(),
    ]);

    if (!response.ok) {
        throw new Error(`Failed to load opt-out page content (status ${response.status})`);
    }

    const content: OptOutPageContent = await response.json();

    if (status === "done") {
        return isNewOptOut ? <OptOutSuccess content={content} isNewOptOut={isNewOptOut} /> : <OptOutSuccess content={content} />;
    }

    const twitchLoginUrl = buildTwitchOptOutUrl();

    return (
        <main className="flex-1 px-6">
            <div className="max-w-md mx-auto py-24">
                <h1 className="text-2xl font-bold mb-6 text-center">{content.title}</h1>
                {user
                    ? (user.is_twitch_excluded
                        ? (
                            <Fragment>
                                <div>{content.already_optout}</div>
                                <Link href="/" className="block text-center text-blue-700 hover:text-blue-500 underline">{content.return_home}</Link>
                            </Fragment>
                        ) : (
                            <Fragment>
                                <p className="text-gray-600 mb-8 text-center">{content.logged_in.prompt}</p>
                                <OptOutButton label={content.logged_in.optout_btn} />
                            </Fragment>
                        )
                    ) : (
                        <Fragment>
                            <p className="text-gray-600 mb-8 text-center">{content.not_logged_in.prompt}</p>
                            <a href={twitchLoginUrl} className="flex items-center justify-center gap-3 px-6 py-3 bg-twitch-brand text-white font-medium rounded hover:bg-twitch-brand-dark border border-twitch-brand hover:border-twitch-brand-dark w-full">
                                <svg aria-hidden="true" viewBox="0 0 24 24" className="w-5 h-5 fill-current">
                                    <path d="M4.265 0L1 3.265v17.47h5.47V24h3.265l3.265-3.265h5.47L24 14.47V0H4.265zm17.47 13.265L18.47 16.53h-5.47l-3.265 3.265V16.53H5.47V2.265h16.265v11zm-5.47-6.53h-2.265v6.53h2.265v-6.53zm-5.47 0H8.53v6.53h2.265v-6.53z" />
                                </svg>
                                <span>{content.not_logged_in.login_btn}</span>
                            </a>
                        </Fragment>
                    )
                }
            </div>
        </main>
    );
}
