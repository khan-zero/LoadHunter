import re
import logging
import hashlib
import time
from telethon.tl.types import MessageMediaDocument, DocumentAttributeSticker, MessageMediaWebPage, MessageMediaPhoto

class FilterEngine:
    def __init__(self, config=None):
        from config import DEFAULT_FILTERS
        # Ensure config is never None and always a valid dict
        self.config = config if isinstance(config, dict) else DEFAULT_FILTERS
        self._compile_regex()
        
        # Memory for duplicate detection: {hash: timestamp}
        self.seen_leads = {}
        
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
            
            # 4. Uzbek Special Characters (Cyrillic + Latin marks)
            self.uz_specials_regex = re.compile(r"[ўқғҳЎҚҒҲ]|[oO]'|[gG]'|[sS][hH]|[cC][hH]")
            
        except re.error as e:
            logging.error(f"Regex compilation error: {e}. Falling back to defaults.")
            # Absolute safe fallbacks
            self.fem_endings = re.compile(r'.*(ova|eva|ова|ева|а|я|ия|iya|ia|xon|хон|bibi|биби)$', re.IGNORECASE)
            self.link_regex = re.compile(r'(https?://|t\.me/)', re.IGNORECASE)
            self.emoji_regex = re.compile(r'[\U0001F000-\U0001FAFF]|[\u2700-\u27BF]|[\u2600-\u26FF]')
            self.uz_specials_regex = re.compile(r"[ўқғҳЎҚҒҲ]|[oO]'|[gG]'|[sS][hH]|[cC][hH]")

    def _get_content_hash(self, text):
        """Generates a normalized hash of the text content."""
        # Normalize: lower, strip whitespace, remove emojis/punctuation
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = "".join(normalized.split()) # Remove all whitespace
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def is_spam_fast(self, text, sender, media=None):
        """
        Cheap filtering logic that doesn't require extra API calls.
        Returns a string reason if spam, or None to continue.
        """
        try:
            # --- LAYER 0: Whitelist & Blacklist ---
            if sender:
                user_id = str(sender.id)
                username = (getattr(sender, 'username', '') or '').lower()
                
                if user_id in self.config.get('whitelist_users', []) or \
                   (username and f"@{username}" in self.config.get('whitelist_users', [])):
                    return "WHITELISTED" # Special return to skip all other filters

                if user_id in self.config.get('blacklist_users', []) or \
                   (username and f"@{username}" in self.config.get('blacklist_users', [])):
                    return "Blacklisted User"

            # --- LAYER A: Entity Metadata ---
            if sender:
                if getattr(sender, 'bot', False):
                    return "Entity: Bot"
                
                if 'bot' in (getattr(sender, 'username', '') or '').lower():
                    return "Username: Bot"

            # --- LAYER B: Visual & Structural Analysis ---
            if media:
                if isinstance(media, MessageMediaPhoto):
                    return "Media: Image"
                if isinstance(media, MessageMediaDocument):
                    if hasattr(media, 'document') and hasattr(media.document, 'attributes'):
                        if any(isinstance(attr, DocumentAttributeSticker) for attr in media.document.attributes):
                            return "Media: Sticker"
                        if media.document.mime_type == 'video/mp4' and any(getattr(attr, 'animated', False) for attr in media.document.attributes):
                            return "Media: GIF"

            text_content = text or ""
            if not text_content.strip():
                return "Noise: No Text Content"
                
            text_lower = text_content.lower()

            # --- LAYER C: Duplicate Detection ---
            content_hash = self._get_content_hash(text_content)
            now = time.time()
            timeout = self.config.get('duplicate_timeout', 600)
            
            # Prune old entries occasionally
            if len(self.seen_leads) > 1000:
                self.seen_leads = {h: t for h, t in self.seen_leads.items() if now - t < timeout}

            if content_hash in self.seen_leads:
                if now - self.seen_leads[content_hash] < timeout:
                    return "Duplicate: Recently Seen"
            
            self.seen_leads[content_hash] = now

            # Link Blacklist
            if self.link_regex.search(text_lower):
                return "Link: Blacklisted URL"

            # Blacklist & Bot Keywords
            blacklist = self.config.get('blacklist_keywords', [])
            bot_keywords = self.config.get('bot_service_keywords', [])
            combined_blacklist = (blacklist if isinstance(blacklist, list) else []) + \
                                 (bot_keywords if isinstance(bot_keywords, list) else [])
            
            for kw in combined_blacklist:
                if str(kw).lower() in text_lower: 
                    return f"Keyword: {kw}"

            # Template Detection
            max_lines = self.config.get('max_line_breaks', 5)
            line_count = text_content.count('\n')
            if line_count > max_lines: 
                return f"Template: {line_count} lines"
            
            if self.emoji_regex.search(text_content): 
                return "Marketing: Contains Emoji"

            # --- LAYER D: Route Filtering (New) ---
            target_routes = self.config.get('target_routes', [])
            if target_routes:
                # If target routes are set, the message MUST contain at least one of them
                route_found = False
                for route in target_routes:
                    if str(route).lower() in text_lower:
                        route_found = True
                        break
                if not route_found:
                    return "Route: Not in target locations"

            # Feminine Name
            if self.config.get('check_feminine', True) and sender:
                first_name = getattr(sender, 'first_name', '') or ''
                last_name = getattr(sender, 'last_name', '') or ''
                name = f"{first_name} {last_name}".strip()
                if name and self.fem_endings.match(name): 
                    return "Feminine Name"

            # Uzbek Guard
            uz_stop_words = self.config.get('uz_stop_words', [])
            if any(sw in text_lower for sw in uz_stop_words):
                return None # Valid Uzbek logistics lead (Passed Fast)
            
            min_uz_val = self.config.get('min_uz_char_percentage', 0.3)
            try:
                min_uz_threshold = float(min_uz_val)
                if min_uz_threshold > 1: min_uz_threshold /= 100
            except: min_uz_threshold = 0.3
            
            if min_uz_threshold > 0:
                trimmed_text = text_content.strip()
                total_chars = len(trimmed_text)
                if total_chars > 20:
                    uz_specials = self.uz_specials_regex.findall(trimmed_text)
                    uz_ratio = len(uz_specials) / total_chars
                    if uz_ratio < min_uz_threshold:
                        return f"International Noise: {uz_ratio*100:.1f}% UzChars"

            return None
        except Exception as e:
            logging.error(f"Error in FilterEngine.is_spam_fast: {e}")
            return None

    def is_spam_social(self, common_chats_count):
        """
        Expensive filtering logic based on social metadata.
        """
        max_common = self.config.get('max_common_groups', 2)
        if common_chats_count == 0: 
            return "External: 0 Common Groups"
        if common_chats_count > max_common: 
            return f"Professional: {common_chats_count} Groups"
        return None

    def is_spam(self, text, sender, common_chats_count, media=None):
        """Compatibility layer for old calls."""
        fast_reason = self.is_spam_fast(text, sender, media)
        if fast_reason == "WHITELISTED": return None
        if fast_reason: return fast_reason
        return self.is_spam_social(common_chats_count)
