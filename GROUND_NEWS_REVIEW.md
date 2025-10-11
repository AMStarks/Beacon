## Competitive Review: Ground News

Link: [ground.news](https://ground.news/)

### What Ground News Does Well (Feature Inventory)
- **Event aggregation**: Merges multiple articles into a single story/event, showing total sources and a visible lean distribution (Left/Center/Right) with percentages.
- **Blindspot surfacing**: Dedicated feed/newsletters highlighting topics under-covered by one side.
- **Personalization**: "For You" feed and a "My News Bias" profile estimating a user’s consumption lean.
- **Local and regional views**: Location-set local news and region pages (US/UK/EU/Asia/etc.).
- **Discovery scaffolding**: Trending topics, topic pages, international sections, and timelines.
- **Trust scaffolding**: Media bias, ownership, and factuality ratings; browsable source directory.
- **Lightweight UX add‑ons**: Daily briefings, multiple newsletters, browser extension, iOS/Android apps.
- **Commercial model**: Freemium + subscription, group plans, gifting, institutional/education.

### Methodology Implied by the Product
- **Story clustering**: Deduplicate and unify coverage into events, normalize/standardize titles.
- **Bias mapping**: Categorical lean per domain with a likely confidence/factuality layer.
- **Coverage mix math**: Compute Left/Center/Right share within each event and visualize it.
- **Blindspot detection**: Compare observed lean mix vs. priors (global or user‑specific) to flag skew.
- **Personal bias inference**: Aggregate a user’s read/click history by source lean to profile bias.
- **Localization**: Geotagging/region tagging to construct local feeds.
- **Curation layers**: Trending, daily briefings, timelines built atop cluster metadata.

### Ideas We Can Implement Soon (Quick Wins for Beacon)
- **Cluster lean mix badge**: We already show source lean; add a per‑cluster histogram and a composite "corroboration score" combining number of sources, lean diversity, and time spread.
- **Blindspot‑lite callouts**: Flag clusters where lean distribution is highly skewed; add "See other perspectives" with cross‑lean links.
- **Daily briefing page/email**: Top clusters by corroboration score and reach; publish and mail.
- **Cluster timelines**: Show first‑seen → latest updates and time‑to‑corroboration.
- **Local tab MVP**: Country/region selector; filter clusters accordingly.
- **Ownership/factuality hints**: Small tooltip per source with ownership/factuality notes.
- **Topic pages**: Aggregate clusters by entities/topics with a simple volume sparkline.

### Methods To Adopt In Beacon (Technical)
- **Event clustering pipeline**: Normalize "event text" = title + excerpt + 1–2k chars, embed, incremental nearest‑neighbor within a recency window; maintain centroids and per‑cluster stats.
- **Lean/quality signals**: Persist `source_lean`, `source_confidence` (done); add `source_factuality`, `ownership_parent`.
- **Corroboration metrics**: `num_sources`, `distinct_domains`, `lean_entropy`, `time_span_hours`, `top5_similarity_mean`.
- **Blindspot scoring**: Compare cluster lean distribution to a baseline prior; allow per‑user priors for personalization.
- **Personal bias profile**: Tally user interactions by lean; present neutral profile and balancing suggestions.
- **Topic extraction**: NER to extract entities/topics; link clusters to topics for timelines and pages.
- **Local mapping**: Domain country heuristics + text geo extraction to label country/region.

### Differentiators We Can Pursue (Point of Difference)
- **Explainable clustering**: Show "why grouped" (shared entities, n‑grams, title similarity, jaccard tokens) and similarity ranges.
- **Corroboration‑first ranking**: Default order by corroboration (diversity × sources × recency), not just recency.
- **Narrative drift tracking**: Visualize headline/excerpt changes across leans over time; show "what changed" diffs.
- **Quote variability & claim map**: Extract quotes/claims; indicate which outlets repeat or alter them; highlight contradictions.
- **Trust deltas & correction ledger**: Track corrections/retractions per source and surface recent changes.
- **Ownership graph**: Visualize parent companies and cross‑ownership; "coverage by ownership cluster".
- **Bias calibration wizard**: Users set a target lean mix; feed actively balances toward it.
- **Perspective prompts in summaries**: Neutral summary plus "how left/right framed it" notes with citations.
- **Paywall‑aware alternates**: Suggest open‑access alternates within a cluster.

### Product/UI Suggestions For Beacon
- **Cluster card**: Title, neutral summary, corroboration score, lean mix bar, sources count, expandable sources grouped by lean.
- **Blindspot feed**: Dedicated tab with Left/Right under‑coverage toggles; chips to flip perspectives.
- **Topic/timeline pages**: Sparkline of article count; key updates; "first report" vs. "consensus reached".
- **Local tab**: Country/region selector; top local clusters with the same badges.
- **Extension MVP (later)**: On‑article overlay with source lean/factuality and counter‑sources.

### Data To Start Collecting
- Per‑article: publish time, detected geo, entities/topics, paywall flag, factuality rating, ownership parent.
- Per‑cluster: corroboration metrics, lean distribution, first_seen, time_to_two_sources, time_to_three_leans.
- Per‑user (optional): view/click events by lean to drive bias profile/recommendations.

### Metrics & Validation
- **Clustering quality**: Sampled purity, split/merge error rate, silhouette‑like proxy, manual audit acceptance rate.
- **Corroboration health**: Median time_to_two_sources; median distinct_domains per cluster at 2/6/24 hours.
- **Blindspot signal**: Count of flagged clusters/day; CTR to "other perspective" sources.
- **Engagement**: CTR on perspective callouts, time on cluster page, newsletter open/click rates.

### Suggested Roadmap
- **Weeks 1–2 (Foundations)**: Corroboration metrics, cluster lean mix bar, blindspot‑lite callouts, timelines, daily briefing.
- **Weeks 3–6 (Differentiators)**: Explainable clustering UI, narrative drift timelines, ownership graph, claim map, bias calibration wizard.

— Prepared for Beacon3, Oct 2025


