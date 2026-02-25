import os
import re
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from zoneinfo import ZoneInfo

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== КАНАЛЫ ГДЕ МОЖНО ИСПОЛЬЗОВАТЬ ======
ALLOWED_CHANNELS = [
    1468386694175789188,
    1199092928472174734,
    1350588850744987791,
]

# ====== ПИНГИ ЛИДЕРОВ И ЗАМОВ ======
FACTION_PINGS = {
    "rm":      {"leader": 1199092925913632839, "deputy": 1199092925506797596},
    "lcn":     {"leader": 1199092925859123281, "deputy": 1199092925506797595},
    "warlock": {"leader": 1199092925859123280, "deputy": 1199092925506797594},
    "yakuza":  {"leader": 1199092925859123279, "deputy": 1199092925506797593},
    "trb":     {"leader": 1199710835384275024, "deputy": 1199710842715897947},
}

ALLOWED_SIZES = {"2x2", "3x3", "4x4", "5x5"}


# ====== УТИЛИТЫ ======

def normalize_tag(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def build_ping_text(tag: str) -> str:
    key = normalize_tag(tag)
    roles = FACTION_PINGS.get(key)
    if not roles:
        return ""
    return f"<@&{roles['leader']}> <@&{roles['deputy']}>"


def get_msk_time():
    return datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")


# ====== EMBED ======

def format_request_embed(
    author,
    tag,
    protiv,
    vremya,
    lokaciya,
    oruzhie,
    biz=None,
    status="🟠 Ожидает ответа",
):

    e = discord.Embed(
        title="Christmas Illegals",
        color=discord.Color.orange()
    )

    desc = (
        f"⚔️ **ЗАБИВ СТРЕЛЫ**\n"
        f"┌ 🏴 Фракция: **`{tag.upper()}`**\n"
        f"└ 🎯 Против: **`{protiv.upper()}`**\n"
    )

    if biz:
        desc += f"🏢 Бизнес: **`{biz}`**\n"

    desc += (
        f"🕒 Время: **`{vremya}`**\n"
        f"📍 Локация: **`{lokaciya}`**\n"
        f"🔫 Оружие: **`{oruzhie}`**"
    )

    e.description = desc

    e.add_field(name="👤 Автор", value=author.mention, inline=True)
    e.add_field(name="📊 Статус", value=status, inline=True)

    e.set_footer(text="Используйте кнопки ниже")

    return e


# ====== КНОПКИ ВЫБОРА КОЛИЧЕСТВА ======

class SizeSelectView(discord.ui.View):

    def __init__(self, parent):
        super().__init__(timeout=60)
        self.parent = parent

    @discord.ui.button(label="2x2", style=discord.ButtonStyle.primary)
    async def s2(self, interaction, button):
        await self.parent.accept_with_size(interaction, "2x2")

    @discord.ui.button(label="3x3", style=discord.ButtonStyle.primary)
    async def s3(self, interaction, button):
        await self.parent.accept_with_size(interaction, "3x3")

    @discord.ui.button(label="4x4", style=discord.ButtonStyle.primary)
    async def s4(self, interaction, button):
        await self.parent.accept_with_size(interaction, "4x4")

    @discord.ui.button(label="5x5", style=discord.ButtonStyle.primary)
    async def s5(self, interaction, button):
        await self.parent.accept_with_size(interaction, "5x5")


# ====== VIEW ОСНОВНАЯ ======

class RequestView(discord.ui.View):

    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.accepted_by_id = None
        self.rejected_by_id = None
        self.size = None

    def lock(self):

        for child in self.children:
            if child.custom_id != "rollback":
                child.disabled = True

    def unlock(self):

        for child in self.children:
            child.disabled = False

    # ===== ПРИНЯТИЕ =====

    async def accept_with_size(self, interaction, size):

        self.accepted_by_id = interaction.user.id
        self.rejected_by_id = None
        self.size = size

        msg = interaction.message
        old = msg.embeds[0]

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.green()
        )

        for f in old.fields:

            if f.name in ["✅ Принял", "❌ Отказал", "👥 Количество"]:
                continue

            if "Статус" in f.name:
                new.add_field(
                    name="📊 Статус",
                    value="🟢 Принято",
                    inline=True
                )
            else:
                new.add_field(
                    name=f.name,
                    value=f.value,
                    inline=f.inline
                )

        new.add_field(
            name="✅ Принял",
            value=f"{interaction.user.mention} ({get_msk_time()} МСК)",
            inline=False
        )

        new.add_field(
            name="👥 Количество",
            value=size,
            inline=False
        )

        self.lock()

        await msg.edit(embed=new, view=self)

        await interaction.response.send_message(
            f"✅ Принято {size}",
            ephemeral=True
        )

    # ===== КНОПКА ПРИНЯТЬ =====

    @discord.ui.button(
        label="✅ Принять",
        style=discord.ButtonStyle.success,
        custom_id="accept"
    )
    async def accept(self, interaction, button):

        await interaction.response.send_message(
            "Выберите количество:",
            view=SizeSelectView(self),
            ephemeral=True
        )

    # ===== ОТКАЗ =====

    @discord.ui.button(
        label="❌ Отказать",
        style=discord.ButtonStyle.danger,
        custom_id="reject"
    )
    async def reject(self, interaction, button):

        self.rejected_by_id = interaction.user.id
        self.accepted_by_id = None

        msg = interaction.message
        old = msg.embeds[0]

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.red()
        )

        for f in old.fields:

            if f.name in ["✅ Принял", "❌ Отказал", "👥 Количество"]:
                continue

            if "Статус" in f.name:
                new.add_field(
                    name="📊 Статус",
                    value="🔴 Отказано",
                    inline=True
                )
            else:
                new.add_field(
                    name=f.name,
                    value=f.value,
                    inline=f.inline
                )

        new.add_field(
            name="❌ Отказал",
            value=f"{interaction.user.mention} ({get_msk_time()} МСК)",
            inline=False
        )

        self.lock()

        await msg.edit(embed=new, view=self)

        await interaction.response.send_message(
            "❌ Отказано",
            ephemeral=True
        )

    # ===== ОТКАТ =====

    @discord.ui.button(
        label="↩️ Откат",
        style=discord.ButtonStyle.secondary,
        custom_id="rollback"
    )
    async def rollback(self, interaction, button):

        allowed = {
            self.author_id,
            self.accepted_by_id,
            self.rejected_by_id
        }

        if interaction.user.id not in allowed:
            await interaction.response.send_message(
                "❌ Нет доступа",
                ephemeral=True
            )
            return

        self.accepted_by_id = None
        self.rejected_by_id = None
        self.size = None

        msg = interaction.message
        old = msg.embeds[0]

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.orange()
        )

        for f in old.fields:

            if f.name in ["✅ Принял", "❌ Отказал", "👥 Количество"]:
                continue

            if "Статус" in f.name:
                new.add_field(
                    name="📊 Статус",
                    value="🟠 Ожидает ответа",
                    inline=True
                )
            else:
                new.add_field(
                    name=f.name,
                    value=f.value,
                    inline=f.inline
                )

        self.unlock()

        await msg.edit(embed=new, view=self)

        await interaction.response.send_message(
            "↩️ Откат выполнен",
            ephemeral=True
        )


# ====== КОМАНДА ======

@bot.tree.command(name="strela", description="Создать стрелу")
async def strela(
    interaction: discord.Interaction,
    tag: str,
    protiv: str,
    biz: str,
    vremya: str,
    oruzhie: str,
    lokaciya: str,
):

    if interaction.channel.id not in ALLOWED_CHANNELS:

        await interaction.response.send_message(
            "❌ Команда недоступна здесь",
            ephemeral=True
        )
        return

    ping = build_ping_text(protiv)

    content = f"🚨 **Новая стрела**\n{ping}"

    embed = format_request_embed(
        interaction.user,
        tag,
        protiv,
        vremya,
        lokaciya,
        oruzhie,
        biz
    )

    view = RequestView(interaction.user.id)

    await interaction.response.send_message(
        content=content,
        embed=embed,
        view=view,
        allowed_mentions=discord.AllowedMentions(roles=True)
    )


# ====== READY ======

@bot.event
async def on_ready():

    await bot.tree.sync()

    print(f"Бот запущен как {bot.user}")


bot.run(os.getenv("TOKEN"))