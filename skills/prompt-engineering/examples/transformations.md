# Prompt transformation examples

These examples are illustrative, not benchmark results.

## Example 1 — Software development

**Original:** “Make me a website for my travel company.”

**Improved prompt:**

> Build a responsive website for a travel company using the existing project's framework and conventions. First inspect the repository and summarize its current structure before changing files.
>
> Goal: Let visitors discover destinations and packages, view package details, and submit a booking enquiry. Include a contact page with a working form.
>
> Requirements:
> - Reuse the existing design system and components where possible.
> - Make navigation, forms, validation, loading states, and error messages functional.
> - Validate input on both client and server where applicable.
> - Do not expose credentials or trust client-supplied prices, roles, or booking status.
> - Do not replace existing features without explaining why.
>
> Deliverables:
> 1. Implement the smallest complete change that meets the requirements.
> 2. Add or update relevant tests.
> 3. List changed files and explain key decisions.
> 4. Report only commands and tests actually run, with results.
> 5. List anything incomplete or requiring external configuration.
>
> Acceptance criteria: Main pages work on mobile and desktop; forms show clear success and failure feedback; no secrets are committed; existing tests continue to pass.

**Why it is stronger:** It defines user outcomes, protects existing project conventions, calls out security-sensitive behavior, and establishes verifiable completion criteria without inventing a technology stack.

## Example 2 — Research

**Original:** “Research AI in education.”

**Improved prompt:**

> Prepare a balanced research brief on how generative AI is being used in higher education.
>
> Scope: Cover learning support, assessment, academic integrity, accessibility, and educator workload. Focus on evidence published in the last three years, using older foundational research only when relevant.
>
> Evidence requirements: Prioritize peer-reviewed research, systematic reviews, official education guidance, and transparent institutional studies. Cite sources next to supported claims, with dates and working links when available. Separate measured findings from opinions, forecasts, and vendor claims. Include conflicting evidence and limitations. Never fabricate studies, statistics, quotations, or citations. If current browsing is unavailable, state that limitation.
>
> Output: Executive summary; findings by topic; benefits and risks with evidence strength; practical recommendations for a university; sources and open questions. Keep it concise enough for a decision-maker to read in about eight minutes.

**Why it is stronger:** It defines scope, timeframe, evidence quality, output structure, and uncertainty handling.

## Example 3 — Data analysis

**Original:** “Analyze my sales data.”

**Improved prompt:**

> Analyze the sales dataset I provide to identify useful business trends.
>
> Before analysis, inspect column names, data types, date range, units, missing values, duplicates, and suspicious values. Summarize data-quality issues before transforming the data. Do not invent missing values or assume currency, time zone, or business definitions without evidence.
>
> When fields are available, report total sales, order count, average order value, and trends over time. Break down results by product, region, or customer segment only if those columns exist. Distinguish descriptive patterns from causal claims. Explain calculations and state exclusions and assumptions.
>
> Deliver an executive summary, key findings with units and date ranges, data-quality notes, suggested visualizations, and reproducible code or formulas if requested. If a missing definition would materially change the results, ask one concise question before proceeding.

**Why it is stronger:** It requires data inspection, prevents silent assumptions, and ties analysis to available fields.

## Example 4 — Writing

**Original:** “Write a better email.”

**Improved prompt:**

> Rewrite the email below so it is clear, polite, and professional while preserving the sender's intent and factual details.
>
> Infer audience and purpose only from the supplied email. Do not invent recipients, commitments, dates, or explanations. Keep the result concise and similar in length unless clarity requires more detail. Provide one polished, ready-to-send version. If an essential detail is missing, use a clearly marked placeholder rather than fabricating it.
>
> Email to rewrite: [Paste the original email here]

**Why it is stronger:** It defines the editing goal and boundaries without adding invented details or unnecessary alternatives.
