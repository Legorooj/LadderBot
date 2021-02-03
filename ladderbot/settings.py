# Copyright (c) 2021 Legorooj. This file is licensed under the terms of the Apache license, version 2.0. #
import discord
from discord.ext import commands
import datetime
import re
import typing
import asyncio
import inspect
import io

from . import db, logging

logger = logging.logger

owner_id: int
bot: commands.Bot
server_id: int
conf: typing.MutableMapping


class emojis:
    """
    http://unicode.org/emoji/charts/full-emoji-list.html

    Use one of:

     * (backslash)N{CLDR Short name},
     * (backslash)u{hex}

    The latter can be extracted
    """
    white_check_mark = '\u2705'
    x = '\N{cross mark}'
    blue_check_mark = '\u2611\ufe0f'


class messages:
    SIGNUP_MESSAGE = (
        f'Hey {{}}, a new week is about to start. Please react with {emojis.white_check_mark} '
        f'to receive a mobile match, or react with {emojis.blue_check_mark} to receive a steam game.'
        f' If you aren\'t registered with me yet, you can use the `$setname` and `$steamname` commands to do so.'
        f'\nSignups will close at midnight on Sunday, UTC.'
    )
    SIGNUPS_CLOSED_MESSAGE = (
        f'~~{{}}~~\nThese signups are now closed. Please wait until the next ones open.'
    )


async def discord_channel_log(*args, **kwargs):
    channel = bot.get_channel(int(conf['channels']['logging']))
    await channel.send(*args, **kwargs)
discord_channel_log.__signature__ = inspect.signature(discord.abc.Messageable.send)


def get_ladder_roles(guild=None) -> typing.Tuple[
    typing.List[discord.Role], discord.Role, discord.Role, discord.Role, discord.Role
]:
    if not guild:
        guild = bot.get_guild(int(conf['DEFAULT']['server_id']))
    
    rung_roles = [
        discord.utils.get(guild.roles, name=n) for n in (str(x) for x in range(1, 13))
    ]
    placement_matches = discord.utils.get(guild.roles, name='Placement Matches')
    ladder_player = discord.utils.get(guild.roles, name='Ladder Player')
    champion = discord.utils.get(guild.roles, name='Champion')
    newbie = discord.utils.get(guild.roles, name='Newbie')
    
    return rung_roles, placement_matches, ladder_player, champion, newbie


def get_rung_role(rung: int, guild=None):
    if not guild:
        guild = bot.get_guild(int(conf['DEFAULT']['server_id']))
    return discord.utils.get(guild.roles, name=str(rung))


def player_in_placement_matches(player_id: int):
    return db.session.query(db.Game).filter(
        db.Game.is_complete.is_(True) &
        db.Game.is_confirmed.is_(True) &
        db.or_(db.Game.host_id == player_id, db.Game.away_id == player_id)
    ).count() < 4


async def fix_roles(*members):
    for member in set(members):
        
        if not member or not isinstance(member, discord.Member):
            continue
        
        logger.debug(f'Fixing roles for {member}')
        
        player: db.Player = db.session.query(db.Player).get(member.id)
        if player is None:
            continue
        
        player.name = member.name
        
        rung_roles, p_m, ladder_player, champ, newbie = get_ladder_roles(member.guild)
        # Remove newbie if the member has it
        if newbie in member.roles:
            await member.remove_roles(newbie)
            
        # Add Ladder Player if the member doesn't have it
        if ladder_player not in member.roles:
            await member.add_roles(ladder_player)

        # Player doesn't have a rung role, give it to them
        if not (set(rung_roles) & set(member.roles)):
            await member.add_roles(get_rung_role(player.rung))
        
        # Placement matches
        player_in_pm = player_in_placement_matches(member.id)
        if player_in_pm:
            if player.complete().count() == 3:
                player.update_ratio()
                if player.win_ratio == 0/3:
                    player.rung = 1
                elif player.win_ratio == 1/3:
                    player.rung = 3
                elif player.win_ratio == 2/3:
                    player.rung = 5
                elif player.win_ratio == 3/3:
                    player.rung = 7
                else:
                    await discord_channel_log(f'Error with setting player rung after PM for {player.mention}. '
                                              f'Notifying <@!{owner_id}>')
            if p_m not in member.roles:
                await member.add_roles(p_m)
        elif not player_in_pm:
            await member.remove_roles(p_m)

        # Player's rung roles are off. Fix.
        if len(set(rung_roles) & set(member.roles)) > 1 or get_rung_role(player.rung) not in member.roles:
            await member.add_roles(get_rung_role(player.rung))
            await member.remove_roles(*set(rung_roles) ^ {get_rung_role(player.rung)})
        
        # Champion
        if player.rung == 12 and player.leaderboard_rank()[0] == 1:
            await member.add_roles(champ)
        else:
            await member.remove_roles(champ)

        db.save()


def is_mod(member: discord.Member):
    if member.id == owner_id:
        return True
    if discord.utils.get(member.guild.roles, name='Mod') in member.roles:
        return True
    return False


def is_mod_check():
    def predicate(ctx):
        return is_mod(ctx.author)
    return commands.check(predicate)


def is_registered():
    async def predicate(ctx: commands.Context):
        registered = db.session.query(db.Player).get(ctx.author.id) is not None
        if not registered and not ctx.invoked_with.startswith('help'):
            await ctx.send(
                f'{ctx.author.mention} is not registered with me. You must be registered to use this command.'
                f' You can register using the `$setname` and `$steamname` commands.'
            )
            return False
        return True
    return commands.check(predicate)


def is_valid_name(name: str):
    keywords = [
        "War", "Spirit", "Faith", "Glory", "Blood", "Empires", "Songs", "Dawn", "Majestic", "Parade",
        "Prophecy", "Prophesy", "Gold", "Fire", "Swords", "Queens", "Knights", "Kings", "Tribes",
        "Tales", "Quests", "Change", "Games", "Throne", "Conquest", "Struggle", "Victory", "Battles",
        "Legends", "Heroes", "Storms", "Clouds", "Gods", "Love", "Lords", "Lights", "Wrath", "Destruction",
        "Whales", "Ruins", "Monuments", "Wonder", "Clowns", "Bongo", "Duh!", "Squeal", "Squirrel", "Confusion",
        "Gruff", "Moan", "Chickens", "Spunge", "Gnomes", "Bell boys", "Gurkins", "Commotion", "LOL", "Shenanigans",
        "Hullabaloo", "Papercuts", "Eggs", "Mooni", "Gaami", "Banjo", "Flowers", "Fiddlesticks", "Fish Sticks", "Hills",
        "Fields", "Lands", "Forest", "Ocean", "Fruit", "Mountain", "Lake", "Paradise", "Jungle", "Desert", "River",
        "Sea", "Shores", "Valley", "Garden", "Moon", "Star", "Winter", "Spring", "Summer", "Autumn", "Divide", "Square",
        "Custard", "Goon", "Cat", "Spagetti", "Fish", "Fame", "Popcorn", "Dessert", "Space", "Glacier", "Ice", "Frozen",
        "Superb", "Unknown", "Test", "Beasts", "Birds", "Bugs", "Food", "Aliens", "Plains", "Volcano", "Cliff",
        "Rapids", "Reef", "Plateau", "Basin", "Oasis", "Marsh", "Swamp", "Monsoon", "Atoll", "Fjord", "Tundra", "Map",
        "Strait", "Savanna", "Butte", "Bay", "Giants", "Warriors", "Archers", "Defenders", "Catapults", "Riders",
        "Sleds", "Explorers", "Priests", "Ships", "Dragons", "Crabs", "Rebellion"
    ]
    return any(word.upper() in name.upper() for word in keywords)


def next_day(day: int) -> datetime.datetime:
    """
    Return a datetime object for midnight on the next `day`.
    
    The earliest date this will return is tomorrow.
    :param int day: Monday is 0 and Sunday is 6
    """
    now = datetime.datetime.utcnow()
    midnight = datetime.datetime.combine(now.today(), datetime.time.min) + datetime.timedelta(days=1)
    days_till = ((day - midnight.weekday()) + 7) % 7
    return midnight + datetime.timedelta(days=days_till)


async def get_member(ctx: commands.Context, member_str: str):
    try:
        member = await commands.MemberConverter().convert(ctx, member_str)
    except commands.BadArgument:
        try:
            member = await commands.MemberConverter().convert(ctx, member_str.strip('@'))
        except commands.BadArgument:
            pass
        else:
            return [member]
    else:
        return [member]
    
    members = ctx.guild.fetch_members()
    possibles = set()
    
    async for poss_member in members:
        name, nick = poss_member.name, (poss_member.nick or '')
        
        if member_str == nick:
            return [poss_member]
        elif (member_str in name) or (member_str in nick):
            possibles.add(poss_member)
        elif member_str.upper() == nick.upper():
            return [poss_member]
        elif (member_str.upper() in name.upper()) or (member_str.upper() in nick.upper()):
            possibles.add(poss_member)
    
    return list(possibles)


async def get_member_raw(ctx: commands.Context, m):
    match = re.match(r'([0-9]{15,21})$', m) or re.match(r'<@!?([0-9]+)>$', m)
    if match:
        user_id = int(match.group(1))
        return ctx.guild.get_member(user_id) or \
            discord.utils.get(ctx.message.mentions, id=user_id) or \
            db.session.query(db.Player).get(user_id)
    return None


async def match_member(member: str, target):
    if member.lower() in target.name.lower():
        return target
    if target.nick:
        if member.lower() in target.nick.lower():
            return target
    return None


def complete_since(ts, player):
    games = db.session.query(db.Game).filter(
        db.or_(db.Game.host_id == player.id, db.Game.away_id == player.id)
    ).filter(
        db.Game.win_claimed_ts > ts
    )
    return games.count() != 0


class GameLoader(commands.Converter):
    
    async def convert(self, ctx, game_id):
        try:
            game_id = int(game_id)
        except Exception:
            await ctx.send(
                f'Unable to convert "{game_id}" to a number.',
                allowed_mentions=discord.AllowedMentions(users=False, roles=False)
            )
            raise commands.UserInputError()
        game = db.session.query(db.Game).get(game_id)
        if not game:
            await ctx.send(f'Unable to find game with ID {game_id}')
            raise commands.UserInputError()
        return game


async def paginate(ctx, title, fields, page_start=0, page_end=10, page_size=10):
    # Based off code from PolyELO bot - https://github.com/Nelluk/Polytopia-ELO-bot

    page_end = page_end if len(fields) > page_end else len(fields)

    first_loop = True
    reaction, user = None, None
    sent_message = None

    while True:
        embed = discord.Embed(title=title)
        for entry in range(page_start, page_end):
            embed.add_field(name=fields[entry][0][:256], value=fields[entry][1][:1024], inline=False)
        if page_size < len(fields):
            embed.set_footer(text=f'{page_start + 1} - {page_end} of {len(fields)}')

        if first_loop is True:
            sent_message = await ctx.send(embed=embed)
            if len(fields) > page_size:
                await sent_message.add_reaction('⏪')
                await sent_message.add_reaction('⬅')
                await sent_message.add_reaction('➡')
                await sent_message.add_reaction('⏩')
            else:
                return
        else:
            try:
                await reaction.remove(user)
            except (discord.ext.commands.errors.CommandInvokeError, discord.errors.Forbidden):
                logger.warning(
                    'Unable to remove message reaction due to insufficient permissions. '
                    'Giving bot \'Manage Messages\' permission will improve usability.'
                )
            await sent_message.edit(embed=embed)

        def check(r, u):
            e = str(r.emoji)
            compare = False
            if page_size < len(fields):
                if page_start > 0 and e in '⏪⬅':
                    compare = True
                elif page_end < len(fields) and e in '➡⏩':
                    compare = True
            return (
                    (u == ctx.message.author or (u.permissions_in(ctx.channel).manage_messages and u != ctx.guild.me))
                    and (r.message.id == sent_message.id) and compare
            )

        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=45.0, check=check)
        except asyncio.TimeoutError:
            try:
                await sent_message.clear_reactions()
            except (discord.ext.commands.errors.CommandInvokeError, discord.errors.Forbidden):
                logger.warning(
                    'Unable to clear message reaction due to insufficient permissions. '
                    'Giving bot \'Manage Messages\' permission will improve usability.'
                )
            finally:
                break
        else:

            if '⏪' in str(reaction.emoji):
                # all the way to beginning
                page_start = 0
                page_end = page_start + page_size

            if '⏩' in str(reaction.emoji):
                # last page
                page_end = len(fields)
                page_start = page_end - page_size

            if '➡' in str(reaction.emoji):
                # next page
                page_start = page_start + page_size
                page_end = page_start + page_size

            if '⬅' in str(reaction.emoji):
                # previous page
                page_start = page_start - page_size
                page_end = page_start + page_size

            if page_start < 0:
                page_start = 0
                page_end = page_start + page_size

            if page_end > len(fields):
                page_end = len(fields)
                page_start = page_end - page_size if (page_end - page_size) >= 0 else 0

            first_loop = False


async def in_bot_channel(ctx):
    if is_mod(ctx.author):
        return True
    channel_id = int(conf['channels']['bot-commands'])
    if ctx.message.channel.id == channel_id:
        return True
    else:
        if ctx.invoked_with == 'help' and ctx.command.name != 'help':
            # Silently fail check when help cycles through every bot command for a check.
            pass
        else:
            await ctx.send(f'This command can only be used in a designated bot channel. Try: <#{channel_id}>')
    return False


def is_in_bot_channel():
    async def predicate(ctx):
        return await in_bot_channel(ctx)
    return commands.check(predicate)


def split_string(string):
    
    # Create a readable object for
    total_length = len(string)
    string = io.StringIO(string)
    buffer = ''
    
    while chunk := string.read(1900):
        # add the chunk onto the buffer
        buffer += chunk
        
        # Get the first 1900 chars from the buffer (leaving the rest there)
        section, buffer = buffer[:1900], buffer[1900:]
        
        # Get up to the last newline
        newline = section.rfind('\n')
        section, overflow = section[:newline], section[newline:]
        
        # If the total length of the string given is less than 1.9k chars, just yield the entire string
        if total_length < 1900:
            yield section + overflow
        else:
            # otherwise put the overflow in the buffer and yield the section
            buffer = overflow + buffer
            
            # yield the section that is now guaranteed to be less than 1.9k chars
            yield section
