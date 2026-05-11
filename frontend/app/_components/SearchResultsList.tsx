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
    twitch_url: string;
    tracked_streams: number;
    peak_viewers: number;
    languages: string[];
    streams: Stream[];
};


export function SearchResultsList({ search_results }: { search_results: SearchResult[] }) {
    return (
        <div className="pt-4">
            <div className="text-center text-brand-blue uppercase">Search Results</div>
            {search_results.map((one_result, index) => (
                <div key={`search-result-${index}`} className="border border-gray-200 p-6 mt-6 rounded-sm shadow-sm shadow-gray-200 bg-white">
                    <div>{one_result.display_name}</div>
                    <div>{one_result.tracked_streams}</div>
                    <div>{one_result.peak_viewers}</div>
                    <div>{one_result.languages}</div>
                </div>
            ))}
        </div>
    );
};
