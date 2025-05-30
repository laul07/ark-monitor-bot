# setstatusupdate.py

import discord
from discord import app_commands
from discord.ext.commands import GroupCog
from discord.ext import tasks
from utils.config import load_config, save_config
from datetime import datetime, timezone
import aiohttp
import a2s  # Use A2S protocol for reliable player counts
import logging
import asyncio

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
            # We'll determine embed color dynamically
            embed_color = discord.Color.green()
            status_list = []
            suspended_list = []
            has_yellow = False
            has_red = False

            if not token:
                embed = discord.Embed(
                    title="📡 Ark Server Status",
                    color=discord.Color.red()
                )
                embed.description = "❌ No Nitrado token configured."
            else:
                async with aiohttp.ClientSession(
                    headers={"Authorization": f"Bearer {token}"}
                ) as session:
                    async def fetch_status(sid):
                        custom_name  = name_map.get(str(sid))
                        display_name = custom_name or f"Server {sid}"
                        try:
                            main_url = f"https://api.nitrado.net/services/{sid}/gameservers"
                            async with session.get(main_url) as resp:
                                if resp.status != 200:
                                    raise ValueError(f"Metadata fetch failed: {resp.status}")
                                mdata = await resp.json()
                            gs = mdata.get("data", {}).get("gameserver", {}) or {}
                            q  = mdata.get("data", {}).get("query", {})      or {}
                            logging.debug(f"[DEBUG] query info for {sid}: {q}")
                            slots = gs.get("slots", "?")
                            status = gs.get("status", "unknown")
                            cfg = gs.get("settings", {}).get("config", {})
                            map_name = cfg.get("map") or gs.get("label") or "Unknown"
                            display_name = (
                                custom_name or
                                cfg.get("server-name") or
                                gs.get("label") or
                                display_name
                            )
                            players = None
                            max_players = None
                            host = q.get("address") or q.get("host")
                            port = q.get("port") or q.get("query_port")
                            if host and port:
                                try:
                                    info = a2s.info((host, int(port)))
                                    players = info.player_count
                                    max_players = info.max_players
                                except Exception as a2s_err:
                                    logging.warning(f"[WARN] A2S query failed for {sid}: {a2s_err}")
                            if players is None:
                                players_url = f"https://api.nitrado.net/services/{sid}/players"
                                async with session.get(players_url) as presp:
                                    if presp.status == 200:
                                        pdata = await presp.json()
                                        logging.debug(f"[DEBUG] /players response for {sid}: {pdata}")
                                        plist = pdata.get("data", {}).get("data", []) or pdata.get("data", [])
                                        players = len(plist)
                            if players is None:
                                players = 0
                            if max_players is None:
                                max_players = slots
                        except Exception as e:
                            logging.error(f"[ERROR] fetching data for {sid}: {e}")
                            map_name     = "Unknown"
                            display_name = custom_name or f"Server {sid}"
                            players      = 0
                            max_players  = "?"
                            status       = "unknown"
                        s = status.lower()
                        if s in ("started", "online"):
                            status_emoji = "🟢"
                        elif s in ("restarting", "updating"):
                            status_emoji = "🟡"
                        else:
                            status_emoji = "🔴"
                        return {
                            "name": display_name,
                            "value": (
                                f"🆔 ID: `{sid}`\n"
                                f"🗺️ Map: `{map_name}`\n"
                                f"🧍 Players: `{players}/{max_players}`\n"
                                f"{status_emoji} Status: `{status}`"
                            ),
                            "status": s
                        }
                    results = await asyncio.gather(*(fetch_status(sid) for sid in server_ids))
                    for result in results:
                        if result["status"] in ("started", "online"):
                            status_list.append(result)
                        elif result["status"] in ("restarting", "updating"):
                            status_list.append(result)
                            has_yellow = True
                        else:
                            suspended_list.append(result)
                            has_red = True
                    # Set embed color
                    if has_red:
                        embed_color = discord.Color.red()
                    elif has_yellow:
                        embed_color = discord.Color.yellow()
                    else:
                        embed_color = discord.Color.green()
                    embed = discord.Embed(
                        title="📡 Ark Server Status",
                        color=embed_color
                    )
                    # Add online/restarting servers first, then suspended/offline
                    all_results = status_list + suspended_list
                    for i, result in enumerate(all_results):
                        embed.add_field(name=result["name"], value=result["value"], inline=False)
                        # Only add blank field between servers, not after last
                        if i < len(all_results) - 1:
                            embed.add_field(name="\u200b", value="\u200b", inline=False)
            embed.description = f"Last updated: <t:{int(datetime.now(timezone.utc).timestamp())}:R>"
            embed.set_footer(text="Auto-updated every 10 minutes")
            # Prune and send/edit message
            try:
                # Only delete previous status message if it exists and is not the current one
                if self.status_message:
                    try:
                        prev_msg = await channel.fetch_message(self.status_message.id)
                        await prev_msg.delete()
                    except Exception:
                        pass
            except Exception as prune_err:
                logging.warning(f"[WARN] prune failed: {prune_err}")
            try:
                self.status_message = await channel.send(embed=embed)
                await self.status_message.pin()
            except Exception as send_err:
                logging.error(f"[ERROR] send/edit failed: {send_err}")
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
