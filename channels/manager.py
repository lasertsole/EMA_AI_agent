"""Channel manager for coordinating chat channels."""
from __future__ import annotations

import json
import asyncio
import logging
from pathlib import Path
from config import ROOT_DIR
from .base import BaseChannel
from typing import Any, Optional
from bus.queue import MessageBus

logger = logging.getLogger(__name__)

class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Optional[dict[str, str]] = None,  bus: Optional[MessageBus] = None):
        if config is None:
            channels_json = Path(ROOT_DIR) / "channels.json"
            if not channels_json.exists():
                return

            config = json.loads(channels_json.read_text())

        if bus is None:
            bus = MessageBus()
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None
        self.config = config
        self._event_loop = asyncio.new_event_loop()
        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize channels discovered via pkgutil scan + entry_points plugins."""
        from channels.registry import discover_all


        for name, cls in discover_all().items():
            section = self.config.get(name, None)
            if section is None:
                continue
            enabled = (
                section.get("enabled", False)
                if isinstance(section, dict)
                else getattr(section, "enabled", False)
            )
            if not enabled:
                continue
            try:
                channel = cls(section, self.bus)
                self.channels[name] = channel
                logger.info("{} channel enabled", cls.display_name)
            except Exception as e:
                logger.warning("{} channel not available: {}", name, e)

        self._validate_allow_from()

    def _validate_allow_from(self) -> None:
        for name, ch in self.channels.items():
            if getattr(ch.config, "allow_from", None) == []:
                raise SystemExit(
                    f'Error: "{name}" has empty allowFrom (denies all). '
                    f'Set ["*"] to allow everyone, or add specific user IDs.'
                )

    async def _start_channel(self, name: str, channel: BaseChannel) -> None:
        """Start a channel and log any exceptions."""
        try:
            await channel.start()
        except Exception as e:
            logger.error("Failed to start channel {}: {}", name, e)

    def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self._event_loop.is_running():
            if not self.channels:
                logger.warning("No channels enabled")
                return

            # Start outbound dispatcher
            self._dispatch_task = self._event_loop.create_task(self._dispatch_outbound())

            # Start channels
            tasks = []
            for name, channel in self.channels.items():
                logger.info("Starting {} channel...", name)
                self._event_loop.create_task(self._start_channel(name, channel))
            print(self._event_loop)
            self._event_loop.run_forever()

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")

        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()

        # Stop all channels
        tasks = []
        for name, channel in self.channels.items():
            try:
                tasks.append(asyncio.create_task(channel.stop()))
            except Exception as e:
                logger.error("Error stopping {}: {}", name, e)

        await asyncio.gather(*tasks, return_exceptions=True)

        # Stop event loop
        self._event_loop.stop()
        self._event_loop = None

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )

                if msg.metadata.get("_progress"):
                    if msg.metadata.get("_tool_hint") and not self.config.channels.send_tool_hints:
                        continue
                    if not msg.metadata.get("_tool_hint") and not self.config.channels.send_progress:
                        continue

                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error("Error sending to {}: {}", msg.channel, e)
                else:
                    logger.warning("Unknown channel: {}", msg.channel)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running
            }
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())