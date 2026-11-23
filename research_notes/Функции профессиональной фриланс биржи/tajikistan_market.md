# Tajikistan: market, payment and legal context for a freelance/services marketplace (2025–2026)

> Method note (read first). The research ran on 2026-11-23. Direct page fetching was blocked in this session for datareportal.com, nbt.tj, timesca.com and dlapiperdataprotection.com, so most facts below come from search-engine snippets and summaries of the cited pages, not from reading the full pages. Each fact has its URL next to it. Re-check the exact numbers on the live pages (especially nbt.tj and DataReportal) before you publish them. Where a fact could not be confirmed, it is marked "not publicly documented / confirm with the bank". Nothing about bank APIs here was invented.

## 1. Payment infrastructure: Korti Milli, card schemes, wallets, banks and acquiring APIs, QR

### Takeaway
Tajikistan's retail payments run on the National Bank's Korti Milli card system plus bank e-wallets. As of mid-2025, about half of all cards in circulation were pure Korti Milli, and more were co-badged with it. Visa is the largest international scheme. Registered e-wallets far outnumber cards (17.7M at end-2025, 19.8M by mid-2026). A unified national QR standard has been live since July 2023. Alif is the only major player with a clearly public online acquiring product (Alif Pay), and it onboards merchants on request. No bank publicly documents a marketplace, split-payment, escrow or mass-payout API.

### Cited Findings
**Card market and schemes**
- As of 30 June 2025, 9.1 million bank payment cards were in circulation, up 20.5% year on year. Scheme shares: Korti Milli 51.6%, Visa 15.3%, "Express Pay – Korti Milli" 10.8%, "UnionPay – Korti Milli" (co-badged) 9.9%, Mastercard 5.2%, local cards 4.7%. Source: NBT data reported via search snippets. — [NBT: Development of the bank payment card market](https://nbt.tj/en/payment_system/rushdi-bozori-kort-oi-pardokhtii-bonk.php); [Trend.az](https://www.trend.az/casia/tajikistan/4073722.html)
- At end-March 2025, Korti Milli's share was 54.1%. — [Trend.az](https://www.trend.az/casia/tajikistan/4038857.html)
- 9.256 million cards were in circulation on 31 July 2025. — [Trend.az](https://www.trend.az/casia/tajikistan/4090224.html)
- End-2025 totals: 10.4M bank cards (+23.7%), 17.7M e-wallets (+46.4%), 3,453 ATMs (+14.9%), 9,017 POS terminals (+10.8%) and 28,762 QR codes (+44.4%). — [Asia-Plus, 12 Feb 2026: "Tajikistan sees significant growth in digital payments"](https://asiaplustj.info/en/news/tajikistan/economic/20260212/tajikistan-sees-significant-growth-in-digital-payments); [Asia-Plus mirror](https://asiaplus.news/?p=401399)
- As of 30 June 2026, 28 credit financial institutions reported 19.8M e-wallets (+25.9% y/y). The NBT does not publish how many of these belong to unique users or are active. — [Times of Central Asia](https://timesca.com/tajikistans-digital-finance-boom-faces-its-next-challenge/)
- In H1 2026, 41% of payments for goods and services were cashless, made with electronic instruments (cards plus wallets). That is 13 percentage points more than a year earlier. — [Times of Central Asia](https://timesca.com/tajikistans-digital-finance-boom-faces-its-next-challenge/)
- **Mir (Russia):** In September 2025, Dushanbe City Bank, the second-largest bank, temporarily stopped serving Mir cards at its ATMs and POS terminals. The stated cause was technical failures/a cyberattack on NSPK, starting 23 September. US sanctions on NSPK's head (15 September 2025) were noted in the same coverage. No country-wide Mir ban was found. — [RTVI](https://rtvi.com/news/odin-iz-krupnejshih-bankov-tadzhikistana-perestal-prinimat-karty-mir/); [Business-Gazeta](https://www.business-gazeta.ru/article/665356); [myfin.by](https://myfin.by/stati/view/krupnyj-bank-tadzikistana-prekratil-obsluzivat-karty-mir-vozmozno-iz-za-kiberataki)
- **Apple Pay / Google Pay:** Apple Pay launched in Tajikistan on 28 July 2026 for Alif and Humo Bank customers. — [daryo.uz, 29 Jul 2026](https://daryo.uz/ru/2026/07/29/kyrgyzstan-tajikistan-expand-contactless-payments-with-apple-pay/); [egov.tj](https://egov.tj/site/innovation/press/news/details/7925?lang=en); [Trend.az](https://www.trend.az/casia/4213461.html). Alif also has a Google Pay page (launch date not captured). — [alif.tj/en/googlepay](https://alif.tj/en/googlepay)

**Unified QR**
- The NBT introduced a unified national QR standard. Merchants began accepting a single QR code on 1 July 2023, replacing the separate codes each bank or wallet used before. 16,472 unified QR codes were installed by August 2024. In August 2024 the NBT chairman blamed QR payment problems on weak internet and phones. — [Asia-Plus, 13 Aug 2024](https://asiaplus.news/en/2024/08/13/the-internet-and-phones-are-to-blame-the-chairman-of-the-national-bank-explained-the-problems-of-payment-with-qr-codes/)
- Under the standard, customers can pay through any participating app, not only an app from the merchant's own provider. The NBT has also issued frameworks for remote identification, for card–e-wallet interaction, and for the unified QR. — [Fintech Times](https://thefintechtimes.com/tajikistan-can-fintech-digitalise-a-remittance-economy/)
- The central banks of Kazakhstan, Kyrgyzstan, Tajikistan, Uzbekistan and Azerbaijan are working to link their national QR systems for cross-border payments. They reportedly aim to have a linking mechanism by end-2026. — [Trend.az](https://trend.az/casia/kazakhstan/4241271.html); [Times of Central Asia](https://timesca.com/central-asia-qr-payments-integration-2026/)
- The NBT publishes a fee schedule that covers interbank settlement and participation in the national payment system Korti Milli. The amounts were not captured, and no public card-to-card commission rule was found. — [NBT payment system overview](https://nbt.tj/en/payment_system/overview.php)

**Banks and wallets with merchant products**
- **Alif (Alif Bank / Alif Mobi / Alif Pay):** According to Wikipedia, Alif launched Alif Pay as its first online acquiring platform, letting Korti Milli cardholders from all Tajik banks pay online. — [Wikipedia: Alif Bank](https://en.wikipedia.org/wiki/Alif_Bank)
  - Alif's acquiring page says merchants can accept cards, wallets and mobile balances. Onboarding works through a request form ("we'll contact you within 48 hours"). No self-serve developer portal or public API reference was found. — [alif.tj/en/business/acquiring](https://alif.tj/en/business/acquiring); [alif.tj/en/business/merchant-acquiring](https://alif.tj/en/business/merchant-acquiring)
  - Alif lists 1,000+ active merchant acquiring partners. — [alif.tj about-us](https://www.alif.tj/en/bank/about-us)
  - A third-party Shopify app (CartDNA) integrates Alif with API credentials. It settles in TJS and does not support recurring payments. — [CartDNA](https://cartdna.com/en/shopify-payment-methods/alif)
  - bePaid (Belarus PSP) documents "Alif Mobi" as an alternative payment method. In that flow the merchant must answer account-verification requests within 14 seconds. This is a PSP integration, not Alif's own API spec. — [bePaid docs](https://docs.bepaid.by/en/payment_methods/apms/alif/)
- **Dushanbe City Bank (DC Next app):** It started as a microcredit deposit organisation (MDO) in 2007 and has operated as CJSC "Dushanbe City Bank" since 2022. DC Next pays taxes, utilities and 200+ services. Its business acquiring page lists POS terminals, QR codes and payment monitoring. No internet acquiring or API terms were found. — [dc.tj business](https://dc.tj/bussiness/en/index.php); [dc.tj about](https://dc.tj/aboutbank/?lang=en); [DC Next public offer](https://dc.tj/documents/img/8_Публичная_оферта_об_условиях_обслуживания)
  - It presented "a new generation of digital solutions" at the IT Park opening in April 2025 and expanded cashless payments in GBAO in October 2025. — [Asia-Plus Apr 2025](https://www.asiaplustj.info/en/news/tajikistan/economic/20250416/dushanbe-city-bank-presents-a-new-generation-of-digital-solutions-at-the-opening-of-it-park); [Asia-Plus Oct 2025](https://asiaplus.news/en/2025/10/29/dushanbe-city-bank-expands-cashless-payments-in-gbao/)
- **Humo Bank (Tajik bank; not the Uzbek "HUMO" card scheme):** It is an Apple Pay launch partner (2026). In September 2026 it required non-residents whose cards were opened remotely to pass in-person biometric identification by 30 September, or have the cards blocked from 1 October. New cards for such clients are issued only in person and for at most one year. — [Novaya Gazeta Europe, 29 Sep 2026](https://novayagazeta.eu/articles/2026/09/29/tadzhikskii-humo-bank-potreboval-ot-rossiiskikh-klientov-posetit-otdelenie-banka-do-kontsa-mesiatsa); [Caspian Post](https://caspianpost.com/tajikistan/tajikistan-s-humo-bank-to-restrict-some-remotely-opened-cards-for-non-residents)
- **Eskhata, Spitamen, Amonatbonk, IBT, Orienbank:** No public internet-acquiring, marketplace or payout API documentation was found in searches. Not publicly documented; confirm with each bank.

### Inferences
- Pay-ins must support Korti Milli (including co-badged cards) and the major wallets (Alif, DC Next, Humo, Eskhata, etc.) through a local acquirer. Visa/Mastercard alone would miss most cards. Alif Pay is the most likely first integration because it explicitly takes Korti Milli cards from all banks plus wallets.
- With ~20M wallets for ~10–11M people and 10.4M cards, "pay from wallet" and the unified QR should be first-class payment options alongside card entry.
- Diaspora clients paying from Russia face uncertainty with Mir cards and with remotely opened Tajik cards (Humo Bank 2026). The platform should not rely on Mir acceptance.
- Split payments, escrow holds and bulk payouts to cards/wallets must be negotiated bilaterally with a bank. No public product was found.

### Gaps
- Public fee schedules (MDR %) for Alif Pay, DC, Eskhata or Humo e-commerce acquiring: not found. Confirm with the banks.
- Whether any Tajik acquirer offers split/marketplace settlement, payouts to cards (OCT-style or Korti Milli card-to-card push) or wallet top-up APIs: not publicly documented. Confirm with the banks.
- The exact share of Mir cards issued in Tajikistan (Mir does not appear in the NBT's scheme breakdown above), and the current (Nov 2026) status of Mir acceptance across banks.
- Korti Milli card-to-card transfer fees and limits.

## 2. Regulation: payment services law, who may hold client funds, escrow implications, currency control

### Takeaway
Payment services fall under the Law "On payment services and payment system" (17/24 Feb 2017, amended 7 Aug 2020 No. 1723, with later amendments reported). The National Bank of Tajikistan (NBT) is the sole licensor and supervisor. Per a secondary guide, e-money (wallets) is issued only by licensed banks or microcredit organisations, and there is no separate e-money institution licence. A foreign or start-up platform therefore cannot hold client funds itself. Escrow must be run on a partner bank's or MDO's balance sheet (nominal/escrow account, or a bank-held wallet). Currency control is under Law No. 964 of 13 June 2013 (edition of 20 June 2024).

### Cited Findings
- The Law of RT "On payment services and payment system" sets the legal and organisational basis for payment systems and payment services. It defines the payment system operator and the payment infrastructure service operator. The edition reviewed includes amendments of 07.08.2020. — [spinform text](https://base.spinform.ru/show_doc.fwx?rgn=95469)
- Law No. 1723 of 7 August 2020 amended the payment services law and took effect on publication. — [spinform](https://base.spinform.ru/show_doc.fwx?rgn=126735)
- A Tajik-language text of the payment law (with 2020/2024 amendments referenced) is hosted at mmk.tj. — [mmk.tj](https://mmk.tj/system/files/Legislation/tj.1397.pdf)
- The NBT licenses payment system operators under Article 14 of the payment law. It publishes the licensing procedure and a register of operators with licence numbers and dates (register dated 02.07.2026). — [NBT licensing procedure](https://www.nbt.tj/en/payment_system/ravandi-dodani-i-ozatnoma-baroi-faoliyati-operatori-nizomi-pardokht.php); [NBT register PDF](https://nbt.tj/files/Фехристи%20ОНП%2002.07.2026.eng.pdf)
- According to a secondary regulatory guide, there is no specific "e-money institution" licence. E-money is issued by licensed banks or microcredit organisations. Payment System Operators (licence plus capital) are distinct from Payment Service Providers (banks/MCOs), and the NBT is the sole supervisor. The guide cites minimum capital of TJS 10m for banks and TJS 1m for MCOs. The guide is secondary and possibly outdated; verify. — [RegAlert: Tajikistan fintech & payments regulation](https://regalert.today/guides/fintech/TJ)
- Consistent with that, NBT statistics count e-wallets as issued by "28 credit financial institutions" (June 2026). — [Times of Central Asia](https://timesca.com/tajikistans-digital-finance-boom-faces-its-next-challenge/)
- The NBT has a "bank payment agents" regime: agents act for banks and do not hold funds in their own right. — [NBT: Bank payment agents](https://nbt.tj/en/payment_system/agenthoi-bonkii-pardokhti.php)
- In December 2023 the NBT revoked the licence of Western Union's Russian operator at the licensee's own request. This shows the NBT also licenses foreign payment system operators. — [daryo.uz](https://daryo.uz/ru/2023/12/29/national-bank-of-tajikistan-revokes-license-for-russian-operator-western-union/); [finance.mail.ru](https://finance.mail.ru/article/nacbank-tadzhikistana-annuliroval-licenziyu-rossiyskogo-operatora-western-union-59159170/)
- The NBT has an instruction on remote banking services (Instruction No. 201, listed as 2025). — [RegAlert document](https://regalert.today/document/instruction-no-201-on-remote-banking-services-4244837d-3c5f-4506-bb37-ddf03d5557bd/text)
- **Currency control:** The Law of RT "On currency regulation and currency control" No. 964 of 13 June 2013 (registered by MoJ 17 June 2013 No. 359) is current, with its latest edition dated 20.06.2024. It defines residents and non-residents. The 1995 law No. 498 is repealed. — [spinform](https://base.spinform.ru/show_doc.fwx?rgn=60988); [prg.kz](https://prg.kz/m/amp/document/31421124)
- **E-wallet monitoring (2026):** Tajikistan began tracking transfers to e-wallets to find unregistered business activity. Per one report, a wallet receiving more than 80 transfers from different senders in a month is flagged for review. The NBT says non-commercial transfers between individuals are not covered. — [Asia-Plus: "Tracking of transfers to electronic wallets will begin"](https://asiaplus.news/?p=548625); [Asia-Plus clarification](https://asiaplus.news/?p=549169); [Central Asian Light](https://www.centralasianlight.org/news/tajikistan-to-begin-monitoring-transfers-to-e-wallets/)

### Inferences
- The platform (especially if it is operated by a foreign or non-bank entity) should not hold users' TJS itself. The workable model is a partner bank or MDO that holds escrow funds, in a nominal/escrow account or by freezing funds in the bank's wallet, while the platform only instructs releases. Getting its own payment-operator licence is a heavy, separate path.
- Freelancers who receive many client payments into personal wallets may be flagged by the 2026 >80-senders rule. This argues for payouts that the bank labels as marketplace payouts, and for encouraging freelancers to register as individual entrepreneurs (see §3).
- For foreign (e.g., Russian or diaspora) clients, pay-ins arrive as cross-border flows subject to Law No. 964 and the bank's AML checks. Plan to collect payer data for the partner bank.

### Gaps
- The exact article text on who may accept and hold funds for third parties, on e-money issuance limits (per-wallet caps for identified vs. unidentified users) and on the capital requirements for payment organisations: not obtained (nbt.tj was unreachable). Confirm with the NBT or local counsel.
- Whether Tajik law recognises a nominal/escrow account (номинальный счёт / эскроу-счёт) in the Civil Code or banking law: not confirmed.
- The rules for residents receiving foreign currency from abroad for services (repatriation, conversion, reporting): not found in snippets.

## 3. Taxation of freelancers / individual entrepreneurs and platform obligations

### Takeaway
The Tax Code took effect on 1 Jan 2022; it is the "2021 Code", which cut the number of taxes from 10 to 7. Individual entrepreneurs (IE) work either on a **patent** (fixed sum covering income and social tax, indexed and with zone coefficients) or on a **certificate**. With a certificate they may choose the simplified regime: 6% of gross income if annual income is ≤ TJS 1 million. No dedicated "self-employed" regime was found. A 2026 pilot taxes entrepreneurs' e-wallet, app and QR receipts at a reduced 3%, with automatic calculation from bank data, from about September 2026. A 2022 government resolution targets disguised employment on patents or certificates.

### Cited Findings
- The new Tax Code entered into force on 1 January 2022 and cut the number of tax types from 10 to 7. — [PwC Tax Summaries: Tajikistan corporate](https://taxsummaries.pwc.com/tajikistan/corporate/taxes-on-corporate-income); [FAOLEX Tax Code 2021](https://faolex.fao.org/en/documents/LEX-FAOC243145/tax-code-tjk-2021)
- **Simplified regime:** IEs may use it if gross annual income does not exceed TJS 1,000,000. The rate is 6% unless the Tax Code says otherwise. It replaces income tax (except withholding tax) and VAT (except import/reverse-charge VAT). Certificate-holders may choose the simplified regime based on gross income or on income less documented expenses. — [PwC Tax Summaries](https://taxsummaries.pwc.com/tajikistan/corporate/taxes-on-corporate-income); [PwC individual](https://taxsummaries.pwc.com/tajikistan/individual/taxes-on-personal-income)
- **Patent:** A fixed tax regardless of income. The patent cost covers income tax and social tax. — [PwC Tax Summaries](https://taxsummaries.pwc.com/tajikistan/corporate/taxes-on-corporate-income)
- Patent fees are indexed annually for inflation. Zonal coefficients for cities and districts are set under Tax Code articles (284, 286, 289, 327 referenced). Current 2026 amounts were not found. — [spinform](https://base.spinform.ru/show_doc.fwx?rgn=139788)
- Government Resolution No. 151 of 31 March 2022 lists signs that an IE on a patent or certificate is really an employee, for example most services going to one customer, income from one source, or features of a labour contract. Only a snippet was available. — [spinform](https://base.spinform.ru/show_doc.fwx?rgn=139788)
- **2026 e-wallet/QR tax pilot:** It covers taxation of transactions by certain entrepreneurs through e-wallets, mobile apps and QR payments from September 2026 (one source says 1 Sept 2026). The rate for IEs on such transactions is reduced from 6% to 3%, with automatic calculation. Banks, wallet operators and QR services feed data, and the NBT is designated system operator. — [Asia-Plus: "A tax on transactions between electronic wallets… September 2026"](https://asiaplus.news/?p=550574); [Times of Central Asia](https://timesca.com/tajikistans-digital-finance-boom-faces-its-next-challenge/); [Alif: "New project is only for entrepreneurs"](https://alif.tj/en/bank/news/new-project-is-only-for-entrepreneurs)
  - Conflicting detail: a secondary guide says the 3% splits into components (1.5% "system tax" + 0.5% social tax, which does not add up to 3%), and its Japanese version mentions a 1% cashback element. Treat the breakdown as unverified. — [beancount.io guide](https://beancount.io/blog/2026/09/18/tajikistan-e-wallet-transaction-tax-mobile-money-guide)
  - An e-invoicing tracker dates the underlying order to 1 April 2026. It says participants must use cash registers, and each payment generates a fiscal receipt. — [e-invoice.app: Tajikistan](https://www.e-invoice.app/news/tajikistan)
- Asia-Plus (2025) contrasts Uzbekistan's simplified small-business taxes with Tajikistan's "complex" entrepreneur rules. — [Asia-Plus](https://asiaplus.news/?p=394204); [Caspian Post](https://caspianpost.com/uzbekistan/uzbekistan-simplifies-taxes-as-tajikistan-clings-to-complex-entrepreneur-rules)
- **IT Park residents:** Reports conflict. One says residents are exempt from most taxes except 6% personal income tax and 1% social tax. Asia-Plus describes 0% profit tax, VAT, dividend and local taxes, with reduced income and social rates. Another Asia-Plus piece says the usual tax and customs benefits were "not yet available" at IT Park Dushanbe. — [Asia-Plus: IT Park opened](https://asiaplus.news/?p=386390); [Asia-Plus: Uzbekistan's IT Park earns $1bn. What about Tajikistan?](https://asiaplus.news/?p=377835)
- Mellow (a freelancer payments service) has a "Freelance and taxes: Tajikistan" help article (contents not captured). — [help.mellow.io](https://help.mellow.io/en/articles/9148831-freelance-and-taxes-tajikistan)

### Inferences
- The marketplace should help freelancers declare an IE status (patent, certificate or simplified regime) and store their TIN (ИНН). If the partner bank sees payouts as entrepreneurial receipts, the 3% pilot regime with automatic calculation may apply. The platform should show fiscal receipts if the bank or QR provider generates them.
- A freelancer who works mostly for one client through the platform risks being re-qualified as an employee under Resolution 151. Disclose this risk in the help center.
- The platform's own commission is a taxable service. If the operator is a Tajik legal entity, standard corporate and VAT rules apply, and it may consider IT Park residency.

### Gaps
- No explicit obligation for a marketplace to withhold tax for freelancers was found. Whether the 2026 pilot makes platforms or their banks tax agents is unclear. Confirm with the Tax Committee (andoz.tj) or counsel.
- Whether IT / freelance activities appear on the list of activities allowed under a patent, and the 2026 patent amounts: not found.
- No "self-employed" (самозанятый) regime was found for Tajikistan.

## 4. Personal data, e-documents / e-signature, e-commerce, consumer protection, public offer

### Takeaway
The Law "On personal data protection" No. 1537 of 3 August 2018 relies mainly on consent. Per secondary sources there is no data-localization requirement. Cross-border transfer is free to "adequate" countries. Otherwise it needs the data subject's consent, a treaty, or a public-interest ground. The regulator was named by presidential decree (amended 31 Jan 2025, No. 949), but sources disagree on which body it is. E-signatures are governed by the new Law "On electronic document and electronic signature" of 15 March 2023 (amended 2025). Public-offer contracts are already standard practice among Tajik banks and apps.

### Cited Findings
- The main law is the Personal Data Protection Law No. 1537 of 3 August 2018. — [DLA Piper Data Protection: Tajikistan](https://www.dlapiperdataprotection.com/index.html?t=law&c=TJ); [ILO NATLEX](https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=109580)
- **Cross-border transfer:** There are no restrictions if the foreign country provides adequate protection. Where it does not, transfer is allowed with the data subject's consent, under an international treaty recognised by Tajikistan, or to protect citizens' rights, health, morality or public order. — [DLA Piper](https://www.dlapiperdataprotection.com/?t=law&c=TJ)
  - GRATA's earlier analysis presents consent as the main route for cross-border transfer. — [GRATA International](https://gratanet.com/publications/personal-data-protection-in-the-republic-of-tajikistan); [Mondaq mirror](https://webiis08.mondaq.com/data-protection/993356/personal-data-protection-in-the-republic-of-tajikistan)
- **Localization:** GRATA (2020) said there is "no requirement for data localization", so data can be stored abroad. No later source showing a change was found. — [GRATA](https://gratanet.com/publications/personal-data-protection-in-the-republic-of-tajikistan)
- Data subjects can revoke consent (Art. 11). — [DataGuidance overview](https://platform.dataguidance.com/notes/tajikistan-data-protection-overview)
- A secondary summary says the law does not prescribe the form of consent except for biometric data, which requires written consent. I could not tie this to one source in the result set; verify in the statute. — [GRATA](https://gratanet.com/publications/personal-data-protection-in-the-republic-of-tajikistan); [CaseGuard](https://caseguard.com/articles/privacy-and-personal-data-protection-in-tajikstan/)
- **Regulator (conflicting):** A presidential decree "On determining the authorized state body for personal data protection" is listed as amended by Decree No. 949 of 31.01.2025. This is an unofficial Google Docs copy; only the title was seen. — [docs.google.com copy](https://docs.google.com/document/d/1zOgGcxrkakclcDyFWLbfJF5kpt_EHMBv/export?format=pdf). DataGuidance (May 2024) names the Communications Service under the Government. DLA Piper says enforcement is mainly by the Main Department for the Protection of State Secrets. — [DataGuidance](https://platform.dataguidance.com/notes/tajikistan-data-protection-overview); [DLA Piper](https://www.dlapiperdataprotection.com/?t=law&c=TJ)
- A 2026 Chambers "Investing in" guide describes processing as generally consent-based and purpose-limited. — [Chambers Investing In 2026: Tajikistan](https://gpg-pdf.chambers.com/investing-in-2026/633/)
- UNESCAP has a Tajikistan data governance profile (background). — [UNESCAP](https://unescap.org/sites/default/d8files/event-documents/Tajikistan-data-governance-profile.pdf)
- **E-signature:** The Law of RT "On electronic document and electronic signature" of 15 March 2023 (Akhbori Majlisi Oli 2023 No. 1-3 art. 17; amended 2025 No. 6-10 art. 646) is the operative act. — [spinform (amending law)](https://base.spinform.ru/show_doc.fwx?rgn=176419)
- Amendments of 24 Dec 2022 No. 1931 to the Economic Procedure Code allow e-filing with a digital e-signature. — [prg.kz](https://prg.kz/m/amp/document/38551187)
- A government resolution names authorized supervisory bodies for e-document flow and for e-commerce (date not visible). No standalone "Law on e-commerce" was found. — [FAOLEX taj221408](https://faolex.fao.org/docs/pdf/taj221408.pdf)
- The World Bank Tajikistan Economic Update (summer 2025) focuses on digital transformation of trade. — [World Bank, 30 Jul 2025](https://www.worldbank.org/en/country/tajikistan/publication/economic-update-2025)
- **Public offer practice:** Dushanbe City Bank publishes a "public offer" governing use of DC Next by individuals and legal entities. Alif publishes a service-use agreement. — [DC public offer](https://dc.tj/documents/img/8_Публичная_оферта_об_условиях_обслуживания); [Alif agreement PDF](https://alifwebsite.alif.tj/uploads/Soglashenie_ob_ispolzovanii_servisa_27_03_2020_c9b2bbd4_dc6bc1ec71.pdf)

### Inferences
- Hosting on Hetzner (Germany/Finland) appears permissible because no localization rule was found. Since EU adequacy under Tajik law has not been formally declared, the safest route is explicit, separate consent at sign-up to cross-border transfer and storage abroad, plus to processing by named sub-processors (e.g., an external AI API that receives chat text). Make consent revocable (Art. 11).
- Any face or selfie biometric KYC should collect written (electronic) consent specifically for biometrics.
- Terms of service should take the form of a public offer (публичная оферта) in Tajik and Russian, the local norm. Acceptance can be electronic. Where qualified e-signature matters, the 2023 e-signature law applies.

### Gaps
- The current name of the personal-data regulator, and whether processors must register or notify it: unresolved because sources conflict.
- Breach-notification duties and penalty amounts: not found.
- Consumer protection law specifics for distance or online services (refund and withdrawal periods): not researched successfully.
- Whether Tajikistan has a standalone e-commerce law (2023–2026): not found.

## 5. Identity documents and e-ID / verification

### Takeaway
Electronic ID cards (a decree of Sept 2013) have been issued since 1 April 2014 to replace the 16-page internal passport. Biometric foreign (travel) passports have been issued since February 2010. Legacy internal passports stayed valid until expiry, and as of 2019 the replacement was lagging. Searches found no single digital-ID law and no public government verification API. Remote identification exists for banks and wallets under NBT rules (developed in 2020 with IFC). The state is expanding Face ID biometrics, e.g., for pensioners from 2025.

### Cited Findings
- A presidential decree of Sept 2013 set up electronic ID cards. Issuance started 1 April 2014 in Dushanbe. ID cards are to fully replace the 16-page internal passports, which remain valid until expiry. — [Asia-Plus, 3 Apr 2014](https://asiaplus.news/en/2014/04/03/tajik-authorities-begin-issuing-new-identification-cards-for-citizens/); [Asia-Plus, 7 Jan 2014](https://asiaplus.news/en/2014/01/07/paper-passports-will-be-replaced-with-id-cards-in-tajikistan/); [ICAO 2014 presentation](https://www.icao.int:443/Meetings/mrtd-tashkent-2014/Documents/Session3_3-Manuchehr.pdf)
- In 2019, passport offices were not on track to replace old passports with ID cards, and an extension of the deadline was being considered. — [Asia-Plus, 5 Jul 2019](https://asiaplus.news/en/2019/07/05/tajik-authorities-can-extend-the-term-of-change-of-passport/)
- Biometric foreign passports were first issued 1 February 2010. — [Wikipedia: Tajik passport](https://wikipedia.com/wiki/Tajik_passport)
- In 2025 the government began moving pensioners to Face ID-based digital identification (863,690 registered pensioners as of 1 Sep 2025). Tajikistan "does not yet have a single, consolidated digital ID law". — [Asia-Plus](https://asiaplus.news/?p=398097); [SEAP nationality profile](https://seap.nationalityforall.org/?p=2805)
- The NBT developed remote client identification procedures in 2020 with its Financial Monitoring Department and IFC, initially for e-wallets. — [DataGuidance news](https://www.dataguidance.com/news/tajikistan-national-bank-develops-methods-remote); [Eurasian Group (EAG)](https://eurasiangroup.org/en/respublika-tadzhikistan-vnedryaet-procedury-udalennoy-identifikacii-dlya-elektronnyh-koshel-kov)
- One analysis says Tajikistan has no independent local e-KYC provider and that digital identification is "a domain dominated by the state". — [Kursiv, 2026](https://kz.kursiv.media/?p=6852625)
- Since 2024, citizens must give fingerprints to obtain a criminal record certificate. — [Asia-Plus](https://asiaplus.news/?p=381268)
- Didit (a global KYC vendor) markets Tajikistan document coverage. Exact document types were not verified. — [didit.me](https://didit.me/solutions/countries/tajikistan/)
- Tajikistan is restructuring its digital government system around data and public services (2026). — [Trend.az](https://www.trend.az/casia/tajikistan/4216372.html)

### Inferences
- KYC should accept the ID card (2014+), the old internal passport (if still valid) and the biometric foreign passport. Diaspora users in Russia mostly carry the foreign passport. Foreign passports are ICAO 9303 machine-readable with an MRZ, by virtue of being biometric e-passports.
- With no public government verification API, rely on (a) the partner bank's KYC, where a payout account at an identified bank or wallet is a strong proxy, and/or (b) a global OCR+liveness vendor, with written biometric consent.

### Gaps
- Whether the ID card has an MRZ and chip, and its exact format: not confirmed in sources.
- Any government e-ID or verification API (e.g., via egov.tj) open to private companies: not found; likely does not exist publicly.
- The current (2026) status of new ID-card or passport reforms: no 2025–2026 announcement found.

## 6. User behavior and infrastructure: internet, devices, messengers, speeds and prices, SMS, languages, migration

### Takeaway
About 6.1M internet users, roughly 57% penetration at end-2025. About 11M mobile connections (above 100% of population). Only about 2.4M social media identities. Android leads with about 76–80% of mobile traffic; iOS about 20–24%. Mobile internet is slow and relatively expensive (139th of 143 for mobile speed in Feb 2025), though it is improving and full 4G is targeted by 2027. WhatsApp and IMO have historically led messaging, and Telegram is strong for channels. Four mobile operators; international SMS aggregators cover OTP. Tajik (Cyrillic) is the state language and Russian is widely used in business. Remittances are about 45–49% of GDP, with 0.5–1.2M Tajiks working in Russia.

### Cited Findings
**Internet and mobile**
- Digital 2025: 6.07M internet users in January 2025 (+113k, +1.9% y/y). — [DataReportal Digital 2025: Tajikistan](https://datareportal.com/reports/digital-2025-tajikistan)
- Digital 2026: about 6.15M internet users at end-2025, 56.8% penetration. 10.9M cellular mobile connections (GSMA Intelligence). — [DataReportal Digital 2026: Tajikistan](https://datareportal.com/reports/digital-2026-tajikistan)
- DataReportal's later page (labelled Digital 2027, data to Oct 2026): internet users +107k (+1.8%) Oct 2025–Oct 2026. 11.3M mobile connections (102% of population). 2.40M social media user identities (21.8% of population). — [DataReportal Digital 2027: Tajikistan](https://datareportal.com/reports/digital-2027-tajikistan)
- Conflicting figures: trade.gov cites over 4.9M users and penetration above 46% by 2025. DataReportal's 2024 edition said 4.25M. — [trade.gov ICT guide](https://www.trade.gov/country-commercial-guides/tajikistan-information-and-communication-technologies-ict); [DataReportal 2024](https://datareportal.com/reports/digital-2024-tajikistan)
- Facebook audience: 2.72M (Sep 2026) and 2.90M (May 2026). Instagram audience: 2.48M (Sep 2026). Mostly male users; women are about one-fifth to one-quarter. — [NapoleonCat social media users](https://napoleoncat.com/stats/social-media-users-in-tajikistan/)
- Facebook Messenger: 614,500 users (5.9% of population) in Sep 2025. — [NapoleonCat messenger](https://napoleoncat.com/stats/messenger-users-in-tajikistan/2025/09)

**Devices**
- StatCounter mobile OS share: Android 80.36% / iOS 19.61% (mobile, June 2026). Mobile+tablet: Android 76.32% / iOS 23.65% (July 2026) and 79.23% / 20.77% (Aug 2026). — [StatCounter mobile OS Tajikistan](https://gs.statcounter.com/os-market-share/mobile/tajikistan); [StatCounter mobile+tablet](https://gs.statcounter.com/os-market-share/mobile-tablet/tajikistan)
- All platforms (Aug 2026): Android 46.6%, Windows 25.6%, iOS 12.3%. So desktop is about a quarter of web traffic. — [StatCounter all platforms](https://gs.statcounter.com/os-market-share/desktop-mobile-tablet/tajikistan)

**Messengers and social**
- An Internews survey (2022, via Statista) found WhatsApp most popular (46%), with IMO second. — [Statista](https://www.statista.com/statistics/1403810/tajikistan-most-popular-messengers/)
- 2021: WhatsApp ~45.7%, IMO ~34.4%, Viber ~4.6%, Telegram ~4.4% as the most-used messenger. — [Voxdash](https://voxdash.com/question/17083)
- An IWPR regional survey names Viber and Telegram as the main messengers for exchanging news in Tajikistan (date not shown). — [ecoi.net / IWPR "How Central Asia Gets Its News"](https://www.ecoi.net/en/document/2018277.html)
- WMTips (web-tech-based, 2026) ranks Telegram second among social platforms (~47%) behind Instagram. This is a weak proxy. — [wmtips](https://www.wmtips.com/technologies/social-media/country/tj/)
- No 2025–2026 messenger usage survey was found.

**Speed, price, coverage, shutdowns**
- In Feb 2025, Tajikistan ranked 139th of 143 countries for mobile internet speed. ISOC Pulse lists 8.51 Mbps average mobile download. — [ts2.tech](https://ts2.tech/en/inside-tajikistans-internet-connectivity-challenges-costs-and-the-satellite-solution/); [ISOC Pulse](https://pulse.internetsociety.org/en/reports/tj/)
- Average mobile speed doubled versus 2022, per trade.gov. — [trade.gov](https://www.trade.gov/country-commercial-guides/tajikistan-information-and-communication-technologies-ict)
- Tcell was named the fastest mobile network for H1 2025 (Ookla) and won an Ookla Speedtest Award at MWC 2026. — [Tcell news](https://www.tcell.tj/en/for-home/news/13594); [Tcell Speedtest Award](https://www.tcell.tj/en/for-home/news/17210)
- Targets are full 4G coverage by 2027 and 5G rollout by 2030. Mobile internet problems persist (Jan 2026). — [daryo.uz](https://daryo.uz/en/2026/01/29/tajikistan-targets-full-4g-coverage-by-2027-5g-rollout-by-2030-as-mobile-internet-issues-persist/)
- The communications agency head said speeds would double by end-2025. The first price cuts came in April 2025, when Tcell and Babilon-Mobile increased data volumes. — [Asia-Plus](https://asiaplus.news/?p=391464); [Asia-Plus "What has changed since early 2025?"](https://asiaplus.news/?p=389942)
- **Price per GB (conflicting):** ~$1.65/GB in 2024, rank 142 of 238 (ts2.tech, citing price-comparison data), versus a regulator official's claim of 2.5 TJS (~$0.25) per GB. — [ts2.tech](https://ts2.tech/en/inside-tajikistans-internet-connectivity-challenges-costs-and-the-satellite-solution/); [Asia-Plus](https://asiaplus.news/?p=389942)
- Regional gaps: GBAO internet was cut after protests in Nov 2021 and May–June 2022. — [HRW 2022](https://www.hrw.org/news/2022/02/07/tajikistan-restore-internet-autonomous-region); [The Diplomat](https://thediplomat.com/2022/05/internet-severed-again-in-tajikistans-gbao). No 2025 GBAO shutdown was found.

**SMS and OTP**
- Four mobile operators: MegaFon Tajikistan, Tcell, ZET-Mobile, Babilon-M. Business SMS is regulated by the Communications Service, and sender IDs are approved via operators. — [sent.dm Tajikistan SMS guide](https://www.sent.dm/resources/tajikistan-sms-guide); [Twilio TJ guidelines](https://www.twilio.com/guidelines/tj/sms)
- Messaggio offers OTP routes on Tcell, MegaFon, Babilon-Mobile and ZET-Mobile. BudgetSMS, SMS.to, D7 and Twilio also list Tajikistan. Secondary pricing is about $0.21–0.45 per SMS. — [Messaggio](https://messaggio.com/messaging/tajikistan/); [BudgetSMS](https://www.budgetsms.net/sms-gateway-pricing/tj/tajikistan); [sent.dm pricing](https://www.sent.dm/en/resources/sms-pricing/tajikistan-sms-pricing)
- Local SMS gateways (e.g., OsonSMS) were not verifiable from search results.

**Languages**
- The Constitution makes Tajik the state language and Russian the language of interethnic communication. The 2009 language law removed Russian's special designation, yet Russian is still used in business and social media. Students must study Russian for two semesters at universities. — [Wikipedia: Languages of Tajikistan](https://en.wikipedia.org/wiki/Languages_of_Tajikistan); [RFE/RL](https://rferl.org/a/Tajikistan_Drops_Russian_As_Official_Language/1846118.html); [NYU GlobaLex](https://www.nyulawglobal.org/globalex/Tajikistan1.html)
- In June 2024, Tajikistan approved the agreement establishing the International Organization for the Russian Language. — [RUDN journal](https://journals.rudn.ru/russian-test/article/view/47939/en_US)

**Labor migration and economy**
- Remittances were about 49% of GDP in 2024 (World Bank) and about 48% (OWID). — [World Bank Economic Update, 30 Jul 2025](https://www.worldbank.org/en/news/press-release/2025/07/30/tajikistan-economic-update-2025); [Our World in Data](https://ourworldindata.org/data-insights/tajikistans-remittances-are-worth-nearly-half-the-countrys-gdp)
- Estimates of Tajik workers in Russia at end-2025 range from under 500k to over 1.2M. — [Asia-Plus, 8 Jan 2026](https://asiaplus.news/en/2026/01/08/how-many-tajik-migrants-are-working-in-russia/)
- FSB data via Vedomosti: 1.44M Tajik citizens entered Russia in 2025, of whom 950k came for work (about 15% fewer than in 2024). — [Asia-Plus, 7 Apr 2026](https://asiaplus.news/en/2026/04/07/vedomosti-950000-migrants-from-tajikistan-arrived-in-russia-in-2025/)
- Russia deported more than 54,000 migrants in Jan–Nov 2025. More than 150,000 Tajiks are on Russia's "controlled persons" list. — [Asia-Plus](https://asiaplus.news/?p=399372); [Asia-Plus, 28 Nov 2025](https://asiaplus.news/en/2025/11/28/number-of-tajik-migrants-on-russias-blacklist-exceeds-150000/)

### Inferences
- Build Android-first (about 4 in 5 mobile users) with a lightweight app (small APK, low-bandwidth mode, image compression, offline drafts). Also ship iOS and a responsive web app, because desktop is about 25% of web traffic.
- For notifications, use push plus SMS OTP through an international aggregator with local-operator routes. Add Telegram bot and WhatsApp channels for notifications; WhatsApp and IMO are dominant for personal messaging, and Telegram is useful for channels and bots.
- Ship the UI in Tajik (Cyrillic) and Russian at launch, with English optional for international clients. Russian matters for diaspora users and for business.
- Remote/online work suits the large diaspora and returnee population hurt by Russian restrictions. Cross-border pay-ins from Russia are a key flow, so see the Mir caveats in §1.

### Gaps
- The DataReportal Digital 2026 full breakdown (YouTube, TikTok, Instagram ad reach and Ookla medians) could not be read; datareportal.com was blocked for fetching.
- No 2025–2026 messenger ranking survey was found.
- Fixed broadband price and speed for 2025–2026: not captured.

## 7. Existing freelance/services platforms, Telegram channels and government IT initiatives

### Takeaway
The local online freelance scene is small. Per the ETF 2024 study, Tajikistan has the fewest online freelancers among the Central Asian countries it covers. Alif's tech arm runs a "Freelance" platform (ToS dated 7 Oct 2023) that explicitly does not process payments or act as escrow, which leaves a gap for a marketplace with safe payments. The government opened IT Park Dushanbe in April 2025 (18 residents by summer 2025), alongside Pamir IT Park in Khorog, and the National Financial Inclusion Strategy 2022–2026 is running.

### Cited Findings
- European Training Foundation study "Platform work in Central Asia" (data Mar–Sep 2023, published 2024): Tajikistan has the lowest number of online freelancers among the covered countries. Data came from Freelancer.com, Guru, Weblancer and others. A separate Tajikistan country report exists. — [ETF summary EN](https://www.etf.europa.eu/sites/default/files/2024-09/Platform%20work%20in%20Central%20Asia%20-%20Summary.pdf); [ETF Tajikistan report](https://www.etf.europa.eu/sites/default/files/2024-08/Tajikistan_Report_final%20v.4.0_clean.pdf)
- **Alif Tech "Freelance"** (OJSC "Alif Tech"): a platform where freelancers and clients post and complete projects. Its ToS (last updated 07.10.2023) says the service does not process payments, is not responsible for financial operations between the parties (who agree payment and fees themselves), and is not liable for non-performance. Seen via a Google Docs copy, not an official alif.tj page. — [ToS copy](https://docs.google.com/document/d/1TOVCtmstxJxg3D-3vzxUIDgM7T3Cxc1AWa4afTeJDI8/export?format=pdf)
- Quasa Connect promotes crypto-paid freelancing to Tajik users. The article notes Tajikistan lacks clear crypto regulation. — [quasa.io](https://quasa.io/ru/media/kak-v-tadzhikistane-zhivut-frilansery-zarabatyvayushchie-kriptovalyutu-cherez-quasa-connect)
- Upwork has a "Hire freelancers in Tajikistan" page (marketing). — [Upwork](https://www.upwork.com/hire/tj/)
- Anecdotal (unverified LinkedIn comment): a user reports Payoneer delays in issuing MT103 for USD transfers to Tajikistan. — [LinkedIn](https://ua.linkedin.com/in/rahmonzoda/en)
- **IT Park Dushanbe** opened 7 April 2025 and had 18 resident companies as of summer 2025. Tajikistan has two IT parks: Pamir IT Park (Khorog) and IT Park Dushanbe. — [Asia-Plus: IT Park opened in Dushanbe](https://old.asiaplustj.info/en/news/tajikistan/economic/20250408/it-park-opened-in-dushanbe); [egov.tj](https://egov.tj/site/innovation/press/news/details/1020?lang=en)
- IT Park Dushanbe, IT Park Uzbekistan and Astana Hub signed a trilateral cooperation agreement. A new IT Park building is planned in Dushanbe. — [Asia-Plus](https://asiaplus.news/?p=398936); [Asia-Plus](https://asiaplus.news/?p=401325)
- In April 2026, the Tajik Transport Digital Center became an IT Park resident. — [Khovar](https://eng.khovar.tj/2026/04/tajik-transport-digital-center-secures-it-park-resident-status/)
- The National Financial Inclusion Strategy 2022–2026 puts digital financial services at its center. The NBT has a financial literacy programme for 2026–2030. — [Times of Central Asia](https://timesca.com/tajikistans-digital-finance-boom-faces-its-next-challenge/); [NBT literacy programme PDF](https://nbt.tj/files/Protection/2026/Программа_повышения_финансовой_грамотности_на_2026_2030_en.pdf)
- Eurasianet: "Central Asian visions of IT boom look distant" (regional context). — [Eurasianet](https://eurasianet.org/central-asian-visions-it-boom-look-distant)

### Inferences
- Competition is weak locally. The main local platform (Alif Tech Freelance) leaves payments to the users. Escrow-backed safe payment in TJS, local-language support and verified profiles would be differentiators.
- Because the freelancer pool is small, demand may lean toward offline/local services (repairs, tutoring, design, SMM) and toward remote work for diaspora or Russian-speaking clients. Plan categories for both.

### Gaps
- Specific Telegram channels or groups used for freelance job posting in Tajikistan: none found through search. Field research is needed.
- Local classifieds and services sites (e.g., Somon.tj) and their service categories were not researched in this pass.
- Current status and user numbers of Alif Tech Freelance: not found.
