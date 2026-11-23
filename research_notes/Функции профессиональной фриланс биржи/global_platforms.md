# Global Freelance Marketplaces: Feature Inventory (Upwork, Fiverr, Freelancer.com, Toptal, Malt, Contra, PeoplePerHour), state as of late 2026

> Method note (important for the report writer): research done 2026-11-23. In this session, direct page fetching (WebFetch) was blocked by the network sandbox for support.upwork.com, help.fiverr.com, freelancer.com, help.malt.com, contra.com. All facts below come from web-search results restricted to official domains (help centers, ToS, official blogs) and quote or paraphrase the official snippets. A few figures come from third-party guides; these are explicitly labelled "(3rd-party)". Facts I could not verify are under "Gaps". Several official help pages are old (search tool reported page ages of 500–2,700 days); where that matters it is flagged.

## 1. Accounts, profiles, badges & reputation systems

### Takeaway
Reputation is a core product mechanic on every open marketplace. It is computed from outcome metrics (ratings, repeat clients, cancellations or disputes, response rate, earnings) and shown as tiered badges: Upwork's JSS with Rising Talent, Top Rated, Top Rated Plus and Expert-Vetted, and Fiverr's New, Level 1, Level 2 and Top Rated. The top tier is gated by manual review. Curated platforms (Toptal) replace reputation with up-front vetting (<3% acceptance).

### Cited Findings
**Upwork badges / JSS**
- Top Rated requires a Job Success Score of at least 90% for at least 13 of the last 16 weeks, plus more than $10,000 in earnings in the past 12 months. — [Upwork: Learn about talent badges](https://support.upwork.com/hc/en-us/articles/360049702614-Learn-about-Upwork-s-talent-badges); [Understand freelancer talent badges](https://support.upwork.com/hc/en-us/articles/211063568-Understand-freelancer-talent-badges)
- Top Rated Plus = "top 3% of performers", which requires proven success on large or long-term contracts. Expert-Vetted = "top 1% of talent". Only Business Plus clients can view Expert-Vetted talent. — [Upwork: talent badges](https://support.upwork.com/hc/en-us/articles/360049702614-Learn-about-Upwork-s-talent-badges); [Upwork: Is Upwork free (pricing breakdown 2026)](https://www.upwork.com/resources/is-upwork-free)
- Uma Recruiter (the AI hiring agent) uses Job Success Score as one of its ranking and evaluation factors. — [Upwork blog: Uma Recruiter](https://www.upwork.com/blog/uma-recruiter-how-we-built-an-agentic-solution-to-talent-matching-and-hiring)

**Fiverr seller levels (current "six-metric" system, introduced in the 2023 level overhaul)**
- The six metrics are rating, response rate, orders, unique clients, earnings and Success Score. Older metrics (order completion rate and on-time delivery ≥90%) were removed. — [Fiverr: New pathways for success](https://www.fiverr.com/cp/freelancers-levels-ratings); [Fiverr Help: Understanding freelancer levels](https://help.fiverr.com/hc/en-us/articles/360010560118-Understanding-Fiverr-s-freelancer-levels)
- **Level 1:** 5 completed orders, 3 unique clients, $400+ earnings, Success Score 5+, 80% response rate, 4.4+ rating. — [Fiverr: New pathways for success](https://www.fiverr.com/cp/freelancers-levels-ratings)
- **Level 2:** 20 orders, 10 unique clients, $2,000+ earnings, Success Score 7+, 90% response rate, 4.6+ rating. — [same](https://www.fiverr.com/cp/freelancers-levels-ratings)
- **Top Rated:** 40 orders, 20 unique clients, $10,000 earnings, Success Score 9+, 90% response rate, 4.7+ rating. It also needs a comprehensive manual review, and possibly skills tests in some subcategories. Reviewers assess professional skills, communication and service, professional presence and compliance. Rejected sellers get an email with the primary reason. — [Fiverr Help: Top Rated freelancers](https://help.fiverr.com/hc/en-us/articles/15140188560913-Top-Rated-freelancers)
- Promotion is automatic within 24 hours of qualifying. Sellers get a 30-day grace period to fix metrics before a level drop. — [Fiverr: New pathways for success](https://www.fiverr.com/cp/freelancers-levels-ratings)
- Success Score is private, on a 0–10 scale, and computed per gig from client satisfaction, communication, conflict-free orders, cancellations, delivery time and value. It is relative to sellers in a similar price range. (3rd-party) — [eduearnhub: Fiverr Success Score explained](https://eduearnhub.com/fiverr-success-score-explained/)
- Separate from levels: Fiverr Pro (vetted) gigs are reviewed by Fiverr's Pro team before they go live. — [Fiverr Help: Creating your Fiverr Pro Gig](https://help.fiverr.com/hc/en-us/articles/29454478348433-Creating-and-optimizing-your-Fiverr-Pro-Gig)
- Fiverr also has Agency accounts, which matters for Zoom eligibility (see Messaging). — [Fiverr Help: Video calls](https://help.fiverr.com/hc/en-us/articles/360011062838-Video-calls-Zoom-calls)

**Toptal (curated model, no open profiles)**
- More than 200,000 people apply each year and fewer than 3% are accepted. Screening assesses communication, personality, domain knowledge and professionalism. — [Toptal: Top 3% press](https://www.toptal.com/press-center/top-3-percent); [Toptal developers](https://www.toptal.com/developers)
- Screening stages (older source, about 4–5 years old): a language and personality interview, a skills review, live exercises, and a real-world test project of up to 3 weeks. — [Toptal: Inside the distributed screening process](https://www.toptal.com/insights/distributed-teams/toptal-distributed-podcast)

### Inferences
- A two-sided reputation system with a private composite score, public tiered badges, automatic promotion with a grace period, and manual review for the top tier is the industry-standard pattern. This makes Fiverr's 2023 system a clean, well-documented template to adapt.
- Fiverr's thresholds are tied to earnings in USD. For Tajikistan they would need re-scaling to local price levels (e.g. TJS-denominated thresholds).

### Gaps
- Exact Upwork JSS formula: Upwork publicly says only that it weighs long-term relationships, positive outcomes, private feedback and contracts with no activity. I could not fetch the JSS article in this session. Rising Talent criteria were not verified.
- Full Upwork profile field list (title, overview, portfolio, employment, education, certifications, languages, hourly rate, availability, video intro) and the profile-completeness meter were not verified with a primary source here (search returned no field-level article). From general product knowledge these fields all exist on Upwork, but treat that as unverified.
- Upwork Agency accounts and the client "payment verified" badge, plus client rating and total-spend display, were not verified with a primary source in this session.
- Freelancer.com "Preferred Freelancer Program" criteria were not found in search results.

## 2. Job posts (client side) & productized services

### Takeaway
Upwork's job-post flow is a short wizard (title, skills, scope, budget, description) with optional screening questions (up to 5), public or invite-only visibility, and an AI generator (Uma). Productized services such as Fiverr gigs, Upwork Project Catalog, PPH Hourlies/Offers and Contra services are a second, parallel buying path built on Basic, Standard and Premium packages.

### Cited Findings
- Upwork posting is a structured workflow: title, skills, scope, budget, description (about 10 minutes), started from Hire talent > Post a Job. — [Upwork: How to post a job 2026](https://www.upwork.com/resources/how-to-post-job-on-upwork); [Upwork Help: Post a job](https://support.upwork.com/hc/en-us/articles/20448713403667--Post-a-job)
- Experience level options are Entry-level, Intermediate and Expert. — [Upwork Help: How to post a job](https://support.upwork.com/hc/en-us/articles/211063408-How-to-post-a-job)
- Scope options: Small (short tasks), Medium (multi-month) and Large (ongoing or 1+ year), plus expected hours and duration. — [Upwork Help: Post a job](https://support.upwork.com/hc/en-us/articles/20448713403667--Post-a-job)
- Clients can add up to 5 screening questions (suggested or custom). The skills field allows up to 10 skills (per the Upwork blog). — [Upwork Help: Post a job](https://support.upwork.com/hc/en-us/articles/20448713403667--Post-a-job); [Upwork: How to post a job](https://www.upwork.com/resources/how-to-post-job-on-upwork)
- Visibility is either public or invite-only ("only freelancers you invite"). — [Upwork: How to post a job](https://www.upwork.com/resources/how-to-post-job-on-upwork)
- The AI Job Post Generator is powered by Uma: "describe your project in a sentence or two, and Uma will generate a draft". Manual posting is also possible. — [Upwork: How to post a job](https://www.upwork.com/resources/how-to-post-job-on-upwork)
- Fiverr Pro gigs are recommended to have 3 packages (Basic, Standard, Premium). — [Fiverr Help: Creating your Fiverr Pro Gig](https://help.fiverr.com/hc/en-us/articles/29454478348433-Creating-and-optimizing-your-Fiverr-Pro-Gig)
- Fiverr gig policy forbids putting an email, phone or third-party messaging handles in gigs for off-platform business. — [Fiverr Help: Gig policies](https://help.fiverr.com/hc/en-us/articles/360011421218-Gig-policies)
- Fiverr buyers can purchase extras and custom offers on orders. — [Fiverr Help: Paying for orders, extras, or custom offers](https://help.fiverr.com/hc/en-us/articles/37332672658193-Paying-for-orders-extras-or-custom-offers)
- PeoplePerHour "Hourlies" (fixed-price productized offers, reportedly renamed "Fixed Offers") start at about £10–£50 for small tasks. (3rd-party) — [Ardingate: PPH fees](https://ardingate.com/guides/compare/peopleperhour-vs-custom/)
- Freelancer.com paid job-post upgrades include Featured project ($9.99, one-time) and Sealed bids (similar fee). This is an old FAQ, about 7 years old. — [Freelancer.com FAQ](https://www.freelancer.com/faq/view.php)

### Inferences
- An MVP for Tajikistan likely needs both paths: (a) job post plus proposals (Upwork model) and (b) packaged services (Fiverr model). Packages with 3 tiers, extras, buyer requirements (questions shown at order start), FAQ and a gallery are the standard gig structure.
- Paid job-post upgrades (featured, urgent, sealed, private/NDA) are an early monetization lever (Freelancer.com model).

### Gaps
- Upwork Project Catalog mechanics (3 tiers, add-ons, fees) and Contra "services" structure were not verified with primary sources in this session.
- Exact Fiverr gig field limits (title length, number of gallery images or videos, max extras, FAQ count, requirement types) were not verified.
- Upwork job-post attachments size limit not verified.

## 3. Proposals, bidding & hiring flow

### Takeaway
Proposal volume is throttled with a paid credit: Upwork Connects cost $0.15 each, with a dynamic cost per job and a Boosted Proposals auction. Freelancer.com uses monthly bid limits by membership. These credits double as a revenue stream and an anti-spam mechanism.

### Cited Findings
- Connects cost $0.15 each and are sold in bundles (minimum 10) or a custom amount. — [Upwork: Is Upwork free](https://www.upwork.com/resources/is-upwork-free); [Upwork: Connects calculator](https://www.upwork.com/tools/connects-calculator)
- Connects per proposal are not fixed. They are "based on the project size, scope, market demand, and other factors". Third-party guides report about 4–16+ per proposal. — [Upwork: How to get more Connects](https://www.upwork.com/resources/how-to-get-more-connects); (3rd-party) [freelancercalculator](https://freelancercalculator.com/upwork-fees-2026/)
- **Boosted Proposals:** freelancers bid extra Connects. The highest bidders' proposals appear in the top 4 slots, labelled "Boosted". Clients pay nothing extra. Freelancers get 10 Connects back the first time they are charged for a boost. — [Upwork Help: What are Boosted Proposals](https://support.upwork.com/hc/en-us/articles/4406541109011-What-are-Boosted-Proposals-on-Upwork)
- Free monthly Connects: Basic plan 10 per month, Freelancer Plus 100 per month. — [Upwork: Is Upwork free](https://www.upwork.com/resources/is-upwork-free); [Upwork: Freelancer Plus guide](https://www.upwork.com/resources/freelancer-plus-guide)
- Older Upwork guides listed 60–70 Connects per month, a $10–$14.99 Plus plan and $1 per extra Connect. These are outdated (pre-2023). — [Upwork Freelancer Guide PDF (old)](https://content-static.upwork.com/blog/uploads/sites/3/2019/10/10113516/19-1010_r1_Update-FL-Guide-for-Connects-_Leyland_.pdf)
- Upwork also sells profile ads ("Promote your profile" / Availability badge ads) paid in Connects. — [Upwork: Promote your profile](https://www.upwork.com/work/ads); [Upwork: How to use Ads](https://www.upwork.com/resources/upwork-ads)
- Upwork's hire flow covers interviews and negotiation in Messages. Contact-info exchange is banned before a contract exists. — [Upwork Help: Interview and negotiate](https://support.upwork.com/hc/en-us/articles/17942933929747--Interview-and-negotiate)
- **Freelancer.com:** bidding is free, but each member has a monthly bid limit that depends on membership plan. — [Freelancer.com FAQ](https://www.freelancer.com/faq/view.php)
- Free members get about 6–8 bids per month and extra bids cost about $0.75 each. Membership tiers are reported as Intro $0.99, Basic $4.95, Plus $9.95, Professional $19.95 and Premier $59.95 per month (3rd-party, sources conflict). — [marketerhire](https://marketerhire.com/blog/freelancer-review); [aiproposer](https://aiproposer.com/learn/freelancer-fees)
- **Toptal** has no bidding. Matchers (domain experts, not recruiters) match clients with talent in under 24 hours on average. Clients get a trial of up to 2 weeks and are not billed if unsatisfied. They can trial up to 3 people per position. Toptal claims a 98% trial-to-hire rate (self-reported). — [Toptal FAQ](https://www.toptal.com/faq); [Toptal developers](https://www.toptal.com/developers)

### Inferences
- A "proposal credits" system (free monthly allowance plus paid top-ups plus an optional boost auction) is a proven model for both anti-spam and revenue. For a low-income market, a generous free allowance with cheap top-ups is advisable.
- Screening questions, client-side shortlisting, an interview chat and offer → accept contract are the canonical funnel steps.

### Gaps
- Upwork "shortlist/archive/hide proposals" and offer-expiry timelines were not verified in this session.
- Freelancer.com official current membership prices and bid counts could not be fetched (freelancer.com blocked). Third-party figures conflict.

## 4. Contracts, escrow, milestones, hourly, delivery & cancellation

### Takeaway
All open marketplaces use escrow: the client funds before work starts and money is released on approval or automatically after a timeout. Key timeouts are Upwork fixed-price 14-day auto-approval plus a 5-day security hold, Fiverr 3-day auto-complete, and PPH Hourlies 7-day auto-release. Hourly protection relies on time-tracker evidence (screenshots and activity) and has caps.

### Cited Findings
**Upwork fixed-price**
- The client funds the milestone into escrow, the freelancer submits work through Upwork, and the client has 14 days to approve or request changes. After that the funds are auto-released and then pass through a 5-day security hold before they can be withdrawn. — [Upwork Help: How payments for milestones and fixed-price contracts work](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work); [How Upwork protects your payments](https://support.upwork.com/hc/en-us/articles/211062568-How-Upwork-protects-your-payments)
- If the client requests a refund, the freelancer has 7 days to respond or dispute. — [same](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work)
- Work is protected only if the milestone was funded before work started and the submission went through Upwork. Payments above the deposited amount and clients with unverified billing are excluded. — [Upwork Help: How Upwork protects your payments](https://support.upwork.com/hc/en-us/articles/211062568-How-Upwork-protects-your-payments)
- Work submitted with "Submit work & request payment" is limited to 25 MB per file. Larger files go via Messages (up to 1 GB) or a link. — [Upwork Community (staff answer)](https://community.upwork.com/t5/New-to-Upwork/Submit-Proposal-File-Size/td-p/1278633)

**Upwork hourly**
- Hours tracked in the desktop app (Work Diary: screenshots, activity levels, memos) are invoiced weekly. — [Upwork Help: manage your work diary](https://support.upwork.com/hc/en-us/articles/211068518-How-to-manage-your-work-diary-on-Upwork); [Hourly Payment Protection](https://support.upwork.com/hc/en-us/articles/211068288-How-Hourly-Payment-Protection-works-for-freelancers)
- Hourly Protection conditions: screenshots must be contract-related, memos must describe the work, activity levels must be adequate, and hours must stay within the weekly limit. Excluded: manual time, idle or empty segments, time over the limit, non-work activity, and missing memos. — [Upwork Help: Hourly Payment Protection](https://support.upwork.com/hc/en-us/articles/211068288-How-Hourly-Payment-Protection-works-for-freelancers)
- Clients can dispute hours within 5 days after the billing period ends. — [Upwork Help: client disputes hours](https://support.upwork.com/hc/en-us/articles/211068588-What-to-do-if-a-client-disputes-your-hours-on-Upwork); [Dispute an agency or freelancer's hours](https://support.upwork.com/hc/en-us/articles/17976540792467--Dispute-an-agency-or-freelancer-s-hours)
- Hourly protection has a lifetime cap of $2,500 per client or 50 hours at the average rate, whichever is lower (reported in help content; the cap figure was in search output and is worth re-checking). — [Upwork Help: Hourly Payment Protection](https://support.upwork.com/hc/en-us/articles/211068288-How-Hourly-Payment-Protection-works-for-freelancers)

**Fiverr orders**
- Order statuses run from requirements to active, delivered, revision (if requested) and completed. If the buyer takes no action within 3 days of delivery, the order auto-completes. Shipping gigs auto-complete after 14 days. — [Fiverr Help: Complete guide to your order](https://help.fiverr.com/hc/en-us/articles/37332473202065-The-complete-guide-to-your-Fiverr-order-Statuses-and-process)
- The buyer can extend the review period by up to 5 additional days. — [Fiverr Terms of Service](https://www.fiverr.com/legal-portal/legal-terms/terms-of-service)
- Cancellation of an active order is requested through the Resolution Center at any time. The freelancer has 48 hours to accept or decline. Completed orders cannot be cancelled via the Resolution Center and need Customer Support instead. — [Fiverr Help: How cancellations work for clients](https://help.fiverr.com/hc/en-us/articles/12864193979793-How-cancellations-work-for-clients); [for freelancers](https://help.fiverr.com/hc/en-us/articles/47789995041297-How-cancellations-work-for-freelancers)
- Support may review cancellation of completed orders up to 14 days after completion, only for misconduct or ToS violations. — [Fiverr Payment Terms](https://www.fiverr.com/legal-portal/legal-terms/payment-terms-of-service)

**PeoplePerHour**
- Escrow holds the buyer's payment. If an invoice is unpaid and not rejected, escrowed money is auto-released to the freelancer. For Hourlies this happens 7 days after the invoice is raised. — [PPH Help: What is Escrow](https://support.peopleperhour.com/hc/en-us/articles/17826151118097-What-is-Escrow-and-how-is-it-used); [Funds have left Escrow](https://support.peopleperhour.com/hc/en-us/articles/205217467-Funds-have-left-Escrow)

**Freelancer.com**
- Uses Milestone Payments (escrowed by the employer, released on approval). — [Freelancer.com: Milestone Payments](https://www.freelancer.com/support/Payments/milestone-payment-for-employers-2228); [Milestone FAQ](https://www.freelancer.com/faq/topic.php?id=12)

### Inferences
- Minimum viable contract engine: offer → accept → fund milestone (escrow) → submit delivery (files and message) → approve, request revision or dispute, with auto-approve after N days → security hold → withdrawable balance. Hourly contracts with a time tracker are complex, and a mobile-first MVP could defer them.
- Recommended configurable timers for the admin panel: auto-approve (3 days on Fiverr, 14 days on Upwork), dispute windows (5–7 days), and clearance (7–14 days).

### Gaps
- Upwork bonus payments, contract-end flow, Fiverr deadline-extension mechanics and revision counts per package were not verified in this session.
- Upwork weekly billing schedule details (Monday cutoff, review by Friday) were not re-verified here.

## 5. Fees, payouts & clearance

### Takeaway
Freelancer-side commission ranges from 0% (Contra, Malt freelancers in some markets) to 20% (Fiverr, PPH first tier). Upwork has moved to a dynamic 0–15% per-contract fee (2025). Client-side fees are typically 3–10% plus small-order or initiation fees. Payout holds are 5–14 days.

### Cited Findings
**Upwork**
- Since about May 2025, the freelancer fee has been variable at 0–15% per contract. It replaced the 2023–2025 flat 10% (and before that a 20/10/5% tier model). It is fixed when the proposal or contract starts and depends on demand, supply, category and membership plan. A typical rate is about 10%. (3rd-party; the official fee article could not be fetched) — [monitask](https://www.monitask.com/blog/upwork-fees/); [freelancercalculator](https://freelancercalculator.com/upwork-fees-2026/)
- Client fees per Upwork's 2026 pricing comparison: service fee 3%–5% on Basic and 8%–10% on Business Plus (no subscription fee). Contract initiation fees apply to every contract on Basic, and on Business Plus only to fixed-price contracts under $100. — [Upwork: Is Upwork free (2026)](https://www.upwork.com/resources/is-upwork-free)
- Freelancer Plus costs $19.99 per month and includes 100 Connects, full Uma access and 0% fee on direct contracts (vs 5% on Basic). Free users get about 10 Uma messages per week. — [Upwork: Is Upwork free](https://www.upwork.com/resources/is-upwork-free); [Freelancer Plus guide](https://www.upwork.com/resources/freelancer-plus-guide)
- Withdrawal fees: Direct to Local Bank $0.99 per withdrawal (receiving bank may add fees), USD wire $50, Instant Pay (US) $2. Direct to US Bank is free for US tax addresses. From 1 Sep 2026, a $2.99 fee applies per Direct to US Bank withdrawal for non-US tax addresses. Payoneer, PayPal and mobile wallet (Direct to Wallet) are also supported. — [Upwork Help: Local Bank fees](https://support.upwork.com/hc/en-us/articles/211060578-What-are-the-fees-limits-and-timing-of-Direct-to-Local-Bank-payments); [Wire transfers](https://support.upwork.com/hc/en-us/articles/211063898); [Direct to U.S. Bank](https://support.upwork.com/hc/en-us/articles/227022468-Direct-to-U-S-Bank-timing-and-fees-explained); [Payoneer](https://support.upwork.com/hc/en-us/articles/211064008-How-quickly-Payoneer-pays-and-what-fees-apply); [Direct to Wallet](https://support.upwork.com/hc/en-us/articles/115001615787-What-are-the-mobile-wallet-fees-and-timing-for-withdrawals)
- 5-day security hold on released fixed-price funds (see section 4). — [Upwork Help: milestone payments](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work)

**Fiverr**
- Buyer service fee is 5.5% of the purchase amount, plus a $3.50 small-order fee for purchases under $200 (Payment Terms, as of about Sep 2025). — [Fiverr Payment Terms](https://www.fiverr.com/legal-portal/legal-terms/payment-terms-of-service)
- Clearance: earnings become available 14 days after order completion, or 7 days for Seller Plus, Top Rated and Pro sellers. — [Fiverr Help: order guide](https://help.fiverr.com/hc/en-us/articles/37332473202065-The-complete-guide-to-your-Fiverr-order-Statuses-and-process); [Fiverr Payment Terms](https://www.fiverr.com/legal-portal/legal-terms/payment-terms-of-service)

**Freelancer.com** (3rd-party, official page blocked)
- Freelancer fee is 10% or $5 (whichever is greater) on fixed-price work, and 10% on hourly. Client fee is 3% or $3 minimum. Paid memberships reduce fees. Reported withdrawal fee is about $3 for bank or PayPal. — [feebite](https://feebite.com/platforms/freelancer-com); [aiproposer](https://aiproposer.com/learn/freelancer-fees); official page (not fetched): [freelancer.com/feesandcharges](https://www.freelancer.com/feesandcharges)

**Malt**
- Clients pay a service fee on top of the freelancer rate: Starter 10%, Advanced 15%, Enterprise custom (on the pre-tax amount). Middle East rates are higher (15% and 20%). Malt invoices its fee to the client separately. The official article says freelancers do not pay fees directly. — [Malt Help: Malt service offers and fees](https://help.malt.com/hc/en-150/articles/29567589850002-What-are-Malt-service-fees-and-offers)
- Conflict: third-party sources still cite a freelancer commission of 10% (first project) or 7% (repeat), 5% after 6 months with the same client, and 2% for clients the freelancer brings. These likely reflect the pre-2024/25 model. — [take-me.fr comparison (Oct 2026)](https://take-me.fr/en/guides/commissions-plateformes-freelance); [homebusinesswatch](https://www.homebusinesswatch.com/companies/malt-freelance)

**PeoplePerHour**
- Freelancer commission is tiered on lifetime billing per buyer: 20% below £250, 7.5% from £250 to £5,000, and 3.5% above £5,000 (excluding VAT). An older PPH page shows £500 thresholds, so the change date is unknown. — [PPH Help: Freelancer commission fees](https://support.peopleperhour.com/hc/en-us/articles/205218337-Freelancer-commission-fees); [PPH Fees (older)](https://support.peopleperhour.com/hc/en-us/articles/205217197-PPH-Fees); [PPH blog: service fees announcement](https://www.peopleperhour.com/blog/product-platform/important-announcement-regarding-service-fees/)
- Buyer fee is about 10% at checkout (3rd-party, not confirmed). — [Ardingate](https://ardingate.com/guides/compare/peopleperhour-vs-custom/)

**Contra**
- Freelancers pay 0% commission. Contra Pro costs $29 per month or $199 per year. — [Contra Pro](https://contra.com/pro)
- Clients reportedly pay a tiered platform fee ($2–$29 by project size) plus Stripe processing of about 2.9% + $0.30. Sources conflict on who bears processing. (3rd-party) — [remogrid](https://www.remogrid.com/blog/freelancing/contra-commission-fees-and-pricing-guide-2026); [freelancecalc](https://freelancecalc.co/contra-fee-calculator/)

**Toptal**
- Billing is on the client's hourly or engagement rate after the trial; Toptal's markup is not publicly disclosed. No-risk trial of up to 2 weeks. — [Toptal FAQ](https://www.toptal.com/faq)

### Inferences
- Market convergence: about 10% freelancer fee and 3–5.5% client fee, plus a small fixed fee on small orders. Platforms keep moving toward dynamic or tiered pricing (Upwork variable, PPH lifetime-per-client tiers) that rewards long-term relationships. A Tajik platform could start with a simple flat fee and reduced fees for repeat clients.
- The clearance or security hold (5–14 days) is a fraud and chargeback buffer. With local payment rails (cards like Korti Milli, e-wallets), the hold could be tuned accordingly.

### Gaps
- Official Upwork variable fee article (support.upwork.com 211062538) could not be fetched. The 0–15% figure and the May 2025 date come from third-party sources only.
- Fiverr seller commission (widely known as 20% of order value) was not re-verified from a primary page in this session.
- Upwork PayPal and Payoneer withdrawal fee amounts were not returned by search.

## 6. Messaging & communication

### Takeaway
In-app chat with file sharing up to 1 GB (Upwork, Fiverr), built-in video calls via Zoom, and a strict ban on sharing contact info or taking work off-platform before a contract, with automated detection and account suspension.

### Cited Findings
- Upwork Messages: attachments up to 1 GB (older blog said 10 attachments and 95 MB total). Built-in video and voice calls via Zoom or Upwork video meetings, with screen sharing. — [Upwork Help: Use messages](https://support.upwork.com/hc/en-us/articles/17943213453715--Use-messages); [How to use Upwork Messages](https://support.upwork.com/hc/en-us/articles/211067768-How-to-use-Upwork-Messages); [Upwork blog (old)](https://www.upwork.com/blog/upwork-messages-your-one-stop-collaboration-tool)
- Upwork prohibits sharing contact info before a contract; violations can mean permanent suspension. After a contract is active, contact info may be exchanged in the contract workroom for business purposes. Enterprise clients have more leeway, but conversations must start in Upwork Messages. — [Upwork Help: How to share documents/files](https://support.upwork.com/hc/en-us/articles/360049608113-How-to-share-documents-files-and-more-on-Upwork); [Interview and negotiate](https://support.upwork.com/hc/en-us/articles/17942933929747--Interview-and-negotiate)
- Fiverr inbox: files up to 1 GB, with larger files shared via cloud links. — [Fiverr Help: Using your inbox effectively](https://help.fiverr.com/hc/en-us/articles/37552118241809-Using-your-inbox-effectively)
- Fiverr prohibits directing users off-platform, alternative payments, external contracts, or sharing personal contact details for off-platform business. — [Fiverr Help: Policy violations explained](https://help.fiverr.com/hc/en-us/articles/48022851354385-Policy-Violations-Explained)
- Fiverr Zoom calls are hosted by Fiverr at no cost. Calls can start from the order page. Starting from the inbox requires at least 1 order in the last 60 days, plus being an Agency or talking to a Fiverr Pro customer. Users must not share passwords, card data or ID numbers on calls. — [Fiverr Help: Video calls (Zoom)](https://help.fiverr.com/hc/en-us/articles/360011062838-Video-calls-Zoom-calls)

### Inferences
- Product requirements: chat with attachments, a pre-contract mode with contact-info masking or detection (phone or Telegram handles, which matter a lot in Tajikistan where Telegram is dominant), and an in-contract workroom. Video calls can come via a third-party SDK.

### Gaps
- Read receipts, message search and Fiverr's automated contact-info filter mechanics were not verified in this session.

## 7. Reviews & disputes / mediation

### Takeaway
Disputes go through structured escalation: mutual negotiation, then platform mediation, then paid binding arbitration. Freelancer.com charges each party $5 or 5% (refunded to the winner); PPH charges the disputing freelancer 10% (minimum £5). Fiverr routes everything through the Resolution Center.

### Cited Findings
- **Freelancer.com:** milestone dispute starts with negotiation, then either party can escalate to arbitration by paying a fee of the greater of $5 or 5%. The other party typically has 4 days to pay or loses by default. The fee is refunded to the winner. Verdicts are "final, binding, and irreversible". Response-window pages conflict (4 days vs 14 days depending on who filed). — [Freelancer.com: Milestone Dispute Resolution Policy](https://www.freelancer.com/page.php?p=info%2Fdispute_policy); [Dispute Resolution FAQ](https://www.freelancer.com/faq/topic.php?code=disputes); [Dispute Resolution Service](https://www.freelancer.com/support/employer/payments/dispute-resolution-service-32237)
- **PeoplePerHour:** parties are encouraged to resolve between themselves, then PPH Customer Services resolves the dispute. Only qualified "trusted" freelancers can dispute a rejected Hourlie invoice. The disputing freelancer pays a non-refundable 10% of the invoice or refund amount (minimum £5, €7 or $8). — [PPH Terms](https://www.peopleperhour.com/static/terms); [PPH Help: refunds](https://support.peopleperhour.com/hc/en-us/articles/205217407-Am-I-entitled-to-a-refund)
- **Upwork:** fixed-price refund request gives a 7-day window to respond or dispute. Hourly disputes are raised within 5 days after the billing week. Upwork offers dispute assistance or mediation; arbitration is described in its legal terms. — [Upwork Help: milestones](https://support.upwork.com/hc/en-us/articles/211063718-How-payments-for-milestones-and-fixed-price-contracts-work); [Upwork: Dispute process demystified](https://www.upwork.com/resources/upwork-dispute-process); [Upwork Legal](https://www.upwork.com/legal)
- **Fiverr:** cancellations go through the Resolution Center (48h for the freelancer to respond). Support handles post-completion cases within 14 days. — [Fiverr Help: cancellations](https://help.fiverr.com/hc/en-us/articles/12864193979793-How-cancellations-work-for-clients); [Fiverr Payment Terms](https://www.fiverr.com/legal-portal/legal-terms/payment-terms-of-service)

### Inferences
- The admin panel needs a dispute queue with case timeline, evidence (chat, files, deliveries), split-refund decisions, and fee handling. Timers and fees should be configurable.

### Gaps
- Two-way, double-blind review mechanics (Upwork's 14-day feedback window, private feedback) and Fiverr's buyer-rates-seller-then-seller-rates-buyer flow were not verified with primary sources in this session.
- Upwork arbitration fees and the third-party arbitrator were not verified.

## 8. Discovery, notifications & recommendations

### Takeaway
AI matching and agentic recruiting (Upwork Uma Recruiter) are replacing manual search for clients. Freelancers get feeds of recommended jobs. Paid visibility (ads, boosts) is layered on top.

### Cited Findings
- Uma Recruiter is an agentic system with an "Agentic Brain" powered by LLMs. It sources candidates, evaluates them on factors including JSS, and returns curated shortlists "in hours" for Business Plus clients. — [Upwork blog: Uma Recruiter](https://www.upwork.com/blog/uma-recruiter-how-we-built-an-agentic-solution-to-talent-matching-and-hiring); [Upwork: Business Plus](https://www.upwork.com/resources/business-plus)
- Toptal uses human matchers (domain experts), with an average time to match under 24 hours. — [Toptal FAQ](https://www.toptal.com/faq)

### Inferences
- MVP-relevant: saved searches, job alerts (push), a "recommended for you" feed, and talent filters (category, skills, rate, level or badge, language, location, rating, availability).

### Gaps
- Specific filter lists, saved-search and job-alert features, and push-notification categories were not verified from primary sources in this session (search budget exhausted).

## 9. Monetization beyond commission & AI features (2024–2026)

### Takeaway
Every platform now combines commission with subscriptions (Upwork Freelancer Plus $19.99, Fiverr Seller Plus $25/$49, Contra Pro $29, Freelancer.com memberships), pay-per-visibility (Connects, Boosted Proposals, Fiverr Ads, profile ads, featured projects) and enterprise tiers. AI is shipped as job-post generation, proposal assistance, agentic recruiting (Uma) and creator-owned AI models (Fiverr Go).

### Cited Findings
- **Upwork:** Freelancer Plus is $19.99/month (100 Connects, full Uma, 0% fee on direct contracts). Business Plus (client) has no subscription fee, 8–10% service fee, Expert-Vetted access and Uma Recruiter. Profile ads are paid in Connects. — [Upwork: Is Upwork free](https://www.upwork.com/resources/is-upwork-free); [Business Plus](https://www.upwork.com/resources/business-plus); [Promote profile](https://www.upwork.com/work/ads)
- **Upwork AI:** Uma powers the Job Post Generator, freelancer-side Uma assistance (about 10 messages per week on free tier, full on Plus), and Uma Recruiter. — [Upwork: How to post a job](https://www.upwork.com/resources/how-to-post-job-on-upwork); [Uma Recruiter blog](https://www.upwork.com/blog/uma-recruiter-how-we-built-an-agentic-solution-to-talent-matching-and-hiring)
- **Fiverr Seller Plus:** Standard $25/month and Premium $49/month, with annual and semi-annual discounts. Tiers are Kickstart, Standard and Premium, and the program is invite-only per the Seller Programs terms. Includes a $5 monthly Fiverr Ads credit (no rollover) and first-time-client promotions (up to 10 per month on Standard, 20 on Premium). Also gives 7-day clearance. — [Fiverr Help: Seller Plus Standard & Premium](https://help.fiverr.com/hc/en-us/articles/360017140717-Seller-Plus-Standard-and-Premium-Advanced-tools-for-business-growth); [Fiverr Seller Programs terms](https://www.fiverr.com/legal-portal/legal-terms/seller-programs-terms); [Growth Tools](https://help.fiverr.com/hc/en-us/articles/5244747923985-Growth-Tools-for-Seller-Plus); [Fiverr Ads](https://help.fiverr.com/hc/en-us/articles/360017729338-Promoting-your-Gigs-with-Fiverr-Ads)
- **Fiverr Ads** (formerly Promoted Gigs): pay-for-visibility promotion of gigs. — [Fiverr Help: Promoting your Gigs with Fiverr Ads](https://help.fiverr.com/hc/en-us/articles/360017729338-Promoting-your-Gigs-with-Fiverr-Ads)
- **Fiverr Go** (announced 2025) has two parts: a Personal AI Creation Model (creators train AI on their own work, and buyers generate in their style) and a Personal AI Assistant that answers clients on the freelancer's behalf. Freelancers control their models, prices and rights. — [Fiverr news: Fiverr Go](https://www.fiverr.com/news/fiverr-go)
- **Contra Pro:** $29/month or $199/year. Freelancers can bring their own clients and pay $0 in fees. — [Contra Pro](https://contra.com/pro)
- **Freelancer.com:** paid memberships with bid limits and lower fees, plus project upgrades (Featured $9.99, Sealed, etc., older data). — [Freelancer.com FAQ](https://www.freelancer.com/faq/view.php)

### Inferences
- Monetization candidates for a Tajik platform, in order of implementation ease: (1) commission split client/freelancer, (2) proposal credits with paid top-ups, (3) a "Pro" subscription (more credits, lower fee, faster payout), (4) paid boosts or featured listings for gigs and jobs, (5) an AI job-post writer and proposal helper (LLM-based, in Tajik, Russian and English).
- Faster payout (7-day vs 14-day clearance) is a valued subscription perk at zero marginal cost.

### Gaps
- Fiverr Go pricing and availability, Fiverr "Neo"/AI brief features, Upwork Uma proposal-writing specifics, and Freelancer.com AI features were not verified.
- Fiverr seller-side 20% fee and Fiverr Pro pricing were not re-verified from a primary source.
