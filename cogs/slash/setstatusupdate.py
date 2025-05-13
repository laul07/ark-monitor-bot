# setstatusupdate.py

import discord
from discord import app_commands
from discord.ext.commands import GroupCog
from discord.ext import tasks
from utils.config import load_config, save_config
from datetime import datetime, timezone
import aiohttp

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
                        # determine display name
                        custom_name  = name_map.get(str(sid))
                        display_name = custom_name or f"Server {sid}"

                        # defaults
                        map_name    = "Unknown"
                        players     = 0
                        max_players = "?"
                        status      = "unknown"

                        try:
                            # fetch metadata
                            main_url = f"https://api.nitrado.net/services/{sid}/gameservers"
                            async with session.get(main_url) as resp:
                                mdata = await resp.json()

                            gs = mdata.get("data", {}).get("gameserver", {}) or {}
                            q  = mdata.get("data", {}).get("query", {})      or {}

                            # dedicated query endpoint if needed
                            if not q or "player_current" not in q:
                                query_url = f"https://api.nitrado.net/services/{sid}/gameservers/query"
                                async with session.get(query_url) as qresp:
                                    if qresp.status == 200:
                                        qdata = await qresp.json()
                                        q = qdata.get("data", {}).get("query", {}) or qdata.get("data", {})

                            # fallbacks from settings.config
                            cfg         = gs.get("settings", {}).get("config", {})
                            config_map  = cfg.get("map", "Unknown")
                            config_name = cfg.get("server-name")
                            slots       = gs.get("slots", "?")

                            # populate
                            display_name = (
                                custom_name or
                                q.get("server_name") or
                                config_name or
                                gs.get("label") or
                                display_name
                            )
                            map_name     = q.get("map", config_map)
                            players      = q.get("player_current", players)
                            max_players  = q.get("player_max", slots)
                            status       = gs.get("status", status)

                        except Exception as e:
                            print(f"[ERROR] fetching/parsing server {sid}: {e}")

                        # choose emoji
                        s = status.lower()
                        if s in ("started", "online"):
                            status_emoji = "🟢"
                        elif s in ("restarting", "updating"):
                            status_emoji = "🟡"
                        else:
                            status_emoji = "🔴"

                        # single field per server, no extra blank before details
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
                        # spacer between servers
                        embed.add_field(name="\u200b", value="\u200b", inline=False)

            embed.description = f"Last updated: <t:{int(datetime.now(timezone.utc).timestamp())}:R>"
            embed.set_footer(text="Auto-updated every 10 minutes")

            # delete old messages except our pinned one
            try:
                async for msg in channel.history(limit=50):
                    if self.status_message is None or msg.id != self.status_message.id:
                        await msg.delete()
            except Exception as prune_err:
                print(f"[WARN] prune failed: {prune_err}")

            # send or edit + pin
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
        config     = load_config(guild.id)
        channel_id = config.get("status_channel_id")
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            await self.update_status_loop.callback(self)

    @app_commands.command(name="setstatusupdate", description="Start auto status updates in a channel.")
    async def setstatusupdate(self, interaction: discord.Interaction, channel_name: str):
        guild  = interaction.guild
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
        config = load_config(interaction.guild.id)
        if "status_channel_id" in config:
            del config["status_channel_id"]
            save_config(interaction.guild.id, config)
            await interaction.response.send_message("🛑 Status updates disabled.", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ No status channel to disable.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(SetStatusUpdateCog(bot))
