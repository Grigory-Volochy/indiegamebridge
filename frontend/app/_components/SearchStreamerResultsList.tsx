"use client";

import Link from "next/link";

export type StreamData = {
    id: string;
    language: string;
    max_viewers: string;
    duration: string;
    games: string[];
    started_at: string;
    finished_at: string;
};

export type StreamerData = {
    login: string;
    display_name: string;
    peak_viewers: number;
    avg_duration: string;
    languages: string[];
    streams: StreamData[];
};

function formatStreamTime(iso: string) {
    const d = new Date(iso);
    const date = d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
    const time = d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
    return `${date} • ${time}`;
}

export function SearchStreamerResultsList({ search_results, search_results_title }: { search_results: StreamerData[]; search_results_title: string }) {
    const twitchUrl = "https://www.twitch.tv/";

    return (
        <div className="pt-16">
            <div className="text-center text-brand-blue uppercase text-lg">{search_results_title}</div>
            {search_results.map((one_result, index) => (
                <div key={`search-result-${index}`} className="border border-gray-200 p-6 mt-6 rounded-sm shadow-sm shadow-gray-200 bg-white">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 items-center pb-4">
                        <div className="font-bold text-lg">{one_result.display_name}</div>
                        <div className="flex flex-col md:flex-row lg:flex-row justify-end gap-6">
                            <a className="inline-block px-6 py-2 bg-twitch-brand text-white font-medium rounded hover:bg-twitch-brand-dark min-w-40 text-center border border-twitch-brand hover:border-twitch-brand-dark"
                                href={twitchUrl + one_result.login} target="_blank" rel="nofollow">Visit Channel</a>
                            <Link className="inline-block px-6 py-2 bg-blue-600 text-white font-medium rounded hover:bg-blue-700 min-w-40 text-center border border-blue-600 hover:border-blue-700"
                                href={`/streamers/${one_result.login}`} rel="nofollow" title="View streamer profile">View profile</Link>
                        </div>
                    </div>
                    <div className="border-gray-200 border-t pt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {one_result.streams.map((one_stream, stream_index) => (
                            <div key={`stream-${stream_index}`} className="border border-gray-200 p-4 text-sm rounded-sm">
                                <div className="p-1"><span className="text-brand-blue">Started: </span><span>{formatStreamTime(one_stream.started_at)}</span></div>
                                <div className="p-1"><span className="text-brand-blue">Finished: </span><span>{formatStreamTime(one_stream.finished_at)}</span></div>
                                <div className="p-1"><span className="text-brand-blue">Duration: </span><span>{one_stream.duration}</span></div>
                                <div className="p-1"><span className="text-brand-blue">Peak Viewers: </span><span>{one_stream.max_viewers.toLocaleString()}</span></div>
                                <div className="p-1 flex flex-row gap-x-2 gap-y-2 flex-wrap mt-2">{
                                    one_stream.games.map((game_name, game_index) => (
                                        <div key={`stream-game-${game_index}`} className="py-1 px-2 rounded-sm bg-gray-200">{game_name}</div>
                                    ))
                                }</div>
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
};
