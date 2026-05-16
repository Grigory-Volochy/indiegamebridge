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

function buildTwitchOptOutUrl(): string {
    // finalize-login with action=optout performs the opt-out (reads Twitch ID,
    // clears session) instead of minting JWT, then redirects to ?status=done.
    const finalize = `/auth/finalize-login/?action=optout&next=${encodeURIComponent("/optout?status=done")}`;
    return `/accounts/twitch/login/?process=login&next=${encodeURIComponent(finalize)}`;
}

export default async function OptOutPage({ searchParams }: { searchParams: Promise<{ status?: string }>; }) {
    const { status } = await searchParams;

    if (status === "done") {
        return <OptOutSuccess />;
    }

    const user = await getCurrentUser();
    const twitchLoginUrl = buildTwitchOptOutUrl();

    return (
        <main className="flex-1 px-6">
            <div className="max-w-md mx-auto py-24">
                <h1 className="text-2xl font-bold mb-6 text-center">Opt Out</h1>
                {user ? (user.is_twitch_excluded ? (
                        <Fragment>
                            <div>You already requested the opt out, and we have successfully handled it. No actions required - we do not collect or store any information about your streams anymore.</div>
                            <Link
                                href="/"
                                className="block text-center text-blue-500 hover:text-blue-400 underline"
                            >
                                Return to Home Page
                            </Link>
                        </Fragment>
                    ) : (
                        <Fragment>
                            <p className="text-gray-600 mb-8 text-center">Want to opt out? By clicking the button below you confirm that you want to remove all related data to your Twitch ID from our database - for further we will exclude any data related to your Twitch ID from collecting.</p>
                            <OptOutButton />
                        </Fragment>
                    )
                ) : (
                    <Fragment>
                        <p className="text-gray-600 mb-8 text-center">Want to opt out? After clicking the button below, you will be asked to log in with your Twitch account, thus we can verify your Twich ID and remove all related data from our database - for further we will exclude any data related to your Twitch ID from collecting.</p>
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
                            <span>Log in with Twitch to verify your Twitch ID</span>
                        </a>
                    </Fragment>
                )}
            </div>
        </main>
    );
}
