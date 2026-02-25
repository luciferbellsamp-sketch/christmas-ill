import os
import re
import discord
import asyncio
from datetime import datetime, timedelta
from discord.ext import commands
from discord import app_commands
from zoneinfo import ZoneInfo


def parse_strela_time(vremya_text: str) -> datetime:
    tz = ZoneInfo("Europe/Moscow")
    s = vremya_text.strip()

    fmts = ["%d.%m.%Y %H:%M", "%H:%M %d.%m.%Y", "%H:%M"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            now = datetime.now(tz)

            if fmt == "%H:%M":
                dt = dt.replace(year=now.year, month=now.month, day=now.day)
                dt = dt.replace(tzinfo=tz)
                if dt <= now:
                    dt = dt + timedelta(days=1)
                return dt

            return dt.replace(tzinfo=tz)
        except ValueError:
            pass

    raise ValueError("Неверный формат времени")


def strela_already_started_from_embed(emb: discord.Embed) -> bool:
    vremya_val = None
    for f in emb.fields:
        if f.name == "\u200b":  # скрытое поле
            vremya_val = (f.value or "").strip()
            break

    if not vremya_val:
        return False

    try:
        dt_target = parse_strela_time(vremya_val)
    except:
        return False

    now = datetime.now(ZoneInfo("Europe/Moscow"))
    return now >= dt_target


async def countdown_updater(message: discord.Message, dt_target: datetime):
    while True:
        try:
            message = await message.channel.fetch_message(message.id)

            emb = message.embeds[0]

            status_value = ""
            for f in emb.fields:
                if "Статус" in f.name:
                    status_value = f.value or ""
                    break

            is_accepted = "Принято" in status_value or "🟢" in status_value

            now = datetime.now(ZoneInfo("Europe/Moscow"))
            left_sec = int((dt_target - now).total_seconds())

            if left_sec <= 0:
                if is_accepted:
                    timer_text = "✅ Уже началось / прошло"
                else:
                    timer_text = "⏳ Время наступило (не принято)"
            else:
                    hours = left_sec // 3600
                    mins = (left_sec % 3600) // 60
                    timer_text = f"{hours:02d}ч {mins:02d}м"

            new = discord.Embed(
                title=emb.title,
                description=emb.description,
                color=emb.color
            )

            for f in emb.fields:
                if f.name == "⏳ До стрелы":
                    new.add_field(
                        name="⏳ До стрелы",
                        value=timer_text,
                        inline=False
                    )
                else:
                    new.add_field(
                        name=f.name,
                        value=f.value,
                        inline=f.inline
                    )

            if emb.footer:
                new.set_footer(text=emb.footer.text)

            await message.edit(embed=new)

            if left_sec <= 0 and is_accepted:

                description = emb.description

                tag = "UNKNOWN"
                protiv = "UNKNOWN"
                biz = None

                m1 = re.search(r"Фракция:\s*\*\*`([^`]+)`\*\*", description)
                m2 = re.search(r"Против:\s*\*\*`([^`]+)`\*\*", description)
                m3 = re.search(r"Бизнес:\s*\*\*`([^`]+)`\*\*", description)

                if m1:
                    tag = m1.group(1)

                if m2:
                    protiv = m2.group(1)

                if m3:
                    biz = m3.group(1)

                author_val = ""
                enemy_roles = ""

                for f in emb.fields:
                    if f.name == "Автор":
                        author_val = f.value

                    if f.name == "Кому":
                        enemy_roles = f.value

                if biz:
                    notify_text = (
                        f"🚨 Стрела между {tag} и {protiv} за бизнес {biz} началась!\n"
                        f"{author_val}\n{enemy_roles}"
                    )
                else:
                    notify_text = (
                        f"🚨 Стрела между {tag} и {protiv} началась!\n"
                        f"{author_val}\n{enemy_roles}"
                    )

                await message.reply(
                    content=notify_text,
                    delete_after=300,
                    allowed_mentions=discord.AllowedMentions(
                        roles=True,
                        users=True
                    )
                )

                return

            await asyncio.sleep(60)

        except Exception as e:
            print("COUNTDOWN ERROR:", e)
            return


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


ALLOWED_CHANNELS = [
    1468386694175789188,
    1199092928472174734,
    1350588850744987791,
]


FACTION_PINGS = {
    "rm": {"leader": 1199092925913632839, "deputy": 1199092925506797596},
    "lcn": {"leader": 1199092925859123281, "deputy": 1199092925506797595},
}


ALLOWED_SIZES = {"2x2", "3x3", "4x4", "5x5"}


def normalize_tag(text: str):
    return text.lower().strip()


def build_ping_text(tag: str):

    roles = FACTION_PINGS.get(normalize_tag(tag))

    if not roles:
        return ""

    return f"<@&{roles['leader']}> <@&{roles['deputy']}>"


class SizeModal(discord.ui.Modal):

    def __init__(self, parent_view):
        super().__init__(title="Количество")

        self.parent_view = parent_view

        self.size = discord.ui.TextInput(
            label="Количество",
            placeholder="3x3"
        )

        self.add_item(self.size)

    async def on_submit(self, interaction):

        await self.parent_view.accept_with_size(
            interaction,
            self.size.value
        )


class RequestView(discord.ui.View):

    def __init__(self, author_id):

        super().__init__(timeout=None)

        self.author_id = author_id

        self.accepted_by_id = None


    @discord.ui.button(
        label="✅ Принять",
        style=discord.ButtonStyle.success
    )
    async def accept(self, interaction, button):

        if strela_already_started_from_embed(
            interaction.message.embeds[0]
        ):
            await interaction.response.send_message(
                "❌ Стрела уже началась",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            SizeModal(self)
        )


    async def accept_with_size(
        self,
        interaction,
        size
    ):

        emb = interaction.message.embeds[0]

        new = discord.Embed(
            title=emb.title,
            description=emb.description,
            color=discord.Color.green()
        )

        for f in emb.fields:

            if "Статус" in f.name:

                new.add_field(
                    name="📊 Статус",
                    value="🟢 Принято"
                )

            else:

                new.add_field(
                    name=f.name,
                    value=f.value,
                    inline=f.inline
                )

        new.add_field(
            name="👥 Количество",
            value=size
        )

        await interaction.message.edit(
            embed=new,
            view=self
        )

        await interaction.response.send_message(
            "✅ Принято",
            ephemeral=True
        )


@bot.tree.command(name="strela")
async def strela(
    interaction,
    tag: str,
    protiv: str,
    biz: str,
    vremya: str,
    oruzhie: str,
    lokaciya: str
):

    embed = discord.Embed(
        title="Christmas Illegals",
        description=(
            f"⚔️ **ЗАБИВ СТРЕЛЫ**\n"
            f"┌ 🏴 Фракция: **`{tag.upper()}`**\n"
            f"└ 🎯 Против: **`{protiv.upper()}`**\n"
            f"🏢 Бизнес: **`{biz}`**\n"
            f"🕒 Время: **`{vremya}`**\n"
            f"📍 Локация: **`{lokaciya}`**\n"
            f"🔫 Оружие: **`{oruzhie}`**"
        ),
        color=discord.Color.orange()
    )

    embed.add_field(
        name="Автор",
        value=interaction.user.mention
    )

    embed.add_field(
        name="📊 Статус",
        value="🟠 Ожидает ответа"
    )

    embed.add_field(
        name="⏳ До стрелы",
        value="Вычисляю..."
    )

    embed.add_field(
        name="\u200b",   # СКРЫТОЕ поле
        value=vremya,
        inline=False
    )

    embed.add_field(
        name="Кому",
        value=build_ping_text(protiv)
    )

    view = RequestView(interaction.user.id)

    await interaction.response.send_message(
        embed=embed,
        view=view
    )

    msg = await interaction.original_response()

    try:

        dt = parse_strela_time(vremya)

        asyncio.create_task(
            countdown_updater(msg, dt)
        )

    except Exception as e:

        print("TIMER ERROR:", e)


@bot.event
async def on_ready():

    await bot.tree.sync()

    print("Bot ready")


bot.run(os.getenv("TOKEN"))