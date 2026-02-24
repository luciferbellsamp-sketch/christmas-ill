import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

class ZabivView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.players = []

    @discord.ui.button(label="✅ Записаться", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.players:
            self.players.append(interaction.user)
        await self.update_embed(interaction)

    @discord.ui.button(label="❌ Отписаться", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.players:
            self.players.remove(interaction.user)
        await self.update_embed(interaction)

    async def update_embed(self, interaction):
        embed = interaction.message.embeds[0]
        player_list = "\n".join([p.mention for p in self.players]) or "Никто не записался"
        embed.set_field_at(2, name="👥 Участники", value=player_list, inline=False)
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

@bot.tree.command(name="zabiv", description="Создать забив капта")
async def zabiv(interaction: discord.Interaction, opponent: str, time: str):
    embed = discord.Embed(
        title="⚔️ Новый забив капта",
        color=discord.Color.red()
    )
    embed.add_field(name="🏷 Против", value=opponent, inline=False)
    embed.add_field(name="⏰ Время", value=time, inline=False)
    embed.add_field(name="👥 Участники", value="Никто не записался", inline=False)

    await interaction.response.send_message(embed=embed, view=ZabivView())

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Бот запущен как {bot.user}")

bot.run(os.getenv("TOKEN"))
