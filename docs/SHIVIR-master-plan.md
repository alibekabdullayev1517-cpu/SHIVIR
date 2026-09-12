# SHIVIR — Final Master Product Plan
### Product + UX/UI + Growth + Safety + Monetization + Technical Master Specification

*This document synthesizes the prior "Sirli Xabar" research and the "SHIVIR" strategic research into one implementation-ready spec. Where the earlier research's numbers are reused, they remain tagged as they were originally: FACT / ESTIMATE / ASSUMPTION / HYPOTHESIS / RECOMMENDATION. Nothing from prior research is treated as automatically true — figures are restated with their original evidence status, not upgraded.*

---

## PART A — PRODUCT STRATEGY

**1. Product vision.** A Telegram-native anonymous messaging product for Uzbekistan that feels premium, not "just another bot," and grows into a small suite of social-utility products sharing one advertising and moderation backbone.

**2. Positioning.** "The trustworthy way to hear what people really think of you — in the app you already use every day."

**3. Core value proposition.** Zero-friction anonymous feedback/messages, delivered inside Telegram, with genuine safety controls and no login required from the sender.

**4. User problem.** People want low-risk honest feedback and social attention; existing options (Sarahah, NGL, Tellonym) are either dead, deceptive, or not Uzbek/Telegram-native.

**5. Why Telegram.** ~25–27M Uzbek users, ~76% reach, no app-store gatekeeping or install friction, native distribution via the founder's meme channel. (FACT/ESTIMATE, per prior research — DataReportar/TGStat-sourced.)

**6. Why SHIVIR (vs. rivals).** Uzbek/Russian-native copy, no deceptive mechanics (a real differentiator given NGL's $5M FTC settlement), and a founder-owned distribution channel that costs nothing to start with.

**7. Product principles.** See Part §3 below (non-negotiables) — genuine messages only, honest copy, safety-by-default, advertiser transparency.

**8. Long-term vision.** V1 = anonymous messaging. V2+ = lightweight social mechanics (reactions, recaps, profile customization) added only once V1's retention and safety are proven — never "because it's technically interesting."

**9. Product moat.** Not technical (the mechanic is copyable in a weekend). The real moat is (a) the founder's existing distribution channel, (b) Uzbek-native trust and copy quality, and (c) accumulated safety/abuse-filtering tuned to local language — all of which compound with time and are slow for a copycat to replicate. ASSUMPTION: a first-mover, channel-driven advantage is defensible for 6–12 months, not indefinitely.

**10. Key assumptions to validate (not facts):** users will create a second link after receiving a message (ASSUMPTION); Instagram Stories remain a viable distribution surface for Shivir links (ASSUMPTION — Instagram has previously restricted link-sticker-style growth tactics for other apps); direct advertisers will pay before Shivir has audited reach numbers (ASSUMPTION, likely false — expect to need 4–8 weeks of data first).

---

## PART B — USER EXPERIENCE STRATEGY

**11. Primary personas:** Recipient (16–28, wants attention/validation), Sender (peer, wants to say the unsayable), Frequent sharer/micro-creator (drives most volume), Casual adult user (low frequency, event-driven), Meme-channel visitor (low intent, top of funnel), Advertiser (local SMB wanting cheap youth reach).

**12. User psychology.** Curiosity, low-social-risk honesty, reciprocity, and social validation are the legitimate engines. Anticipation and humor support return visits. Explicitly excluded as engines: manufactured uncertainty via fake signals (see non-negotiables).

**13–23. Journey stages (Discovery → Onboarding → Link creation → Sharing → Sender journey → Recipient journey → Inbox → Consumption → Re-share → Re-engagement → Retention):** each stage's goal, friction, and risk were mapped in detail in the prior research (Part 6/11 of the Sirli Xabar audit and Part 6 of the Shivir strategy answer) and carry over unchanged. The one addition here: **each stage must pass the "5-second test" (§11 below) independently** — if a user can misunderstand what to do next at any single stage, that stage is broken regardless of how good the surrounding stages are.

---

## PART C — UI/UX MASTER SPECIFICATION

### Design Philosophy
Premium = **clarity + hierarchy + speed + consistency + emotional design + purposeful micro-interactions + trust.** Not gradients or extra animation. Every animation must communicate state change (sending, arriving, success) — never decorate.

### Complete Screen Inventory & Specifications

Each screen below follows: Objective · Entry · Exit · Hierarchy · Key components · States · Microcopy (UZ) · Analytics event · Acceptance criteria.

#### BOT SCREENS

**1. Start**
- Objective: convey what Shivir is and what to do next, in one glance.
- Entry: deep link (`t.me/shivirbot?start=<token>`) or organic `/start`.
- Exit: Language screen (first-time) or Welcome (returning).
- Hierarchy: 1) one-line value statement, 2) single primary CTA, nothing else competing for attention.
- Components: bot avatar/logo, headline, primary button "Boshlash".
- States: first-time vs. returning user (skip language/welcome for returning users).
- Microcopy: *"Salom! Shivir — sizga do'stlaringizdan anonim xabarlar keladigan joy 👀"*
- Event: `bot_started` {source, is_returning}.
- Acceptance: a first-time user reaches Link Creation in ≤2 taps.

**2. Language**
- Objective: select Uzbek/Russian once.
- Entry: Start (first-time only). Exit: Welcome.
- Components: two large tap targets (O'zbek / Русский), auto-detected default highlighted.
- Event: `onboarding_language_selected` {lang}.
- Acceptance: selection persists for all future sessions without re-asking.

**3. Welcome**
- Objective: the single value explanation screen — pass the "why should I care" test.
- Components: one illustrative visual (not a screenshot wall), one sentence of value, primary CTA "Havola yaratish".
- Microcopy: *"Shaxsiy havolangizni yarating, uni ulashing — do'stlaringiz sizga anonim xabar yubora oladi."*
- Event: `onboarding_completed`.
- Acceptance: no scrolling required; visible without interaction on a standard phone screen.

**4. Create Link**
- Objective: generate the personal link with zero form-filling.
- Entry: Welcome/menu. Exit: Link Ready.
- Behavior: link is generated automatically on tap — no username/bio/setup required for V1.
- Loading state: ≤1s target; if longer, show a purposeful micro-animation (not a bare spinner) with label "Havolangiz tayyorlanmoqda...".
- Error state: retry button, plain-language reason ("Server band, qayta urinib ko'ring").
- Event: `link_created` {link_id}.
- Acceptance: link generated and copyable within 2 seconds server time (p95).

**5. Link Ready**
- Objective: hand the user their link plus obvious next action (share).
- Components: link display (tap-to-copy), primary CTA "Ulashish", secondary "Nusxalash".
- Microcopy: *"Tayyor! Endi bu havolani Instagram yoki Telegram'da ulashing."*
- Event: `link_ready_viewed`.
- Acceptance: link is copied to clipboard with visible confirmation on tap.

**6. Share**
- Objective: reduce sharing friction to one tap, native to platform (native share sheet on mobile).
- Components: native OS/Telegram share sheet trigger; fallback manual-copy row if share sheet unavailable (e.g., desktop Telegram).
- Event: `link_shared` {channel: instagram/telegram/other/copy}.
- Acceptance: works inside Telegram's in-app browser and Instagram's in-app browser without a broken redirect.

**7. Inbox Entry / 8. Inbox**
- Objective: surface new messages clearly; make "nothing new" feel calm, not dead.
- Components: card list (newest first), unread indicator, per-card preview (first ~60 chars), single native sponsored card inserted at most once per N cards (see §29–30).
- Empty state: friendly illustration + "Hozircha xabar yo'q. Havolangizni ulashing!" + share CTA (converts empty state into a growth surface).
- Event: `inbox_opened` {unread_count}.
- Acceptance: unread state clears only on actual open, never on inbox view alone.

**9. Message Detail**
- Objective: deliver the message with full context and clear actions.
- Components: message text, timestamp, action row (Delete / Report / Block / Share as card / Create my own link).
- Reveal behavior: message shown immediately and in full — **no blur, no tease, no paywall** (this would edge toward the deceptive "reveal" mechanic the FTC penalized NGL for).
- Event: `message_opened` {message_id}.
- Acceptance: all four actions reachable within one screen, no submenu required.

**10. Delete Confirmation / 11. Block Confirmation**
- Objective: prevent accidental destructive actions without adding friction to legitimate ones.
- Pattern: single confirm sheet, clear consequence statement ("Bu xabar butunlay o'chiriladi"), cancel always the visually lighter option (never dark-pattern the cancel button).
- Events: `message_deleted`, `sender_blocked`.

**12. Report Flow**
- Objective: make reporting fast (≤2 taps) since report friction correlates with under-reporting of real harm.
- Components: reason chips (Harassment / Threat / Sexual content / Spam / Other), optional free-text, confirmation.
- Event: `report_created` {reason}.
- Acceptance: report is submitted and sender auto-flagged for abuse-score increment without recipient needing to also tap Block separately (reporting should imply protective action).

**13. Empty Inbox** — see #8.

**14. Settings / 15. Privacy / 16. Safety / 17. Help**
- Objective: build trust through transparency, not just compliance.
- Components: plain-language privacy summary (not just a legal-policy link), safety tips, contact/support path, language switch, link regeneration/disable toggle.
- Microcopy (privacy): *"Biz yuboruvchining shaxsini saqlamaymiz va hech qachon oshkor qilmaymiz."*

**18. Link Regeneration/Disabled State**
- Objective: give the user control if their link is being abused (mass-reported) or they want a fresh one.
- Behavior: old link immediately invalidated; new token issued; old link's pending messages preserved in inbox.
- Event: `link_regenerated` {reason: user_initiated/abuse_auto_disable}.

#### SENDER WEB SCREENS (no login, external page)

**19. Sender Landing**
- Objective: convert a curious visitor into a sender within seconds — this is the highest-drop-off screen in the whole funnel.
- Components: recipient's display context (first name only, no other identity signal), one-line reassurance of anonymity, message compose field visible immediately (no separate "start" tap).
- Microcopy: *"Bu odamga anonim xabar yuboring. Ular kim yozganini bilishmaydi."*
- Event: `sender_page_viewed` {link_id}.
- Acceptance: compose field is focusable within 1 tap of page load; page loads in <2s on 3G-equivalent (important for Uzbekistan mobile networks).

**20. Message Compose / 21. Prompt Suggestions / 22. Character Counter**
- Objective: solve blank-page anxiety.
- Components: 3–4 rotating neutral prompt chips ("Sen haqingda..."), live character counter, send button disabled until ≥1 character.
- Event: `message_started`.

**23. Sending**
- Purposeful micro-animation (e.g., a subtle "sending" pulse), not a generic spinner — ties to §9 (motion has to communicate state).

**24. Success**
- Microcopy: *"Xabaringiz yuborildi ✅ Anonimligingiz saqlanadi."*
- Secondary CTA (soft, not forced): "O'zingizning Shivir havolangizni yarating" — this is the sender→user conversion moment.
- Event: `message_sent` {link_id, char_count}.

**25. Rate Limited**
- Microcopy: plain-language, no technical jargon: *"Juda tez-tez xabar yubordingiz. Bir necha daqiqadan so'ng qayta urinib ko'ring."*
- Event: `send_rate_limited`.

**26. Link Invalid / 27. Recipient Unavailable**
- Microcopy: *"Bu havola faol emas."* — never leak *why* (blocked vs. deleted vs. expired) to avoid identity-inference attacks against the recipient.

**28. Abuse Warning**
- Triggered pre-send if the filter flags likely harassment/threats/sexual content.
- Pattern: soft interstitial — "Bu xabar qoidalarga zid bo'lishi mumkin. Davom etasizmi?" with an edit option — not a silent block, to reduce both false positives and give the sender a chance to reconsider (a small deterrent effect is itself a safety feature).
- Event: `abuse_warning_shown` {trigger_category}.

**29. Error** — standard error pattern (see §55).

#### SHARING SCREENS

**30. Share-Card Generation / 31. Card Preview / 32. Share Options / 33. Copy Link / 34. Fallback Share**
- See §15 (Share Card Master Design) below for full detail.
- Event: `share_card_generated`, `share_card_downloaded`, `share_to_instagram`, `share_to_telegram`.

---

## DESIGN SYSTEM (design recommendations, not fixed facts — to be validated with real users)

**Brand personality:** modern, intriguing, premium, friendly, trustworthy, youthful but not childish.

**Color palette (recommendation):**
- Primary: deep indigo/violet (#5B4FE8) — trust + intrigue, avoids the "hot pink NGL" and "casino neon" aesthetics competitors lean on.
- Secondary/accent: warm teal (#2DD4BF) for success/positive states.
- Neutrals: near-black text (#151521), mid-gray (#8A8A99), light surface (#F7F7FB), pure white cards.
- Semantic: error/danger (#EF4444), warning (#F59E0B), success (#22C55E).
- Dark mode: invert neutrals (#0E0E14 background, #1B1B26 surface) — Telegram's own dark-mode users are a meaningful share, so dark mode is not optional polish.

**Typography:** a geometric-humanist sans with full Cyrillic + Latin coverage (e.g., Inter, Manrope, or Golos Text) — verify actual glyph coverage before final selection. Weight scale: Regular (body), Medium (labels/buttons), SemiBold (headings). Base size 16px mobile, 1.4–1.5 line-height for Uzbek/Russian text (both languages run longer than English — design for ~30% more character length than an English mock).

**Spacing:** 8pt grid (4/8/12/16/24/32/48).

**Radius:** cards 16px, buttons 12px, inputs 10px — soft but not "bubbly."

**Icons:** single-weight line icons, consistent stroke width, no mixed icon families.

**Motion principles:** every animation maps to a real state change (sent, arrived, error, success); duration 150–250ms for micro-interactions, easing out for entrances, easing in for exits; respect `prefers-reduced-motion`.

---

## MOBILE-FIRST & CROSS-SURFACE CONSTRAINTS

Shivir must work correctly inside: Telegram in-app browser (iOS/Android), Instagram in-app browser, mobile Safari, mobile Chrome, and Telegram's own iOS/Android clients. Known risk areas (RECOMMENDATION to test explicitly, not ASSUMPTION of correctness): Instagram's in-app browser has historically restricted certain JS APIs (clipboard, some redirects) — the sender page must degrade gracefully (manual copy fallback) rather than fail silently; Telegram's in-app browser handles deep-link handoff differently between iOS and Android — test the `t.me` → external web → back-to-bot round trip on both before launch.

---

## MICRO-INTERACTIONS

Premium feeling comes from: (1) instant visual acknowledgment of every tap (no dead taps), (2) state transitions that never "jump" without a bridging animation, (3) message-arrival having a distinct, calm (not alarming) motion, (4) success states that feel rewarding but brief (under 1s), (5) consistent, boring-on-purpose navigation transitions (novelty in animation reads as amateur, not premium). Avoid: bouncing icons, confetti, or anything that reads as a mobile-game reward loop — that aesthetic undermines the "trustworthy" brand pillar.

---

## UX WRITING SYSTEM (Uzbek primary, Russian fallback)

| Context | Uzbek | Russian (fallback) |
|---|---|---|
| Start | Salom! Shivir — sizga do'stlaringizdan anonim xabarlar keladigan joy 👀 | Привет! Shivir — место, где друзья могут отправить тебе анонимное сообщение 👀 |
| Create link | Havolangiz tayyor! Uni ulashing. | Ваша ссылка готова! Поделитесь ею. |
| Share | Havolangizni Instagram yoki Telegram'da ulashing | Поделитесь ссылкой в Instagram или Telegram |
| Sender landing | Bu odamga anonim xabar yuboring | Отправьте анонимное сообщение этому человеку |
| Send success | Xabaringiz yuborildi ✅ Anonimligingiz saqlanadi | Сообщение отправлено ✅ Ваша анонимность сохранена |
| Notification | Sizga yangi Shivir xabari keldi 👀 | Вам пришло новое сообщение Shivir 👀 |
| Empty inbox | Hozircha xabar yo'q. Havolangizni ulashing! | Пока нет сообщений. Поделитесь ссылкой! |
| Report | Bu xabar shikoyat qilindi | Жалоба на сообщение отправлена |
| Block | Bu yuboruvchi bloklandi | Отправитель заблокирован |
| Privacy | Biz yuboruvchining shaxsini saqlamaymiz va hech qachon oshkor qilmaymiz | Мы не сохраняем и никогда не раскрываем личность отправителя |
| Safety | Haqorat, tahdid yoki nomaqbul xabarlar taqiqlanadi | Оскорбления, угрозы и неприемлемый контент запрещены |
| Ads | Bu — reklama | Это реклама |
| Generic error | Nimadir xato ketdi. Qayta urinib ko'ring. | Что-то пошло не так. Попробуйте снова. |

All copy: short, natural, human, non-deceptive — never implies identity can be revealed, never manufactures urgency.

---

## FIRST-TIME EXPERIENCE — THE 5-SECOND TEST

Every first-time screen must survive: *What is this? What do I do? Why? What's next?* If any MVP screen fails this (notably: Welcome, Sender Landing, Message Detail), it gets redesigned before launch — not shipped with a "we'll improve it later" excuse, since first impressions in this category are largely non-recoverable (a confused first-time sender simply leaves).

## "ZERO CONFUSION" RULE
Applied per-screen above via the Acceptance Criteria lines — each screen's acceptance criterion is, in effect, its zero-confusion test.

---

## CORE USER FLOW (production-level, with latency/error/analytics per transition)

| Transition | Latency target | UI state | Error state | Event |
|---|---|---|---|---|
| Discovery → Open | n/a (external) | — | broken deep link → fallback to bot search | `link_clicked` |
| Open → Understand | <1s render | Welcome screen | — | `onboarding_completed` |
| Understand → Create link | <2s (p95) | loading micro-animation | retry button | `link_created` |
| Create → Share | instant | native share sheet | fallback copy row | `link_shared` |
| Someone taps → Sender page | <2s load | skeleton state | link-invalid screen | `sender_page_viewed` |
| Write → Send | instant local, <1s server ack | sending animation | rate-limit / abuse-warning interstitial | `message_sent` |
| Send → Recipient notification | <5s (batched) | Telegram native notification | delivery-failed → retry queue | `message_received` |
| Notification → Inbox | instant | badge/unread indicator | — | `inbox_opened` |
| Inbox → Read | instant | full reveal, no tease | — | `message_opened` |
| Read → React/Share | instant | action sheet | — | `share_card_generated` |
| Share → New user | external | — | — | `new_link_created` (if they create one) |

---

## VIRAL LOOP — WHERE IT BREAKS AND HOW TO STRENGTHEN EACH TRANSITION

Reusing the K-factor model from the prior research (K = share rate × avg viewers/share × CTR × sender-conversion × recipient-to-new-link conversion; Base-case K≈0.39, sub-1 in steady state — ESTIMATE): the highest-leverage break points are **(a) share rate** (fixed primarily by share-card quality, §15) and **(b) recipient-to-new-link conversion** (fixed primarily by the Success-screen soft CTA, screen #24, and the empty-inbox CTA, screen #8). Instrument both explicitly as the two numbers the founder dashboard should surface first (see §28).

---

## SHARE CARD MASTER DESIGN

Format: 1080×1920 (Instagram Story native). Three variants to test, one default:

- **Variant A (Quote card):** large centered message text on a clean gradient background (brand indigo→teal), small Shivir wordmark bottom-center, "Menga anonim xabar yubor 👀" + short link/QR at bottom. *Recommended default* — simplest, fastest to generate, lowest embarrassment risk since it reads as a "look what I got" artifact rather than a personal confession.
- **Variant B (Chat-bubble card):** message styled as an incoming chat bubble inside a phone-frame mockup — higher production value, higher render cost, better for demonstrating the product itself (good for the founder's own promotional content, not necessarily the default user-generated card).
- **Variant C (Minimal/text-only):** just the message + link, no heavy branding — lowest friction to share but weakest brand propagation; use only as a fallback for very long messages that don't fit A/B cleanly.

Privacy: never render any sender-identifying information on the card (no message metadata, no timestamp-based inference risk); recipient explicitly chooses which message to turn into a card (never auto-generated/auto-posted).

---

## RETENTION

D1/D7/D30 category benchmarks are NOT directly portable to Shivir (ESTIMATE only, per prior research: D1 ~20–30%, D7 ~8–12%, D30 ~3–6%). Ranked by impact × complexity × risk:
1. **Share-card loop** — high impact, medium complexity, low risk. Build first.
2. **Persistent inbox + genuine notifications** — high impact, low complexity, low risk. Build first.
3. **Weekly recap** ("Bu hafta N ta xabar oldingiz") — medium impact, low complexity, low risk. V1.1.
4. **Reactions/lightweight social mechanics** — medium impact, medium complexity, medium moderation risk. V2, only after safety systems are proven.
5. **Reply-to-sender** — potentially high engagement but high harassment/safety risk (Tellonym/ASKfm failure pattern) — **excluded from V1**, revisit only with a dedicated safety design (thread caps, disable-replies toggle).

---

## FEATURE ROADMAP (V1 → V4)

- **V1 (launch):** link creation, sender web page, inbox, delete/report/block, rate limiting, Uzbek/Russian abuse filter, human moderation queue, share-card (Variant A), genuine notifications, privacy policy.
- **V1.1 (fast-follow):** weekly recap, prompt suggestions rotation, Variant B/C share cards, link regeneration UX polish.
- **V2 (post product-market signal):** native sponsored inbox card (first monetization surface), basic Founder Dashboard, AI classification layer (V2 of moderation roadmap), reactions.
- **V3:** Shivir Ads intake bot, advertiser dashboard, Mini App (for ad-network SDK compatibility), risk-scoring moderation (V3).
- **V4:** cross-product shared ad infrastructure (if a second bot is built), adaptive moderation (V4), AI founder assistant.

V1 stays intentionally small — every item above V1.1 is explicitly deferred pending the Decision Gates (§66).

---

## SAFETY (Trust & Safety architecture — UX-integrated)

Layered exactly as in the prior research: per-fingerprint/per-link/global rate limiting; Uzbek+Russian keyword/heuristic abuse filter (V1) → AI classification (V2) → risk scoring (V3) → adaptive moderation (V4); report/block/delete on every message; severity tiers L1 (nuisance → auto rate-limit) / L2 (harassment → block + filter escalation) / L3 (threats/sexual/illegal → auto-remove + evidence preservation + human review + escalation where legally required). Structural advantage retained: **no public feed**, which caps harassment blast radius versus Yik Yak/Whisper/ASKfm-style products.

**Moderation UX (for the human moderator, not the end user):** a queue sorted by severity then recency; each item shows message context, sender abuse-score history, and one-click actions (dismiss / warn / disable link / escalate); every action writes an audit-log entry (moderator, timestamp, reason) for accountability and future dispute review.

**AI Moderation Roadmap:** V1 rules-only (fast, cheap, higher false-negative rate — acceptable at launch scale); V2 AI classification (catches paraphrased abuse rules miss, adds latency/cost, needs human-reviewed false-positive sampling); V3 risk scoring (per-sender cumulative score feeding automatic restrictions); V4 adaptive moderation (thresholds tuned from real outcome data). At every stage, a human remains the final authority on anything above L1 severity — AI never auto-bans on ambiguous content.

---

## PRIVACY

Store: recipient Telegram user ID, message content (until deleted), link tokens, a short-retention hashed abuse fingerprint, timestamps, aggregated analytics. Never store: sender Telegram identity, precise location, persistent cross-session cookies, raw long-term IP logs. Anonymity terminology must be literally true — never claim identity "can never be known even by us" if any fingerprinting for abuse prevention exists; instead say plainly that sender identity is not shown to the recipient and is used only in hashed form to prevent abuse.

---

## TELEGRAM PRODUCT ARCHITECTURE

Recommendation unchanged from prior research: **Bot (recipient) + external web page (sender), no login required** — because Instagram-origin senders cannot be forced through Telegram authentication without killing conversion. Mini App added in V3 once ad-network SDK integration requires it.

---

## TECHNICAL MASTER ARCHITECTURE (small-team, no over-engineering)

```
User → Instagram / Telegram → Sender Web (FastAPI) → API →
  → Abuse Filter/Moderation Queue → PostgreSQL
  → Notification Worker (Redis queue) → Telegram Bot API → Recipient

Advertiser → Shivir Ads (V3) → Campaign Engine → Ad Inventory Allocator
  → Analytics Store → Founder Dashboard
```

Stack: Python + aiogram (bot) + FastAPI (sender web/API) + PostgreSQL + Redis (rate-limit + notification queue) + a lightweight card-image renderer (Pillow or HTML-to-image) + single Linux VPS behind Nginx/HTTPS for V1. No microservices, no Kubernetes until a measured trigger (queue lag, CPU saturation) justifies it — see the prior research's Part 43/19 scaling triggers, unchanged at 10K/50K/100K tiers.

---

## DATABASE (final schema, condensed)

`users`(tg_user_id PK, lang, created_at, blocked_bot, settings) · `public_links`(id, owner_user_id FK, token unique, created_at, active, report_count) · `messages`(id, link_id FK, recipient_user_id FK idx, body, created_at idx, opened_at, deleted_at, abuse_score, sender_fingerprint_hash) · `blocks`(id, user_id, sender_fingerprint_hash) · `reports`(id, message_id, reason, status, created_at) · `moderation_actions`(id, target, action, severity, moderator, created_at) · `events`(id, user_id nullable, name, props jsonb, created_at) · `advertisers`(id, business_name, contact, status) [V3] · `campaigns`(id, advertiser_id FK, budget, dates, status, creative) [V3] · `ad_impressions`(id, user_id, campaign_id, placement, created_at, clicked) [V2/V3]. Sensitivity: message body + fingerprint = high (short retention on fingerprint); tg_user_id = medium.

---

## SECURITY CHECKLIST
`initData` HMAC-SHA-256 validation server-side (V3 Mini App); parameterized queries everywhere; CSRF token on the sender form; XSS-safe output encoding on the web page and card renderer; webhook secret token over HTTPS; Redis token-bucket rate limiting (fingerprint/link/global); secrets via env/secret manager, never in code; PII-free structured logging; encrypted, tested backups; admin panel behind auth + IP allowlist + 2FA; dependency scanning in CI.

---

## ANALYTICS — EVENT TAXONOMY

`bot_started`, `onboarding_language_selected`, `onboarding_completed`, `link_created`, `link_ready_viewed`, `link_shared`, `link_clicked`, `sender_page_viewed`, `message_started`, `abuse_warning_shown`, `send_rate_limited`, `message_sent`, `message_received`, `inbox_opened`, `message_opened`, `message_deleted`, `sender_blocked`, `report_created`, `link_regenerated`, `share_card_generated`, `share_card_downloaded`, `share_to_instagram`, `share_to_telegram`, `new_link_created`, plus (V2+) `ad_impression`, `ad_clicked`. Each carries user_id (nullable for sender-side anonymous events), relevant foreign IDs, timestamp, and event-specific properties as noted inline above.

---

## NORTH STAR METRICS — TWO, NOT MERGED

- **USER NORTH STAR:** *Weekly active recipients who received ≥1 genuine message* — measures real value delivered to the person the product exists for.
- **BUSINESS NORTH STAR:** *Revenue per 1,000 MAU* — measures whether the business side is actually working at whatever scale exists, without forcing user value and monetization into one artificial composite number.

Supporting metrics: new-link creation rate, share rate, D7 retention, report rate (safety health), advertiser renewal rate (once V3 exists).

---

## FOUNDER DASHBOARD (V2+ specification, not MVP)

Sections: **Product** (users, DAU, MAU, messages, active links, retention) · **Growth** (Instagram traffic, shares, clicks, K-factor) · **Safety** (reports, blocks, moderation queue depth, open incidents) · **Ads** (advertisers, active campaigns, revenue, impressions, CTR, fill) · **Finance** (revenue, costs, net) · **Infrastructure** (CPU, RAM, DB, queue lag, error rate) · **Alerts** (anomaly flags across all of the above). UI hierarchy: a single "today" summary view surfacing the 3–5 metrics that moved most, with drill-down per section — designed to answer "what should I look at today?" rather than presenting every metric with equal visual weight.

---

## ADVERTISING PHILOSOPHY & INVENTORY

Core principle: advertiser count can grow, but per-user ad density must not be perceptible as an increase. Mechanism: frequency capping (test Low/Medium/High against D1/D7/session-length/bot-block-rate guardrails, per prior research §37–38) and campaign rotation/pacing across a fixed daily inbox-impression budget. Natural inventory surfaces, ranked by UX impact (lowest first): native inbox sponsored card (V2) → sponsored prompt in compose (V2/V3) → Mini App ad-network surfaces (V3) → channel/bot bundle sponsorships (V2, sold manually). Do not add banner-style placements — they read as "cheap bot," directly undermining the premium positioning.

**Shivir Ads (V3 platform):** Advertiser → campaign form → AI pre-check (prohibited categories, scam/landing-page checks, language compliance) → human review and pricing (AI never finalizes price or placement) → payment → creative approval → launch → delivery/rotation → analytics → report → renewal. Advertiser dashboard (V3): campaign status, budget, audience, dates, placement, reach, impressions, clicks, CTR, historical campaigns, one-click rebook.

**50-advertiser model:** critically, 50 advertisers ≠ 50× ad exposure per user — they share a fixed daily inbox-impression pool via rotation/pacing, so advertiser count and revenue-per-advertiser are jointly constrained by DAU, not independent variables. This must be modeled explicitly before selling more than a handful of concurrent campaigns.

**Revenue scenarios ($500/$1K/$2K/$3K/$5K/$7K):** using the prior hybrid model (direct campaigns + programmatic backfill at Uzbek eCPM ~$1–3, ESTIMATE), each roughly doubling of target requires roughly proportional MAU growth up to the point direct-inventory saturates per the 50-advertiser constraint above — beyond that point, further revenue growth requires either DAU growth or a second monetizable surface (e.g., Mini App ad-network inventory), not just adding more advertisers to the same inbox slot. **No fake certainty**: treat all of $500–$7K as ESTIMATE ranges requiring live validation, not projections to commit to publicly.

---

## GROWTH STRATEGY

Primary channels: Instagram (Reels/Stories/UGC), the founder's meme Telegram channel, and organic user-sharing. Meme-channel promotion capped at ~1–2×/week to avoid audience fatigue and channel damage (per prior research). Instagram creative system: at least 20 concepts spanning curiosity, humor, demonstration/reaction (the NGL-proven format), UGC reposts, social proof, and direct CTA — all excluding deceptive content per the non-negotiables. First-30-days cadence: Day 1–3 friends/founder seeding, Day 4–7 first meme-channel post, Week 2 UGC reposting begins, Week 3–4 cadence increases only if fatigue signals (unfollow rate, engagement decline) stay flat.

---

## EXPERIMENTATION SYSTEM (representative set; expand to 20 pre-launch)

Each test: Hypothesis → Variant → Primary metric → Guardrail → Decision rule. Priority tests for V1: (1) share-card Variant A vs. B on share rate, guardrail report rate; (2) sender-page prompt-suggestions on/off on message-start rate; (3) notification batching interval on D7 vs. block-bot rate; (4) empty-inbox CTA copy on new-link creation rate.

---

## PRODUCT & BUSINESS RED TEAM (condensed; full list carries over from prior research Parts 35–36/55–58)

Highest-probability, highest-impact scenarios: nobody shares (mitigation: share-card quality is the single highest-leverage fix); a bullying incident goes public (mitigation: severity-L3 pipeline + PR response plan, treated as existential-risk priority #1); ad revenue 10× lower than modeled (mitigation: direct-led hybrid model, not programmatic-dependent); founder bandwidth runs out (mitigation: V1 scope stays deliberately small; automation deferred to V2+, not built prematurely).

---

## FOUNDER OPERATIONS & AUTOMATION ROADMAP

Manual at V1: moderation review, advertiser negotiation (once V3 exists), content/promotion decisions. Automated from V1: rate limiting, notification delivery, basic analytics aggregation. Automation roadmap: V1 basic automation (queues, notifications) → V2 moderation automation (AI classification assist, not final decisions) → V3 advertiser automation (AI pre-screening) → V4 AI operational assistant (dashboard Q&A layer). Principle unchanged: automate repetitive work, keep humans in control of safety/legal/commercial decisions.

---

## QUALITY BAR (apply to every feature decision)

Does it improve user experience? Does it help acquisition/sharing? Does it increase return probability? Does it introduce safety risk? Does it improve sustainable monetization? Does it create unnecessary engineering burden? Does it preserve user/advertiser trust? Any feature failing "user value," "safety," or "trust" is rejected regardless of how well it scores elsewhere.

---

## FINAL MVP DEFINITION

**BUILD NOW:** bot (start/language/link creation/inbox/message detail/delete/block/report), no-login sender web page (landing/compose/send/success/rate-limit/abuse-warning/error states), Uzbek+Russian rate limiting and abuse filter, human moderation queue, share-card Variant A, genuine batched notifications, privacy policy, core analytics events.

**BUILD AFTER VALIDATION:** weekly recap, Variant B/C cards, native sponsored inbox card, Founder Dashboard, AI classification (moderation V2), Mini App, Shivir Ads platform, reactions.

**DO NOT BUILD:** fake messages/notifications/typing/viewers/crushes, paid identity-reveal mechanics, subscription traps, public feed, reply-to-sender (until a dedicated safety redesign exists), banner ads.

---

## FINAL MASTER USER FLOW

Instagram/meme-channel discovery → bot /start → language (first-time) → welcome/value → link creation → share (native sheet) → viewer taps link → sender web landing → compose (with prompts) → send → recipient notification (batched) → inbox → message detail (full reveal) → action (delete/report/block/share-card/create-own-link) → [if share-card] Instagram Story/Telegram share → new viewer → loop repeats → [V3] advertiser ecosystem layers in as a parallel, non-intrusive revenue track once product usage justifies it.

---

## FINAL UI SPECIFICATION TABLE (MVP screens)

| Screen | Goal | Primary CTA | Secondary CTA | Key components | States | Main event |
|---|---|---|---|---|---|---|
| Start | Convey value fast | Boshlash | — | Logo, headline, button | first-time/returning | `bot_started` |
| Language | Set language | O'zbek / Русский | — | Two tap targets | — | `onboarding_language_selected` |
| Welcome | Explain value | Havola yaratish | — | Visual, one-line value | — | `onboarding_completed` |
| Create Link | Generate link | (auto) | — | Loading animation | loading/error | `link_created` |
| Link Ready | Hand off link | Ulashish | Nusxalash | Link display | — | `link_ready_viewed` |
| Share | Reduce share friction | Native share sheet | Copy link | Share sheet trigger | fallback | `link_shared` |
| Inbox | Show messages | Open message | Create new link (empty state) | Card list | empty/populated | `inbox_opened` |
| Message Detail | Deliver message | Delete/Report/Block/Share | Create own link | Full text, action row | — | `message_opened` |
| Sender Landing | Convert visitor | Compose field | — | Reassurance copy, compose | invalid-link | `sender_page_viewed` |
| Compose | Enable sending | Yuborish | Prompt chip | Text field, counter | rate-limited/abuse-warning | `message_started` |
| Send Success | Confirm + convert | Create own link | — | Confirmation, soft CTA | — | `message_sent` |
| Share Card Preview | Convert message to growth asset | Share to Instagram | Download / Copy link | Card image, variant | generation error | `share_card_generated` |

---

## FINAL DESIGN TOKENS (recommendations, not fixed facts)

Colors: primary `#5B4FE8`, accent `#2DD4BF`, text `#151521`, muted `#8A8A99`, surface `#F7F7FB`, error `#EF4444`, success `#22C55E`. Typography: base 16px, headings SemiBold, body Regular, line-height 1.45. Spacing: 8pt scale. Radius: cards 16px / buttons 12px / inputs 10px. Motion: 150–250ms, ease-out on enter, ease-in on exit. Icons: single-weight line style. *(All values are starting recommendations to validate visually with real screens, not final specs.)*

---

## ACCESSIBILITY

Minimum 4.5:1 text contrast, ≥44px tap targets, scalable text (no fixed-px text that breaks with OS font-size settings), full functionality without animation (`prefers-reduced-motion` respected), no reliance on color alone for state (e.g., pair red with an icon/label for errors). No RTL requirement (Uzbek/Russian are both LTR).

## LOCALIZATION
Uzbek-first, Russian second, per the copy table above. Design text containers assuming ~30% more length than an English equivalent to avoid truncation/wrapping bugs.

## PERFORMANCE UX
Instant: <100ms (taps, toggles) — no loading state needed. Fast: 100ms–2s — use the purposeful micro-animation. Slow: >2s — must show a labeled progress state, never a bare spinner with no context.

## ERROR EXPERIENCE
Every error: plain-language reason, no jargon (no "500 Internal Server Error"), a clear next action (retry/go back/contact support), and — where relevant — a fallback path (e.g., manual copy-link when native share fails).

---

## PREMIUM FEEL AUDIT (self-check before launch)
Run the 10-question audit from the brief (generic? cheap-bot look? clutter? confusing screens? purposeful animation? natural copy? trustworthy? beautiful sharing? effortless onboarding? fast?) against actual built screens, not mockups — any "no" triggers a required fix before launch, not a backlog ticket.

## DESIGN COMPETITIVE AUDIT
Versus NGL/Sendit/Tellonym: those products lean on saturated neon/gradient aesthetics and dopamine-style micro-rewards. Shivir's differentiation is calmer, higher-contrast, trust-signaling design plus Uzbek-native copy — not a "cooler" version of the same visual language.

## FINAL PRODUCT DIFFERENTIATORS (top 5, reasoning-backed)
1. Founder-owned distribution channel (structural, not copyable overnight). 2. Uzbek/Russian-native copy and safety filtering (rivals are English-first). 3. No deceptive mechanics — a real trust differentiator post-NGL scandal. 4. No-login sender flow optimized for Instagram-origin traffic. 5. Calm, trust-forward visual design versus the category's neon-dopamine norm.

---

## FINAL ARCHITECTURE DIAGRAM
See Technical Master Architecture above (single consolidated diagram covering both the user-facing pipeline and the V3 advertiser pipeline).

## FINAL DEVELOPMENT PLAN (Stage 0–9)
Stage 0 Foundation (repo/CI/schema) → Stage 1 Core bot (start/link/inbox) → Stage 2 Sender web → Stage 3 Recipient experience (notifications/read) → Stage 4 Safety (filter/report/block/moderation queue) → Stage 5 Share (card generation) → Stage 6 Analytics (event pipeline) → Stage 7 Polish (copy/design/error states) → Stage 8 Testing (QA plan below) → Stage 9 Launch (meme-channel soft launch). Each stage: deliverables, dependencies on the prior stage, acceptance criteria as specified per-screen above, and the risk it primarily retires.

## EXACT BUILD ORDER — FIRST 50 TASKS (dependency + risk + user value ordered)
1–5: repo/CI/env setup, DB schema migration, base bot skeleton, webhook security, logging. 6–12: link creation flow, link-token generation/uniqueness, `/start` + language + welcome screens. 13–20: sender web page skeleton, compose form, send API, rate-limiting middleware. 21–27: abuse filter (Uzbek/Russian lexicon v1), abuse-warning interstitial, message storage, sender-fingerprint hashing. 28–33: recipient notification worker, inbox screen, message-detail screen, delete/report/block actions. 34–38: moderation queue (admin-only), severity tiers, audit logging. 39–43: share-card renderer (Variant A), share-sheet integration, copy-link fallback. 44–47: core analytics event pipeline, privacy policy page, settings screen. 48–50: end-to-end QA pass on Telegram+Instagram in-app browsers, load test, soft-launch readiness review.

## ACCEPTANCE CRITERIA (Given/When/Then, representative)
- **Given** a first-time user taps a Shivir deep link, **when** they complete /start, **then** they reach Link Creation within 2 taps and under 3 seconds total load time.
- **Given** a sender submits a message, **when** the abuse filter flags it, **then** the sender sees the Abuse Warning interstitial with an edit option before the message is stored.
- **Given** a recipient blocks a sender, **when** that sender's fingerprint attempts to send again via any link, **then** the message is silently dropped without notifying the sender.

## QA PLAN
Unit (services/filters), integration (send→deliver pipeline), end-to-end (full user journey on real devices), abuse/red-team (attempt every Part-59-style edge case), security (checklist above), performance (load test to 10K-tier targets), cross-browser (Telegram iOS/Android in-app browser, Instagram in-app browser, mobile Safari/Chrome), notification delivery reliability, share-card rendering correctness.

## LAUNCH READINESS CHECKLIST
Product (MVP scope frozen) · UX (premium-feel audit passed) · Safety (filter + moderation queue live, severity pipeline tested) · Technical (load test passed, backups verified) · Analytics (all MVP events firing correctly) · Content (Instagram account + first creative batch ready) · Growth (meme-channel first post scheduled) · Infrastructure (monitoring/alerts configured).

## POST-LAUNCH LEARNING LOOP
Data → insight → experiment → feature → data, anchored on the two North Star metrics and the Decision Gates below — no feature ships without a hypothesis tied to at least one of them.

---

## DECISION GATES

| Gate | Metric | Threshold (initial, to calibrate with real data) | Meaning | Next action |
|---|---|---|---|---|
| 1 — Activation | % new users who create a link | ≥40% | Product concept lands | If below, fix onboarding/Welcome screen |
| 2 — Sharing | % link-owners who share within 48h | ≥35% | Sharing friction acceptable | If below, redesign Share screen/CTA |
| 3 — Message conversion | % sender-page visitors who send | ≥5% | Sender flow works | If below, redesign Sender Landing |
| 4 — Retention | D7 | ≥8–10% | Recurring value exists | If below, prioritize retention features over growth |
| 5 — Safety | Unresolved severe (L3) incidents | 0 | Safety pipeline functioning | Any incident triggers immediate pipeline review |
| 6 — Advertiser demand | Inbound advertiser interest at ~10K+ MAU | ≥1 qualified lead/week | Market exists | If absent, delay monetization build |
| 7 — Revenue | Revenue per 1,000 MAU | any positive, trending up | Monetization functioning at all | Compare against §35 scenarios |
| 8 — Scale | Infra headroom | <60% sustained CPU / queue lag <30s | Current tier sufficient | Migrate per scaling triggers when breached |

*Thresholds above are RECOMMENDATIONS to calibrate once real data exists — not benchmarks pulled from unrelated products.*

---

## FINAL SCORECARD (0–100, consistent with prior research's method)

Product value 55 · UX/UI quality — TBD until built (design is spec-only so far) · Viral potential 65 · Retention 40 · Safety 45 · Telegram fit 85 · Uzbekistan fit 85 · Monetization 45 · Advertiser appeal 55 · Buildability 80 · Scalability 75 · Operational simplicity 70 · Defensibility 35. **Overall ≈ 60/100, medium confidence** — unchanged from the prior research since this document specifies *how* to build, not new market evidence that would move the score.

---

## SHIVIR MASTER PLAN

**Phase 1 — Build:** Goal: ship V1 MVP. Product: screens/flows above. UX: premium-feel audit passed. Growth: none yet (pre-launch). Metrics: Gate 1–3 instrumented. Risks: scope creep — mitigate via the strict BUILD NOW list. Exit: MVP live, gates instrumented.

**Phase 2 — Launch:** Goal: first real users via meme channel. Product: bug-fix cadence. UX: monitor drop-off per screen. Growth: 1–2 meme-channel posts/week. Metrics: Gate 1–2 data arriving. Risks: channel fatigue, safety incidents. Exit: Gate 1–2 thresholds met or clearly diagnosed.

**Phase 3 — Learn:** Goal: validate retention/safety assumptions. Product: V1.1 fast-follows (recap, prompts). Metrics: D7 trend. Risks: novelty decay outpacing fixes. Exit: Gate 4 assessed honestly (may fail — that's valid information, not a reason to fabricate success).

**Phase 4 — Grow:** Goal: strengthen the viral loop. Product: share-card variant testing. Growth: Instagram creative system scaled. Metrics: K-factor components. Risks: Instagram platform changes. Exit: Gate 2–3 trending favorably.

**Phase 5 — Monetize:** Goal: first revenue. Product: native sponsored inbox card, basic advertiser intake (manual). Metrics: Gate 6–7. Risks: ad load harming retention — guardrail explicitly. Exit: positive revenue-per-1000-MAU trend.

**Phase 6 — Automate:** Goal: reduce founder operational load. Product: Founder Dashboard V2, moderation AI-assist. Risks: automating safety decisions prematurely — keep humans on anything above L1. Exit: dashboard answers "what should I look at today?" reliably.

**Phase 7 — Expand:** Goal: Shivir Ads platform, possible second product sharing infrastructure. Risks: premature platform investment before Shivir itself is proven — gate this phase explicitly on Phase 5 success. Exit: Shivir Ads live with ≥1 paying advertiser cohort retained.

**Phase 8 — Scale:** Goal: infra scale-up per measured triggers only. Risks: over-engineering ahead of need. Exit: infra tier matches actual MAU tier without downtime.

---

## FINAL FOUNDER SUMMARY

**What is Shivir?** A Telegram-native anonymous messaging bot for Uzbekistan, built to feel premium and trustworthy rather than like a generic bot, with a no-login sender web page and a genuinely safe, non-deceptive core loop.

**Why might it work?** Uzbekistan's Telegram penetration is exceptional, the founder already owns a distribution channel, and the category's proven demand (NGL, Sarahah) hasn't been served well in Uzbek/Russian with real safety design.

**Where do we win?** Distribution cost (near-zero via the meme channel), trust differentiation (no deceptive mechanics, unlike every major rival that got punished for them), and calm/premium design versus the category's neon-dopamine norm.

**Where might we lose?** Retention (novelty decay is real and unsolved by any competitor), monetization (Uzbek ad economics are thin — direct deals matter more than programmatic), and safety (one bullying incident can end the brand, per Sarahah's exact history).

**What do we build now?** The BUILD NOW list above — nothing more.

**What do we build later?** Recap, sponsored inbox card, Founder Dashboard, Shivir Ads, Mini App — all gated on real usage data.

**How do we satisfy users?** Genuine messages only, instant full-reveal (no tease/paywall), fast and calm design, real safety controls.

**How do we satisfy advertisers?** Transparency, measurable reporting, and never letting ad density become perceptible — professionalism over volume.

**How do we make revenue?** Direct/native sponsored placements first, programmatic backfill second, gated on proven reach (Gate 6) before selling anything.

**How do we keep it alive long-term?** Keep V1 small and safe, let real Decision-Gate data — not enthusiasm — decide what gets built next, and treat any safety incident as the top operational priority it is.

---

## FINAL EXECUTION RULE — HELD THROUGHOUT THIS DOCUMENT
No invented metrics presented as fact (all are explicitly marked ESTIMATE/RECOMMENDATION); no blind competitor-copying (explicit differentiation reasoning given per decision); monetization never prioritized over user trust (ad-density principle, no banner ads, no forced-reveal ads); no features added because they "sound cool" (every V2+ feature is gated on validation, not included in V1).

---

## FINAL ANSWER: NEXT 72 HOURS

If development starts tomorrow: **Hour 0–24** — finalize DB schema, repo/CI, and the abuse-lexicon v1 draft; build `/start` → language → welcome → link creation. **Hour 24–48** — build the sender web page (landing → compose → send → success) with rate limiting and the abuse-warning interstitial; wire the notification worker. **Hour 48–72** — build inbox → message detail → delete/report/block, the share-card renderer (Variant A only), and core analytics events; do a first end-to-end pass on both Telegram's and Instagram's in-app browsers. **Launch readiness** is declared only once the Launch Readiness Checklist above is fully green — not on a calendar date.

---

# BUILD NOW
Bot core (start/language/welcome/link/inbox/message-detail/delete/report/block) · no-login sender web page with rate limiting + abuse filter + abuse-warning interstitial · human moderation queue · share-card Variant A · genuine batched notifications · privacy policy · core analytics.

# DEFER
Weekly recap, Variant B/C cards, native sponsored inbox card, Founder Dashboard, AI moderation V2+, Mini App, Shivir Ads, reactions, reply-to-sender.

# NEVER BUILD
Fake messages/notifications/typing/viewers/crushes/sender-hints; deceptive or paid identity-reveal; manipulative subscriptions; public harassment feed; banner-style ads; any feature that fails the Quality Bar's "trust" or "safety" test.

# NEXT 72 HOURS
See "Final Answer: Next 72 Hours" above.

# FINAL LAUNCH CRITERIA
All BUILD NOW items shipped and passing their acceptance criteria · Launch Readiness Checklist fully green · Decision Gates 1–3 instrumented (not yet necessarily passed — instrumented, so real data starts flowing from day one) · zero known unresolved L3-severity safety gaps · Uzbek/Russian abuse lexicon v1 live · privacy policy published.
