import { Fragment } from "react/jsx-runtime";
import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { getCurrentUser } from "../../_lib/auth";
import { PageHeader, PageHeaderContent, PageFooter, PageFooterContent } from "../../_components";

type StreamerProfilePageContent = {
    header_content: PageHeaderContent;
    content: string;
    footer_content: PageFooterContent;
};

export const metadata: Metadata = {
    robots: { index: false, follow: false },
};

export default async function StreamerProfilePage({ params }: { params: Promise<{ login: string }>; }) {
    const { login } = await params;

    const user = await getCurrentUser();
    if (!user) {
        redirect(`/login?next=${encodeURIComponent(`/streamers/${login}`)}`);
    }

    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    const [response] = await Promise.all([
        fetch(`${apiBase}/pages/home/`)
    ]);

    if (!response.ok) {
        throw new Error(`Failed to load streamer page content (status ${response.status})`);
    }

    const content: StreamerProfilePageContent = await response.json();

    return (
        <Fragment>
            <PageHeader user={user} content={content.header_content}></PageHeader>

            <main className="flex-1 px-6">
                <div className="max-w-2xl mx-auto py-16">
                    <h1 className="text-2xl font-bold mb-4">Streamer: {login}</h1>
                    <p className="text-gray-600">
                        Detailed streamer profile is coming soon. The data source and caching
                        strategy are still being decided.
                    </p>
                </div>
            </main>

            <PageFooter content={content.footer_content}></PageFooter>
        </Fragment>
    );
}
