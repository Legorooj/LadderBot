# Copyright (c) 2021 Legorooj. This file is licensed under the terms of the Apache license, version 2.0. #
import asyncio

import os
import re

import discord
from discord.ext import commands

from ladderbot import db, settings
from ladderbot.logging import logger


class Admin(commands.Cog):
    
    def __init__(self, bot: commands.Bot, conf: dict):
        self.bot = bot
        self.conf = conf
    
    @commands.Cog.listener()
    async def on_ready(self):
        s = f'Online. Logged in as {self.bot.user.name}/{self.bot.user.id}, PID {os.getpid()}'
        print(s)
        logger.info(s)
    
    @commands.command(aliases=['restart'])
    @commands.is_owner()
    async def quit(self, ctx: commands.Context):
        """Stop the bot's process."""
        db.session.close()
        logger.info('Shutting down.')
        await ctx.send('Shutting down...')
        await self.bot.close()
    
    @commands.command(hidden=True)
    @commands.is_owner()
    async def confirm_clear_signupmessages(self, ctx):
        db.session.query(db.SignupMessage).delete()
        db.save()
        await ctx.send('Cleared.')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def confirm_clear_players(self, ctx):
        db.session.query(db.Player).delete()
        db.save()
        await ctx.send('Cleared.')

    @commands.command(hidden=True)
    @commands.is_owner()
    async def confirm_clear_signups(self, ctx):
        db.session.query(db.Signup).delete()
        db.save()
        await ctx.send('Cleared.')
    
    @commands.command()
    @commands.is_owner()
    async def delete(self, ctx: commands.Context, game: settings.GameLoader, *, args: str = None):
        """*Owner*: delete an in progress/yet to be started game"""
        game: db.Game
        args = args or ''
    
        if not game:
            return await ctx.send('Game ID not provided.')
        
        if game.is_complete and '-override' not in args.lower():
            return await ctx.send(f'Please unwin the game first.')
        
        db.GameLog.write(game_id=game.id, message=f'{db.GameLog.member_string(ctx.author)} manually deleted the game.')
        
        db.delete(game)
        
        logger.info(f'Game {game.id} deleted.')
        
        await ctx.send(f'Game {game.id} deleted.')
    
    @commands.command()
    @settings.is_mod_check()
    async def confirm(self, ctx: commands.Context, *, game: settings.GameLoader = None):
        """
        *Mod*: List unconfirmed games, or confirm unconfirmed games.
        
        **Examples**:
        - `[p]confirm` - List unconfirmed games
        - `[p]confirm 50` - Confirms the winner of game 50
        """
        game: db.Game
    
        if not game:
            
            games = db.Game.query().filter(
                db.Game.is_complete.is_(True),
                db.Game.is_confirmed.is_(False)
            )
            
            fields = []

            for game in games:

                content_str = f'**WINNER**: (Unconfirmed) {game.winner.member(ctx.guild).display_name}'
    
                fields.append(
                    (
                        f'Game {game.id}   {game.host.name} vs {game.away.name}\n*{game.name}*',
                        f'{(game.started_ts or game.opened_ts).date().isoformat()} - {content_str}'
                    )
                )
            
            return await settings.paginate(
                ctx, fields=fields, title=f'{games.count()} unconfirmed games',
                page_start=0, page_end=15, page_size=15
            )
        
        if not (game.is_complete and not game.is_confirmed):
            return await ctx.send(f'`{ctx.prefix}confirm` can only be used on complete but unconfirmed games.')

        db.GameLog.write(
            game_id=game.id,
            message=f'Win confirmed for winner **{discord.utils.escape_markdown(game.winner.name)}** '
                    f'by Mod {db.GameLog.member_string(ctx.author)} '
        )
        game.win_confirmed(game.winner_id)
        await game.process_win()
        self.bot.loop.create_task(
            settings.fix_roles(
                ctx.author, game.host.member(ctx.guild), game.away.member(ctx.guild)
            )
        )
        await self.bot.get_cog('Matchmaking').announce_end(ctx.guild, ctx.channel, game)
        await ctx.send(f'Game **{game.id}** winner confirmed as **{discord.utils.escape_markdown(game.winner.name)}**')
    
    @commands.command()
    @settings.is_mod_check()
    async def logs(self, ctx: commands.Context, *, search_term: str = None):
        """
        *Mod*: Search game logs
        """
        
        if search_term is None:
            search_term = ''
    
        search_term = re.sub(r'\b(\d{1,6})\b', r'\_\1\_', search_term, count=1) if search_term else None
        # Above finds a 2-6 digit number in search_term and adds underscores around it
        # This will cause it to match against the __GAMEID__ the log entries are prefixed with and not substrings from
        # user IDs

        # replace @Mentions <@272510639124250625> with just the ID 272510639124250625
        search_term = re.sub(r'<@[!&]?([0-9]{17,21})>', '\\1', search_term) if search_term else None

        results = db.GameLog.search(search_term)
        
        message_list = []
        for entry in results:
            message_list.append(
                (f'`{entry.message_ts.strftime("%Y-%m-%d %H:%M:%S")}`', entry.message[:500])
            )
            
        message_list = message_list or [('No entries found', '')]
        
        await settings.paginate(
            ctx, f'Searching for log entries containing *{search_term}*'.replace("_", ""),
            message_list
        )
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        
        player: db.Player = db.session.query(db.Player).get(member.id)
        
        if not player:
            return
        
        if signups := db.Signup.query().filter(db.Signup.player == player):
            signups.delete()
        
        player.active = False
        mod_role = discord.utils.get(member.guild.roles, name='Mod')
        if (incomplete_games_count := player.incomplete().count()) != 0:
            await settings.discord_channel_log(
                f'{mod_role.mention} - {member.mention} ({member.display_name}) has left the server and has '
                f'{incomplete_games_count} incomplete games.'
            )
        
    @commands.Cog.listener()
    async def on_member_join(self, member):
        
        player: db.Player = db.session.query(db.Player).get(member.id)
        
        if not player:
            return
        
        player.active = True
        player.name = member.name
        
    @commands.Cog.listener()
    async def on_user_update(self, before: discord.User, after: discord.User):
        if before.name != after.name:
            p: db.Player = db.session.query(db.Player).get(after.id)
            p.name = after.name
    
            db.save()
    
            db.GameLog.write(
                message=f'{db.GameLog.member_string(after)} changed username from `{before.name}` to `{after.name}`.'
            )
        
    @commands.command()
    @settings.is_mod_check()
    async def swap_host(self, ctx, *, game: settings.GameLoader = None):
        """
        *Mod*: Swap the host and away players in a game
        """
        if not game:
            return await ctx.send('Game ID not provided.')
        
        game: db.Game
        old_host, host_step = game.host, game.host_step
        old_away, away_step = game.away, game.away_step
        game.host = old_away
        game.host_step = away_step
        game.away = old_host
        game.away_step = host_step
        game.host_switched = True
    
        db.save()
        
        db.GameLog.write(
            message=f'Host switched from `{old_host.name}` to `{old_away.name}` by {db.GameLog.member_string(ctx.author)}.',
            game_id=game.id
        )
        
        return await ctx.send(f'Host changed from **{old_host.name}** to **{old_away.name}**.')
    
    @commands.command()
    @commands.is_owner()
    async def check_rungs(self, ctx: commands.Context):
        
        await ctx.send('Checking that all rung changes have been applied correctly.')
        logger.debug('Checking rungs...')
        
        done = 0
        
        for player in db.Player.query():
            player: db.Player
            
            games = player.complete().filter(db.Game.is_confirmed.is_(True)).order_by(db.Game.win_claimed_ts.asc())
            
            player_rung = 1
            for game in games:
                game: db.Game
                logger.debug(f'{player.name} ({player.id}) --- game {game.id}, with {game.host_step_change} for the '
                             f'host, and {game.away_step_change} for away.')
                if game.host_id == player.id:
                    player_rung += game.host_step_change
                else:
                    player_rung += game.away_step_change
                
                if player_rung < 1:
                    player_rung = 1
                elif player_rung > 12:
                    player_rung = 12
            
            if is_bad := (player_rung != player.rung):
                await ctx.send(f'Player {player.name} ({player.id}) had rung {player.rung} in the database, '
                               f'but should have had {player_rung}. Fixing...')
            
                db.GameLog.write(
                    f'{db.GameLog.member_string(player)} - rung changed to {player_rung} from {player.rung} as part of '
                    f'a rung check.'
                )
                
                player.rung = player_rung
                
                db.save()
                
                if (m := ctx.guild.get_member(player.id)) and is_bad:
                    self.bot.loop.create_task(settings.fix_roles(m))
                
                done += 1
        
        await ctx.send(f'{done} players fixed.')


def setup(bot, conf):
    bot.add_cog(Admin(bot, conf))
