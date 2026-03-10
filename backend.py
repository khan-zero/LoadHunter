import os
import asyncio
import threading
import logging
from telethon import TelegramClient, events, utils, errors
from telethon.tl.functions.messages import GetCommonChatsRequest
from config import API_ID, API_HASH, SESSION_DIR

class LoadHunterBackend:
    def __init__(self, loop, on_lead_callback, on_groups_callback, on_error_callback, on_filter_log_callback=None, on_ready_callback=None):
        self.loop = loop
        self.on_lead = on_lead_callback
        self.on_groups = on_groups_callback
        self.on_error = on_error_callback
        self.on_filter_log = on_filter_log_callback
        self.on_ready = on_ready_callback
        
        self.client = None
        self.listening = False
        self._starting = False
        self.common_chats_cache = {}
        self.filter_engine = None
        self._thread = None
        self._loop_ready = threading.Event()

    def start(self, filter_engine):
        if self._starting or (self.client and self.client.is_connected()):
            logging.warning("Backend already starting or connected.")
            return

        self._starting = True
        self.filter_engine = filter_engine
        if not self._thread or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
            self._thread.start()
        
        # Wait for the loop to be running before scheduling
        def schedule_init():
            self._loop_ready.wait(timeout=5)
            if self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self._init_client(), self.loop)
            else:
                self._starting = False
                logging.error("Asyncio loop failed to start in time.")

        threading.Thread(target=schedule_init, daemon=True).start()

    def _run_event_loop(self):
        """Runs the asyncio event loop in a dedicated thread."""
        asyncio.set_event_loop(self.loop)
        self._loop_ready.set()
        try:
            self.loop.run_forever()
        except Exception as e:
            logging.error(f"Event loop crashed: {e}")
        finally:
            # Clean up pending tasks properly when the loop is stopped
            try:
                if self.loop.is_running():
                    pending = asyncio.all_tasks(self.loop)
                    if pending:
                        for task in pending:
                            task.cancel()
                        # Run until all tasks are cancelled (max 2 seconds)
                        self.loop.run_until_complete(asyncio.wait(pending, timeout=2))
                if not self.loop.is_closed():
                    self.loop.close()
            except Exception as e:
                logging.error(f"Error during loop closure cleanup: {e}")

    async def _init_client(self):
        session_path = os.path.join(SESSION_DIR, 'loadhunter_session')
        # Use a more robust connection policy
        self.client = TelegramClient(session_path, int(API_ID), API_HASH, connection_retries=10, retry_delay=2)
        
        try:
            logging.info("Connecting to Telegram...")
            # Use a timeout for the initial connection
            await asyncio.wait_for(self.client.connect(), timeout=30)
            
            if not await self.client.is_user_authorized():
                self._starting = False
                self.on_error("AUTH_REQUIRED")
                return

            self._starting = False
            logging.info("Telegram client connected and authorized.")

            # Initial groups fetch - help Telethon 'see' entities
            dialogs = await self.client.get_dialogs(limit=100)
            group_names = [d.name for d in dialogs if d.is_group or d.is_channel]
            self.on_groups(group_names)

            if self.on_ready:
                self.on_ready()

            @self.client.on(events.NewMessage)
            async def handler(event):
                # Critical check for stop state
                if not self.listening:
                    return
                if not event.is_group: 
                    return
                
                try:
                    # Get sender with robust entity fetching
                    try:
                        sender = await event.get_sender()
                        if not sender:
                            sender = await self.client.get_entity(event.sender_id)
                    except Exception:
                        return # Skip if we can't resolve sender
                    
                    # Check cache first for common groups
                    if sender.id in self.common_chats_cache:
                        common_count = self.common_chats_cache[sender.id]
                    else:
                        try:
                            # Robustly call GetCommonChatsRequest
                            common = await self.client(GetCommonChatsRequest(user_id=sender, max_id=0, limit=100))
                            common_count = len(common.chats)
                            self.common_chats_cache[sender.id] = common_count
                        except Exception:
                            common_count = 0
                    
                    reason = self.filter_engine.is_spam(event.text, sender, common_count, media=event.media)
                    
                    first_name = getattr(sender, 'first_name', '') or ''
                    last_name = getattr(sender, 'last_name', '') or ''
                    name = f"{first_name} {last_name}".strip() or "Unknown"

                    if self.on_filter_log:
                        status = "REJECTED: " + reason if reason else "PASSED"
                        self.on_filter_log(name, status)

                    if not reason:
                        # Construct robust tg:// link for direct app opening
                        try:
                            # Try to get username for resolve link, fallback to numeric ID
                            chat = await event.get_chat()
                            if getattr(chat, 'username', None):
                                tg_link = f"tg://resolve?domain={chat.username}&post={event.id}"
                            else:
                                # For private groups/channels, use privatepost with the 100-prefix (absolute ID)
                                peer_id = abs(utils.get_peer_id(event.input_chat))
                                tg_link = f"tg://privatepost?channel={peer_id}&post={event.id}"
                        except Exception:
                            tg_link = f"tg://openmessage?chat_id={event.chat_id}&message_id={event.id}"
                        
                        self.on_lead(name, common_count, event.text or "[Media/No Text]", tg_link, event.chat_id, event.id)
                except Exception as e:
                    logging.error(f"Error in backend handler: {e}", exc_info=True)

            await self.client.run_until_disconnected()
        except (asyncio.TimeoutError, ConnectionError) as e:
            logging.error(f"Telegram connection timed out or failed: {e}")
            self._starting = False
            self.on_error("CONNECTION_FAILED")
            return
        except Exception as e:
            logging.error(f"Client initialization error: {e}", exc_info=True)
            self._starting = False
            self.on_error("INIT_FAILED")
            return
        finally:
            self._starting = False

    async def disconnect(self):
        """Cleanly disconnects the Telegram client."""
        self.listening = False
        if self.client:
            try:
                if self.client.is_connected():
                    await asyncio.wait_for(self.client.disconnect(), timeout=5)
                logging.info("Telegram client disconnected.")
            except Exception as e:
                logging.error(f"Error during Telethon disconnect: {e}")

    async def logout(self):
        """Signs out of Telegram and deletes the session file."""
        self.listening = False
        if self.client:
            try:
                if not self.client.is_connected():
                    await self.client.connect()
                await self.client.log_out()
                logging.info("Logged out from Telegram.")
                
                # Delete session file
                session_path = os.path.join(SESSION_DIR, 'loadhunter_session.session')
                if os.path.exists(session_path):
                    os.remove(session_path)
                    logging.info(f"Session file deleted: {session_path}")
                return True
            except Exception as e:
                logging.error(f"Error during logout: {e}")
                return False
        return False

    async def forward_lead(self, chat_id, message_id, destinations):
        """Forwards a specific message to multiple destinations. Falls back to sending text if protected."""
        if not self.client or not self.client.is_connected():
            logging.error("Cannot forward: Client not connected.")
            return False
        
        if isinstance(destinations, str):
            destinations = [destinations]

        success_count = 0
        for dest in destinations:
            try:
                # Handle numeric IDs provided as strings
                target = dest
                if isinstance(dest, str) and (dest.startswith('-') or dest.isdigit()):
                    try:
                        target = int(dest)
                    except ValueError:
                        pass
                
                await self.client.forward_messages(target, message_id, chat_id)
                logging.info(f"Lead forwarded to {dest}.")
                success_count += 1
            except Exception as e:
                err_msg = str(e)
                if "protected chat" in err_msg or "restricted" in err_msg:
                    logging.info(f"Forwarding restricted for {message_id} in {chat_id} to {dest}. Falling back to sending text...")
                    try:
                        # Fetch message and send as new
                        msg = await self.client.get_messages(chat_id, ids=message_id)
                        if msg and msg.text:
                            chat = await msg.get_chat()
                            sender = await msg.get_sender()

                            chat_title = getattr(chat, 'title', 'Unknown Group') if chat else 'Unknown Group'
                            
                            first_name = getattr(sender, 'first_name', '') if sender else ''
                            last_name = getattr(sender, 'last_name', '') if sender else ''
                            sender_name = f"{first_name} {last_name}".strip() if (first_name or last_name) else "Unknown Sender"
                            if sender and getattr(sender, 'username', None):
                                sender_name += f" (@{sender.username})"
                            
                            try:
                                if chat and getattr(chat, 'username', None):
                                    msg_link = f"https://t.me/{chat.username}/{msg.id}"
                                elif chat:
                                    # For private groups/channels
                                    bare_id = abs(chat.id)
                                    # Format for private groups: t.me/c/ID/MsgID
                                    msg_link = f"https://t.me/c/{bare_id}/{msg.id}"
                                else:
                                    msg_link = f"tg://openmessage?chat_id={chat_id}&message_id={msg.id}"
                            except Exception:
                                msg_link = f"tg://openmessage?chat_id={chat_id}&message_id={message_id}"

                            header = (
                                f"🚀 **Restricted Lead Sent as New Message:**\n\n"
                                f"👤 **Sender:** {sender_name}\n"
                                f"👥 **Group:** {chat_title}\n"
                                f"🔗 **Original Message:** {msg_link}\n\n"
                            )
                            await self.client.send_message(target, header + msg.text, link_preview=False)
                            logging.info(f"Lead sent as new message to {dest} (Forwarding was restricted).")
                            success_count += 1
                            continue
                    except Exception as send_err:
                        logging.error(f"Fallback send failed to {dest}: {send_err}")
                
                logging.error(f"Failed to forward lead to {dest}: {e}")
        
        return success_count > 0

    def toggle_listening(self, state):
        self.listening = state
        logging.info(f"Listening state set to: {state}")
