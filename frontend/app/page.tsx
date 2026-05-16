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

type CallToAction = {
    title: string;
    input_placeholder: string;
    btn_text: string;
}

type HomePageContent = {
    title: string;
    description: string;
    info: string;
    project_goal: Section;
    search_form: SearchFormData;
    search_results: StreamerData[];
    methodology: Section;
    roadmap: FeaturedSection;
    cta: CallToAction;
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

    return (
        <Fragment>
            {/* Header */}
            <header className="pt-16 pb-12 px-6 bg-brand-blue text-white shadow-sm shadow-gray-200">
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
                        <div className="my-8 p-6 border border-orange-500 rounded-sm bg-white shadow-sm shadow-gray-200">
                            <h2 className="text-lg mb-4">{content.cta.title}</h2>
                            <form>
                                <fieldset className="flex flex-row justify-center flex-wrap">
                                    <input type="email" id="top_cta_email" autoComplete="off" name="email" required={true}
                                        className="bg-white px-4 py-2 rounded-sm text-black min-w-40 w-full md:min-w-80 md:w-80 lg:min-w-80 lg:w-80 border border-gray-200 focus-visible:outline-gray-400"
                                        placeholder={content.cta.input_placeholder}
                                        defaultValue="" />
                                    <button type="submit"
                                        className="bg-orange-500 px-8 py-2 mx-auto md:ml-3 lg:ml-3 rounded-sm text-white hover:bg-orange-600 cursor-pointer shadow-sm shadow-gray-200 min-w-40 mt-6 md:mt-0 lg:mt-0"
                                    >{content.cta.btn_text}</button>
                                </fieldset>
                            </form>
                        </div>
                        <SearchStreamerResultsList search_results={content.search_results}></SearchStreamerResultsList>
                    </div>
                </section>

                {/* Methodology */}
                <section className="border-t border-gray-200 px-6">
                    <div className="max-w-[1000] mx-auto py-8">
                        <h2 className="text-2xl font-bold mb-4">{content.methodology.title}</h2>
                        <p>{content.methodology.description}</p>
                    </div>
                </section>
                <section className="border-t border-gray-200 px-6">
                    <div className="max-w-[1000] mx-auto py-16">
                        <h2 className="text-2xl font-bold mb-4">{content.roadmap.title}</h2>
                        <p>{content.roadmap.description}</p>
                        <ul>
                        {content.roadmap.features.map((feature, index) => (
                            <li key={"coming-feature-" + index}>{feature}</li>
                        ))}
                        </ul>
                    </div>
                </section>
            </main>

            {/* Footer */}
            <footer className="pt-16 pb-12 px-6 bg-brand-blue text-white">
                <section className="max-w-[1000] mx-auto">
                    <h2 className="mb-5 text-lg">{content.cta.title}</h2>
                    <form className="mb-32">
                        <fieldset className="flex flex-row justify-center flex-wrap">
                            <input type="email" id="footer_cta_email" autoComplete="off" name="email" required={true}
                                className="bg-white px-4 py-2 rounded-sm text-black min-w-40 w-full md:min-w-80 md:w-80 lg:min-w-80 lg:w-80 focus-visible:outline-gray-400"
                                placeholder={content.cta.input_placeholder}
                                defaultValue="" />
                            <button type="submit"
                                className="bg-orange-500 px-8 py-2 mx-auto md:ml-3 lg:ml-3 rounded-sm hover:bg-orange-600 cursor-pointer min-w-40 mt-6 md:mt-0 lg:mt-0"
                            >{content.cta.btn_text}</button>
                        </fieldset>
                    </form>
                </section>
                <section className="max-w-[1000] mx-auto text-gray-300 font-thin text-sm">
                    <span>{content.data_source}</span>
                    <Link className="ml-2 text-blue-400 hover:text-blue-300" 
                        href={`/optout`}
                        rel="nofollow"
                        title="Opt out">{content.opt_out_text}</Link>
                </section>
            </footer>
        </Fragment>
    );
}
