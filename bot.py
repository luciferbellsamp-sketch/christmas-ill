import os
import re
import discord
import asyncio
from datetime import datetime, timedelta
from discord.ext import commands
from discord import app_commands
from zoneinfo import ZoneInfo


def parse_strela_time(vremya_text: str) -> datetime:
    """
    Принимает:
    - "21:10"
    - "25.02.2026 21:10"
    - "21:10 25.02.2026"
    Возвращает datetime в TZ Europe/Moscow.
    """
    tz = ZoneInfo("Europe/Moscow")
    s = vremya_text.strip()

    fmts = ["%d.%m.%Y %H:%M", "%H:%M %d.%m.%Y", "%H:%M"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            now = datetime.now(tz)

            if fmt == "%H:%M":
                # если только время — считаем сегодня по МСК, если уже прошло — завтра
                dt = dt.replace(year=now.year, month=now.month, day=now.day)
                dt = dt.replace(tzinfo=tz)
                if dt <= now:
                    dt = dt + timedelta(days=1)  # завтра
                return dt

            # есть дата
            return dt.replace(tzinfo=tz)
        except ValueError:
            pass

    raise ValueError("Неверный формат времени. Пример: 21:10 или 25.02.2026 21:10")


def format_delta(dt_target: datetime) -> str:
    tz = ZoneInfo("Europe/Moscow")
    now = datetime.now(tz)
    diff = dt_target - now
    sec = int(diff.total_seconds())

    if sec <= 0:
        return "✅ Уже началось / прошло"

    days = sec // 86400
    sec %= 86400
    hours = sec // 3600
    sec %= 3600
    mins = sec // 60

    if days > 0:
        return f"{days}д {hours:02d}ч {mins:02d}м"
    return f"{hours:02d}ч {mins:02d}м"


async def countdown_updater(message: discord.Message, dt_target: datetime):
    while True:
        try:
            message = await message.channel.fetch_message(message.id)
            if not message.embeds:
                return

            emb = message.embeds[0]

            # Определяем статус из поля "Статус"
            status_value = ""
            for f in emb.fields:
                if "Статус" in f.name:
                    status_value = (f.value or "").strip()
                    break

            is_accepted = "Принято" in status_value or "🟢" in status_value

            # Считаем остаток времени
            tz = ZoneInfo("Europe/Moscow")
            now = datetime.now(tz)
            left_sec = int((dt_target - now).total_seconds())

            # Значение таймера в поле
            if left_sec <= 0:
                if is_accepted:
                    timer_text = "✅ Уже началось / прошло"
                else:
                    timer_text = "⏳ Время наступило (не принято)"
            else:
                # обычный отсчёт (без "✅")
                days = left_sec // 86400
                rem = left_sec % 86400
                hours = rem // 3600
                rem %= 3600
                mins = rem // 60
                if days > 0:
                    timer_text = f"{days}д {hours:02d}ч {mins:02d}м"
                else:
                    timer_text = f"{hours:02d}ч {mins:02d}м"

            # Пересобираем embed: меняем ТОЛЬКО поле таймера
            new = discord.Embed(title=emb.title, description=emb.description, color=emb.color)

            found_timer = False
            for f in emb.fields:
                if f.name == "⏳ До стрелы":
                    new.add_field(name="⏳ До стрелы", value=timer_text, inline=False)
                    found_timer = True
                else:
                    new.add_field(name=f.name, value=f.value, inline=f.inline)

            if not found_timer:
                new.add_field(name="⏳ До стрелы", value=timer_text, inline=False)

            if emb.footer:
                new.set_footer(text=emb.footer.text)

            await message.edit(embed=new)

            # Если время наступило:
            if left_sec <= 0:
                # 1) НЕ принято -> ничего не отправляем, просто стоп
                if not is_accepted:
                    return

                # 2) Принято -> отправляем reply и удаляем через 7 минут
                description = emb.description or ""

                # Автор (из поля "Автор")
                author_val = ""
                for f in emb.fields:
                    if f.name == "Автор":
                        author_val = f.value or ""
                        break

                # Кому (из поля "Кому") — там у тебя пинги лидера/зама
                enemy_roles = ""
                for f in emb.fields:
                    if f.name == "Кому":
                        enemy_roles = f.value or ""
                        break

                # Фракции + бизнес из description
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

                allowed = discord.AllowedMentions(roles=True, users=True, everyone=False)

                await message.reply(
                     content=notify_text,
                     allowed_mentions=allowed,
                     mention_author=True,
                     delete_after=300
                 )

                return

            await asyncio.sleep(60)

        except Exception as e:
            print("COUNTDOWN ERROR:", e)
            return


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== НАСТРОЙКИ ПИНГОВ ПО ТЕГАМ ======
ALLOWED_CHANNELS = [
    1468386694175789188,  # канал 1
    1199092928472174734,  # канал 2
    1350588850744987791,  # канал 3
]

FACTION_PINGS = {
    "rm":      {"leader": 1199092925913632839, "deputy": 1199092925506797596},
    "lcn":     {"leader": 1199092925859123281, "deputy": 1199092925506797595},
    "warlock": {"leader": 1199092925859123280, "deputy": 1199092925506797594},
    "yakuza":  {"leader": 1199092925859123279, "deputy": 1199092925506797593},
    "trb":     {"leader": 1199710835384275024, "deputy": 1199710842715897947},
}

ALLOWED_SIZES = {"2x2", "3x3", "4x4", "5x5"}


def normalize_tag(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())

def strela_already_started_from_embed(emb: discord.Embed) -> bool:
    vremya_val = None
    for f in emb.fields:
        if f.name == "__strela_time__":
            vremya_val = (f.value or "").strip()
            break

    if not vremya_val:
        return False

    try:
        dt_target = parse_strela_time(vremya_val)
    except Exception:
        return False

    now = datetime.now(ZoneInfo("Europe/Moscow"))
    return now >= dt_target
def build_ping_text(tag: str) -> str:
    key = normalize_tag(tag)
    roles = FACTION_PINGS.get(key)
    if not roles:
        return ""
    return f"<@&{roles['leader']}> <@&{roles['deputy']}>"


def format_request_embed(
    author: discord.Member,
    tag: str,
    protiv: str,
    vremya: str,
    lokaciya: str,
    oruzhie: str,
    biz: str | None = None,
    status: str = "🟠 Ожидает ответа",
    accepted_by: discord.Member | None = None,
    size: str | None = None,
) -> discord.Embed:
    e = discord.Embed(
        title="Christmas Illegals",
        color=discord.Color.orange() if accepted_by is None else discord.Color.green(),
        description=""
    )

    lines = []
    lines.append(
        f"⚔️ **ЗАБИВ СТРЕЛЫ**\n"
        f"┌ 🏴 Фракция: **`{tag.upper()}`**\n"
        f"└ 🎯 Против: **`{protiv.upper()}`**"
    )

    if biz:
        lines.append(f"🏢 Бизнес: **`{biz}`**")

    lines.append(f"🕒 Время: **`{vremya}`**")
    lines.append(f"📍 Локация: **`{lokaciya}`**")
    lines.append(f"🔫 Оружие: **`{oruzhie}`**")
    e.description = "\n".join(lines)

    e.add_field(name="Автор", value=author.mention, inline=True)
    e.add_field(name="Статус", value=status, inline=True)

    if accepted_by:
        e.add_field(name="✅ Принял", value=accepted_by.mention, inline=False)
    if size:
        e.add_field(name="👥 Количество", value=size, inline=False)

    e.set_footer(text="Кнопки ниже: принять / отказать / откат")
    return e


# ====== MODAL ДЛЯ ВВОДА КОЛИЧЕСТВА ======
class SizeModal(discord.ui.Modal, title="Принять стрелу: количество"):
    size = discord.ui.TextInput(
        label="Количество (2x2 / 3x3 / 4x4 / 5x5)",
        placeholder="Например: 3x3",
        required=True,
        max_length=5
    )

    def __init__(self, parent_view: "RequestView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        val = normalize_tag(str(self.size.value))
        val = val.replace("х", "x")

        if val not in ALLOWED_SIZES:
            await interaction.response.send_message(
                "❌ Неверный формат. Разрешено только: 2x2, 3x3, 4x4, 5x5",
                ephemeral=True
            )
            return

        await self.parent_view.accept_with_size(interaction, val)


# ====== VIEW С КНОПКАМИ ======
class RequestView(discord.ui.View):
    def __init__(self, author_id: int):
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

    async def accept_with_size(self, interaction: discord.Interaction, size: str):
        self.accepted_by_id = interaction.user.id
        self.size = size
        self.rejected_by_id = None

        msk_time = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")

        msg = interaction.message
        old = msg.embeds[0]

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.green()
        )

        for f in old.fields:
            # пропускаем служебные поля
            if f.name in {"✅ Принял", "👥 Количество", "❌ Отказал"}:
                continue

            # меняем статус
            if "Статус" in f.name:
                new.add_field(
                    name="📊 Статус",
                    value="🟢 Принято",
                    inline=True
                )
            else:
                new.add_field(name=f.name, value=f.value, inline=f.inline)

        # кто принял + время
        new.add_field(
            name="✅ Принял",
            value=f"{interaction.user.mention} ({msk_time} МСК)",
            inline=False
        )

        # количество
        new.add_field(
            name="👥 Количество",
            value=size,
            inline=False
        )

        new.set_footer(text="Используйте кнопки ниже")

        self.lock_if_finished()
        await msg.edit(embed=new, view=self)

        await interaction.response.send_message(
            f"✅ Принято {size}",
            ephemeral=True
        )
        
    discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="req_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Блокировка если стрела уже началась
        emb = interaction.message.embeds[0]
        if strela_already_started_from_embed(emb):
            await interaction.response.send_message(
                "❌ Нельзя принять — стрела уже началась.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(SizeModal(self))
    @discord.ui.button(label="❌ Отказать", style=discord.ButtonStyle.danger, custom_id="req_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        emb = interaction.message.embeds[0]
        if strela_already_started_from_embed(emb):
            await interaction.response.send_message(
                "❌ Нельзя отказать — стрела уже началась.",
                ephemeral=True
            )
            return
        msk_time = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y %H:%M")

        self.rejected_by_id = interaction.user.id
        self.accepted_by_id = None
        self.size = None

        msg = interaction.message
        old = msg.embeds[0]

        new = discord.Embed(
            title=old.title,
            description=old.description,
            color=discord.Color.red()
        )

        for f in old.fields:
            if f.name in {"✅ Принял", "👥 Количество", "❌ Отказал"}:
                continue

            if "Статус" in f.name:
                new.add_field(
                    name="📊 Статус",
                    value="🔴 Отказано",
                    inline=True
                )
            else:
                new.add_field(name=f.name, value=f.value, inline=f.inline)

        new.add_field(
            name="❌ Отказал",
            value=f"{interaction.user.mention} ({msk_time} МСК)",
            inline=False
        )

        new.set_footer(text=old.footer.text if old.footer else "")

        self.lock_if_finished()
        await msg.edit(embed=new, view=self)

        await interaction.response.send_message("❌ Отказано.", ephemeral=True)

    @discord.ui.button(label="↩️ Откат", style=discord.ButtonStyle.secondary, custom_id="req_rollback")
    async def rollback(self, interaction: discord.Interaction, button: discord.ui.Button):
        allowed = {self.author_id, self.accepted_by_id, self.rejected_by_id}
        allowed.discard(None)

        if interaction.user.id not in allowed:
            await interaction.response.send_message(
                "❌ Откат может сделать только автор или принявший/отказавший.",
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
            if f.name in {"✅ Принял", "👥 Количество", "❌ Отказал"}:
                continue

            # важно: ловим и "Статус", и "📊 Статус"
            if "Статус" in f.name:
                new.add_field(name="Статус", value="🟠 Ожидает ответа", inline=True)
            else:
                new.add_field(name=f.name, value=f.value, inline=f.inline)

        new.set_footer(text=old.footer.text if old.footer else "")

        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False

        await msg.edit(embed=new, view=self)
        await interaction.response.send_message("↩️ Откат выполнен.", ephemeral=True)


# ====== КОМАНДА СОЗДАНИЯ ЗАЯВКИ ======
@bot.tree.command(name="strela", description="Создать забив стрелы (заявка + кнопки)")
@app_commands.describe(
    tag="Тег твоей фракции (кто забив): lcn/rm/trb/yakuza/warlock ...",
    protiv="Тег фракции соперника (кому забив): lcn/rm/trb/yakuza/warlock ...",
    biz="Бизнес/объект (id бизнеса)",
    vremya="Время (xx:xx)",
    oruzhie="Оружие (как напишешь)",
    lokaciya="Локация (как напишешь)",
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
    if interaction.channel.id not in ALLOWED_CHANNELS:
        await interaction.response.send_message(
            "❌ Эту команду можно использовать только в канале стрел.",
            ephemeral=True
        )
        return

    ping_from = build_ping_text(tag)
    ping_to = build_ping_text(protiv)

    content = f"**🚨 Новая стрела**\n{ping_to}"

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

    embed.add_field(name="⏳ До стрелы", value="Вычисляю...", inline=False)
    embed.add_field(name="__strela_time__", value=vremya, inline=False)

    embed.add_field(name="Кому", value=(ping_to if ping_to else protiv), inline=False)

    view = RequestView(author_id=interaction.user.id)
    allowed = discord.AllowedMentions(roles=True, users=True, everyone=False)

    await interaction.response.send_message(
        content=content,
        embed=embed,
        view=view,
        allowed_mentions=allowed
    )

    msg = await interaction.original_response()

    try:
        dt_target = parse_strela_time(vremya)
        asyncio.create_task(countdown_updater(msg, dt_target))
    except Exception as e:
        print("TIMER START ERROR:", e)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Бот запущен как {bot.user}")


bot.run(os.getenv("TOKEN"))