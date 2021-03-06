# Copyright (c) 2021 Legorooj. This file is licensed under the terms of the Apache license, version 2.0. #
import datetime
import random
from typing import Dict, List

from discord import TextChannel, Member, Message, RawReactionActionEvent, AllowedMentions, Embed
from discord.ext import commands, tasks
from jinja2 import Template

from ladderbot import settings, db
from ladderbot.logging import logger


class League(commands.Cog):
    
    def __init__(self, bot, conf):
        self.bot = bot
        self.conf = conf
        
        self.message_id = None
        
        self.relevant_emojis = [
            settings.emojis.blue_check_mark,
            settings.emojis.white_check_mark
        ]
        
        self.signup_loop.start()
    
    def cog_unload(self):
        self.signup_loop.cancel()
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent):
        signupmessage: db.SignupMessage = db.session.query(db.SignupMessage).filter(
            db.SignupMessage.is_open.is_(True)
        ).first()
        
        if self.message_id != getattr(signupmessage, 'message_id', self.message_id):
            self.message_id = signupmessage.message_id
        
        if payload.message_id != self.message_id:
            return
        
        if payload.user_id == self.bot.user.id:
            return

        channel = payload.member.guild.get_channel(payload.channel_id)
        message: Message = await channel.fetch_message(payload.message_id)
        emoji = self.bot.get_emoji(payload.emoji.id) if payload.emoji.id else payload.emoji

        if emoji.name not in self.relevant_emojis:
            await message.remove_reaction(emoji, payload.member)
        
        if emoji.name == settings.emojis.white_check_mark:
            await self.add_signup(payload.member, signupmessage, message, emoji, mobile=True)
        elif emoji.name == settings.emojis.blue_check_mark:
            await self.add_signup(payload.member, signupmessage, message, emoji, mobile=False)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent):
        msg: db.SignupMessage = db.session.query(db.SignupMessage).filter(
            db.SignupMessage.is_open.is_(True)
        ).first()
        
        if self.message_id != getattr(msg, 'message_id', self.message_id):
            self.message_id = msg.message_id
        
        if payload.message_id != self.message_id:
            return
        
        if payload.user_id == self.bot.user.id:
            return

        if payload.emoji.name not in self.relevant_emojis:
            return
        
        member = self.bot.get_user(payload.user_id)
        
        if payload.emoji.name == settings.emojis.white_check_mark:
            await self.remove_signup(member, msg, mobile=True)
        elif payload.emoji.name == settings.emojis.blue_check_mark:
            await self.remove_signup(member, msg, mobile=False)
    
    @staticmethod
    async def add_signup(member: Member, signupmessage, message: Message, emoji, mobile):
        
        p: db.Player = db.Player.get(member.id)
        if not p:
            await message.remove_reaction(emoji, member)
            return await member.send(f'You must be registered with me to signup for matches.')
        elif p.ign is None and mobile:
            await message.remove_reaction(emoji, member)
            return await member.send(f'You have not set your mobile name.')
        elif p.steam_name is None and not mobile:
            await message.remove_reaction(emoji, member)
            return await member.send(f'You have not set your steam name.')
        
        if (s := db.Signup.query().filter(db.Signup.player_id == member.id).first()) is not None:
            await message.remove_reaction(emoji, member)
            platform_str = 'mobile' if s.mobile else 'steam'
            return await member.send(
                f'You are already signed up for {platform_str}. You cannot signup for both platforms.'
            )
        
        signup = db.Signup(
            signup_id=signupmessage.id,
            player_id=member.id,
            mobile=mobile
        )
        
        db.add(signup)
        
        await member.send(
            f'You are now signed up for next week\'s **{"mobile" if mobile else "steam"}** games. '
            f'If you would like to remove yourself, just remove the reaction you just placed.'
        )
        logger.debug(
            f'{member.name} signed up for {"steam" if not mobile else "mobile"} matchups, signupmessage id '
            f'{signupmessage.id}'
        )
    
    @staticmethod
    async def remove_signup(member: Member, signupmessage, mobile):
        signup: db.Signup = db.session.query(db.Signup).filter_by(
            signup_id=signupmessage.id,
            player_id=member.id,
            mobile=mobile
        ).first()
        
        if signup:
            db.delete(signup)
            
            await member.send(
                f'You have been removed from the list of players for next week\'s **{"mobile" if mobile else "steam"}**'
                f' games. You can sign back up by reacting to the signup message again.'
            )
            logger.debug(
                f'{member.name} removed from signups for the {"steam" if not mobile else "mobile"} '
                f'matchups of signup id {signupmessage.id}'
            )
    
    @tasks.loop(minutes=5)
    async def signup_loop(self):
        signupmessage = db.session.query(db.SignupMessage).filter_by(is_open=True).first()
        if signupmessage:
            # Signups are open. Check if we can close them.
            if signupmessage.close_at < datetime.datetime.utcnow():
                logger.info('Closing signups.')
                await self.close_signups()
        else:
            if datetime.datetime.utcnow().weekday() == 5:
                signupmessages = db.session.query(db.SignupMessage).filter(db.SignupMessage.close_at > datetime.datetime.utcnow()).count()
                if not signupmessages:
                    # It's saturday, open the signups
                    logger.info('Opening signups')
                    await self.open_signups()
                else:
                    logger.info(
                        'Not opening signups, as there is a signupmessage object with a closing date later than now.'
                    )
    
    @signup_loop.before_loop
    async def pre_loop(self):
        await self.bot.wait_until_ready()
    
    async def open_signups(self, manual=False, ping: str = None):
        if ping == 'noping':
            ping = ''
        else:
            ping = ping or '@everyone'
        # Get the channel
        announcements: TextChannel = self.bot.get_channel(
            int(self.conf['channels']['announcements'])
        )
        
        # Send the message, add the reactions
        msg = await announcements.send(
            settings.messages.SIGNUP_MESSAGE.format(ping if ping != '' else 'everyone'),
            allowed_mentions=AllowedMentions(everyone=True)
        )
        await msg.add_reaction(settings.emojis.white_check_mark)
        await msg.add_reaction(settings.emojis.blue_check_mark)
        
        day = settings.next_day(0)
        
        db.add(
            db.SignupMessage(
                message_id=msg.id,
                is_open=True,
                close_at=day
            )
        )
        db.save()
        self.message_id = msg.id
        
        logger.info(
            f'Signups have been {"automatically " if not manual else ""}'
            f'opened. They will close at {day}, UTC time.'
        )
    
    async def close_signups(self, manual=False):
        signup_message: db.SignupMessage = db.session.query(db.SignupMessage).filter_by(is_open=True).first()
        channel: TextChannel = self.bot.get_channel(
            int(self.conf['channels']['announcements'])
        )
        logger.debug(signup_message.message_id)
        msg = await channel.fetch_message(signup_message.message_id)
        
        await msg.edit(content=settings.messages.SIGNUPS_CLOSED_MESSAGE.format(msg.content))
        await msg.clear_reactions()
        
        signup_message.is_open = False
        db.save()
        self.message_id = None
        
        logger.info(
            f'Signups have been {"automatically " if not manual else ""}'
            f'closed.'
        )
        
        if not manual:
            await self.create_matchups()
    
    @commands.command(aliases=['close_signups', 'open_signups'])
    @settings.is_mod_check()
    async def signups(self, ctx: commands.Context, ping: str = None):
        """
        Open or close signups manually.
        
        - [p]open_signups - open signups
        - [p]close_signups - close signups
        """
        
        if ctx.invoked_with == 'close_signups':
            
            # Make sure there are actually signups open.
            if not db.session.query(db.SignupMessage).filter_by(is_open=True).first():
                return await ctx.send('Signups are not open, and therefore cannot be closed.')
            
            logger.debug(f'Close signups triggered manually by {ctx.author.name}/{ctx.author.id}')
            
            await self.close_signups(manual=True)
            return await ctx.send(f'Signups manually closed by {ctx.author.mention}')
        
        elif ctx.invoked_with == 'open_signups':
            
            # Make sure there aren't signups already open
            if db.session.query(db.SignupMessage).filter_by(is_open=True).first():
                return await ctx.send('Signups are already open, and more cannot be opened.')
            
            logger.debug(f'Open signups triggered manually by {ctx.author.name}/{ctx.author.id}')
            
            await self.open_signups(manual=True, ping=ping)
            return await ctx.send(f'Signups manually opened by {ctx.author.mention}')
        else:
            await ctx.send(f'Run `{ctx.prefix}help signups` please.')
    
    async def create_matchups(self):
        logger.debug(f'Generating matchups')
        
        mobile_signups = db.session.query(db.Signup).filter_by(mobile=True)
        steam_signups = db.session.query(db.Signup).filter_by(mobile=False)
        
        if not mobile_signups.count() and not steam_signups.count():
            return logger.info('Not creating matchups - no one has signed up.')
        elif not mobile_signups.count():
            logger.info('Not creating matches for mobile - no signups')
        elif not steam_signups.count():
            logger.info('Not creating matches for steam - no signups')
        
        # First of all, get all the players.
        mobile_players = [x.player for x in mobile_signups.all()]
        steam_players = [x.player for x in steam_signups.all()]
        
        mobile_players_even = len(mobile_players) % 2 == 0
        steam_players_even = len(steam_players) % 2 == 0
        
        if not mobile_players_even or not steam_players_even:
            
            async def remove_random(member_list: List, platform):
                pl = member_list.pop(random.randint(0, len(member_list) - 1))
                m = self.bot.get_user(pl.id)
                await m.send(
                    f'You have been randomly removed from the {platform} matchups for this week\'s PolyLadder games.'
                    f' Sorry!'
                )
                logger.info(f'{m.name}#{m.discriminator}/{m.id} kicked from {platform} matches.')
            
            # We don't have an even number of players. Kick one of them.
            duplicates = set(mobile_players) & set(steam_players)
            if not duplicates:
                # No players have signed up for both steam and mobile
                pass
                if not mobile_players_even:
                    await remove_random(mobile_players, 'mobile')
                if not steam_players_even:
                    await remove_random(steam_players, 'steam')
            else:
                # There are duplicate players - player's who have signed up for both platforms.
                if len(duplicates) > 1:
                    if not mobile_players_even:
                        # mobile
                        p = duplicates.pop()
                        member = self.bot.get_user(p.id)
                        await member.send(
                            'You have been removed from mobile matchups for this week\'s PolyLadder matches, '
                            'due to player limits and to you signing up for both steam and mobile.'
                        )
                        mobile_players.remove(p)
                        logger.info(f'{member.name}#{member.discriminator}/{member.id} kicked from mobile matches.')
                    if not steam_players_even:
                        # steam
                        p = duplicates.pop()
                        member = self.bot.get_user(p.id)
                        await member.send(
                            'You have been removed from steam matchups for this week\'s PolyLadder matches, '
                            'due to player limits and to you signing up for both steam and mobile.'
                        )
                        steam_players.remove(p)
                        logger.info(f'{member.name}#{member.discriminator}/{member.id} kicked from steam matches.')
                else:
                    if not mobile_players_even:
                        # Only 1 duplicate
                        p = duplicates.pop()
                        member = self.bot.get_user(p.id)
                        await member.send(
                            'You have been removed from mobile matchups for this week\'s PolyLadder matches, '
                            'due to player limits and to you signing up for both steam and mobile.'
                        )
                        mobile_players.remove([p, member])
                        logger.info(f'{member.name}#{member.discriminator}/{member.id} kicked from mobile matches.')
                    if not steam_players_even:
                        await remove_random(steam_players, 'steam')
        
        # Load the discord member objects
        mobile: List[List[db.Player, Member]] = list()
        steam: List[List[db.Player, Member]] = list()
        
        for player in mobile_players:
            mobile.append(
                [player, self.bot.get_user(player.id)]
            )
        for player in steam_players:
            steam.append(
                [player, self.bot.get_user(player.id)]
            )
        
        # Now that we have an even number of players in each tier, start generating matchups
        # Create the tier objects
        mobile_tiers: Dict[int, list] = {
            x: [] for x in range(1, 13)
        }
        steam_tiers: Dict[int, list] = {
            x: [] for x in range(1, 13)
        }
        
        # Place people in their initial rungs.
        for player, member in mobile:
            mobile_tiers[player.rung].append(
                (player, member)
            )
        
        for player, member in steam:
            steam_tiers[player.rung].append(
                (player, member)
            )
        
        # Iterate through each rung, from the bottom up, and move people up if there's an odd
        # number of people in that rung.
        for r in range(1, 13):
            rung = mobile_tiers[r]
            rung.sort(key=lambda x: x[0].win_ratio)
            if len(rung) % 2 == 0:
                continue
            mobile_tiers[r + 1].append(rung.pop(0))
        
        for r in range(1, 13):
            rung = steam_tiers[r]
            rung.sort(key=lambda x: x[0].win_ratio)
            if len(rung) % 2 == 0:
                continue
            steam_tiers[r + 1].append(rung.pop(0))
        
        # Rungs are sorted, create the matchups
        mobile_games = self.make_games(mobile_tiers, True)
        steam_games = self.make_games(steam_tiers, False)
        
        platform_msg_source = Template(
            """
**{{platform}}**:\n
{% for tier, games in gms.items() if games is not none %}
Tier {{tier}} matchups:
{% for game in games %}
<@{{game.host.id}}> ({{game.host_step}}) hosts vs <@{{game.away_id}}> ({{game.away_step}}) - Game {{game.id}}
{% endfor %}


{% endfor %}
"""
        )
        
        if mobile_games or steam_games:
            chan: TextChannel = self.bot.get_channel(int(self.conf['channels']['matchups']))
            tribe_tier = random.randint(1, 3)
            await chan.send(
                f'A new week of games has been generated!\nWe will be using **Level {tribe_tier}** tribes this week.\n'
                f'Here are your games:'
            )
            if mobile_games:
                message = f'\n\n{platform_msg_source.render(gms=mobile_games, platform="Mobile")}'
                
                for block in settings.split_string(message):
                    await chan.send(block)
            if steam_games:
                message = f'\n\n{platform_msg_source.render(gms=steam_games, platform="Steam")}'
                for block in settings.split_string(message):
                    await chan.send(block)
            await chan.send(
                '\n\nPlease create your games as soon as possible. '
                'If your game has not $started in the next 72 hours (3 days), '
                'the away player will become the host. If the new host does not '
                'start the game 72 hours after that, the game will be cancelled.'
            )
            mobile_signups.delete()
            steam_signups.delete()
            
            db.save()
    
    @staticmethod
    def make_games(tiers: Dict[int, list], mobile: bool):
        out = {
            x: [] for x in range(1, 13)
        }
        tiers_to_delete = []
        for tier_number, players in tiers.items():
            tiers[tier_number] = []
            if not players:
                tiers_to_delete.append(tier_number)
                continue
            random.shuffle(players)
            players = iter(players)
            for host, away in zip(players, players):
                game = db.Game(
                    host_id=host[0].id,
                    away_id=away[0].id,
                    host_step=host[0].rung,
                    away_step=away[0].rung,
                    mobile=mobile,
                    opened_ts=datetime.datetime.utcnow(),
                    step=tier_number
                )
                db.add(game)
                db.GameLog.write(game_id=game.id,
                                 message=f'Game opened by me. {db.GameLog.member_string(host[1])} hosts against '
                                         f'{db.GameLog.member_string(away[1])}'
                                 )
                out[tier_number].append(game)
        for t in tiers_to_delete:
            del out[t]
        return out
    
    @commands.command()
    @commands.is_owner()
    async def gen(self, ctx: commands.Context = None):
        await self.create_matchups()
    
    @commands.command()
    @settings.is_in_bot_channel()
    async def guide(self, ctx: commands.Context):
        """
        Show an overview of what the bot is for and how to use it.
        """
        embed: Embed = Embed(title=f'LadderBot - Guide')
        
        embed.add_field(
            name='About this bot',
            value='LadderBot is a Discord bot designed to help run the PolyLadder 1v1 League.',
            inline=False
        )
        
        embed.add_field(
            name='Registration',
            value=f'Use the `{ctx.prefix}setname` and `{ctx.prefix}steamname`'
                  f' commands to set you mobile and steam names.',
            inline=False
        )
        
        embed.add_field(
            name='Signups',
            value='Signups are opened every weekend (UTC time), with matches being generated every Monday. '
                  'React to the message in announcements to sign up for either steam or mobile matches.',
            inline=False
        )
        
        embed.add_field(
            name='Starting games',
            value=f'When you\'ve been assigned as the host in a game, send a friend request to your opponent in '
                  f'Polytopia. Once it\'s been accepted, you have 3 days to create the game in Polytopia and start '
                  f'it in the bot by using the `{ctx.prefix}start` command. See `{ctx.prefix}help start` for more '
                  f'information on how to use the command. If you haven\'t started the game in 3 days, your opponent '
                  f'becomes the game host and they have 3 days to start the game, as you did. If the game is still not '
                  f'started, then it will be deleted.'
        )
        
        embed.add_field(
            name='Marking a game as won',
            value=f'Once a game ends, you can tell the bot who won by using the `{ctx.prefix}win` command.'
        )
        
        embed.set_footer(text='Developer: Legorooj')
        embed.set_thumbnail(url=self.bot.user.avatar_url_as(size=512))
        
        return await ctx.send(embed=embed)

    @commands.command()
    async def credits(self, ctx: commands.Context):
        """
        Display development credits
        """
        
        embed: Embed = Embed(title=f'LadderBot - credits')
        
        embed.add_field(name='Developer', value='Legorooj (<@608290258978865174>)')
        embed.add_field(name='Source Code', value='https://github.com/Legorooj/LadderBot')
        embed.add_field(name='Contributions', value='jd (alphaSeahorse)', inline=False)
        
        return await ctx.send(embed=embed)


def setup(bot, conf):
    bot.add_cog(League(bot, conf))
