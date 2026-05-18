"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Fragment } from "react/jsx-runtime";

type OptOutSuccessContent = {
    title: string;
    return_home: string;
    already_optout: string;
    success_optout: string;
};

export function OptOutSuccess({ content, isNewOptOut }: { content: OptOutSuccessContent; isNewOptOut?: string; }) {
    // Strip ?status=done so a refresh shows the default opt-out view rather
    // than the success message again — we deliberately keep no client-side
    // flag so the success copy only renders during this one navigation.
    useEffect(() => {
        window.history.replaceState(null, "", "/optout");
    }, []);

    return (
        <main className="flex-1 px-6">
            <div className="max-w-md mx-auto py-24">
                <h1 className="text-2xl font-bold mb-6 text-center">{content.title}</h1>
                {isNewOptOut === 'yes'
                    ? <p className="text-gray-600 mb-8 text-center">{content.success_optout}</p>
                    : <Fragment>
                            <div>{content.already_optout}</div>
                        </Fragment>
                }
                <Link href="/"className="block text-center text-blue-700 hover:text-blue-500 underline">
                    {content.return_home}
                </Link>
            </div>
        </main>
    );
}
