"use client";

import { Fragment, useState } from "react";

export type Game = {
    host_game_id: string;
    host_name: string;
};

export type Stream = {
    host_stream_id: string;
    language: string;
    max_viewers: string;
    started_at: string;
    finished_at: string;
    games: Game[];
};

export type SearchResult = {
    display_name: string;
    login: string;
    tracked_streams: number;
    peak_viewers: number;
    languages: string[];
    streams: Stream[];
};


export function SearchResultsList({ search_results }: { search_results: SearchResult[] }) {
    const twitchUrl = "https://www.twitch.tv/";

    return (
        <div className="pt-4">
            <div className="text-center text-brand-blue uppercase">Search Results</div>
            {search_results.map((one_result, index) => (
                <div key={`search-result-${index}`} className="border border-gray-200 p-6 mt-6 rounded-sm shadow-sm shadow-gray-200 bg-white">
                    <div className="font-bold">{one_result.display_name}</div>
                    <div>Language(s): {one_result.languages.join(', ')}</div>
                    <div>Total tracked strams: {one_result.tracked_streams}</div>
                    <div>Peak viewers: {one_result.peak_viewers}</div>
                    <div>
                        {one_result.streams.map((oone_stream, stream_index) => (
                            <div key={`stream-${stream_index}`}>{
                                oone_stream.games.map((one_game, game_index) => (
                                    <span key={`stream-game-${game_index}`}>{one_game.host_name}</span>
                                ))
                            }</div>
                        ))}
                    </div>
                    <div><a className="inline-block px-6 py-3 bg-twitch-brand text-white font-medium rounded hover:bg-twitch-brand-dark"
                            href={twitchUrl + one_result.login}>Visit Twitch Channel</a></div>
                </div>
            ))}
        </div>
    );
};
