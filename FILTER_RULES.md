this project name is "load hunter".

1. Overview

The goal of this system is to identify Primary Cargo Owners (Original Shippers) while filtering out Middlemen (Dispatchers/Logists), Bots, and International Spam. The system uses a multi-layered approach combining metadata, text structure, and social proof.
2. Filtering Layers
Layer A: Entity & Social Metadata

    Bot Detection: * Immediate rejection if sender.bot == True.

        Username check for strings matching *bot* or *robot*.

    Shared Group Constraint:

        Logic: Professional logists are members of numerous cargo-sharing groups.

        Filter: If common_chats_count > max_common_groups (Default: 2), the user is flagged as a professional.

        Filter: If common_chats_count == 0, the user is flagged as an external spammer/scrapper.

Layer B: Visual & Structural Analysis

    Media Blacklist: Automatic rejection of any message containing Stickers or GIFs.

    Link Blacklist: Automatic rejection of messages containing URLs (http, https, t.me). Original shippers rarely use external links; they use phone numbers.

    Template Detection:

        Line Break Limit: If text.count('\n') > max_line_breaks (Default: 5), it is flagged as a "Template" message (Dispatcher style).

        Emoji Density: If the message contains >3 emojis, it is flagged as "Professional Marketing" rather than a "Direct Request."

Layer C: Language & Content Validation

    The Uzbek Guard:

        Logic: Focus on local Uzbekistan logistics.

        Filter: Message must contain at least 30% Uzbek-specific characters (ў, қ, ғ, ҳ, Ў, Қ, Ғ, Ҳ) or common stop-words (e.g., yuk bor, mashina kerak, aka).

        Exclusion: Purely English or Russian messages are discarded as international noise.

    Gender-Based Filtering (Optional):

        Regex Pattern: .*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$.

        Logic: Identifies feminine names/endings to prioritize traditional masculine-dominated logistics profiles as per user preference for direct drivers.

3. Data Persistence (filters.json)

All filtering thresholds must be externalized to a JSON file to allow for "AI Auto-Tuning." The structure is:
JSON

{
  "max_common_groups": 2,
  "max_line_breaks": 5,
  "min_uz_char_percentage": 0.3,
  "blacklist_keywords": ["dispatcher", "logist", "fura", "ref"],
  "bot_service_keywords": ["guruhda yozish uchun", "qo'shishingiz kerak"],
  "fem_endings_regex": ".*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$"
}

4. Output & Action Workflow

    Lead Capture: If a message passes all filters, it is displayed in the UI.

    Phone Extraction: Automatically extract numbers matching \+?\d{9,12}.

    The "One-Click" Call: Numbers must be wrapped in a tel:{number} URI to trigger the synchronized call via Z Flip 3.

    Success Logging: Every time a user clicks "Open in Telegram," the message body is logged to successful_leads.txt for future AI analysis of "Good Leads."
