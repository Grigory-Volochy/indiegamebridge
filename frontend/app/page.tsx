import { Fragment } from "react/jsx-runtime";
import { AuthStatus, SearchStreamerForm, SearchStreamerResultsList, SearchFormData, StreamerData } from "./_components";
import { getCurrentUser } from "./_lib/auth";
import Link from "next/link";

type Section = {
    title: string;
    description: string;
};

type FeaturedSection = {
    title: string;
    description: string;
    features: string[];
};

type HomePageContent = {
    title: string;
    description: string;
    info: string;
    project_goal: Section;
    search_form: SearchFormData;
    search_results_title: string;
    search_results: StreamerData[];
    methodology: Section;
    roadmap: FeaturedSection;
    data_source: string;
    opt_out_text: string;
};

export default async function Home() {
    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    const [response, user] = await Promise.all([
        fetch(`${apiBase}/pages/home/`),
        getCurrentUser(),
    ]);

    if (!response.ok) {
        throw new Error(`Failed to load home page content (status ${response.status})`);
    }

    const content: HomePageContent = await response.json();

    const opt_out_link = <Link className="underline text-blue-400 hover:text-blue-300" href={`/optout`} rel="nofollow" title="Opt out">{content.opt_out_text}</Link>;

    return (
        <Fragment>
            {/* Header */}
            <header className="pt-10 pb-12 px-6 bg-brand-blue text-white shadow-sm shadow-gray-200">
                <div className="max-w-[1000] mx-auto">
                    <div className="flex justify-end mb-2">
                        <AuthStatus user={user} />
                    </div>
                    <h1 className="text-3xl font-bold">{content.title}</h1>
                    <p className="mt-6 text-lg">{content.description}</p>
                    <p className="mt-6 text-sm opacity-70">{content.info}</p>
                </div>
            </header>

            {/* Main */}
            <main className="w-full">

                {/* Project Goal */}
                <section className="px-6">
                    <div className="max-w-[1000] mx-auto pt-16 pb-8">
                        <h2 className="text-2xl font-bold mb-4">{content.project_goal.title}</h2>
                        <p>{content.project_goal.description}</p>
                    </div>
                </section>

                {/* Demo Search */}
                <section className="px-6">
                    <div className="max-w-[1000] mx-auto pt-4 pb-16">
                        <SearchStreamerForm search_form={content.search_form}></SearchStreamerForm>
                        <SearchStreamerResultsList search_results={content.search_results} search_results_title={content.search_results_title}></SearchStreamerResultsList>
                    </div>
                </section>

                {/* Methodology */}
                <section className="border-t border-gray-200 px-6">
                    <div className="max-w-[1000] mx-auto py-16">
                        <h2 className="text-2xl font-bold mb-4">{content.methodology.title}</h2>
                        <p>{content.methodology.description}</p>
                    </div>
                </section>
                <section className="border-t border-gray-200 px-6">
                    <div className="max-w-[1000] mx-auto py-16">
                        <h2 className="text-2xl font-bold mb-4">{content.roadmap.title}</h2>
                        <p className="pb-2">{content.roadmap.description}</p>
                        <ul className="list-disc pl-5">
                            {content.roadmap.features.map((feature, index) => (
                                <li key={"coming-feature-" + index} className="py-2">{feature}</li>
                            ))}
                        </ul>
                    </div>
                </section>
            </main>

            {/* Footer */}
            <footer className="pt-16 pb-12 px-6 bg-brand-blue text-white">
                <section className="max-w-[1000] mx-auto text-gray-300 font-thin text-sm">
                    <div>{content.data_source.split('%opt_out_link%').map((part, i, arr) => (
                        <Fragment key={i}>
                            {part}
                            {i < arr.length - 1 && opt_out_link}
                        </Fragment>
                    ))}</div>
                </section>
            </footer>
        </Fragment>
    );
}
