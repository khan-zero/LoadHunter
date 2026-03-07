import re
from telethon.tl.types import MessageMediaDocument, DocumentAttributeSticker, MessageMediaWebPage, MessageMediaPhoto

class FilterEngine:
    def __init__(self, config):
        self.config = config
        self._compile_regex()
        # Uzbek common stop-words from FILTER_RULES.md
        self.uz_stop_words = ["yuk bor", "mashina kerak", "aka", "fura", "ref", "yuk", "bor", "kerak", "nechi", "tonna"]
        self.link_regex = re.compile(r'(https?://|t\.me/)', re.IGNORECASE)
        self.emoji_regex = re.compile(r'[\U0001F000-\U0001FAFF]|[\u2700-\u27BF]|[\u2600-\u26FF]')
        self.uz_specials_regex = re.compile(r'[ўқғҳЎҚҒҲ]')

    def _compile_regex(self):
        """Compiles regex from config, falling back to a safe default if invalid."""
        regex_str = self.config.get('fem_endings_regex', r'.*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$')
        try:
            self.fem_endings = re.compile(regex_str, re.IGNORECASE)
        except re.error:
            self.fem_endings = re.compile(r'.*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$', re.IGNORECASE)

    def is_spam(self, text, sender, common_chats_count, media=None):
        # --- LAYER A: Entity & Social Metadata ---
        # 1. IMMEDIATE BOT SKIP
        if sender:
            if getattr(sender, 'bot', False):
                return "Entity: Bot"
            
            username = getattr(sender, 'username', '') or ''
            if 'bot' in username.lower():
                return "Username: Bot"

        # 2. Shared Group Constraint
        max_common = self.config.get('max_common_groups', 2)
        if common_chats_count == 0: 
            return "External: 0 Common Groups"
        if common_chats_count > max_common: 
            return f"Professional: {common_chats_count} Groups"

        # --- LAYER B: Visual & Structural Analysis ---
        # 3. Media Blacklist (Images, Stickers, GIFs)
        if media:
            if isinstance(media, MessageMediaPhoto):
                return "Media: Image"
            if isinstance(media, MessageMediaDocument):
                # Check for stickers
                if any(isinstance(attr, DocumentAttributeSticker) for attr in media.document.attributes):
                    return "Media: Sticker"
                # Check for GIFs (usually mp4 with animated attribute)
                if media.document.mime_type == 'video/mp4' and any(getattr(attr, 'animated', False) for attr in media.document.attributes):
                    return "Media: GIF"

        text_content = text or ""
        if not text_content.strip():
            return "Noise: No Text Content"
            
        text_lower = text_content.lower()

        # 5. Link Blacklist (http, https, t.me)
        if self.link_regex.search(text_lower):
            return "Link: Blacklisted URL"

        # 5. Blacklist & Bot Keywords
        combined_blacklist = self.config.get('blacklist_keywords', []) + self.config.get('bot_service_keywords', [])
        for kw in combined_blacklist:
            if kw.lower() in text_lower: return f"Keyword: {kw}"

        # 6. Template Detection
        max_lines = self.config.get('max_line_breaks', 5)
        if text_content.count('\n') > max_lines: 
            return f"Template: {text_content.count('\n')} lines"
        
        if self.emoji_regex.search(text_content): 
            return "Marketing: Contains Emoji"

        # --- LAYER C: Language & Content Validation ---
        # 7. Feminine Name (Optional)
        if self.config.get('check_feminine', True) and sender:
            first_name = getattr(sender, 'first_name', '') or ''
            last_name = getattr(sender, 'last_name', '') or ''
            name = f"{first_name} {last_name}".strip()
            if name and self.fem_endings.match(name): return "Feminine Name"

        # 8. The Uzbek Guard
        min_uz_val = self.config.get('min_uz_char_percentage', 0.3)
        # Normalize: if > 1, assume it's a percentage (30 instead of 0.3)
        min_uz_threshold = min_uz_val if min_uz_val <= 1 else min_uz_val / 100
        
        if min_uz_threshold > 0:
            # Check for stop-words first (Fast pass)
            if any(sw in text_lower for sw in self.uz_stop_words):
                return None # Valid Uzbek logistics lead
            
            # Calculate Uzbek-specific character percentage
            total_chars = len(text_content.strip())
            if total_chars > 20: # Only apply ratio to substantive messages
                uz_specials = self.uz_specials_regex.findall(text_content)
                uz_ratio = len(uz_specials) / total_chars
                if uz_ratio < min_uz_threshold:
                    return f"International Noise: {uz_ratio*100:.1f}% UzChars"

        return None
