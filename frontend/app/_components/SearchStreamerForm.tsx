"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import { CurrentUser } from "../_lib/auth";

export type FieldData = {
    v: string;
    l: string;
};

export type SearchStreamerFilterData = {
    filter_type: string;
    filter_name: string;
    filter_label: string;
    multi_values: FieldData[];
    multi_default: string[];
    single_default: string;
    min_values: FieldData[];
    min_default: string;
    max_values: FieldData[];
    max_default: string;
};

export type SearchFormData = {
    title: string;
    aria_label: string;
    filters: SearchStreamerFilterData[];
    button_text: string;
    demo_title: string;
    demo_note: string;
    search_notes: string[];
    cta_link_text: string;
};

export function SearchStreamerForm({ search_form, user }: { search_form: SearchFormData; user: CurrentUser | null }) {
    const [formData, setFormData] = useState<Record<string, any>>(() => {
        const initial: Record<string, any> = {};
        for (const one_filter of search_form.filters) {
            if (one_filter.filter_type === 'multiselect') {
                initial[one_filter.filter_name] = [...one_filter.multi_default];
            } else if (one_filter.filter_type === 'range') {
                initial[`${one_filter.filter_name}_min`] = one_filter.min_default;
                initial[`${one_filter.filter_name}_max`] = one_filter.max_default;
            } else if (one_filter.filter_type === 'dropdown') {
                initial[one_filter.filter_name] = one_filter.single_default;
            }
        }
        return initial;
    });

    const handleCheckboxChange = (filterName: string, value: string, isChecked: boolean) => {
    setFormData((prev) => {
        const currentValues = prev[filterName] || [];
            if (isChecked) {
                return { ...prev, [filterName]: [...currentValues, value] };
            } else {
                return { ...prev, [filterName]: currentValues.filter((v: string) => v !== value) };
            }
        });
    };

    // Handler for Select Dropdowns (Range)
    const handleSelectRange = (filterName: string, type: 'min' | 'max', value: string) => {
        setFormData((prev) => ({
            ...prev,
            [`${filterName}_${type}`]: value
        }));
    };

    // Handler for Select Dropdowns (Single)
    const handleDropdownChange = (filterName: string, value: string) => {
        setFormData((prev) => ({
            ...prev,
            [filterName]: value
        }));
    };

    return (
        <div className="overflow-hidden rounded-sm border border-gray-200 shadow-sm shadow-gray-200 bg-white p-6">
            <div className="uppercase mb-5 text-brand-blue text-lg">{search_form.title}</div>
            <form className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-5" aria-label={search_form.aria_label}>
                {search_form.filters.map((one_filter) => (
                    <fieldset key={one_filter.filter_name}
                            className={`flex items-center flex-wrap col-span-1 ${
                                one_filter.filter_type === 'multiselect'
                                    ? one_filter.multi_values.length > 10
                                        ? 'lg:col-span-3 md:col-span-2 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1'
                                        : (one_filter.multi_values.length > 3
                                            ? 'lg:col-span-2 md:col-span-2'
                                            : ''
                                        )
                                    : ''
                                }`}>
                        <legend className="mr-4 text-sm text-brand-blue">{one_filter.filter_label}</legend>
                        {(() => {
                            switch (one_filter.filter_type) {

                                case 'multiselect':
                                    return (
                                        <Fragment>
                                            {one_filter.multi_values.map((one_value, index) => {
                                                const id = `${one_filter.filter_name}_${index}`;
                                                const isChecked = formData[one_filter.filter_name]?.includes(one_value.v) || false;

                                                return (
                                                    <div key={id} className="mr-5 mb-1 flex-row flex items-center">
                                                        <input id={id}
                                                            type="checkbox"
                                                            name={one_filter.filter_name}
                                                            value={one_value.v}
                                                            className="w-4 h-4 rounded mr-2 cursor-pointer"
                                                            checked={isChecked}
                                                            onChange={(e) => handleCheckboxChange(one_filter.filter_name, one_value.v, e.target.checked)}
                                                        />
                                                        <label htmlFor={id} className="cursor-pointer">{one_value.l}</label>
                                                    </div>
                                                );
                                            })}
                                        </Fragment>
                                    );

                                case 'range':
                                    return (
                                        <Fragment>
                                            <select id={`${one_filter.filter_name}_min`}
                                                name={`${one_filter.filter_name}_min`}
                                                className="p-2 border border-gray-200 rounded-sm grow cursor-pointer outline-gray-400"
                                                value={formData[`${one_filter.filter_name}_min`] || one_filter.min_default || ''}
                                                onChange={(e) => handleSelectRange(one_filter.filter_name, 'min', e.target.value)}
                                            >
                                                {one_filter.min_values.map((one_value, index) => (
                                                    <option key={`${one_filter.filter_name}_min_${index}`} value={one_value.v}>
                                                        {one_value.l}
                                                    </option>
                                                ))}
                                            </select>
                                            <span className="p-2">to</span>
                                            <select id={`${one_filter.filter_name}_max`}
                                                name={`${one_filter.filter_name}_max`}
                                                className="p-2 border border-gray-200 rounded-sm grow cursor-pointer outline-gray-400"
                                                value={formData[`${one_filter.filter_name}_max`] || one_filter.max_default || ''}
                                                onChange={(e) => handleSelectRange(one_filter.filter_name, 'max', e.target.value)}
                                            >
                                                {one_filter.max_values.map((one_value, index) => (
                                                    <option key={`${one_filter.filter_name}_max_${index}`} value={one_value.v}>
                                                        {one_value.l}
                                                    </option>
                                                ))}
                                            </select>
                                        </Fragment>
                                    );

                                case 'dropdown':
                                    return (
                                        <Fragment>
                                            <select id={one_filter.filter_name}
                                                name={one_filter.filter_name}
                                                className="p-2 border border-gray-200 rounded-sm grow cursor-pointer outline-gray-400"
                                                value={formData[one_filter.filter_name] || one_filter.single_default || ''}
                                                onChange={(e) => handleDropdownChange(one_filter.filter_name, e.target.value)}
                                            >
                                                {one_filter.multi_values.map((one_value, index) => (
                                                    <option key={`${one_filter.filter_name}_${index}`} value={one_value.v}>
                                                        {one_value.l}
                                                    </option>
                                                ))}
                                            </select>
                                        </Fragment>
                                    );

                                default:
                                    return null;
                            }
                        })()}
                    </fieldset>
                ))}
                <div className="col-span-1 md:col-span-2 lg:col-span-3 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-5">
                    <div className="col-span-1 md:col-span-1 lg:col-span-2 text-sm italic">
                        {search_form.search_notes.map((one_note, index) => (
                            <div key={`note-${index}`} className="before:content-(--note-marker) ml-4 before:absolute before:-left-4 relative"
                                style={{ ["--note-marker" as any]: `"${"*".repeat(index + 1)}"` }}
                            >{one_note}</div>
                        ))}
                    </div>
                    <fieldset className="flex justify-center col-span-1 items-start">
                        <button type="submit" disabled={!user}
                            className={!user
                                ? "bg-gray-300 px-8 py-2 rounded-sm text-white hover:bg-gray-300 cursor-not-allowed shadow-sm shadow-gray-200 min-w-40"
                                : "bg-blue-600 px-8 py-2 rounded-sm text-white hover:bg-blue-700 cursor-pointer shadow-sm shadow-gray-200 min-w-40"
                            }
                        >{search_form.button_text}</button>
                    </fieldset>
                </div>
                {!user
                    ? <div className="col-span-1 lg:col-span-3 md:col-span-2 text-orange-600 mt-4 border-t border-orange-500 pt-4">
                        <div>
                            <span className="font-bold uppercase">{search_form.demo_title}</span>
                            <span> {search_form.demo_note}</span>
                        </div>
                        <div className="text-center mt-4">
                            <Link href="/login" className="underline text-blue-700 hover:text-blue-500 ml-2">{search_form.cta_link_text}</Link>
                        </div>
                    </div>
                    : null
                }
            </form>
        </div>
    );
};
