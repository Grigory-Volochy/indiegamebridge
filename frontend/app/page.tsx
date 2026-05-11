import { Fragment } from "react/jsx-runtime";
import { SearchStreamersForm, SearchForm } from "./_components";

type SearchResults = {
    display_name: string;
    login: string;
    twitch_url: string;
    tracked_streams: number;
    peak_viewers: number;
    languages: string[];
};

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
    search_form: SearchForm;
    search_results: SearchResults[];
    methodology: Section;
    roadmap: FeaturedSection;
    data_source: string;
    cta: CallToAction;
};

export default async function Home() {
    const apiBase = process.env.API_BASE_URL ?? "http://localhost:8000";
    const response = await fetch(`${apiBase}/pages/home/`);

    if (!response.ok) {
        throw new Error(`Failed to load home page content (status ${response.status})`);
    }

    const content: HomePageContent = await response.json();

    return (
        <Fragment>
            {/* Header */}
            <header className="pt-16 pb-12 px-6 bg-brand-blue text-white shadow-sm shadow-gray-200">
                <div className="max-w-[1000] mx-auto">
                    <h1 className="text-3xl font-bold">{content.title}</h1>
                    <p className="mt-6 text-lg">{content.description}</p>
                    <p className="mt-6 text-sm opacity-70">{content.info}</p>
                </div>
            </header>

            {/* Main */}
            <main className="w-full">

                {/* Project Goal */}
                <section>
                    <div className="max-w-[1000] mx-auto pt-16 pb-8">
                        <h2 className="text-2xl font-bold mb-4">{content.project_goal.title}</h2>
                        <p>{content.project_goal.description}</p>
                    </div>
                </section>

                {/* Demo Search Results */}
                <section>
                    <div className="max-w-[1000] mx-auto pt-4 pb-16">
                        <div className="my-8 p-6 border border-orange-500 rounded-sm bg-white shadow-sm shadow-gray-200">
                            <h2 className="text-xl mb-4">{content.cta.title}</h2>
                            <form>
                                <fieldset>
                                <input type="email" id="top_cta_email" name="email" required={true}
                                    className="bg-white px-4 py-3 rounded-sm text-black min-w-80 border border-gray-200 focus-visible:outline-gray-400"
                                    placeholder={content.cta.input_placeholder}
                                    defaultValue="" />
                                <button type="submit" className="bg-orange-500 px-8 py-3 ml-3 rounded-sm text-white hover:bg-orange-600 cursor-pointer shadow-sm shadow-gray-200">{content.cta.btn_text}</button>
                                </fieldset>
                            </form>
                        </div>
                        <SearchStreamersForm search_form={content.search_form}></SearchStreamersForm>
                    </div>
                </section>

                {/* Methodology */}
                <section className="w-full">
                    <div className="max-w-[1000] mx-auto py-8">
                        <h2>{content.methodology.title}</h2>
                        <p>{content.methodology.description}</p>
                    </div>
                </section>
                <section className="border-t border-gray-200 shadow-sm shadow-gray-200">
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
                    <h2 className="mb-5 text-xl">{content.cta.title}</h2>
                    <form className="mb-32">
                        <fieldset>
                            <input type="email"
                                className="bg-white px-4 py-3 rounded-sm text-black min-w-80 focus-visible:outline-gray-400" placeholder={content.cta.input_placeholder} defaultValue="" />
                            <button type="submit" className="bg-orange-500 px-8 py-3 ml-3 rounded-sm hover:bg-orange-600 cursor-pointer">{content.cta.btn_text}</button>
                        </fieldset>
                    </form>
                </section>
                <section className="max-w-[1000] mx-auto text-gray-300 font-thin text-sm">
                    {content.data_source}
                </section>
            </footer>
        </Fragment>
    );
}
