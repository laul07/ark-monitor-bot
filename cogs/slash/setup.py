# setup.py

import discord
from discord import app_commands
from discord.ext.commands import Cog
from discord.ui import Modal, TextInput
from utils.config import load_config, save_config
import aiohttp

class NitradoSetupModal(Modal, title="ARK Server Setup - Nitrado Token"):
    def __init__(self, interaction: discord.Interaction):
        super().__init__()
        self.interaction = interaction

        self.token_input = TextInput(
            label="Enter your Nitrado API Token",
            placeholder="Paste your Nitrado token here",
            style=discord.TextStyle.long,
            required=True,
        )
        self.add_item(self.token_input)

    async def on_submit(self, interaction: discord.Interaction):
        token = self.token_input.value
        guild_id = self.interaction.guild.id
        guild_name = self.interaction.guild.name

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get("https://api.nitrado.net/services", headers=headers) as resp:
                    print(f"[DEBUG] Token submitted: {token[:4]}••••{token[-4:]}")
                    print(f"[DEBUG] API response status: {resp.status}")
                    raw = await resp.text()
                    print(f"[DEBUG] Raw API response: {raw}")

                    if resp.status == 200:
                        data = await resp.json()
                        services = data.get("data", {}).get("services", [])

                        ark_servers = [
                            svc for svc in services
                            if svc.get("type") == "gameserver"
                               and "ark" in svc.get("details", {}).get("game", "").lower()
                        ]

                        # extract names and ids
                        ark_server_names = [svc["details"]["name"] for svc in ark_servers]
                        ark_server_ids   = [str(svc["id"])            for svc in ark_servers]

                        # load existing config
                        config = load_config(guild_id)
                        config["nitrado_token"]         = token
                        config["nitrado_token_preview"] = token[:4] + "••••" + token[-4:]
                        config["linked_servers"]        = ark_server_names
                        config["server_ids"]            = ark_server_ids

                        # add mapping of id -> custom server name
                        config["server_names"] = {
                            sid: name for sid, name in zip(ark_server_ids, ark_server_names)
                        }

                        # save with guild metadata
                        save_config(guild_id, config, guild_name=guild_name)

                        # build response message
                        msg = "✅ Token accepted and saved.\n\n"
                        if ark_server_names:
                            msg += "🎮 Linked ARK Servers:\n"
                            msg += "\n".join(f"- {name} (ID: {sid})"
                                              for sid, name in zip(ark_server_ids, ark_server_names))
                        else:
                            msg += "⚠️ No ARK servers found on this account."

                        await interaction.response.send_message(msg, ephemeral=True)
                    else:
                        await interaction.response.send_message(
                            f"❌ Invalid token. Response code: {resp.status}\nCheck console for details.",
                            ephemeral=True
                        )
            except Exception as e:
                print(f"[ERROR] Exception during Nitrado request: {e}")
                await interaction.response.send_message(
                    "❌ An error occurred while validating the token.", ephemeral=True
                )

class SetupCog(Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setup",
        description="Start ARK monitoring setup for this server."
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_command(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ This command must be used in a server.", ephemeral=True
            )
            return

        modal = NitradoSetupModal(interaction)
        await interaction.response.send_modal(modal)

async def setup(bot):
    await bot.add_cog(SetupCog(bot))
