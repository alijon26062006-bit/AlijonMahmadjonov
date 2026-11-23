# Algorithms, Trust & Safety and Admin/Back-office of Freelance & Two-sided Service Marketplaces

> Method note (read first): research done 2026-11-23. In this session, direct page fetching was blocked for upwork.com, support.upwork.com, help.fiverr.com, fiverr-res.cloudinary.com, medium.com and olxgroup.com (network allowlist). All facts below come from search-engine extracts of those pages (title + URL + quoted snippets), not from full-page reads. Treat numbers as "reported by the source page as indexed"; verify exact wording before quoting in product/legal documents. Dates are given where the source showed them; undated help-center articles are "current as indexed (2025–2026)".

## 1. Search ranking & matching (Upwork, Fiverr, Freelancer.com, Airbnb, Etsy)

### Takeaway
No major marketplace publishes its ranking formula; they disclose only the *families* of signals: query/skill relevance + quality/reputation (success score, ratings, completion) + seller behaviour (responsiveness, availability) + price fit + personalization, with recent data weighted higher. New sellers are handled by separate programs (Upwork Rising Talent badge, Fiverr level system) rather than by an explicitly disclosed "boost". Paid placement exists (Upwork Boosted Proposals auction, Etsy Ads) and is labeled and (per Etsy) kept separate from organic ranking.

### Cited Findings
**Fiverr**
- Fiverr help center: search placement reflects how a Gig performs on several quality and business metrics *compared with other Gigs in the marketplace*; Fiverr aims to show the best fit for each individual search rather than one fixed ranking. Factors named: machine-learning models, review scores, pricing, availability, freelancer responsiveness — [Fiverr: Fiverr's search and recommendation system](https://help.fiverr.com/hc/en-us/articles/37332082211217-Fiverr-s-search-and-recommendation-system); [Fiverr: Can't find your Gig?](https://help.fiverr.com/hc/en-us/articles/4599361153809-Can-t-find-your-Gig)
- Fiverr Success Score (1–10): each Gig is evaluated in six key areas (order-process and client-relationship factors); Gig scores roll up into the seller's overall score; benchmarked against freelancers *in the same price range*; a 10 is not required for success — [Fiverr: The success score, explained](https://www.fiverr.com/cp/success-score-explained); [Fiverr Help: Success score](https://help.fiverr.com/hc/en-us/articles/21965360854673-Success-score)
- Recent data is weighted more heavily than older data in the Success Score (Fiverr community/education post, Dec 2024 / June 2025) — [Fiverr Community: Two things you should know about your success score](https://community.fiverr.com/public/blogs/two-things-you-should-know-about-your-success-score-2025-06-23); [Fiverr Community: Understanding the Fiverr algorithm (2025-06-02)](https://community.fiverr.com/public/blogs/understanding-the-fiverr-algorithm-what-impact-your-ranking-2025-06-02)
- A "critically low" Success Score labels an account as low-performance and reduces platform visibility; levels are re-evaluated periodically — [Fiverr Help: Achieving levels / Fiverr's new level system](https://help.fiverr.com/hc/en-us/articles/360010560118-Fiverr-s-new-level-system)
- Level criteria combine completed orders, unique clients, earnings, Success Score, response rate and rating; Top Rated requires a manual review. Thresholds reported inconsistently across indexed versions (one extract: Level 1 = Success Score 5+, Level 2 = 7+; another extract of the "New pathways" page lists Level 1 with 9+ score/4.7+ rating/90% response — conflicting; verify live) — [Fiverr: New pathways (levels)](https://www.fiverr.com/cp/freelancers-levels-ratings); [Fiverr Help: Achieving levels](https://help.fiverr.com/hc/en-us/articles/360010560118-Achieving-levels)
- Rollout of the new level system used a one-month "shadow" period (new level visible only to the seller, buyers still saw old level) before going live on "March 14" (year not shown in extract; community threads about it date to 2024) — [Fiverr: New pathways](https://www.fiverr.com/cp/freelancers-levels-ratings). Sellers complained of scores "stuck at 4" and gigs dropping (anecdotal) — [Fiverr Community thread 327880](https://community.fiverr.com/public/forum/boards/freelancer-lounge-sry/posts/327880-success-score-and-new-level-system-is-the-worst-change-in-fiverr-ever-agree)
- Promoted Gigs eligibility depends on Success Score (users report becoming ineligible after score drop; anecdotal) — [Fiverr Community thread 330021](https://community.fiverr.com/public/forum/boards/support-and-troubleshooting-by1/posts/330021-became-ineligible-to-promoted-gig-and-the-stability-of-success-score)

**Upwork**
- Best Match: Upwork's spring 2024 product release added "enhancements to Best Match ranking in your proposal manager and Best Match insights, powered by Uma, Upwork's Mindful AI" — [Upwork Updates: Spring 2024](https://www.upwork.com/updates/spring-2024)
- Upwork's data-science blog (2019, older) lists the toolset used for matching: CTR prediction, learning-to-rank, collaborative filtering, content-based filtering, wide-and-deep recommenders; calls search & recommendation "the biggest opportunity" — [Upwork Eng: Data, ML and Marketplace Optimization – Part 1](https://www.upwork.com/careers/engineering-blog/data-machine-learning-and-marketplace-optimization-at-upwork-part-1-user-level-growth); [Part 2: Market Level Growth](https://www.upwork.com/careers/engineering-blog/data-machine-learning-and-marketplace-optimization-at-upwork-part-2-market-level-growth)
- Upwork combined an ontology (skills taxonomy) with ML to improve match (Medium/Geek Culture write-up) — [Combining Ontology and Machine Learning to Improve Match](https://medium.com/geekculture/combining-ontology-and-machine-learning-to-improve-match-1013719c6859)
- Community staff answers: Best Match depends on profile skills, work history and "a variety of factors" (no formula disclosed) — [Upwork Community: Best Matches Job Feed](https://community.upwork.com/t5/Freelancers/Best-Matches-Job-Feed/m-p/1211125)
- Rising Talent (new-talent program): needs 100% complete profile with accurate skills, a submitted proposal or active work in the past 90 days; agencies also need ≥2 team members; eligibility recomputed every two weeks; meeting criteria does not guarantee the badge (category and "other factors" considered) — [Upwork Help: Top Rated and Rising Talent](https://support.upwork.com/hc/en-us/articles/211063568-Top-Rated-and-Rising-Talent); [Upwork: How to get Rising Talent badge](https://www.upwork.com/resources/how-to-get-rising-talent-badge)
- Top Rated requires ≥90% JSS (maintained) — [Upwork: Talent badges explained](https://www.upwork.com/resources/talent-badges-explained)
- Paid placement — Boosted Proposals: freelancer bids extra Connects in an auction for the **top four slots** of the client's applicant list; auction runs 7 days or until hire; boost Connects refunded if not in top four *and* client did not interact — [Upwork Help: Boosted Proposals](https://support.upwork.com/hc/en-us/articles/4406541109011-Boosted-Proposals); [Upwork Help: Boost your proposal](https://support.upwork.com/hc/en-us/articles/4406395531795-Boost-your-proposal)
- Labeling: boosted proposals marked with a blue lightning bolt; a Sept 2022 announcement said clients see "Highly Interested" + lightning bolt and are told these are from talent who paid to express interest (current wording unverified) — [Upwork Community: Increasing Transparency in Boosted Proposals (2022)](https://community.upwork.com/t5/Support-Forum/Increasing-Transparency-in-Boosted-Proposals/m-p/1149695)

**Freelancer.com** — no official ranking/"Freelancer Rank" documentation surfaced (see Gaps).

**Airbnb (engineering, primary)**
- Listing embeddings learned from search sessions used for similar-listing recs and real-time personalization; "Search Ranking and Similar Listings drive 99% of our booking conversions" (2018) — [Airbnb Eng: Listing Embeddings in Search Ranking](https://medium.com/airbnb-engineering/listing-embeddings-for-similar-listing-recommendations-and-real-time-personalization-in-search-601172f7603e)
- "Applying Deep Learning to Airbnb Search" (2018): initial gains came from gradient-boosted decision trees; gains plateaued, then moved to neural nets — [arXiv 1810.09591](https://ar5iv.labs.arxiv.org/html/1810.09591)
- Two-stage retrieval → ranking: Embedding-Based Retrieval narrows eligible homes to a smaller pool scored by heavier models; listing vectors computed offline in daily batch; contrastive learning; bookings lift "on par with some of the largest ML improvements to search ranking in the past two years" — [Airbnb Tech: Embedding-Based Retrieval for Airbnb Search](https://airbnb.tech/ai-ml/embedding-based-retrieval-for-airbnb-search/); [arXiv 2601.06873 (2026)](https://arxiv.org/abs/2601.06873)
- "Beyond Pairwise Learning-To-Rank at Airbnb" (2025) — [arXiv 2505.09795](https://arxiv.org/pdf/2505.09795)

**Etsy**
- Ranking factors not equally weighted; main ones: query relevancy (title/tags) and listing quality (conversion, clicks, favorites, purchases); shop-level signals reportedly include average review rating, message response rate and case rate over past 3 months (as quoted from Etsy Seller Handbook by third parties) — [Etsy Community: How Etsy Search Works](https://community.etsy.com/t5/WHAT-39-S-NEW/How-Etsy-Search-Works/td-p/114197969); [Etsy Seller Handbook podcast transcript](https://www.etsy.com/uk/seller-handbook/article/podcast-transcript-etsy-search/397558006917); [Marmalead: How Etsy actually ranks listings (3rd party)](https://blog.marmalead.com/how-etsy-actually-ranks-listings/)
- Etsy states running Etsy Ads does not influence organic search placement outside designated ad spaces (quoted via third-party page; a different third-party guide claims the opposite — trust Etsy) — [EcommerceBytes](https://www.ecommercebytes.com/pkvo); [Printful Etsy SEO](https://www.printful.com/blog/etsy-seo)

**Regulatory transparency of ranking (EU, relevant as best practice)**
- EU P2B Regulation Art. 5: platforms must disclose main ranking parameters and reasons for their relative importance; paid ranking boosts require extra disclosure. Commission proposed repeal of P2B on 19 Nov 2025 (digital simplification package; status unverified) — [EC: Platform-to-business trading practices](https://digital-strategy.ec.europa.eu/en/policies/platform-business-trading-practices)
- DSA Art. 27: platforms using recommender systems must explain main parameters in T&Cs and any user options to modify them — [Pinsent Masons: How the DSA changes things for platforms](https://www.pinsentmasons.com/out-law/analysis/how-the-digital-services-act-changes-things-for-platforms)

### Inferences
- Common pattern to copy at launch: Stage 1 filter (category/skills/language/location/availability/price) → Stage 2 weighted score = relevance × (quality: rating, completion, on-time, success score) × (behaviour: response rate/time, recent activity) + controlled new-seller exposure slot; recency-weighting of quality metrics (Fiverr). Airbnb's history (GBDT first, then neural nets, then embedding retrieval) shows ML comes after data accumulates.
- Benchmarking quality "against peers in the same price range" (Fiverr) is a cheap fairness trick usable in a small market.
- Paid boosts should be capped (Upwork caps at top 4 slots), clearly labeled, and separate from organic score (Etsy).
- Publishing a plain-language "how ranking works" page mirrors EU P2B/DSA practice; useful for trust even if not legally required in Tajikistan.

### Gaps
- No official Freelancer.com ranking/Freelancer Rank documentation retrieved.
- No official disclosure of any explicit "new seller boost" multiplier at Fiverr or Upwork; existence only implied by programs (Rising Talent) — unconfirmed.
- Exact current Fiverr level thresholds conflict between indexed versions.

## 2. Recommendations (jobs→freelancers, talent→clients, alerts) & rule-based start

### Takeaway
Published material shows a progression: rules/heuristics and taxonomy matching → GBDT/learning-to-rank → embeddings and two-tower retrieval; LLM assistants (Upwork Uma) now sit on top for ranking insights. Primary engineering write-ups exist for Airbnb and (older) Upwork; Fiverr engineering details were not retrievable.

### Cited Findings
- Upwork's recommender toolkit (2019): CTR prediction, LTR, collaborative filtering, content-based filtering, wide-and-deep — [Upwork Eng Part 1](https://www.upwork.com/careers/engineering-blog/data-machine-learning-and-marketplace-optimization-at-upwork-part-1-user-level-growth); summary — [Upwork Eng Summary](https://www.upwork.com/careers/engineering-blog/data-machine-learning-and-marketplace-optimization-at-upwork-summary)
- Upwork "Scaling AI models for better work outcomes" (Uma) — [Upwork Blog](https://www.upwork.com/blog/scaling-ai-models-for-better-work-outcomes); Best Match insights powered by Uma (spring 2024) — [Upwork Updates Spring 2024](https://www.upwork.com/updates/spring-2024)
- Upwork's 2025–2026 job listings for "Search & Recommendations" ML engineers describe modelling user preferences, intent and context (signals of current direction) — [Greenhouse: Upwork job](https://job-boards.greenhouse.io/upwork/jobs/7490995003); [BuiltIn listing](https://builtin.com/job/senior-applied-machine-learning-engineer-search-recommendations/7324272)
- Fiverr help center describes a combined "search and recommendation system" using ML models (no technical detail) — [Fiverr Help](https://help.fiverr.com/hc/en-us/articles/37332082211217-Fiverr-s-search-and-recommendation-system)
- Airbnb: GBDT first, plateau, then deep learning (2018) — [arXiv 1810.09591](https://ar5iv.labs.arxiv.org/html/1810.09591); embeddings for similar-item recs and real-time personalization — [Airbnb Eng](https://medium.com/airbnb-engineering/listing-embeddings-for-similar-listing-recommendations-and-real-time-personalization-in-search-601172f7603e)

### Inferences
- For a small Tajik market: start with (a) skills/category taxonomy match, (b) saved searches + instant/daily alerts on new jobs matching freelancer skills, (c) rule-based score with hand-set weights, logging impressions/clicks/applications/hires from day 1 so LTR/GBDT can be trained later (Airbnb path). Multilingual (Tajik/Russian/English) text embeddings could be added early for job↔profile similarity since they need no interaction data.

### Gaps
- No Fiverr engineering blog post on ranking/recs retrieved (medium.com/fiverr-engineering blocked/not surfaced). No Etsy Code as Craft post surfaced. No Upwork post-2023 technical write-up on Best Match found.
- Saved-search/alert mechanics of Upwork/Fiverr not documented in retrieved sources.

## 3. Reputation systems (JSS, reviews integrity, private feedback)

### Takeaway
Upwork JSS = client-satisfaction composite weighted by contract value, with long-term relationships helping; shown only after ≥2 projects with ≥2 clients in 24 months; no-feedback contracts excluded since Nov 2020; private feedback status is contradictory across help pages. Airbnb uses a 14-day double-blind review window and automated fake-review removal.

### Cited Findings
- JSS measures client satisfaction; higher-earning jobs have bigger impact; long-term client relationships help but absence doesn't hurt — [Upwork Help: How is my JSS calculated](https://support.upwork.com/hc/en-us/articles/38437458199059-How-is-my-Job-Success-Score-calculated); [Upwork Help: What is a JSS](https://support.upwork.com/hc/en-us/articles/38437362753171-What-is-a-Job-Success-Score)
- Eligibility: ≥2 projects with ≥2 clients within 24 months — [Upwork Help: When will I get a JSS](https://support.upwork.com/hc/en-us/articles/38437546570643-When-will-I-get-a-JSS)
- Update cadence conflicts: one article says daily, another every 2 weeks; community post says four scores over different windows (e.g., past 24 months) are computed and the highest displayed — [Upwork Community: How JSS is Calculated](https://community.upwork.com/t5/Announcements/How-Job-Success-Score-is-Calculated/m-p/906255)
- JSS update December 2023 (release note) — [Upwork Community: JSS Update Dec 2023](https://community.upwork.com/t5/Product-Release-Notes/Job-Success-Score-Update-December-2023/ba-p/1481522)
- From Nov 8, 2020, contracts ending without feedback excluded from JSS — [Upwork release note](https://community.upwork.com/t5/Product-Release-Notes/No-feedback-contracts-no-longer-impact-Job-Success-Score-JSS/bc-p/923483/highlight/true)
- Factors include disputed contracts; on unpaid contracts negative feedback can affect JSS, but no payment + no feedback does not — [Upwork Help: What factors affect my JSS](https://support.upwork.com/hc/en-us/articles/38439816969875-What-factors-affect-my-Job-Success-Score)
- Private feedback: one Upwork help article says private feedback is "no longer requested from your clients and no longer impacts your reputation, including JSS"; another says any end-of-contract feedback is considered — **conflict, unresolved** — [Upwork Help 17931783162643](https://support.upwork.com/hc/en-us/articles/17931783162643); [Upwork Help: Job Success insights](https://support.upwork.com/hc/en-us/articles/32389629156755-Job-Success-insights)
- Job Success insights page shows how the score is calculated and what affects it (not for agencies) — [Upwork Help: Job Success insights](https://support.upwork.com/hc/en-us/articles/32389629156755-Job-Success-insights)
- Fiverr Success Score: per-Gig scores across six areas, peer-benchmarked by price range, recency-weighted — [Fiverr: success score explained](https://www.fiverr.com/cp/success-score-explained)
- Airbnb: 14-day window after checkout; double-blind (neither sees the other's until both submit or window closes) — [Airbnb Help 2673](https://www.airbnb.com/help/article/2673); Airbnb does not pre-moderate reviews; automated system removes reviews likely fake (not tied to genuine stay or made to inflate ratings); removal only for clear policy violations; prohibited: fake reservation for a review, second account to self-review, coordinated manipulation — [Airbnb Help 548: dispute moderation for reviews](https://www.airbnb.com/help/article/548/airbnbs-dispute-moderation-for-reviews); [Airbnb Help 3048](https://www.airbnb.ca/help/article/3048); retaliatory-review protections expanded Nov 2022 (per third party) — [Hospitable](https://hospitable.com/airbnb-review-policy)
- Avito: ML model classifies reviews genuine vs suspicious (anti-boosting); a user post claims >90% accuracy (not official) — [VK post](https://vk.ru/@avito_biz24-avito-otzyv-otklonen-sistemoi-borby-s-nakrutkami-chto-delat)

### Inferences
- Design: reviews only from completed paid orders; double-blind 14-day window; separate public rating vs internal "success score" that includes disputes, cancellations, late delivery, response rate; weight by order value; require minimum N orders/clients before showing score (Upwork: 2/2) to avoid noise; show "New" badge instead.

### Gaps
- Exact JSS formula never published by Upwork. Current status of private feedback unresolved.

## 4. Fraud & abuse patterns and detection; off-platform policies & penalties

### Takeaway
Top patterns: off-platform payment steering, fake clients/jobs (incl. AI-generated), "pay for background check/equipment" scams, Telegram/WhatsApp lures, multi-accounting, identity fraud, state-linked actors. Detection: ML job screening pre-publication, contact-info masking/blocking in messages, device/location intelligence (Upwork–Incognia 2026), velocity and network rules. Penalties: Upwork — loss of badges up to permanent account closure; Fiverr — automated warnings, loss of protections, account action.

### Cited Findings
**Off-platform policy**
- Upwork: circumvention = meeting on Upwork then paying outside without the conversion fee; 24-month Non-Circumvention Period during which Upwork must be exclusive payment method; conversion fee allows legitimate exit — [Upwork Help: Why can't I get paid directly](https://support.upwork.com/hc/en-us/articles/360048105134-Why-Can-t-I-Get-Paid-Directly); [ConductAtlas summary of Upwork ToS (3rd party)](https://conductatlas.com/platform/upwork/upwork-terms-of-service/non-circumvention-and-conversion-fee/)
- Upwork penalties: sharing contact info before contract and taking payments off-platform can cause loss of talent badges and, in some cases, permanent account closure; breaching non-circumvention → suspension — [Upwork Help 360048105134](https://support.upwork.com/hc/en-us/articles/360048105134); [Upwork Help: On-platform interviews](https://support.upwork.com/hc/en-us/articles/360052511833-On-platform-Interviews)
- Fiverr: do not share emails, phone numbers or third-party messaging apps for off-platform business; violates ToS; off-platform users lose secure payment and dispute protections; violation triggers an **automated** notice email; warnings may be the first step; reports go to Trust & Safety — [Fiverr Community Standards: Off-platform policy](https://help.fiverr.com/hc/en-us/articles/38728907371665-Community-Standards-Off-platform-policy); [Fiverr: Stay protected](https://help.fiverr.com/hc/en-us/articles/12792122691601); [Fiverr: Policy Violations Explained](https://help.fiverr.com/hc/articles/48022851354385)
- Airbnb: system automatically screens out phone numbers, emails and other personal info in listings, house rules and messages until a reservation is booked — [Airbnb News: Preventing fake listing scams](https://news.airbnb.com/what-were-doing-to-prevent-fake-listing-scams/)

**Patterns & detection**
- Upwork uses ML to scan jobs for fraud signals *before posting*; responds to user reports; warns scams may appear before T&S removes them — [Upwork: How to identify scams (2026)](https://www.upwork.com/resources/upwork-scams); [Upwork: Spotting fake job posts](https://www.upwork.com/resources/spotting-fake-job-posts)
- Red flags Upwork lists: AI-generated fake profiles, fake background-check payment requests, clients with multiple open jobs and no spend; AI lets scammers create fake postings at scale — [Upwork: Upwork scams](https://www.upwork.com/resources/upwork-scams)
- Upwork 2025 Transparency Report (published Feb 26, 2026): identity-verified freelancers +22%; bad-actor freelancer proposals −82% YoY; offers from malicious client accounts −>90% YoY — [Upwork Blog: 2025 Transparency Report](https://www.upwork.com/blog/upworks-2025-transparency-report-our-ongoing-work-to-protect-yours); [Upwork 2025 Year in Review](https://www.upwork.com/blog/creating-opportunity-in-2025-upworks-year-in-review)
- 2024 data (Upwork support attachment, as indexed): 827,265 job posts [removed — wording cut off] and 184,914 accounts suspended — [Upwork attachment](https://support.upwork.com/hc/article_attachments/49240410937491) (verify)
- Upwork partnered with Incognia (2026): cross-device risk intelligence, location precision, tamper detection, device intelligence — [Upwork scams page](https://www.upwork.com/resources/upwork-scams); [The Paypers](https://thepaypers.com/fraud-and-fincrime/news/incognia-teams-up-with-upwork-to-optimise-marketplace-trust-and-integrity)
- Upwork statement on state-linked activity (e.g., fraudulent remote-worker schemes) — [Upwork Blog](https://www.upwork.com/blog/upwork-statement-on-state-sponsored-threats)
- Upwork Account Health Hub (2025): dashboard showing account status/enforcement — [Upwork Blog: Account Health Hub](https://www.upwork.com/blog/transparency-you-can-see-inside-upworks-new-account-health-hub)
- Fiverr scams (community): buyers asking for email to "complete payment" with fake screenshots; Telegram scams; Fiverr support never contacts via inbox — [Fiverr Community: Telegram scam](https://community.fiverr.com/forums/topic/334610-the-telegram-scam); [Fiverr: Avoiding spam and staying safe](https://help.fiverr.com/hc/en-us/articles/37333200572049-Avoiding-spam-and-staying-safe-on-Fiverr)
- Chargebacks: Fiverr says bank/PayPal claims take 45 days to 3 months — [Fiverr Help: refunds & chargebacks](https://help.fiverr.com/hc/en-us/articles/360049910953-Requesting-a-refund-for-a-canceled-order)
- Avito uses oneFactor ML platform (commercial since early 2022) incl. preventing repeat registrations of fraudsters — [Rozetked](https://rozetked.me/news/25540-avito-odnim-iz-pervyh-protestiroval-platformu-mashinnogo-obucheniya-onefactor)
- Vendor framing (Stripe/SEON, treat as practitioner, not research): rules = fast explicit layer (velocity windows, thresholds, cohort-based by tenure); device fingerprint (browser config, screen, fonts; persists across cookie clears; emulator/VM = high-precision signal); multi-account via shared device/IP/email-domain graph; risk score → approve/review/decline; tuned rules respond in hours while ML needs volume — [Stripe: ecommerce fraud prevention](https://stripe.com/resources/more/ecommerce-fraud-prevention); [SEON: fraud rules](https://seon.io/resources/fraud-rules-for-fintechs/)
- Off-platform steering often avoids keywords and splits across messages; needs conversation-level intent detection; signal: conversation goes silent right after contact exchange (vendor sources) — [Stream blog](https://getstream.io/blog/off-platform-payment-requests/); [Sardine](https://www.sardine.ai/learn/off-platform-payment-abuse)

### Inferences
- Minimum launch stack: contact-info/link detection in chat pre-contract (mask + warn, escalating to restriction), job-post screening (rules + LLM), device ID + IP + phone uniqueness for multi-account graphs, velocity limits on new accounts (messages/proposals/withdrawals per hour/day), payout holds for new accounts, and a user-visible "account health" page (Upwork 2025).
- Conversation-silence-after-contact-share and repeated cancellations between the same pair are cheap circumvention signals.

### Gaps
- No public detail on how Upwork/Fiverr score payment risk internally. Money-laundering typologies specific to freelance platforms not found in primary sources this session.

## 5. Chat moderation with AI/LLMs

### Takeaway
Real deployments use a cascade: regex/keyword + small classifier → LLM on the uncertain minority (DoorDash <10%) with conversation-level context (Whatnot) → human review for actions; outputs should be scores, not booleans. Platforms disclose scanning in help/privacy pages (Airbnb explicitly) and auto-block/redact contact info.

### Cited Findings
- Airbnb discloses: "We may review or analyze your messages on Airbnb for safety, support, and to provide and improve our services"; one main reason is fraud prevention; system may block messages from being sent; contact details/external links can be removed; Airbnb does not scan messages for third-party marketing nor sell analyses; users can exercise rights over message data incl. for certain AI features — [Airbnb Help 1121](https://airbnb.com/help/article/1121); [Airbnb Help 1121 (CA)](https://www.airbnb.ca/help/article/1121)
- Fiverr: off-platform contact sharing triggers automated notices; users can report messages, Gigs, video calls, briefs — [Fiverr: Policy Violations Explained](https://help.fiverr.com/hc/articles/48022851354385); [Fiverr: Reporting content](https://help.fiverr.com/hc/articles/9596156809105)
- Fiverr EU DSA Transparency Report covering 17 Feb–31 Dec 2024 describes automated and manual moderation, reports forwarded to T&S team (figures not retrieved) — [Fiverr DSA Transparency Report (PDF)](https://fiverr-res.cloudinary.com/image/upload/attachments/generic_asset/asset/475a04a34e698e3faa4a31101c104a8a-1749451231889/DSA%20Transparency%20Report_Final.pdf)
- OLX: moderates chat messages in real time; built "Chat Images GenAI" to flag fraudulent images in sales chats, which represent ~30% of fraud cases on its Polish platform (Jan 2026) — [OLX Group](https://www.olxgroup.com/?p=4590)
- Vestiaire Collective: historically regex flagged suspicious messages → human annotators; compares classic ML vs LLM; scammers adapt language quickly — [Vestiaire Connected (Medium)](https://medium.com/vestiaire-connected/how-to-create-your-own-ai-chat-moderation-model-c2bab9029c65)
- DoorDash SafeChat: small in-house model screens first; LLM only for messages not confidently safe (<10% of messages); recommends LLM output a score for threshold tuning — [InfoQ: DoorDash LLM moderation platform](https://infoq.com/presentations/doordash-llm-ai-moderation-platform)
- Whatnot (2023, case write-up): per-message judgement had low precision; LLM over full conversation history; outcomes close / act / escalate-to-human — [ZenML LLMOps DB](https://www.zenml.io/llmops-database/llm-enhanced-trust-and-safety-platform-for-e-commerce-content-moderation)
- Yelp (Mar 2024): AI pipeline for inappropriate language using moderator severity scores — [Yelp Engineering](https://engineeringblog.yelp.com/2024/03/ai-pipeline-inappropriate-language-detection.html)
- Google study: LLM-assisted human raters — highlighting relevant text raised human precision and recall by 9–11 pts absolute; 41.5% better use of rater capacity — [arXiv 2406.12800](https://arxiv.org/html/2406.12800v1)
- Most LLM moderation errors (FP/FN) stem from missing context — [Cambridge core reader (Grossman et al.)](https://www.cambridge.org/core/product/2F8E6B537B55F11468499BEB15BAEB5C/core-reader); LLM moderation evaluation — [arXiv 2309.14517](https://arxiv.org/pdf/2309.14517)
- Gumtree Australia reports ~80% drop in fraudulent messages with Stream AI moderation (vendor case study; page also shows ~25% elsewhere — inconsistent) — [Stream: Gumtree case study](https://getstream.io/blog/gumtree-australia-case-study/)
- Pipeline described by a 2026 practitioner post: signal detection → AI analysis → policy decision → human review → feedback → policy improvement; false positives matter as much as detection — [Faster Than Light blog](https://fasterthanlight.me/blog/post/building-ai-assisted-anti-fraud-moderation)
- Avito auto-moderation (ads/video): Whisper fine-tuned on Avito data as first stage; sample of "clean" items sent to manual check to measure metrics — [prog.world (translation of Avito Habr post)](https://prog.world/how-we-launched-automatic-video-moderation-in-avito-ads); Avito auto-moderation DS article — [Habr 882572](https://habr.com/ru/articles/882572)

### Inferences
- For the planned AI agent moderating every chat: (1) deterministic pre-filter (phones +992, emails, Telegram/WhatsApp handles, URLs, card numbers) before LLM — cheap and explainable; (2) LLM over a sliding conversation window, output a risk score + category + evidence span; (3) graduated actions: soft inline warning → mask → block send → T&S queue; never auto-ban on LLM alone; (4) random sampling of "clean" chats for human QA to measure false negatives (Avito practice); (5) disclose scanning in ToS/privacy and in-chat banner (Airbnb practice); keep data on own server, limit retention.

### Gaps
- Upwork's message-scanning practice not documented in retrieved sources. Vinted/Avito chat-specific ML details not found. Fiverr DSA report figures not retrieved (fetch blocked).

## 6. Identity verification (KYC)

### Takeaway
Upwork requires ID verification to submit proposals, accept contracts and withdraw; uses government ID + address match, sometimes a live video call with an agent; review up to 48h. Fiverr uses a third-party ID + live selfie check, may be required before publishing Gigs, premium programs, or on risk; statuses required/in progress/verified; documents kept 30 days.

### Cited Findings
- Upwork: accepted IDs passport, driver's license, national ID; ID photo must match profile photo; address on ID must match profile — [Upwork Help: ID Verification](https://support.upwork.com/hc/en-us/articles/9908325862163-ID-Verification); [Upwork Help: Verify your identity](https://support.upwork.com/hc/en-us/articles/26040445438611-Verify-your-identity)
- Upwork video verification: team schedules a short video meeting with camera on to confirm account holder; not an English test; review may take up to 48h; some users asked to re-verify — [Upwork Help: Troubleshoot Video Verification](https://support.upwork.com/hc/en-us/articles/360010687433-Troubleshoot-Video-Verification); [Upwork Community (2023)](https://community.upwork.com/t5/Support-Forum/Identity-Verification/m-p/1420337)
- Upwork deletes submitted ID image after 30 days; third-party provider keeps up to 1 year; verification required to submit proposals, accept contracts, withdraw; optional Identity Verified badge costs 35 Connects — [Upwork: Identity verified badge](https://www.upwork.com/resources/identity-verified-badge)
- Upwork 2025: expanded verification *earlier* in the talent journey → +22% verified freelancers — [Upwork 2025 Transparency Report blog](https://www.upwork.com/blog/upworks-2025-transparency-report-our-ongoing-work-to-protect-yours)
- Fiverr: verification may be needed to offer services, publish Gigs, join premium programs, when account safety is in doubt, or by regulation; third-party software validates government ID authenticity and selfie authenticity and matches them; no saved images/screenshots; statuses: required / in progress / verified; ID copy and selfie kept 30 days; Fiverr never requests ID via email — [Fiverr Help: Verify your identity](https://help.fiverr.com/hc/en-us/articles/13127850435345-Verify-your-identity); [Fiverr: Verifying identity as new freelancer](https://help.fiverr.com/hc/en-us/articles/6348992414097); [Fiverr: ID verification data protection](https://help.fiverr.com/hc/en-us/articles/13127840321937)
- Complaints of failed checks and long restrictions (anecdotal) — [Fiverr Community 327620](https://community.fiverr.com/forums/topic/327620-my-account-was-temporarily-restricted-after-uploading-id-documents-its-more-than-1-year-now)

### Inferences
- Tiered KYC fits a small market: phone (SMS/Telegram OTP) at signup → ID + selfie before first payout or above a threshold → video call for flagged/high-value accounts; manual review queue with SLA ≤48h; store minimal data, delete images after decision (30 days as at Upwork/Fiverr).

### Gaps
- Specific payout thresholds triggering KYC at Upwork/Fiverr not found. Fiverr vendor (Persona etc.) not confirmed.

## 7. Dispute resolution & arbitration operations

### Takeaway
Typical ladder: parties negotiate in a resolution center with short auto-resolve timers → platform mediation (non-binding) → paid binding arbitration (Upwork, Freelancer.com) or support decision (Fiverr). Timers and default outcomes (silence = lose) drive most resolutions.

### Cited Findings
- Upwork fixed-price: Upwork dispute team gives non-binding recommendation; if disagreement, parties may go to binding arbitration by a neutral third party; when funds not in escrow, mediation first; if both decline arbitration the case closes — [Upwork: Dispute process demystified](https://www.upwork.com/resources/upwork-dispute-process); [Upwork Help 14044146250259](https://support.upwork.com/hc/en-us/articles/14044146250259); [Upwork Help: Respond to an escrow dispute](https://support.upwork.com/hc/en-us/articles/211062068-Respond-to-an-Escrow-Dispute)
- Upwork escrow terms: arbitration available if fixed-price escrow funded at least once; if a party doesn't pay arbitration fee within 5 business days of first notice, funds go to the party that paid — [Upwork Community quoting escrow instructions](https://community.upwork.com/t5/Freelancers/Dispute-leading-to-Arbitration/td-p/967019)
- Arbitration fee reported in 2020 as $291 per party (client + freelancer) with Upwork paying ~$293 (anecdotal, dated) — [Upwork Community 2020](https://community.upwork.com/t5/Freelancers/Dispute-Resolution-and-Arbitration-fee-of-291/m-p/733685); Upwork now calls escrow "project funds"
- Fiverr Resolution Center: freelancer has 48h to accept/decline a cancellation request, else auto-cancel; "Very Late" (24h after Late) allows immediate cancel; completed orders need Customer Support; Resolution Center requests go to the other party, Support not auto-notified — [Fiverr Help: How cancellations work for clients](https://help.fiverr.com/hc/en-us/articles/37552956376977-How-cancellations-work-for-clients); [Fiverr Help: Using the Resolution Center](https://help.fiverr.com/hc/en-us/articles/37552897293329-Using-the-Resolution-Center)
- Freelancer.com: disputes only for Milestone Payments; filer states amount they'd pay/accept; respondent has 4 days (freelancer) or 14 days (client) to respond or loses; arbitration when one refuses to settle and both pay arbitration fee; Dispute team gives final, irreversible verdict — [Freelancer.com: Dispute Resolution Services](https://www.freelancer.com/faq/topic.php?code=disputes); [Freelancer support mirror](https://www.freelancer.is/support/Payments/dispute-resolution-service-32237)

### Inferences
- For launch: resolution center with structured reasons, evidence upload (files, chat excerpts auto-attached), 48–72h response timers with default outcomes, partial-refund slider (Freelancer.com "amount I'd accept"), then staff decision; the AI chat moderator's logs become evidence. Paid external arbitration is unrealistic in Tajikistan at launch; use internal 2-tier review (agent → senior).

### Gaps
- Current Upwork arbitration fee/provider not confirmed. Staff tooling for disputes at these companies not publicly documented.

## 8. Admin / back-office capabilities

### Takeaway
Public operator docs (Sharetribe Console) show the baseline: user management/filters/bans, approval gating, transaction state overrides with actor attribution, listing approval, review management, CSV export, email users. Big platforms add user-facing account-health dashboards and transparency reporting. No primary source detailed RBAC/audit/2FA for staff at Upwork/Fiverr.

### Cited Findings
- Sharetribe Console: filter users (has listings, verified email, banned); restrict who can initiate transactions; approve users before access or listing; email users; delete Stripe data on account removal — [Sharetribe docs: Console manage users](https://www.sharetribe.com/docs/concepts/console-manage-users); [Sharetribe Help: Restrict transaction rights](https://www.sharetribe.com/help/en/articles/9790336-restrict-transaction-rights); [Sharetribe: User access control](https://sharetribe.com/docs/concepts/user-access-control-in-sharetribe)
- Operator transitions to change transaction states; changelog shows which admin initiated a transition (audit trail) — [Sharetribe Help: Manage transactions](https://www.sharetribe.com/help/en/articles/9263620-manage-transactions); [Sharetribe changelog 2025](https://www.sharetribe.com/changelog/small-improvements-2025/)
- Listing approval ("Pending approval"), reviews management page, banned users' messages hidden, CSV export on every Manage page, private-marketplace mode, third-party moderation/analytics extensions — [Sharetribe: Console manage listings](https://www.sharetribe.com/docs/concepts/console-manage-listings/); [Sharetribe: Marketplace management](https://www.sharetribe.com/features/marketplace-management/)
- Upwork Account Health Hub (user-facing status/enforcement transparency, 2025) — [Upwork Blog](https://www.upwork.com/blog/transparency-you-can-see-inside-upworks-new-account-health-hub)
- DSA transparency reporting of moderation (Fiverr 2024 report) — [Fiverr DSA report](https://fiverr-res.cloudinary.com/image/upload/attachments/generic_asset/asset/475a04a34e698e3faa4a31101c104a8a-1749451231889/DSA%20Transparency%20Report_Final.pdf)

### Inferences
- Recommended modules: Users (search, status, notes, risk score, linked accounts graph, sanctions with reason codes), Queues (AI-flagged chats, reports, listings/jobs, reviews, KYC, disputes, payouts) with SLAs and assignment, Finance (payout approval/holds, refunds/partial refunds, fee & commission config, promo codes), CMS (categories/skills taxonomy, help pages, banners), Analytics (GMV, take rate, fill rate, time-to-first-response, time-to-hire, repeat rate, dispute rate), Security (RBAC roles: support, moderator, finance, admin; mandatory 2FA; immutable audit log of every admin action incl. viewing chats/KYC; 4-eyes on payouts/bans).

### Gaps
- No primary source on Upwork/Fiverr internal admin tooling, staff RBAC, or 2FA requirements; recommendations above are inference.

## 9. Marketplace health metrics

### Takeaway
a16z (Feb 2020) "13 metrics" frames liquidity (fill/match rate, time to match, market depth), retention cohorts and repeat rate as core; early-stage marketplaces should prioritize match rate and time-to-match.

### Cited Findings
- a16z "13 Metrics for Marketplace Companies" (Jeff Jordan, Li Jin, D'Arcy Coolican, Andrew Chen, Feb 21 2020): includes liquidity measured by fill/match rate, time to match, market depth; user retention cohorts, core-action retention cohorts — [a16z](https://a16z.com/13-metrics-for-marketplace-companies/); glossary — [a16z marketplace glossary](https://a16z.com/the-marketplace-glossary/)
- Lenny's Newsletter: "The most important marketplace metrics" — [Lenny's Newsletter](https://www.lennysnewsletter.com/p/the-most-important-marketplace-metrics)
- Liquidity definition and caveats (state time window with fill rate; high fill rate can hide poor quality that shows in repeat rate) — [Point Nine: WTF is marketplace liquidity](https://writing.pointnine.com/p/wtf-is-marketplace-liquidity); [Rework: marketplace metrics](https://resources.rework.com/libraries/marketplace-growth/marketplace-metrics)
- Stripe: 14 key marketplace metrics (GMV, take rate, etc.) — [Stripe](https://stripe.com/en-br/resources/more/14-key-marketplace-metrics)

### Inferences
- Launch dashboard: % jobs with ≥1 proposal in 24h, % jobs hired within 7/14 days (fill rate), median time-to-first-proposal and time-to-hire, client repeat-hire rate at 90 days, GMV, take rate, dispute rate, AI-flag rate & precision of moderation.

### Gaps
- Full list of a16z's 13 metrics not retrieved verbatim; Reforge/NFX not covered this session.
