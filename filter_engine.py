import re
import logging
from telethon.tl.types import MessageMediaDocument, DocumentAttributeSticker, MessageMediaWebPage, MessageMediaPhoto

class FilterEngine:
    def __init__(self, config=None):
        from config import DEFAULT_FILTERS
        # Ensure config is never None and always a valid dict
        self.config = config if isinstance(config, dict) else DEFAULT_FILTERS
        self._compile_regex()
        
        # Uzbek common stop-words from FILTER_RULES.md
        self.uz_stop_words = ["yuk bor", "mashina kerak", "aka", "fura", "ref", "yuk", "bor", "kerak", "nechi", "tonna"]
        
    def _compile_regex(self):
        """Pre-compiles all regex patterns to optimize the processing loop."""
        try:
            # 1. Feminine Endings
            fem_pattern = self.config.get('fem_endings_regex')
            if not fem_pattern:
                from config import DEFAULT_FILTERS
                fem_pattern = DEFAULT_FILTERS['fem_endings_regex']
            self.fem_endings = re.compile(fem_pattern, re.IGNORECASE)
            
            # 2. Links
            self.link_regex = re.compile(r'(https?://|t\.me/)', re.IGNORECASE)
            
            # 3. Visual Noise (Emojis/Symbols)
            self.emoji_regex = re.compile(r'[\U0001F000-\U0001FAFF]|[\u2700-\u27BF]|[\u2600-\u26FF]')
            
            # 4. Uzbek Special Characters
            self.uz_specials_regex = re.compile(r'[ўқғҳЎҚҒҲ]')
            
        except re.error as e:
            logging.error(f"Regex compilation error: {e}. Falling back to defaults.")
            # Absolute safe fallbacks
            self.fem_endings = re.compile(r'.*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$', re.IGNORECASE)
            self.link_regex = re.compile(r'(https?://|t\.me/)', re.IGNORECASE)
            self.emoji_regex = re.compile(r'[\U0001F000-\U0001FAFF]|[\u2700-\u27BF]|[\u2600-\u26FF]')
            self.uz_specials_regex = re.compile(r'[ўқғҳЎҚҒҲ]')

    def is_spam(self, text, sender, common_chats_count, media=None):
        """
        Main filtering logic. Returns a string reason if spam, or None if it's a valid lead.
        """
        try:
            if self.config is None:
                from config import DEFAULT_FILTERS
                self.config = DEFAULT_FILTERS

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
                    if hasattr(media, 'document') and hasattr(media.document, 'attributes'):
                        if any(isinstance(attr, DocumentAttributeSticker) for attr in media.document.attributes):
                            return "Media: Sticker"
                        # Check for GIFs (usually mp4 with animated attribute)
                        if media.document.mime_type == 'video/mp4' and any(getattr(attr, 'animated', False) for attr in media.document.attributes):
                            return "Media: GIF"

            text_content = text or ""
            if not text_content.strip():
                return "Noise: No Text Content"
                
            text_lower = text_content.lower()

            # 4. Link Blacklist (http, https, t.me)
            if self.link_regex.search(text_lower):
                return "Link: Blacklisted URL"

            # 5. Blacklist & Bot Keywords
            blacklist = self.config.get('blacklist_keywords', [])
            bot_keywords = self.config.get('bot_service_keywords', [])
            combined_blacklist = (blacklist if isinstance(blacklist, list) else []) + \
                                 (bot_keywords if isinstance(bot_keywords, list) else [])
            
            for kw in combined_blacklist:
                if str(kw).lower() in text_lower: 
                    return f"Keyword: {kw}"

            # 6. Template Detection
            max_lines = self.config.get('max_line_breaks', 5)
            line_count = text_content.count('\n')
            if line_count > max_lines: 
                return f"Template: {line_count} lines"
            
            if self.emoji_regex.search(text_content): 
                return "Marketing: Contains Emoji"

            # --- LAYER C: Language & Content Validation ---
            # 7. Feminine Name (Optional)
            if self.config.get('check_feminine', True) and sender:
                first_name = getattr(sender, 'first_name', '') or ''
                last_name = getattr(sender, 'last_name', '') or ''
                name = f"{first_name} {last_name}".strip()
                if name and self.fem_endings.match(name): 
                    return "Feminine Name"

            # 8. The Uzbek Guard
            min_uz_val = self.config.get('min_uz_char_percentage', 0.3)
            # Normalize: if > 1, assume it's a percentage (30 instead of 0.3)
            try:
                min_uz_threshold = float(min_uz_val)
                if min_uz_threshold > 1:
                    min_uz_threshold = min_uz_threshold / 100
            except (ValueError, TypeError):
                min_uz_threshold = 0.3
            
            if min_uz_threshold > 0:
                # Check for stop-words first (Fast pass)
                if any(sw in text_lower for sw in self.uz_stop_words):
                    return None # Valid Uzbek logistics lead
                
                # Calculate Uzbek-specific character percentage
                trimmed_text = text_content.strip()
                total_chars = len(trimmed_text)
                if total_chars > 20: # Only apply ratio to substantive messages
                    uz_specials = self.uz_specials_regex.findall(trimmed_text)
                    uz_ratio = len(uz_specials) / total_chars
                    if uz_ratio < min_uz_threshold:
                        return f"International Noise: {uz_ratio*100:.1f}% UzChars"

            return None
        except Exception as e:
            logging.error(f"Error in FilterEngine.is_spam: {e}", exc_info=True)
            return None # Fail open
