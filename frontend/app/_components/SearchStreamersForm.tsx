"use client";

import { Fragment, useState } from "react";

export type FieldSet = {
    v: string;
    l: string;
};

export type SearchFilterField = {
    filter_type: string;
    filter_name: string;
    filter_label: string;
    multi_values: FieldSet[];
    multi_default: string[];
    single_default: string;
    min_values: FieldSet[];
    min_default: string;
    max_values: FieldSet[];
    max_default: string;
};

export type SearchForm = {
    title: string;
    aria_label: string;
    filters: SearchFilterField[];
    button_text: string;
    demo_title: string;
    demo_note: string;
};

export function SearchStreamersForm({ search_form }: { search_form: SearchForm }) {
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
                                one_filter.multi_values.length > 10
                                    ? 'lg:col-span-3 md:col-span-2 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-1'
                                    : (one_filter.multi_values.length > 3
                                        ? 'lg:col-span-2 md:col-span-2'
                                        : ''
                                    )
                                }`}>
                        <legend className="mr-4 text-sm italic text-brand-blue">{one_filter.filter_label}</legend>
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
                <fieldset className="flex items-center">
                    <button type="submit" disabled={true}
                        className="bg-gray-300 px-8 py-3 mx-auto rounded-sm text-white hover:bg-gray-300 cursor-not-allowed shadow-sm shadow-gray-200 min-w-40"
                    >{search_form.button_text}</button>
                </fieldset>
                <div className="lg:col-span-3 md:col-span-2 grid grid-cols-1 text-orange-600 mt-4 border-t border-orange-500 pt-4">
                    <span className="font-bold uppercase">{search_form.demo_title}</span><span>{search_form.demo_note}</span>
                </div>
            </form>
        </div>
    );
};
