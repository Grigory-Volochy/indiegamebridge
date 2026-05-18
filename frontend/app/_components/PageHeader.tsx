"use client";

import Link from "next/link";
import { CurrentUser } from "../_lib/auth";
import { AuthStatus } from "./AuthStatus";

export type PageHeaderContent = {
    title: string;
    description: string;
    info: string;
};

export function PageHeader({ user, content }: { user: CurrentUser | null; content: PageHeaderContent; } ) {
    return (
        <header className="pb-12 bg-brand-blue text-white shadow-sm shadow-gray-200">
            <section className="border-b border-b-white mb-16 px-6">
                <div className="max-w-[1000] mx-auto">
                    <div className="flex justify-end pb-2 pt-6">
                        <Link href="/" className="mr-auto text-white hover:underline">Home</Link>
                        <AuthStatus user={user} />
                    </div>
                </div>
            </section>
            <section className="px-6">
                <div className="max-w-[1000] mx-auto">
                    <h1 className="text-3xl font-bold">{content.title}</h1>
                    <p className="mt-6 text-lg">{content.description}</p>
                    <p className="mt-6 text-sm opacity-70">{content.info}</p>
                </div>
            </section>
        </header>
    );
}
