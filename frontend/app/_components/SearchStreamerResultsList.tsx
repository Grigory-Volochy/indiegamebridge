"use client";

import { Fragment, useState } from "react";

export type StreamData = {
    id: string;
    language: string;
    max_viewers: string;
    duration: string;
    games: string[];
};

export type StreamerData = {
    login: string;
    display_name: string;
    tracked_streams: number;
    peak_viewers: number;
    avg_duration: string;
    languages: string[];
    streams: StreamData[];
};


export function SearchStreamerResultsList({ search_results }: { search_results: StreamerData[] }) {
    const twitchUrl = "https://www.twitch.tv/";

    return (
        <div className="pt-4">
            <div className="text-center text-brand-blue uppercase">Search Results</div>
            {search_results.map((one_result, index) => (
                <div key={`search-result-${index}`} className="border border-gray-200 p-6 mt-6 rounded-sm shadow-sm shadow-gray-200 bg-white">
                    <div className="font-bold">{one_result.display_name}</div>
                    <div>Language(s): {one_result.languages.join(', ')}</div>
                    <div>Total tracked streams: {one_result.tracked_streams}</div>
                    <div>Peak viewers: {one_result.peak_viewers}</div>
                    <div className="mt-4 border-gray-200 border-t p-4">
                        <div className="text-brand-blue">Streams:</div>
                        {one_result.streams.map((oone_stream, stream_index) => (
                            <div key={`stream-${stream_index}`} className="">
                                <div>Duration: {oone_stream.duration}</div>
                                {oone_stream.games.map((game_name, game_index) => (
                                    <span key={`stream-game-${game_index}`} className="border-red-200 border-l-2 p-2">{game_name}</span>
                                ))}
                            </div>
                        ))}
                    </div>
                    <div className="flex flex-col md:flex-row lg:flex-row justify-end gap-6">
                        <a className="inline-block px-6 py-3 bg-twitch-brand text-white font-medium rounded hover:bg-twitch-brand-dark min-w-40 text-center"
                            href={twitchUrl + one_result.login} target="_blank">Visit Channel</a>
                        {/* TODO: set URL for 'View profile' link - should open a streamer profile page with all information available */}
                        <a className="inline-block px-6 py-3 bg-brand-blue text-white font-medium rounded hover:bg-brand-blue-dark min-w-40 text-center"
                            href="#" target="_blank">View profile</a>
                    </div>
                </div>
            ))}
        </div>
    );
};
