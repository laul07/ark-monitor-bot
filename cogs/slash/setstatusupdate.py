# setstatusupdate.py

import discord
from discord import app_commands
from discord.ext.commands import GroupCog
from discord.ext import tasks
from utils.config import load_config, save_config
from datetime import datetime, timezone
import aiohttp
import a2s  # Use A2S protocol for reliable player counts

class SetStatusUpdateCog(GroupCog, name="status"):
    def __init__(self, bot):
        self.bot = bot
        self.status_message = None
        self.update_status_loop.start()

    @tasks.loop(minutes=10)
    async def update_status_loop(self):
        await self.bot.wait_until_ready()

        for guild in self.bot.guilds:
            config     = load_config(guild.id)
            channel_id = config.get("status_channel_id")
            server_ids = config.get("server_ids", [])
            name_map   = config.get("server_names", {})

            if not channel_id or not server_ids:
                continue

            channel = guild.get_channel(channel_id)
            if not channel:
                continue

            token = config.get("nitrado_token")
            embed = discord.Embed(
                title="📡 Ark Server Status",
                color=discord.Color.green()
            )

            if not token:
                embed.description = "❌ No Nitrado token configured."
            else:
                async with aiohttp.ClientSession(
                    headers={"Authorization": f"Bearer {token}"}
                ) as session:
                    for sid in server_ids:
                        # Custom or default display name
                        custom_name  = name_map.get(str(sid))
                        display_name = custom_name or f"Server {sid}"

                        try:
                            # Fetch server metadata
                            main_url = f"https://api.nitrado.net/services/{sid}/gameservers"
                            async with session.get(main_url) as resp:
                                if resp.status != 200:
                                    raise ValueError(f"Metadata fetch failed: {resp.status}")
                                mdata = await resp.json()

                            gs = mdata.get("data", {}).get("gameserver", {}) or {}
                            slots = gs.get("slots", "?")
                            status = gs.get("status", "unknown")
                            cfg = gs.get("settings", {}).get("config", {})
                            # Map name from config or label
                            map_name = cfg.get("map") or gs.get("label") or "Unknown"
                            # Display name selection
                            display_name = (
                                custom_name or
                                cfg.get("server-name") or
                                gs.get("label") or
                                display_name
                            )

                            # Attempt A2S server query
                            players = None
                            max_players = None
                            connect = gs.get("connect", {})
                            ip = connect.get("address")
                            port = connect.get("query_port")
                            if ip and port:
                                try:
                                    info = a2s.info((ip, port))
                                    players = info.player_count
                                    max_players = info.max_players
                                except Exception as a2s_err:
                                    print(f"[WARN] A2S query failed for {sid}: {a2s_err}")

                            # Fallback: players endpoint
                            if players is None:
                                players_url = f"https://api.nitrado.net/services/{sid}/players"
                                async with session.get(players_url) as presp:
                                    if presp.status == 200:
                                        pdata = await presp.json()
                                        plist = pdata.get("data", {}).get("data", []) or pdata.get("data", [])
                                        players = len(plist)

                            # Final defaults
                            if players is None:
                                players = 0
                            if max_players is None:
                                max_players = slots

                        except Exception as e:
                            print(f"[ERROR] fetching data for {sid}: {e}")
                            map_name = "Unknown"
                            display_name = custom_name or f"Server {sid}"
                            players = 0
                            max_players = "?"
                            status = "unknown"

                        # Status emoji
                        s = status.lower()
                        if s in ("started", "online"):
                            status_emoji = "🟢"
                        elif s in ("restarting", "updating"):
                            status_emoji = "🟡"
                        else:
                            status_emoji = "🔴"

                        # Add to embed
                        embed.add_field(
                            name=display_name,
                            value=(
                                f"🆔 ID: `{sid}`\n"
                                f"🗺️ Map: `{map_name}`\n"
                                f"🧍 Players: `{players}/{max_players}`\n"
                                f"{status_emoji} Status: `{status}`"
                            ),
                            inline=False
                        )
                        embed.add_field(name="\u200b", value="\u200b", inline=False)

            # Footer
            embed.description = f"Last updated: <t:{int(datetime.now(timezone.utc).timestamp())}:R>"
            embed.set_footer(text="Auto-updated every 10 minutes")

            # Prune old messages
            try:
                async for msg in channel.history(limit=50):
                    if self.status_message is None or msg.id != self.status_message.id:
                        await msg.delete()
            except Exception as prune_err:
                print(f"[WARN] prune failed: {prune_err}")

            # Send or edit status message
            try:
                if self.status_message:
                    await self.status_message.edit(embed=embed)
                    if not self.status_message.pinned:
                        await self.status_message.pin()
                else:
                    self.status_message = await channel.send(embed=embed)
                    await self.status_message.pin()
            except Exception as send_err:
                print(f"[ERROR] send/edit failed: {send_err}")
                self.status_message = await channel.send(embed=embed)

    async def manual_status_update(self, guild):
        """Trigger an immediate status update."""
        config = load_config(guild.id)
        channel_id = config.get("status_channel_id")
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            await self.update_status_loop.callback(self)

    @app_commands.command(name="setstatusupdate", description="Start auto status updates in a channel.")
    async def setstatusupdate(self, interaction: discord.Interaction, channel_name: str):
        """Configure the channel for automatic status updates."""
        guild = interaction.guild
        config = load_config(guild.id)

        existing = discord.utils.get(guild.channels, name=channel_name)
        if existing:
            config["status_channel_id"] = existing.id
            msg = f"✅ Using existing channel `{channel_name}`."
        else:
            new_ch = await guild.create_text_channel(channel_name)
            config["status_channel_id"] = new_ch.id
            msg = f"✅ Created channel `{channel_name}`."
        save_config(guild.id, config)
        await interaction.response.send_message(msg, ephemeral=True)
        await self.manual_status_update(guild)

    @app_commands.command(name="view", description="View current status update channel.")
    async def view_status(self, interaction: discord.Interaction):
        """View the currently configured status channel."""
        config = load_config(interaction.guild.id)
        cid    = config.get("status_channel_id")
        if cid:
            ch = interaction.guild.get_channel(cid)
            mention = ch.mention if ch else f"(ID: {cid})"
            await interaction.response.send_message(f"🔎 Updates go to: {mention}", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ No status channel configured.", ephemeral=True)

    @app_commands.command(name="disable", description="Disable status updates.")
    async def disable_status(self, interaction: discord.Interaction):
        """Disable automatic status updates."""
        config = load_config(interaction.guild.id)
        if "status_channel_id" in config:
            del config["status_channel_id"]
            save_config(interaction.guild.id, config)
            await interaction.response.send_message("🛑 Status updates disabled.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ No status channel to disable.", ephemeral=True)

async def setup(bot):
    """Add the status update cog to the bot."""
    await bot.add_cog(SetStatusUpdateCog(bot))
