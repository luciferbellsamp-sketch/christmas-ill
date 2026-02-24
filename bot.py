import os
import re
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from zoneinfo import ZoneInfo

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== НАСТРОЙКИ ПИНГОВ ПО ТЕГАМ ======
TAG_ROLE_PINGS = {
    "trb": [1475926501194072259],
    "трб": [1475926501194072259],

    "yakuza": [1475926311234043996],
    "якуза": [1475926311234043996],

    "warlock": [1475930203959328778],
    "варлок": [1475930203959328778],

    "lcn": [1475926258931204186],
    "лкн": [1475926258931204186],
    "la cosa nostra": [1475926258931204186],

    "rm": [1475926293257261277],
    "russian mafia": [1475926293257261277],
    "русская мафия": [1475926293257261277],
}

ALLOWED_SIZES = {"2x2", "3x3", "4x4", "5x5"}


def normalize_tag(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def build_ping_text(tag: str) -> str:
    roles = TAG_ROLE_PINGS.get(normalize_tag(tag), [])
    return " ".join(f"<@&{rid}>" for rid in roles)


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
        title="⚔️ Забив стрелы",
        color=discord.Color.orange(),
    )

    desc = []
    desc.append(f"**Забиваю стрелу {tag.upper()} против {protiv.upper()}**")

    if biz:
        desc.append(f"**Война за бизнес:** {biz}")

    desc.append(f"**Время проведения:** {vremya}")
    desc.append(f"**Локация:** {lokaciya}")
    desc.append(f"**Оружие:** {oruzhie}")

    e.description = "\n".join(desc)

    e.add_field(name="Автор", value=author.mention, inline=True)
    e.add_field(name="Статус", value=status, inline=True)

    e.set_footer(text="Кнопки ниже: принять / отказать / откат")

    return e


# ===== MODAL =====
class SizeModal(discord.ui.Modal, title="Принять стрелу"):
    size = discord.ui.TextInput(label="Количество (2x2 / 3x3 / 4x4 / 5x5)")

    def __init__(self, parent_view):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):

        val = normalize_tag(str(self.size.value)).replace("х", "x")

        if val not in ALLOWED_SIZES:
            await interaction.response.send_message(
                "❌ Разрешено только: 2x2, 3x3, 4x4, 5x5",
                ephemeral=True,
            )
            return

        await self.parent_view.accept_with_size(interaction, val)


# ===== VIEW =====
class RequestView(discord.ui.View):

    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id
        self.accepted_by_id = None
        self.size = None
        self.rejected_by_id = None

    def lock_if_finished(self):

        if self.accepted_by_id or self.rejected_by_id:

            for child in self.children:
                if isinstance(child, discord.ui.Button):

                    if child.custom_id == "req_rollback":
                        child.disabled = False
                    else:
                        child.disabled = True

    async def accept_with_size(self, interaction, size):

        self.accepted_by_id = interaction.user.id
        self.size = size
        self.rejected_by_id = None

        msg = interaction.message
        old = msg.embeds[0]

        # ВРЕМЯ МСК
        msk_time = datetime.now(
            ZoneInfo("Europe/Moscow")
        ).strftime("%d.%m.%Y %H:%M")

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.green()
        )

        for f in old.fields:

            if f.name in {"✅ Принял", "👥 Количество", "❌ Отказал"}:
                continue

            if f.name == "Статус":
                new.add_field(
                    name="Статус",
                    value="🟢 Принято",
                    inline=True
                )
            else:
                new.add_field(
                    name=f.name,
                    value=f.value,
                    inline=f.inline
                )

        # ДОБАВЛЕНО ВРЕМЯ
        new.add_field(
            name="✅ Принял",
            value=f"{interaction.user.mention} ({msk_time} МСК)",
            inline=False
        )

        new.add_field(
            name="👥 Количество",
            value=size,
            inline=False
        )

        new.set_footer(text="Статус стрелы")

        self.lock_if_finished()

        await msg.edit(embed=new, view=self)

        await interaction.response.send_message(
            f"✅ Принято в {msk_time} МСК",
            ephemeral=True
        )

    @discord.ui.button(
        label="✅ Принять",
        style=discord.ButtonStyle.success,
        custom_id="req_accept"
    )
    async def accept(self, interaction, button):
        await interaction.response.send_modal(SizeModal(self))

    @discord.ui.button(
        label="❌ Отказать",
        style=discord.ButtonStyle.danger,
        custom_id="req_reject"
    )
    async def reject(self, interaction, button):

        self.rejected_by_id = interaction.user.id

        msg = interaction.message
        old = msg.embeds[0]

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.red()
        )

        new.add_field(
            name="❌ Отказал",
            value=interaction.user.mention,
            inline=False
        )

        self.lock_if_finished()

        await msg.edit(embed=new, view=self)

        await interaction.response.send_message(
            "❌ Отказано",
            ephemeral=True
        )

    @discord.ui.button(
        label="↩️ Откат",
        style=discord.ButtonStyle.secondary,
        custom_id="req_rollback"
    )
    async def rollback(self, interaction, button):

        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Только автор может откатить",
                ephemeral=True
            )
            return

        msg = interaction.message
        old = msg.embeds[0]

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.orange()
        )

        new.add_field(
            name="Статус",
            value="🟠 Ожидает ответа",
            inline=True
        )

        for child in self.children:
            child.disabled = False

        await msg.edit(embed=new, view=self)

        await interaction.response.send_message(
            "↩️ Откат выполнен",
            ephemeral=True
        )


# ===== COMMAND =====

@bot.tree.command(name="strela", description="Создать забив стрелы (заявка + кнопки)")
@app_commands.describe(
    tag="Тег твоей фракции (кто забив): lcn/rm/trb/yakuza/warlock",
    protiv="Тег фракции соперника (кому забив): lcn/rm/trb/yakuza/warlock",
    biz="Бизнес / объект (ID бизнеса)",
    vremya="Время проведения (например: 23:40)",
    oruzhie="Оружие (например: дигл, шот, рифла)",
    lokaciya="Локация (например: каменка)",
)
async def strela(
    interaction: discord.Interaction,
    tag: str,
    protiv: str,
    biz: str,
    vremya: str,
    oruzhie: str,
    lokaciya: str,
):

    ping_from = build_ping_text(tag)
    ping_to = build_ping_text(protiv)

    content = " ".join(x for x in [ping_from, ping_to] if x).strip()

    embed = format_request_embed(
        author=interaction.user,
        tag=tag,
        protiv=protiv,
        vremya=vremya,
        lokaciya=lokaciya,
        oruzhie=oruzhie,
        biz=biz,
        status="🟠 Ожидает ответа",
    )

    embed.add_field(
        name="Кому",
        value=(ping_to if ping_to else protiv.upper()),
        inline=False
    )

    view = RequestView(author_id=interaction.user.id)

    allowed = discord.AllowedMentions(
        roles=True,
        users=True,
        everyone=False
    )

    await interaction.response.send_message(
        content=content,
        embed=embed,
        view=view,
        allowed_mentions=allowed
    )


@bot.event
async def on_ready():
    await bot.tree.sync()
    print("Бот запущен")


bot.run(os.getenv("TOKEN"))
