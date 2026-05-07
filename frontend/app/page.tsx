import { Fragment } from "react/jsx-runtime";

type TableRow = {
  display_name: string;
  login: string;
  twitch_url: string;
  tracked_streams: number;
  peak_viewers: number;
  languages: string[];
};

type HomePageContent = {
  title: string;
  description: string;
  info: string;
  table_rows: TableRow[];
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
      <header className="pt-16 pb-12 px-6 bg-brand-blue text-white">
        <div className="max-w-[1000] mx-auto">
          <h1 className="text-3xl font-bold">{content.title}</h1>
          <p className="mt-6 text-lg">{content.description}</p>
          <p className="mt-6 text-sm opacity-70">{content.info}</p>
        </div>
      </header>
      <main className="max-w-[1000] mx-auto py-8">
        <section>
          <h2>Top Streamers</h2>
          <p>The ranking table is updated hourly and displays top streamers who broadcasting games on English, French, and German languages.</p>
        </section>
        <section>
          <table className="mt-8 mb-16 w-full border-collapse text-left rounded-lg overflow-hidden bg-white shadow-sm">
            <thead>
              <tr className="border-b-gray-500 text-white bg-brand-blue uppercase">
                <th className="p-4 font-normal w-16">#</th>
                <th className="p-4 font-normal">Streamer</th>
                <th className="p-4 font-normal">Tracked streams</th>
                <th className="p-4 font-normal">Peak viewers</th>
                <th className="p-4 font-normal">LANG</th>
              </tr>
            </thead>
            <tbody>
              {content.table_rows.map((row, index) => (
                <tr key={row.login} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="p-4">{index + 1}</td>
                  <td className="p-4">
                    <a href={row.twitch_url} target="_blank" rel="noopener noreferrer" className="underline">
                      {row.display_name}
                    </a>
                  </td>
                  <td className="p-4">{row.tracked_streams}</td>
                  <td className="p-4">{row.peak_viewers}</td>
                  <td className="p-4">{row.languages.join(" | ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section>
          <h2>Methodology</h2>
          <p>We track stramers who broadcasting games on Twitch streaming platform with at least 3 viewers. The streamers with the higher viewers number on a stream during latest 10 days is shown at higher position in the table.</p>
        </section>
      </main>
      <footer className="pt-16 pb-12 px-6 bg-brand-blue text-white">
        <section className="max-w-[1000] mx-auto">
          <h2 className="mb-5">Get notified when filtering and advanced search goes live</h2>
          <form className="mb-32">
            <fieldset>
              <input type="email" className="bg-white px-4 py-3 rounded-sm text-black min-w-80" placeholder="your@email.com" defaultValue="" />
              <button type="submit" className="bg-orange-500 px-8 py-3 ml-3 rounded-sm hover:bg-orange-600 cursor-pointer">Notify Me</button>
            </fieldset>
          </form>
        </section>
        <section className="max-w-[1000] mx-auto">
          <small>Data sourced from public Twitch streams. Streamers can opt out at any time.</small>
        </section>
      </footer>
    </Fragment>
  );
}
