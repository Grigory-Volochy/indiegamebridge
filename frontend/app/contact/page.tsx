import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
    title: "Contact — IndieGameBridge",
    robots: { index: false, follow: false },
};

export type ContactPageContent = {
    title: string;
    return_home: string;
    body: string;
};

export default async function ContactPage() {
    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    const response = await fetch(`${apiBase}/pages/contact/`);

    if (!response.ok) {
        throw new Error(`Failed to load contact page content (status ${response.status})`);
    }

    const content: ContactPageContent = await response.json();

    return (
        <main className="flex-1 px-6">
            <div className="max-w-md mx-auto py-24">
                <h1 className="text-2xl font-bold mb-6 text-center">{content.title}</h1>
                <p className="text-gray-600 mb-8 text-center">{content.body}</p>
                <Link href="/" className="block text-center text-blue-500 hover:text-blue-400 underline">{content.return_home}</Link>
            </div>
        </main>
    );
}
