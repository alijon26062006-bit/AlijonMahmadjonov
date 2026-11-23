# App Store and Google Play requirements for a two-sided freelance/services marketplace app (Expo/React Native), current as of Nov 2026

Research date: 2026-11-23. Apple quotes come straight from the live App Review Guidelines page (developer.apple.com/app-store/review/guidelines, fetched 2026-11-23; the page shows no "last updated" date). **Caveat on Google:** support.google.com could not be fetched from this research environment (DNS blocked). Every Google Play policy point below comes from search-engine extracts of the official Play Console Help pages, plus secondary sources. The wording is close to the official text but may not be exact. Re-check against the live Policy Center before relying on it.

## 1. Payments: is IAP / Google Play Billing required for client-to-freelancer payments (escrow)?

### Takeaway
No for the core job payments. On Apple, physical or real-world services (repair, delivery) fall squarely under 3.1.3(e), where you **must not** use IAP. Remote 1:1 services between two people can rely on 3.1.3(d) "Person-to-Person Services". On Google Play, physical services and peer-to-peer payments are exempt from Play Billing, and P2P payments **must not** go through it. The grey zone is digital deliverables (logo files, code, translations) delivered *inside* the app. The established marketplaces (e.g., Upwork) process job payments outside IAP, but no Apple text names "freelance marketplace" explicitly.

### Cited Findings
- **Apple 3.1.3(e) Goods and Services Outside of the App:** "If your app enables people to purchase physical goods or services that will be consumed outside of the app, you **must** use purchase methods other than in-app purchase to collect those payments, such as Apple Pay or traditional credit card entry." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.1.3(d) Person-to-Person Services:** "If your app enables the purchase of real-time person-to-person services between two individuals (for example tutoring students, medical consultations, real estate tours, or fitness training), you may use purchase methods other than in-app purchase to collect those payments. One-to-few and one-to-many real-time services must use in-app purchase." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.1.3 intro (anti-steering, with a US exception):** "The following apps may use purchase methods other than in-app purchase. Apps in this section cannot, within the app, encourage users to use a purchasing method other than in-app purchase, except for apps on the United States storefront and as set forth in 3.1.1(a) and 3.1.3(a)." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.1.1 (digital unlocks need IAP):** "If you want to unlock features or functionality within your app, (by way of example: subscriptions, in-game currencies, game levels, access to premium content, or unlocking a full version), you must use in-app purchase." Also: "Apps may use in-app purchase currencies to enable customers to 'tip' the developer or digital content providers in the app." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.1.1 (digital gift cards):** "Digital gift cards, certificates, vouchers, and coupons which can be redeemed for digital goods or services can only be sold in your app using in-app purchase." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.1.1(a), US storefront:** "These entitlements are not required for developers to include buttons, external links, or other calls to action in their United States storefront apps." In all other storefronts, "except for the United States storefront, where this prohibition does not apply, apps and their metadata may not include buttons, external links, or other calls to action that direct customers to purchasing mechanisms other than in-app purchase." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **US court context:** On Dec 11, 2025 the Ninth Circuit (No. 25-2935) largely upheld the Epic v. Apple anti-steering injunction. It held that Apple may charge a commission on linked-out purchases, limited to costs "genuinely and reasonably necessary" to coordinate the external hand-off, and that the injunction bars only "prohibitive" commissions. Apple may also require IAP prompts to be as prominent as link-out prompts. — [Fenwick](https://www.fenwick.com/insights/publications/ninth-circuit-largely-upholds-ruling-in-epic-v-apple); [Opinion PDF (Justia)](https://cases.justia.com/federal/appellate-courts/ca9/25-2935/25-2935-2025-12-11.pdf). In April 2026 the Ninth Circuit reversed a stay that had let Apple keep its commission structure during a Supreme Court appeal (not verified in detail). — [MacRumors, 2026-04-29](https://www.macrumors.com/2026/04/29/epic-games-wins-reversal-app-store-fee-battle/)
- **EU (DMA):** Apple announced that from Oct 1, 2026 the Core Technology Fee is replaced by a "Core Technology Commission, a simple 5% commission on digital transactions in apps distributed outside the App Store," with new DPLA Attachment 14 for EU terms. — [Apple Developer News, 2026-08-18](https://developer.apple.com/news/?id=gmws0jgp)
- **Google Play Payments policy (from search extracts of the official page):** Play Billing is required for digital goods and services, but **not** for physical goods, physical services or peer-to-peer payments. "Google Play's billing system must not be used for peer-to-peer payments, content that facilitates online gambling, or any product category deemed unacceptable under Google's Payments Center Content Policies." The same page says Play Billing must be used for "the SKUs in your app that include more digital goods or services than physical goods or services, and for the SKUs in your app that are marketed to users as digital goods or services." — [Understanding Google Play's Payments policy](https://support.google.com/googleplay/android-developer/answer/10281818?hl=en); main policy page [answer/9858738](https://support.google.com/googleplay/android-developer/answer/9858738)
- **Google US programs:** Google's help page says "Developers may continue to link users to external content or to offer alternative billing systems by complying with the following policies and programs (as launched on December 9, 2025)". A July 22, 2026 notice says US-enrolled developers will need to report transactions and pay service fees; the start date could not be confirmed. — [Play Console Help 15582165](https://support.google.com/googleplay/android-developer/answer/15582165?hl=en)
- **Google–Epic settlement (2026):** reported cut of the Play fee to 20%, with expanded billing choice worldwide by Sep 30, 2027. Reported fee figures conflict (10%/20% vs a 5% figure) and the settlement needed court approval. — [TechCrunch 2026-03-04](https://techcrunch.com/2026/03/04/google-settles-with-epic-games-drops-its-play-store-commissions-to-20); [MacRumors 2026-06-24](https://macrumors.com/2026/06/24/google-play-store-fee-change/); [Notebookcheck](https://www.notebookcheck.net/Google-cuts-Play-Store-fees-as-Epic-settlement-reshapes-Android-app-payments.1243278.0.html)

### Inferences
- **Physical or local jobs (repair, delivery, on-site work):** 3.1.3(e) applies. Use Stripe, a local PSP or Apple Pay, never IAP. On Google these are "physical services", so Play Billing is not used.
- **Remote 1:1 jobs (design, programming, translation) paid from client to freelancer through escrow:** Apple's closest text is 3.1.3(d). Its examples are *real-time* services ("tutoring", "consultations"), while freelance deliverables are usually asynchronous. A conservative reading is that this is a gap in the text. In practice, App Review has long accepted non-IAP payment for services that a specific human performs for a specific client (Upwork's job payments run outside IAP; see §2). On Google, client→freelancer escrow payments fit "peer-to-peer payments" or services. Mitigations:
  - frame the payment as payment for a human service contract, not as "buying digital content in the app";
  - do not sell any templates, stock assets or pre-made digital items. Pre-made digital goods would clearly need IAP / Play Billing under 3.1.1 and the Google SKU rule above.
- **Tips:** "tips" to freelancers inside the app could be read as "tipping digital content providers" under 3.1.1. Safer to make a tip part of the service payment (an order add-on) and not a standalone digital tip.
- **Outside the US storefront:** do not show "pay cheaper on our website" calls to action for digital items (anti-steering in 3.1.3 / 3.1.1(a)). Inside the US storefront, link-outs are allowed.

### Gaps
- There is no official Apple statement that names freelance marketplaces with asynchronous digital deliverables. The classification above is inference, so expect possible reviewer questions and prepare Review Notes explaining the payment flow.
- The exact current Google Payments policy text could not be fetched directly (support.google.com blocked). The final US / worldwide Google fee terms after the 2026 settlement are unconfirmed.
- Whether Apple has formally rewritten guidelines after the 2025–2026 court rulings, beyond the US-storefront carve-outs quoted above, was not checked line by line.

## 2. Platform fees: "Pro" subscriptions, paid boosts or "Connects" sold to freelancers

### Takeaway
Yes, these need IAP / Google Play Billing. They are digital features used inside the app. Apple 3.1.3(g) explicitly says that selling "boosts" in an app requires IAP, and Upwork sells Connects and Freelancer Plus through Apple IAP.

### Cited Findings
- **Apple 3.1.3(g):** "Digital purchases for content that is experienced or consumed in an app, including buying advertisements to display in the same app (such as sales of 'boosts' for posts in a social media app) must use in-app purchase." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.1.1:** subscriptions and in-app currencies that unlock features must use IAP. "Any credits or in-game currencies purchased via in-app purchase may not expire, and you should make sure you have a restore mechanism for any restorable in-app purchases." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 2.1(b):** "If you offer in-app purchases in your app, make sure they are complete, up-to-date, visible to the reviewer and functional." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Upwork precedent:** the Upwork iOS App Store listing shows Connects as in-app purchases — [App Store: Upwork](https://apps.apple.com/us/app/-/id1446736499). Upwork's help center describes buying Freelancer Plus / Agency Plus through Apple IAP and notes that in-app prices "may cost slightly more than subscriptions purchased on Upwork.com, due to Apple's processing fees." — [Upwork Support](https://support.upwork.com/hc/en-us/articles/360041683353-Upwork-subscription-via-Apple-in-app-purchase)
- **Google:** Play Billing is required for SKUs "marketed to users as digital goods or services" — [Play Console Help 10281818](https://support.google.com/googleplay/android-developer/answer/10281818?hl=en)

### Inferences
- The platform commission taken from the escrowed job payment is not a separate digital purchase, so it can stay in your own payment processor.
- Pro plans, boosts, featured placement, bid credits and "Connects" all need IAP / Play Billing, except where US link-out or alternative-billing rules apply.
- Credits bought by IAP must not expire.
- Mixing escrow balance and IAP credits in one wallet is risky. Keep them as separate ledgers.

### Gaps
- No public Fiverr or Kwork precedent for their iOS billing structure was verified.

## 3. Account deletion

### Takeaway
Both stores require account deletion that the user can start from inside the app. Google also requires a web link that works without the app, declared in the Data safety form.

### Cited Findings
- **Apple 5.1.1(v):** "If your app supports account creation, you must also offer account deletion within the app." Also: "If your app doesn't include significant account-based features, let people use it without a login." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 5.1.1(i):** the privacy policy must "Explain its data retention/deletion policies and describe how a user can revoke consent and/or request deletion of the user's data." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Google:** apps that allow account creation must give users a way to request deletion both in the app and via a **web link resource**. The web page must let users request deletion without reinstalling the app, must load without error, and must reference the app or developer name. The link and the deletion disclosure go in the **Data safety form** in Play Console. Deleting an account must also delete the associated user data, and any data retained for security, fraud prevention or regulatory reasons must be clearly disclosed. Apps in regulated industries may add extra steps to complete a deletion. — [Play Console Help 13327111](https://support.google.com/googleplay/android-developer/answer/13327111); [Android Developers Blog, Apr 2023](https://android-developers.googleblog.com/2023/04/giving-people-more-control-over-their-data.html)

### Inferences
- For an escrow marketplace, deletion should be allowed even with open orders. You can say that transaction or financial records are kept for the legally required period (AML / tax). Disclose this in the privacy policy and in the Data safety "data retained" answer.
- Blocking deletion entirely while an order is in progress is a likely rejection risk. Prefer "request accepted; completes after open orders are closed or refunded". This is inference.
- Users who signed in with Apple: revoke the Sign in with Apple token on deletion. This is Apple's documented practice, not verified in this session.

### Gaps
- Apple's separate "Offering account deletion in your app" support page (token revocation details) was not fetched.

## 4. Sign in with Apple / Login services (Apple 4.8)

### Takeaway
Offering Google Sign-In triggers 4.8. You must also offer an equivalent privacy-preserving login, which in practice means Sign in with Apple. Phone/SMS OTP is your own account system and does not by itself trigger 4.8.

### Cited Findings
- **Apple 4.8:** "Apps that use a third-party or social login service (such as Facebook Login, Google Sign-In, Log in with X, Sign In with LinkedIn, Login with Amazon, or WeChat Login) to set up or authenticate the user's primary account with the app must also offer as an equivalent option another login service with the following features:
  - the login service limits data collection to the user's name and email address;
  - the login service allows users to keep their email address private as part of setting up their account; and
  - the login service does not collect interactions with your app for advertising purposes without consent."

  — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **4.8 exceptions** (another login is not required if):
  - "Your app exclusively uses your company's own account setup and sign-in systems."
  - Education / enterprise apps that sign in with an existing education or enterprise account.
  - "Your app uses a government or industry-backed citizen identification system or electronic ID to authenticate users."
  - Clients for a specific third-party service.
  - Alternative app marketplaces.

  — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Sign in with Apple relay domain:** Apple announced a new relay-email domain. Developers "should ensure that their account systems, email validation logic, and allowlists accept addresses on the new `private.icloud.com` domain." — [Apple Developer News, 2026-08-24](https://developer.apple.com/news/?id=1ptvdtcm)
- **5.1.1(v):** "Apps may not require users to enter personal information to function, except when directly relevant to the core functionality of the app or required by law." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### Inferences
- The app needs phone OTP + Google + Sign in with Apple, with Apple shown as an equal option (same prominence).
- Do not force users who signed in with Apple and hid their email to then enter a real email, unless it is needed for the service. Collecting a phone number for payments or KYC is defensible as "required by law / core functionality".
- Allow browsing listings without login, since 5.1.1(v) says let people use the app without a login where features are not account-based. Strongly recommended for a marketplace.

### Gaps
- None material.

## 5. User-generated content (profiles, portfolios, reviews, chat)

### Takeaway
Both stores require four things:
- content filtering or moderation;
- in-app reporting of content and users;
- user blocking;
- published contact info (Apple) / acceptance of terms of use before posting (Google).

Apple tightened 1.2 in 2026: random or anonymous chat explicitly falls under it, and nonconsensual intimate imagery, including AI-generated imagery, is explicitly covered.

### Cited Findings
- **Apple 1.2** applies to apps that "enable users to create, generate, upload, share, or otherwise contribute content… This includes social media, user-generated content platforms, and AI content creation apps. To prevent abuse, such apps must include:
  - A method for filtering objectionable material from being posted to the app
  - A mechanism to report offensive content and timely responses to concerns
  - The ability to block abusive users from the service
  - Published contact information so users can easily reach you"

  — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 1.2, remediation:** "Developers who fail to implement appropriate safeguards or fail to remediate identified violations after notice may be considered in violation of the Developer Code of Conduct." Apps used primarily for "random or anonymous chat" "do not belong on the App Store." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 2026 updates:**
  - Feb 6, 2026: "apps with random or anonymous chat are subject to the 1.2 User-Generated Content guideline" — [Apple News d75yllv4](https://developer.apple.com/news/?id=d75yllv4)
  - Oct 16, 2026: "1.2: Content moderation requirements now explicitly cover nonconsensual intimate imagery — including imagery generated using AI tools". The same update added new 2.5.19 on bait-and-switch / hidden features. — [Apple News vvzx6cul](https://developer.apple.com/news/?id=vvzx6cul); [Apple News 92th7e5i](https://developer.apple.com/news/?id=92th7e5i)
- **Google UGC policy (search extracts of official text):**
  - apps must implement "robust, effective and ongoing UGC moderation";
  - users must accept the app's terms of use or user policy before creating or uploading UGC;
  - an "in-app system for reporting and blocking objectionable UGC and users" is required;
  - "UGC features that enable 1:1 user interaction with specific users must provide an in-app functionality for blocking users."

  Google's help article says missing reporting or blocking features lead to policy violations, and that these features must be "clearly labeled". — [Play Policy: UGC 9876937](https://support.google.com/googleplay/android-developer/answer/9876937); [Play Console Help 12923286](https://support.google.com/googleplay/android-developer/answer/12923286)

### Inferences
Implement and show reviewers:
- a "Report" action on profiles, portfolio items, reviews, job posts and chat messages;
- "Block user" in the chat and on the profile;
- a terms-of-use (EULA) acceptance checkbox at sign-up;
- a support email or contact page in the app and on the store listing;
- automated filtering (your AI moderation agent qualifies as a "method for filtering");
- a documented response SLA, for example 24 hours. A 24h SLA is common reviewer expectation lore and is not quoted in the text.

### Gaps
- The full verbatim Google UGC policy could not be fetched.

## 6. Privacy: nutrition labels, privacy manifests, Data safety, ATT, disclosure of AI scanning of messages

### Takeaway
You need all of the following:
- a privacy policy URL in both store listings and inside the app;
- Apple App Privacy answers and Google Data safety answers that match your SDKs;
- a valid PrivacyInfo.xcprivacy (enforced since May 1, 2024);
- ATT only if you track across apps or sites;
- since Nov 2025, explicit disclosure and consent before sending personal data to **third-party AI** (Apple 5.1.2(i)). This covers AI moderation of chats that uses an external LLM API.

### Cited Findings
- **Apple 5.1.1(i):** "All apps must include a link to their privacy policy in the App Store Connect metadata field and within the app in an easily accessible manner." The policy must identify the data collected and all its uses, and confirm that third parties give equal protection. — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 5.1.2(i):** "You must clearly disclose where personal data will be shared with third parties, including with third-party AI, and obtain explicit permission before doing so." Also: "You must receive explicit permission from users via the App Tracking Transparency APIs to track their activity." And: "Your app may not require users to enable system functionalities (such as push notifications, location services, tracking) in order to access functionality…" — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/). Secondary sources date the third-party-AI wording to the Nov 13, 2025 revision — [Open Terms Archive memo](https://opentermsarchive.org/en/memos/apple-updates-app-store-rules-on-data-use-age-gating-external-software-and-loan-app-disclosures/); [PPC Land](https://ppc.land/apple-tightens-app-store-age-controls-and-data-sharing-disclosure/)
- **Apple 5.1.1(ii)–(iv):**
  - consent is required even for data that is anonymous at collection;
  - "Ensure your purpose strings clearly and completely describe your use of the data";
  - "Where possible, use the out-of-process picker or a share sheet rather than requesting full access to protected resources like Photos";
  - "if a user declines to share Location, offer the ability to manually enter an address."

  — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Privacy manifests:** "starting May 1, 2024, apps that don't describe their use of required reason API in their privacy manifest file aren't accepted by App Store Connect." Each third-party SDK must ship its own manifest. — [Apple: Describing use of required reason API](https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api); [Apple: Privacy manifest files](https://developer.apple.com/documentation/bundleresources/privacy-manifest-files)
- **Expo:** "all Expo SDK packages that use 'required reason' APIs have a PrivacyInfo file included." However, Apple does not correctly parse all PrivacyInfo files from static CocoaPods dependencies, so Expo recommends declaring them in app config (`ios.privacyManifests` in app.json). — [Expo: Apple privacy](https://docs.expo.dev/guides/apple-privacy/)
- **Google Data safety:** account deletion and the web deletion link are declared in the Data safety form — [Play Console Help 13327111](https://support.google.com/googleplay/android-developer/answer/13327111)
- **SDK minimums:** from April 28, 2026, uploads must be built with the iOS 26 SDK or later — [Apple News ueeok6yw](https://developer.apple.com/news/?id=ueeok6yw). From April 2027, the iOS 27 SDK is required — [Apple News k1mtkt1k](https://developer.apple.com/news/?id=k1mtkt1k)

### Inferences
- **AI moderation that sends chat messages and files to an external LLM (e.g., OpenAI, Anthropic, Google):**
  - name the provider category in the privacy policy;
  - show an explicit consent screen before the first chat, e.g. "Messages are checked by AI (provider X) for fraud and safety";
  - declare "Messages / Other user content" collected for "App functionality" in both Apple App Privacy and Google Data safety.

  If moderation runs entirely on your own servers with your own model, this is not "third-party AI", but the use still needs disclosure in the privacy policy.
- Do not add ad or attribution SDKs unless needed. If you add them, you need ATT and must disclose "tracking".
- Expo SDK 54+ / RN builds must meet the current iOS SDK minimum (iOS 26 SDK until April 2027).

### Gaps
- The current Google Data safety field list was not fetched.
- No Google-specific rule on disclosing AI scanning of messages was found, beyond the general Data safety and User Data policy.

## 7. Financial features: escrow, money transfer, KYC, regulated services

### Takeaway
Apple 5.1.1(ix) says apps in highly regulated fields such as "banking and financial services" should be submitted by a **legal entity** that provides the services, not an individual. 3.2.1(viii) requires licensing for money-management apps. An escrow marketplace should enroll as an organization and use a licensed payment provider (e.g., Stripe Connect or a local licensed PSP). Then the app is a marketplace using a licensed processor, not a financial-services app itself.

### Cited Findings
- **Apple 5.1.1(ix):** "Apps that provide services in highly regulated fields (such as banking and financial services, healthcare, gambling, legal cannabis use, air travel and crypto exchanges) or that require sensitive user information should be submitted by a legal entity that provides the services, and not by an individual developer." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.2.1(viii):** "Apps used for financial trading, investing, or money management should be submitted by the financial institution performing such services and must have necessary licensing and permissions in the locations where you make them available." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 3.2.2(ix):** loan apps have an APR cap of 36%. This only matters if you add "advance payout" or credit features. — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### Inferences
- Holding client funds in escrow yourself (without a licensed partner) may trigger money-transmitter or e-money licensing in many jurisdictions, and gives App Review grounds to ask for licenses under 3.2.1(viii) / 5.1.1(ix).
- Use a licensed PSP or escrow partner. Describe it in Review Notes, e.g. "Payments processed and held by [licensed provider]; we do not hold funds".
- Publish as an **organization** account.
- KYC of freelancers (ID photo, selfie) is "sensitive user information". This is one more reason for organization enrollment and for clear purpose strings.

### Gaps
- The **Google Play Financial Services policy** and its Play Console "Financial features" declaration were not retrieved (support.google.com blocked). Whether an escrow marketplace must complete the financial features declaration, and which category applies, remains unverified. Check the Play Console App content → Financial features declaration directly.

## 8. AI features (AI moderation agent in chat)

### Takeaway
Google's AI-Generated Content policy applies only if the app *generates* content with AI that users see. If your agent writes messages into chats (warnings, suggestions, summaries), add in-app "report or flag" of AI output. Apple covers AI content under 1.2 ("AI content creation apps") and 5.1.2(i) (third-party AI disclosure).

### Cited Findings
- **Google AI-Generated Content policy:** apps that generate content using AI "must contain in-app user reporting or flagging features that allow users to report or flag offensive content to developers without needing to exit the app," and developers "should utilize user reports to inform content filtering and moderation." Scope: content generated by text, voice or image prompts, "including text chatbots where the AI generated chatbot interaction is a central feature of the app". The policy does not cover apps that only host AI content. — [Play Console Help 13985936](https://support.google.com/googleplay/android-developer/answer/13985936); [Understanding AI-Generated Content policy 14094294](https://support.google.com/googleplay/android-developer/answer/14094294); [Android Developers Blog, Jun 2024](https://android-developers.googleblog.com/2024/06/enabling-safe-ai-experiences.html)
- **Google 2026:** blog post on preventing non-consensual intimate content in GenAI apps — [Android Developers Blog, Aug 2026](https://developer.android.com/blog/posts/ensuring-safety-in-the-generative-ai-ecosystem-protecting-users-from-non-consensual-intimate-content?hl=en)
- **Apple:**
  - 1.2 now names "AI content creation apps", and NCII "including imagery generated using AI tools" — [Apple News vvzx6cul](https://developer.apple.com/news/?id=vvzx6cul)
  - 5.1.2(i) requires disclosure and permission for sharing with "third-party AI" — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### Inferences
- Label AI messages in chat clearly as AI or system messages.
- Give each AI message a "Report" action.
- Do not let the AI agent produce images.
- A pure classifier that silently blocks or flags messages probably falls outside Google's AI-Generated Content scope. It still falls under the UGC filtering and Apple 5.1.2(i) disclosure rules.

### Gaps
- No Apple guideline specific to AI agents in chat was found beyond the above.

## 9. Other review traps: demo account, minimum functionality, age rating, permissions, push, location

### Takeaway
Typical marketplace rejections:
- no working demo accounts for **both** sides (client and freelancer);
- an empty marketplace (no listings visible to the reviewer);
- forced login before browsing;
- a missing or incomplete age-rating questionnaire, which has new 2025–2026 questions (13+/16+/18+ tiers, social media capability questions, Shared Location / Dating descriptors);
- unclear permission purpose strings.

### Cited Findings
- **Apple 2.1(a):** "include demo account info (and turn on your back-end service!) if your app includes a login. If you are unable to provide a demo account due to legal or security obligations, you may include a built-in demo mode in lieu of a demo account with prior approval by Apple." Also: "placeholder text, empty websites, and other temporary content should be scrubbed before submission." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 4.2 Minimum Functionality:** "Your app should include features, content, and UI that elevate it beyond a repackaged website. If your app is not particularly useful, unique, or 'app-like,' it doesn't belong on the App Store." — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)
- **Apple 2.5.19 (new Oct 2026):** clarifies the prohibition on hidden, dormant or undocumented features and on "apps misrepresenting what they do during the App Review process and then changing after approval." — [Apple News 92th7e5i](https://developer.apple.com/news/?id=92th7e5i); [Apple News vvzx6cul](https://developer.apple.com/news/?id=vvzx6cul)
- **Age ratings (July 2025 overhaul):**
  - new 13+, 16+ and 18+ tiers alongside 4+ and 9+;
  - all apps had to answer the new questionnaire by **Jan 31, 2026** to avoid interrupted update submissions.

  — [Apple News: Updated age ratings](https://developer.apple.com/news/?id=ks775ehf); [Apple Upcoming Requirements](https://developer.apple.com/news/upcoming-requirements?id=07242025a); [MacRumors](https://www.macrumors.com/2025/07/25/apple-overhauls-app-store-age-ratings/)
- **Social media questions (Jul 9, 2026):** "A social media capability is defined as the ability to redistribute, amplify, or interact with user-generated content through a social feed or similar discovery method." Apps with it show a "Social Media" content descriptor. "Beginning in September 2026, responses will be required when submitting new apps or updates." — [Apple News tlur8uvi](https://developer.apple.com/news/?id=tlur8uvi)
- **New content descriptors (from Nov 16, 2026; deadline Jan 12, 2027):**
  - "Shared Location: Sharing of real-world location with another person or group" (Brazil: A16);
  - "Dating and Relationships" (18+ minimum).

  — [Apple News yxkh08us](https://developer.apple.com/news/?id=yxkh08us)
- **Age-assurance laws:** Texas law applies to new Apple Accounts from June 4, 2026, and Apple recommends the Declared Age Range API — [Apple News sg176nne](https://developer.apple.com/news/?id=sg176nne). Age requirements also apply in Brazil, Australia, Singapore, Utah and Louisiana — [Apple News f5zj08ey](https://developer.apple.com/news/?id=f5zj08ey)
- **Apple 5.1.2(i):** an app "may not require users to enable system functionalities (such as push notifications, location services, tracking) in order to access functionality". **5.1.1(iv):** offer manual address entry if Location is declined. — [App Review Guidelines](https://developer.apple.com/app-store/review/guidelines/)

### Inferences
- **Demo accounts:** give App Review two pre-seeded accounts (client and freelancer), at least one active order and chat, and a payment sandbox. If login is phone-OTP only, provide a test phone number with a fixed OTP code. Unconfirmed reviewer lore says OTP-only login without a test code is a frequent rejection cause.
- **Age rating:** answer "user-generated content / messaging" honestly. Expect at least 13+ (likely 16+/18+ if unrestricted chat with strangers). The descriptor "Shared Location" applies if courier or delivery location is shown live to the client. Seed the marketplace with real listings in the launch region.
- **Location:** use only "while in use" location for local search. Background location would need strong justification on both stores; Google requires a background-location permission declaration (known policy, not fetched this session).
- **Files and camera:** use the system photo/document pickers (PHPicker / Android Photo Picker) and avoid broad storage permissions.

### Gaps
- Google Play's new age-rating / IARC changes for 2025–2026 were not researched.
- The Google Photo & Video Permissions policy and background-location declaration text were not fetched.

## 10. Developer accounts: Google closed-testing rule, D-U-N-S, Tajikistan availability

### Takeaway
New **personal** Google Play accounts must run a closed test with 12+ testers for 14 consecutive days before production access. Organization accounts need a D-U-N-S number on both stores. Google's own table lists Tajikistan as supported for **developer** registration but **not merchant** registration. A Tajikistan-based developer can publish free apps, but cannot sell Play Billing subscriptions or boosts without a merchant entity in a supported country. Apple's status for Tajikistan was not confirmed.

### Cited Findings
- **Google closed testing:** personal developer accounts created after Nov 13, 2023 must have "at least 12 testers… opted in to your closed test… continuously for the preceding 14 days" before applying for production. The number was originally 20 and was lowered to 12. Internal and open testing do not count. — [Play Console Help 14151465](https://support.google.com/googleplay/android-developer/answer/14151465); [Android Authority](https://www.androidauthority.com/google-play-app-testing-requirement-3510580); [RevenueCat](https://www.revenuecat.com/blog/engineering/google-play-14-day/)
- **Google Tajikistan:** Google's table marks Tajikistan with a check mark for developer registration and a cross for merchant registration (from search extract; verify live). Tajikistan is on the list of countries where users can buy paid apps. — [Play Console Help 9306917](https://support.google.com/googleplay/android-developer/answer/9306917); [Paid app availability 143779](https://support.google.com/googleplay/answer/143779)
- **Apple D-U-N-S:**
  - Apple uses the D-U-N-S Number to verify the organization's legal entity;
  - "DBAs, fictitious businesses, trade names, or branches" are not accepted;
  - individuals do not need D-U-N-S;
  - D-U-N-S is free via Dun & Bradstreet.

  — [Apple: D-U-N-S Number](https://developer.apple.com/support/D-U-N-S/); [Apple: Enrollment](https://developer.apple.com/support/enrollment/)
- **Apple regional limits:** enrollment may not be supported in certain regions due to sanctions or other restrictions. No official list naming Tajikistan was found. — [Apple: Enrollment](https://developer.apple.com/support/enrollment/)

### Inferences
- **Practical setup for a Tajikistan-based team:**
  - for Play Billing and Apple IAP payouts (Pro plans, boosts), register a legal entity in a merchant-supported country (e.g., Kazakhstan, UAE, Georgia, US LLC), get a D-U-N-S number for it, and enroll both stores as an **organization**;
  - organization enrollment also avoids Google's 12-tester rule (the official page scopes that rule to personal accounts) and satisfies Apple 5.1.1(ix) for financial services;
  - if the app has no IAP or subscriptions at launch (only escrow via an external PSP), a Tajik developer account may suffice on Google. Apple remains unconfirmed.
- Allow up to ~30 days for D-U-N-S issuance (secondary source).

### Gaps
- Apple Developer Program availability and IAP payouts (Paid Apps Agreement banking) for Tajikistan residents or entities are unconfirmed. Check developer.apple.com/support/enrollment and the App Store Connect bank-country list, or contact Apple Developer Support.
- The Google merchant table could not be fetched directly. Confirm the live status at answer/9306917.
- No OFAC or other sanctions issue specific to Tajikistan was found. Tajikistan is not a comprehensively sanctioned country under US programs (general knowledge, not verified in this session).
