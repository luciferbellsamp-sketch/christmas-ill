import os
import re
import discord
from discord.ext import commands
from discord import app_commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ====== НАСТРОЙКИ ПИНГОВ ПО ТЕГАМ ======
# ВСТАВЬ СЮДА ID РОЛЕЙ (ПКМ по роли -> Copy Role ID, включи Developer Mode в Discord)
TAG_ROLE_PINGS = {
    # TRB
    "trb": [1475926501194072259],
    "трб": [1475926501194072259],

    # Yakuza
    "yakuza": [1475926311234043996],
    "якуза": [1475926311234043996],

    # Warlock
    "warlock": [1475930203959328778],
    "варлок": [1475930203959328778],

    # La Cosa Nostra (LCN)
    "lcn": [1475926258931204186],
    "лкн": [1475926258931204186],
    "la cosa nostra": [1475926258931204186],
    "lacosa nostra": [1475926258931204186],

    # Russian Mafia (RM)
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
        title="⚔️ Забив стрелы",
        color=discord.Color.orange() if accepted_by is None else discord.Color.green(),
        description=""
    )

    # Верхняя часть “как в твоём окне”
    lines = []
    lines.append(f"**Забиваю стрелу {tag.upper()} против {protiv}**")
    if biz:
        lines.append(f"**Война за бизнес:** {biz}")
    lines.append(f"**Время проведения:** {vremya}")
    lines.append(f"**Локация:** {lokaciya}")
    lines.append(f"**Оружие:** {oruzhie}")
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
        # привести к виду 3x3 (на случай русской х)
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
        self.accepted_by_id: int | None = None
        self.size: str | None = None
        self.rejected_by_id: int | None = None

    def lock_if_finished(self):
        # блокируем кнопки после финала (можно оставить "Откат" активным)
        if self.accepted_by_id or self.rejected_by_id:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    if child.custom_id in {"req_rollback"}:
                        child.disabled = False
                    else:
                        child.disabled = True

    async def accept_with_size(self, interaction: discord.Interaction, size: str):
        self.accepted_by_id = interaction.user.id
        self.size = size
        self.rejected_by_id = None

        # обновляем embed
        msg = interaction.message
        old = msg.embeds[0]

        # Достанем “шапочные” данные обратно из embed.description
        # (в реале лучше хранить в message.content/json, но для простоты берём оттуда)
        # Тут просто меняем цвет/поля
        # Пересобираем новый embed на базе старого
        new = discord.Embed(title=old.title, description=old.description, color=discord.Color.green())

        # Переносим поля кроме служебных, затем добавляем “Принял/Количество”
        for f in old.fields:
            if f.name in {"✅ Принял", "👥 Количество"}:
                continue
            if f.name == "Статус":
                new.add_field(name="Статус", value="🟢 Принято", inline=True)
            else:
                new.add_field(name=f.name, value=f.value, inline=f.inline)

        new.add_field(name="✅ Принял", value=interaction.user.mention, inline=False)
        new.add_field(name="👥 Количество", value=size, inline=False)
        new.set_footer(text=old.footer.text if old.footer else "")

        self.lock_if_finished()
        await msg.edit(embed=new, view=self)
        await interaction.response.send_message(f"✅ Принято. Количество: **{size}**", ephemeral=True)

    @discord.ui.button(label="✅ Принять", style=discord.ButtonStyle.success, custom_id="req_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Открываем modal ввода количества
        await interaction.response.send_modal(SizeModal(self))

    @discord.ui.button(label="❌ Отказать", style=discord.ButtonStyle.danger, custom_id="req_reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.rejected_by_id = interaction.user.id
        self.accepted_by_id = None
        self.size = None

        msg = interaction.message
        old = msg.embeds[0]
        new = discord.Embed(title=old.title, description=old.description, color=discord.Color.red())

        for f in old.fields:
            if f.name in {"✅ Принял", "👥 Количество"}:
                continue
            if f.name == "Статус":
                new.add_field(name="Статус", value="🔴 Отказано", inline=True)
            else:
                new.add_field(name=f.name, value=f.value, inline=f.inline)

        new.add_field(name="❌ Отказал", value=interaction.user.mention, inline=False)
        new.set_footer(text=old.footer.text if old.footer else "")

        self.lock_if_finished()
        await msg.edit(embed=new, view=self)
        await interaction.response.send_message("❌ Отказано.", ephemeral=True)

    @discord.ui.button(label="↩️ Откат", style=discord.ButtonStyle.secondary, custom_id="req_rollback")
    async def rollback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Чтобы не было злоупотребления: откат может делать автор или тот, кто принял/отказал
        allowed = {self.author_id, self.accepted_by_id, self.rejected_by_id}
        allowed.discard(None)

        if interaction.user.id not in allowed:
            await interaction.response.send_message("❌ Откат может сделать только автор или принявший/отказавший.", ephemeral=True)
            return

        self.accepted_by_id = None
        self.rejected_by_id = None
        self.size = None

        msg = interaction.message
        old = msg.embeds[0]
        # Возврат в “ожидание”
        new = discord.Embed(title=old.title, description=old.description, color=discord.Color.orange())

        # пересоберём поля: Автор/Статус, уберём служебные
        for f in old.fields:
            if f.name in {"✅ Принял", "👥 Количество", "❌ Отказал"}:
                continue
            if f.name == "Статус":
                new.add_field(name="Статус", value="🟠 Ожидает ответа", inline=True)
            else:
                new.add_field(name=f.name, value=f.value, inline=f.inline)

        new.set_footer(text=old.footer.text if old.footer else "")

        # разблокируем кнопки
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False

        await msg.edit(embed=new, view=self)
        await interaction.response.send_message("↩️ Откат выполнен.", ephemeral=True)


# ====== КОМАНДА СОЗДАНИЯ ЗАЯВКИ ======
@bot.tree.command(name="strela", description="Создать забив стрелы (заявка + кнопки)")
@app_commands.describe(
    tag="Тег твоей фракции (кто забивает): lcn/rm/trb/yakuza/warlock ...",
    protiv="Тег фракции соперника (кому забивают): lcn/rm/trb/yakuza/warlock ...",
    vremya="Время (как напишешь)",
    oruzhie="Оружие (как напишешь)",
    lokaciya="Локация (как напишешь)",
    biz="Бизнес/объект (необязательно)",
)
async def strela(
    interaction: discord.Interaction,
    tag: str,
    protiv: str,
    vremya: str,
    oruzhie: str,
    lokaciya: str,
    biz: str | None = None,
):
    ping_from = build_ping_text(tag)
    ping_to = build_ping_text(protiv)

    # пингуем обе стороны (и убираем лишние пробелы)
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

    # Добавим явное поле "Кому" (чтобы в эмбеде было видно, кому забивают)
    embed.add_field(name="Кому", value=(ping_to if ping_to else komu_tag), inline=False)

    view = RequestView(author_id=interaction.user.id)
    allowed = discord.AllowedMentions(roles=True, users=True, everyone=False)

    await interaction.response.send_message(content=content, embed=embed, view=view, allowed_mentions=allowed)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"Бот запущен как {bot.user}")


bot.run(os.getenv("TOKEN"))
