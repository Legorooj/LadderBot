# Copyright (c) 2020 Legorooj. This file is licensed under the terms of the Apache license, version 2.0. #
import datetime
from discord import Member, TextChannel, utils
from discord.ext import commands, tasks

from ladderbot import settings, db
from .logging import logger


class Matchmaking(commands.Cog):
    
    def __init__(self, bot: commands.Bot, conf: dict):
        self.bot = bot
        self.conf = conf
    
    async def announce_start(self, guild, channel, game: db.Game):
        drafts: TextChannel = self.bot.get_channel(int(self.conf['channels']['drafts']))
        
        host: Member = guild.get_member(game.host_id)
        away: Member = guild.get_member(game.away_id)
        
        message = (
            f'New game ID {game.id} started! Roster: {host.mention} {away.mention}'
        )
        
        await drafts.send(message, embed=game.embed(guild))
        await channel.send(
            f'Game ID {game.id} has been started! Check {drafts.mention} for more information.'
        )
    
    async def announce_end(self, guild, channel, game: db.Game):
        drafts: TextChannel = self.bot.get_channel(int(self.conf['channels']['drafts']))
        
        host: Member = self.bot.get_user(game.host_id)
        away: Member = self.bot.get_user(game.away_id)
        winner: Member = self.bot.get_user(game.winner_id)
        
        message = (
            f'Game ID {game.id} completed! Congrats {winner.mention}! Roster: {host.mention} {away.mention}'
        )
        await drafts.send(message, embed=game.embed(guild))
        await channel.send('All sides have confirmed this victory. Good game!')
    
    @tasks.loop(minutes=30)
    async def autoconfirm_loop(self):
        logger.debug('Running autoconfirm loop')
        
        unconfirmed = db.session.query(db.Game).filter(
            db.Game.is_complete.is_(True) &
            db.Game.is_confirmed.is_(False) &
            db.Game.win_claimed_ts < datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        )
        
        for game in unconfirmed.all():
            game: db.Game
            game.win_confirmed(game.winner_id)
            await self.announce_end(
                self.bot.get_guild(settings.server_id), self.bot.get_channel(self.conf['channels']['logs']), game
            )
            await settings.discord_channel_log(
                f'Game {game.id} autoconfirmed. Win claimed more than 24 hours ago. 1 of 2 sides had confirmed.'
            )
            logger.info(
                f'Game {game.id} autoconfirmed. Win claimed more than 24 hours ago. 1 of 2 sides had confirmed.'
            )
        if unconfirmed.count() != 0:
            logger.info(f'Autoconfirm process complete. {unconfirmed.count()} games confirmed.')
            await settings.discord_channel_log(f'Autoconfirm process complete. {unconfirmed.count()} games confirmed.')
    
    @commands.command(aliases=['steamname'])
    async def setname(self, ctx: commands.Context, *, args=None):
        """
        Register yourself with the bot.
        
        **Examples**:
        - `[p]setname IN GAME NAME`
        - `[p]steamname STEAMNAME`
        """
        args = args.split() if args else []
        if not args:
            await ctx.send(
                f'No arguments supplied. Please run `{ctx.prefix}help {ctx.invoked_with}` to find out how to use '
                f'this command.'
            )
        
        dest: Member = await settings.get_member_raw(ctx, args[0]) or ctx.author
        if dest.id != ctx.author.id:
            logger.debug('setname invoked by a third party.')
            if not settings.is_mod(ctx.author):
                logger.debug('Insufficient user level.')
                return await ctx.send(f'You aren\'t authorized to set another user\'s name.')
            name = ' '.join(args[1:])
        else:
            name = ' '.join(args[0:])
        
        if not name:
            return await ctx.send('No name provided.')
        
        if name == 'none':
            name = None
        
        steam = ctx.invoked_with == 'steamname'
        
        player = db.session.query(db.Player).filter(db.Player.id == dest.id).first()
        created = True if player else False
        
        if player:
            setattr(player, 'steam_name' if steam else 'ign', name)
            db.save()
            
            await ctx.send(
                f'{dest.mention} has been updated'
            )
        else:
            if steam:
                player = db.Player(
                    id=dest.id,
                    steam_name=name
                )
            else:
                player = db.Player(
                    id=dest.id,
                    ign=name
                )
            db.add(player)
            
            await ctx.send(
                f'{dest.mention} has successfully registered themselves with me on '
                f'{"**steam**" if steam else "**mobile**"}.'
            )
        
        if name is not None:
            await settings.fix_roles(ctx.author, dest)
            if steam:
                alts = db.session.query(db.Player).filter(
                    db.Player.steam_name.ilike(name)
                )
            else:
                alts = db.session.query(db.Player).filter(
                    db.Player.ign.ilike(name)
                )
            if alts.count() > 1:
                mod_role = utils.get(ctx.guild.roles, name='Moderator')
                msg = (
                    f':warning: This polytopia name is already entered in the database. '
                    f'If you need help using this bot please contact a {mod_role.mention} or <@{settings.owner_id}>.'
                    f' Duplicated players: {", ".join(alt.mention for alt in alts)}'
                )
                return await ctx.send(msg)
            
        db.GameLog.write(
            f'{db.GameLog.member_string(dest)} {"steam" if steam else "mobile"} username '
            f'{"set" if created else "updated"} to `{utils.escape_markdown(name)}`'
        )
    
    @commands.command()
    async def name(self, ctx: commands.Context, *, member: str = None):
        """
        Get the mobile and steam in game names of a player.
        
        **Examples**:
        - `[p]name legorooj` - return the steam name of legorooj
        """
        
        if member is None:
            members = [ctx.author]
        else:
            members = await settings.get_member(ctx, member)
        
        if len(members) == 1:
            m = members[0]
            p: db.Player = db.session.query(db.Player).get(m.id)
            if p is None:
                return await ctx.send(
                    f'{m.name}{" ({})".format(m.nick) if m.nick is not None else ""} is not registered with me.'
                )
            
            if p.ign is None and p.steam_name is not None:
                # If the player is only registered on steam
                await ctx.send(f'Steam name for **{m.name}**:')
                await ctx.send(f'{p.ign}')
            elif p.ign is not None and p.steam_name is None:
                # If the player is only registered on mobile
                await ctx.send(f'Name for **{m.name}**:')
                await ctx.send(f'{p.ign}')
            else:
                # If the player is registered on both steam and mobile
                await ctx.send(f'Name for **{m.name}** (Steam name: `{p.steam_name}`):')
                await ctx.send(f'{p.ign}')
        elif len(members) == 0:
            await ctx.send(
                f'Could not find any server member matching **{utils.escape_mentions(member)}**. '
                f'Try specifying with a @Mention'
            )
        else:
            await ctx.send(
                f'Found {len(members)} users matching **{utils.escape_mentions(member)}**.'
                f' Try specifying with an @Mention or more characters.'
            )
    
    @commands.command()
    @settings.is_registered()
    @settings.is_in_bot_channel()
    async def start(self, ctx: commands.Context, game: settings.GameLoader = None, *, game_name: str = None):
        """
        Mark a game as started. Use this command after you have created the game in Polytopia.
        
        **Example:**
        `[p]start 100 Spirit of War`"""
        game: db.Game
        if not game:
            return await ctx.send('Game ID not provided.')
        if not game_name:
            return await ctx.send('Name not provided.')
        
        if game.is_started is True:
            return await ctx.send(f'Game ID {game.id} has already started with name **{game.name}**.')
        
        host, away = ctx.guild.get_member(game.host_id), ctx.guild.get_member(game.away_id)
        
        if ctx.author.id != host.id:
            if not settings.is_mod(ctx.author):
                return await ctx.send(f'Only the game host or a Moderator can do this.')
        
        if not settings.is_valid_name(game_name):
            await ctx.send(
                f':warning: That game name looks made up. Please create the game in Polytopia, then come '
                f'back and enter the name of the game you just made.'
            )
        
        game.name = game_name
        game.is_started = True
        game.started_ts = datetime.datetime.utcnow()
        
        db.save()
        
        await self.announce_start(ctx.guild, ctx.channel, game)
        await settings.fix_roles(ctx.author)
        
        db.GameLog.write(
            game_id=game.id,
            message=f'{db.GameLog.member_string(ctx.author)} started game with name '
                    f'**{utils.escape_markdown(game.name)}**'
        )
    
    @commands.command()
    @settings.is_registered()
    @settings.is_in_bot_channel()
    async def rename(self, ctx: commands.Context, game: settings.GameLoader = None, *, game_name: str = None):
        """
        Renames an existing game (due to restarts).
        
        You can rename any game where you are the host.
        
        **Example:**
        - `[p]rename 120 Sword of Bell Boys`
        """
        game: db.Game
        if not game:
            return await ctx.send('Game ID not provided.')
        if not game_name:
            return await ctx.send('Name not provided.')
        
        if game.is_started is False:
            return await ctx.send('This game has not been started.')
        elif game.is_complete:
            return await ctx.send('This game is completed. You cannot rename completed games.')
        
        host = ctx.guild.get_member(game.host_id)
        
        if ctx.author.id != host.id:
            if not settings.is_mod(ctx.author):
                return await ctx.send(f'Only the game host or a Moderator can do this.')
        
        if not settings.is_valid_name(game_name):
            await ctx.send(
                f':warning: That game name looks made up. Please create the game in Polytopia, then come '
                f'back and enter the name of the game you just made.'
            )
        
        old_name = game.name
        game.name = game_name
        db.save()
        
        await ctx.send(f'Game {game.id} has been renamed to "**{game_name}**" from "**{old_name}**".')
        db.GameLog.write(
            game_id=game.id,
            message=f'{db.GameLog.member_string(ctx.author)} renamed the game to '
                    f'**{utils.escape_markdown(game.name)}**'
        )
    
    @commands.command()
    @settings.is_registered()
    @settings.is_in_bot_channel()
    async def win(self, ctx: commands.Context, game: settings.GameLoader = None, *, winner_str: str = None):
        """
        Declare the winner of a game
        
        **Examples**:
        - [p]win 123 legorooj
        """
        game: db.Game
        if not game:
            return await ctx.send('Game ID not provided.')
        
        host: Member
        away: Member
        winner = None
        host, away = ctx.guild.get_member(game.host_id), ctx.guild.get_member(game.away_id)
        
        if ctx.author.id not in (host.id, away.id) and not settings.is_mod(ctx.author):
            return await ctx.send(f'You are not a participant in game {game.id}.')
        if not game.is_started:
            return await ctx.send(f'Game ID {game.id} has not yet started.')
        if game.is_complete or game.is_confirmed:
            winner = host if host.id == game.winner_id else away
        if game.is_confirmed:
            return await ctx.send(
                f'Game {game.id} is already completed with winner **{winner.name}**'
                f'{" ({})".format(winner.nick) if winner.nick is not None else ""}.')
        
        if not winner_str:
            return await ctx.send(
                f'Sides in this game are:\nSide 1 (host): '
                f'{host.name}{" ({})".format(host.nick) if host.nick is not None else ""}\n'
                f'Side 2 (away): {away.name}{" ({})".format(away.nick) if away.nick is not None else ""}'
            )
        
        winning_side: Member = await settings.get_member_raw(ctx, winner_str)
        if not winning_side:
            matches = [
                x for x in
                (await settings.match_member(winner_str, host), await settings.match_member(winner_str, away))
                if x is not None
            ]
            if len(matches) == 2:
                return await ctx.send(
                    f'"{winner}" matches both sides in game {game.id}. Please be more specific, or use a @Mention'
                )
            elif len(matches) == 1:
                winning_side = matches[0]
            else:
                return await ctx.send(
                    f'Sides in this game are:\nSide 1 (host): '
                    f'{host.name}{" ({})".format(host.nick) if host.nick is not None else ""}\n'
                    f'Side 2 (away): {away.name}{" ({})".format(away.nick) if away.nick is not None else ""}'
                )
        
        if settings.is_mod(ctx.author) and ctx.author.id not in (host.id, away.id):
            # author is a mod, and not in the game. Mark as won.
            db.GameLog.write(
                game_id=game.id,
                message=f'Win claim logged by {db.GameLog.member_string(ctx.author)} for winner'
                        f'**{utils.escape_markdown(winning_side.display_name)}**'
            )
            game.win_confirmed(winning_side.id)
            await game.process_win(ctx)
            self.bot.loop.create_task(settings.fix_roles(ctx.author, host, away))
            return await self.announce_end(ctx.guild, ctx.channel, game)
        elif game.is_complete:
            if game.winner_id == winning_side.id:
                # Game has a logged but not confirmed winner yet.
                if game.win_claimed_by and game.win_claimed_by == ctx.author.id:
                    # Author has already logged a win claim. Ignore it.
                    await ctx.send(f'You have already logged a win claim.')
                else:
                    # This player hasn't logged a win confirm yet; confirm the game.
                    db.GameLog.write(
                        game_id=game.id,
                        message=f'Win claim logged by {db.GameLog.member_string(ctx.author)} for winner'
                                f'**{utils.escape_markdown(winning_side.display_name)}**'
                    )
                    game.win_confirmed(winning_side.id)
                    await game.process_win(ctx)
                    self.bot.loop.create_task(settings.fix_roles(ctx.author, host, away))
                    return await self.announce_end(ctx.guild, ctx.channel, game)
            else:
                db.GameLog.write(
                    game_id=game.id,
                    message=f'Win claim logged by {db.GameLog.member_string(ctx.author)} for winner'
                            f'**{utils.escape_markdown(winning_side.display_name)}**'
                )
                db.GameLog.write(
                    game_id=game.id,
                    message=f'Conflicting win claims; cancelling them.'
                )
                # Conflicting win claims; revert them all
                logged_winner = ctx.guild.get_member(game.winner_id)
                await ctx.send(
                    f':warning: game {game.id} already has {logged_winner.name} as the logged winner!'
                )
                game.is_complete = False
                game.winner_id = None
                game.win_claimed_ts = None
                game.win_claimed_by = None
                game.is_confirmed = False
                db.save()
                return await ctx.send(
                    f'All win claims for this game have been **reset** due to there being conflicting win claims.\n'
                    f'Notifying players {host.mention} {away.mention}'
                )
        elif game.winner_id is None:
            # No win claim has been logged yet.
            if winning_side.id != ctx.author.id:
                # Win claim is for the other side - automatically confirm it
                db.GameLog.write(
                    game_id=game.id,
                    message=f'Win claim logged by {db.GameLog.member_string(ctx.author)} for winner'
                            f'**{utils.escape_markdown(winning_side.display_name)}**'
                )
                game.win_confirmed(winning_side.id)
                await game.process_win(ctx)
                self.bot.loop.create_task(settings.fix_roles(ctx.author, host, away))
                return await self.announce_end(ctx.guild, ctx.channel, game)
            # win claim is not for the other side. Don't autoconfirm.
            db.GameLog.write(
                game_id=game.id,
                message=f'Win claim logged by {db.GameLog.member_string(ctx.author)} for winner'
                        f'**{utils.escape_markdown(winning_side.display_name)}**'
            )
            game.win_unconfirmed(winning_side.id, ctx.author.id)
            await ctx.send(
                f'Game {game.id} completed pending confirmation of winner {winning_side.mention}.\n'
                f'To confirm, have opponents use the command `$win {game.id} {winner_str}`.\n'
                f'Notifying {host.mention} {away.mention}.'
            )
    
    @commands.command()
    @settings.is_mod_check()
    async def unstart(self, ctx: commands.Context, game: settings.GameLoader = None):
        """*Mod*: reset an in progress game to a pending game"""
        game: db.Game
        
        if not game:
            return await ctx.send('Game ID not provided.')
        
        if game.is_complete or game.is_confirmed:
            return await ctx.send(f'Game {game.id} is already marked as completed.')
        if not game.is_started:
            return await ctx.send(f'Game {game.id} has not been started yet.')
        
        game.is_started = False
        game.is_name = None
        game.started_ts = None
        db.save()

        db.GameLog.write(
            game_id=game.id,
            message=f'{db.GameLog.member_string(ctx.author)} changed in-progress game to pending game. '
                    f'(`{ctx.prefix}unstart`)'
        )
        return await ctx.send(f'Game {game.id} has been successfully unstarted.')
    
    @commands.command()
    @settings.is_mod_check()
    async def unwin(self, ctx: commands.Context, game: settings.GameLoader = None):
        """*Mod*: Reset a completed game to incomplete"""
        game: db.Game
        
        if not game:
            return await ctx.send('Game ID not provided.')
        
        if not game.is_complete:
            return await ctx.send(f'Game {game.id} is not marked as completed.')
        
        # Load the objects
        host = db.session.query(db.Player).get(game.host_id)
        away = db.session.query(db.Player).get(game.away_id)
        away_rung, host_rung = away.rung, host.rung
        
        host_member, away_member = ctx.guild.get_member(game.host_id), ctx.guild.get_member(game.away_id)
        
        if game.host_step_change is not None or game.away_step_change is not None:
            # reverse rung changes
            if game.host_step_change < 0:
                if game.host_step != 1:
                    host_rung = max(min(host.rung - game.host_step_change, 12), 1)
                away_rung = max(min(away.rung - game.away_step_change, 12), 1)
            else:
                if game.away_step != 1:
                    away_rung = max(min(away.rung - game.away_step_change, 12), 1)
                host_rung = max(min(host.rung - game.host_step_change, 12), 1)
            
            away.rung = away_rung
            host.rung = host_rung
        
        game.away_step_change = None
        game.host_step_change = None
        game.is_complete = False
        game.is_confirmed = False
        game.win_claimed_ts = None
        game.winner_id = None
        db.save()
        
        self.bot.loop.create_task(settings.fix_roles(ctx.author, host_member, away_member))

        db.GameLog.write(
            game_id=game.id,
            message=f'{db.GameLog.member_string(ctx.author)} staff member used unwin command'
        )
        return await ctx.send(
            f'Game {game.id} successfully marked as incomplete. Rung changes have been reverted.'
        )
    
    @commands.command()
    @settings.is_in_bot_channel()
    async def incomplete(self, ctx: commands.Context, *, member: str = None):
        """
        List incomplete games for you or other players.
        
        **Examples**:
        - `[p]incomplete` - Lists your incomplete games
        - `[p]incomplete rebuilding` - Lists incomplete games for rebuilding
        """
        
        if member is None:
            members = [ctx.author]
        else:
            members = await settings.get_member(ctx, member)
        
        player: db.Player
        
        if len(members) == 1:
            m = members[0]
            player: db.Player = db.session.query(db.Player).get(m.id)
            if player is None:
                return await ctx.send(
                    f'*{m.name}{" ({})".format(m.nick) if m.nick is not None else ""}* is not registered with me.'
                )
        elif len(members) == 0:
            return await ctx.send(
                f'Could not find any server member matching **{utils.escape_mentions(member)}**. '
                f'Try specifying with a @Mention'
            )
        else:
            return await ctx.send(
                f'Found {len(members)} users matching **{utils.escape_mentions(member)}**.'
                f' Try specifying with an @Mention or more characters.'
            )
        
        dest = ctx.guild.get_member(player.id)
        
        games = player.incomplete()
        
        if games.count() == 0:
            return await ctx.send(
                f'No results found. See `$help incomplete` for examples.\nIncluding players: *{dest.name}*'
            )
        
        fields = []
        for game in games.all():
            host, away = ctx.guild.get_member(game.host_id), ctx.guild.get_member(game.away_id)
            
            if game.is_complete and game.is_confirmed is False:
                winner = ctx.guild.get_member(game.winner_id)
                content_str = f'**WINNER**: (Unconfirmed) {winner.mention}'
            elif game.is_started:
                content_str = 'Incomplete'
            else:
                content_str = 'Not started'
            
            fields.append(
                (
                    f'Game {game.id}   {host.name} vs {away.name}\n*{game.name}*',
                    f'{getattr(game, "started_ts", game.opened_ts).date().isoformat()} - {content_str}'
                )
            )
        
        await settings.paginate(
            ctx, fields=fields, title=f'{games.count()} incomplete games\nIncluding player: *{dest.name}*',
            page_start=0, page_end=15, page_size=15
        )
        
    @commands.command()
    async def game(self, ctx: commands.Context, *, game: settings.GameLoader = None):
        """
        Show details on a game.
        
        **Examples**:
        - `[p]game 1251` - See details on game # 1251.
        """
        game: db.Game
        if not game:
            return await ctx.send('Game ID not provided.')
        
        return await ctx.send(embed=game.embed(ctx))


def setup(bot, conf):
    bot.add_cog(Matchmaking(bot, conf))
