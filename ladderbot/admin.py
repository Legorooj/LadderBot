# Copyright (c) 2020 Legorooj. This file is licensed under the terms of the Apache license, version 2.0. #
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
        db.session.close()
        logger.info('Shutting down.')
        await ctx.send('Shutting down...')
        await self.bot.close()
    
    @commands.command()
    @commands.is_owner()
    async def clear_signupmessages(self, ctx):
        db.session.query(db.SignupMessage).delete()
        db.save()
        await ctx.send('Cleared.')

    @commands.command()
    @commands.is_owner()
    async def clear_players(self, ctx):
        db.session.query(db.Player).delete()
        db.save()
        await ctx.send('Cleared.')

    @commands.command()
    @commands.is_owner()
    async def clear_signups(self, ctx):
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
    async def confirm(self, ctx: commands.Context, game: settings.GameLoader):
        pass
    
    @commands.command()
    @settings.is_mod_check()
    async def logs(self, ctx: commands.Context, *, search_term: str = None):
        
        if search_term is None:
            search_term = ''
    
        search_term = re.sub(r'\b(\d{2,6})\b', r'_\1_', search_term, count=1) if search_term else None
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


def setup(bot, conf):
    bot.add_cog(Admin(bot, conf))
