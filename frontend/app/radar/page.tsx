import type { Metadata } from "next";
import { SITE_NAME } from "@/lib/site";
import RadarClient from "./RadarClient";
export const metadata: Metadata = { title: `Radar - ${SITE_NAME}`, alternates: { canonical: "/radar" } };
export default function Page() { return <RadarClient />; }
