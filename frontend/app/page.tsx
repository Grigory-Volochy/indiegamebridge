import { Fragment } from "react/jsx-runtime";
import { 
    SearchStreamerForm,
    SearchStreamerResultsList,
    SearchFormData,
    StreamerData,
    PageHeader,
    PageHeaderContent,
    PageFooter,
    PageFooterContent
} from "./_components";
import { getCurrentUser } from "./_lib/auth";

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
    header_content: PageHeaderContent;
    project_goal: Section;
    search_form: SearchFormData;
    search_results_title: string;
    search_results: StreamerData[];
    methodology: Section;
    roadmap: FeaturedSection;
    footer_content: PageFooterContent;
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
            <PageHeader user={user} content={content.header_content}></PageHeader>

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
                        <SearchStreamerForm search_form={content.search_form} user={user}></SearchStreamerForm>
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

            <PageFooter content={content.footer_content}></PageFooter>
        </Fragment>
    );
}
