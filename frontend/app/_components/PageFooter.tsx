"use client";

import { Fragment } from "react/jsx-runtime";
import Link from "next/link";

type FooterLink = {
    text: string;
    url: string;
    nofollow: number;
    is_internal: number;
}

export type PageFooterContent = {
    data_source: string;
    opt_out_text: string;
    footer_links: FooterLink[];
};

export function PageFooter({ content }: { content: PageFooterContent; } ) {
    const link_styles = "underline text-blue-500 hover:text-white";
    const opt_out_link = <Link className={link_styles} href={`/optout`} rel="nofollow">{content.opt_out_text}</Link>;
    return (
        <footer className="pt-16 pb-12 px-6 bg-brand-blue text-white">
            <section className="max-w-[1000] mx-auto text-gray-300 font-thin text-sm">
                {content.footer_links.map((one_link, index) => (
                    one_link.is_internal
                        ? <Link key={`footer-link-${index}`}
                            href={one_link.url}
                            className={`p-2 mr-4${link_styles}`}
                            rel={one_link.nofollow ? 'nofollow' : undefined}>{one_link.text}</Link>
                        : <a key={`footer-link-${index}`}
                            href={one_link.url}
                            className={`p-2 mr-4${link_styles}`}
                            rel={one_link.nofollow ? 'nofollow' : undefined}>{one_link.text}</a>
                ))}
            </section>
            <section className="max-w-[1000] mx-auto text-gray-300 font-thin text-sm">
                <div className="p-2">{content.data_source.split('%opt_out_link%').map((part, i, arr) => (
                    <Fragment key={i}>
                        {part}
                        {i < arr.length - 1 && opt_out_link}
                    </Fragment>
                ))}</div>
            </section>
        </footer>
    );
}
