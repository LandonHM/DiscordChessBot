'''

General things to add:

    Database and that stuff
        users game history, settings (how to set settings)

    find out if when cur gets filled ? i think shouold be fine cause everythgin time i use data i call new fetch command

    fix checks

    maybe make the functions into a class for easier read
    maybe make a custom help/advanced help
    handle the draw case
    ???
    Profit?

    UNDO
'''
#also need help but thats anotha issue

#discord imports
import discord
from discord.ext import commands
import asyncio
#chess imports
import chess
import chess.engine
import chess.svg
import chess.pgn
import cairosvg
#general system imports
import os
import sys
import re
from datetime import datetime,timedelta
import requests
import mariadb
from dotenv import load_dotenv
#local imports
from chess_game import ChessGame

#@commands.guild_only() - useful maybe

class chess_cog(commands.Cog):
    def __init__(self, bot):
        self.FILE = None
        self.REQ_TIME = None
        self.CUR = bot.CUR 
        self.CONN = bot.CONN 
        self.transport = None
        self.engine = None
        self.challenges = []
        self.ongoing_games = []
    
    
    async def init_engine(self):
        self.transport, self.engine = await chess.engine.popen_uci("/usr/games/stockfish")
    
    @commands.command(
        help="Used to challenge another user in a standard chess game",
        brief="Used to start a game of chess.",
        aliases=['c']
    )
    async def challenge(self, ctx, *args):
        print("challenge read from", ctx.author)

        if len(args) == 0:
            return


        if not ctx.message.mention_everyone:
            if ctx.bot.user in ctx.message.mentions:
                #check if game already in channel
                for g in self.ongoing_games:
                    if g.channel == ctx.channel:
                        return
                self.ongoing_games.append(ChessGame(ctx.author, 0, ctx.channel, args[-1]))
                await self.ongoing_games[-1].start_game()
            else:
                now = datetime.now()
                self.challenges.append((ctx.message.mentions, ctx.author, ctx.channel, now, args[-1]))


    @commands.command(
        help="Accepts a challenge from another user",
        brief="Accepts a pending challenge",
        usage="@user will accept a challenge from that user, or no @ will accept the most recent challenge",
        aliases=['a']
    )
    async def accept(self, ctx, *args):

        print("accept read from", ctx.author)
        now = datetime.now() #used to clear out old self.challenges

        for idx in range(len(self.challenges)):
            challenge = self.challenges[idx]

            if (challenge[3]-now) > timedelta(minutes=15):
                print("challenge timed out")
                self.challenges.pop(idk)
                continue

            #first see if the challenge is the same channel as the accept
            if challenge[2] == ctx.channel:

                #if there is a game already in the channel, do not start another
                for game in self.ongoing_games:
                    if game.channel == ctx.channel:
                        return

                #see if the accepter is one of the people challenged
                for mention in challenge[0]:
                    if mention.id == ctx.author.id:
                        #see if accepter @'d someone, if not just accept first challenge
                        if(len(ctx.message.mentions)) == 0:
                            print("game start between ", ctx.author, challenge[1], "in channel", ctx.channel)
                            self.ongoing_games.append(ChessGame(challenge[1], ctx.author, ctx.channel, challenge[4]))
                            await self.ongoing_games[-1].start_game()
                            self.challenges.pop(idx)
                            return
                        else:
                            #find the challenger who the accepter @'d
                            for mention2 in ctx.message.mentions:
                                if mention2.id == challenge[1]:
                                    print("@ game start between ", ctx.author, challenge[1], "in channel", ctx.channel)
                                    self.ongoing_games.append(ChessGame(challenge[1], ctx.author, ctx.channel, challenge[4]))
                                    await self.ongoing_games[-1].start_game()
                                    self.challenges.pop(idx)
                                    return


    @commands.command(
        help="Plays the move sent by the user in the form of Standard Algebraic Notation",
        brief="Plays a move",
        aliases=['p']
    )
    async def play(self, ctx, *args):
        fin = None
        idx = 0
        for idx in range(len(self.ongoing_games)):
            if self.ongoing_games[idx].channel == ctx.channel:
                #if bot is playing, send the bot move.
                if self.ongoing_games[idx].bot:
                    if self.engine == None:
                        await self.init_engine()
                        print("engine inti")
                        
                    fin = await self.ongoing_games[idx].play_move(args[0], ctx.author.id, ctx.message, self.engine)
                else:
                    fin = await self.ongoing_games[idx].play_move(args[0], ctx.author.id, ctx.message, None)

        #if fin has data then the game ended
        if fin is not None:
            await self.end_game(self.ongoing_games[idx],fin)
            self.ongoing_games.pop(idx)


    @commands.command(
        help="If both players offer draw then game is ended on a draw, to recind a draw, use the command a second time",
        brief="Offers/Accept/Recinds draw",
        aliases=["d"]
    )
    async def draw(self, ctx, *args):
        fin = None
        idx = 0
        for idx in range(len(self.ongoing_games)):
            if self.ongoing_games[idx].channel == ctx.channel:
                fin = await self.ongoing_games[idx].play_move("draw", ctx.author.id, ctx.message)

        if fin is not None:
            await end_game(self.ongoing_games[idx],fin,ctx.guild,ctx.channel)
            self.ongoing_games.pop(idx)

    async def end_game(self, cur_game, fin, guild, channel):
        if fin[1]:
            await cur_game.channel.send("Game was tied")
        elif fin[0]:
            await cur_game.channel.send("White Victory")
        else:
            await cur_game.channel.send("Black Victory")

        #if db is up, save to db
        if self.CUR is not None:
            #if player is 0, then played against the bot
            if cur_game.playerWhite == 0:
                t = (0,cur_game.playerBlack.id,str(cur_game.pgn),fin[0],fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
            elif cur_game.playerBlack == 0:
                t = (0,cur_game.playerWhite.id,str(cur_game.pgn),(1^fin[0]),fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
            elif cur_game.playerWhite.id > cur_game.playerBlack.id:
                t = (cur_game.playerBlack.id,cur_game.playerWhite.id,str(cur_game.pgn),(1^fin[0]),fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
            else:
                t = (cur_game.playerWhite.id,cur_game.playerBlack.id,str(cur_game.pgn),fin[0],fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
            self.CUR.execute("insert into Matches(User1ID,User2ID,PGN,win,tie,date,GuildID,ChannelID) values(%d,%d,%s,%d,%d,%s,%d,%d)", t)
        else:
            await cur_game.channel.send("The database is down, so this game will not be remebered")



    '''
    @commands.command(
        help="Displays the previous matches played by the caller",
        brief="Returns last few matches of the caller",
        aliases=["h"]
    )
    async def history(self, ctx, *args):
        if self.CUR is None:
            await ctx.send("Cannot fetch history right now, as the database is down")
            return

        if ctx.message.mentions is None:
            self.CUR.execute(f"Select PGN from Matches WHERE (User1ID={ctx.author.id} OR User2ID={ctx.author.id}) AND GuildId={ctx.guid.id}")
            num = min(3 if len(args) == 0 else (int(args[0])),len(self.CUR))
            for i in range(num-1):
                FILE = open("board.png", "wb")
                FILE.write(cairosvg.svg2png(chess.svg.board(board=chess.pgn.read_game(self.CUR[i][0]), size=500)))
                self.prev = await ctx.send(file=discord.File("board.png"))
                FILE.close()

        else: #complete
            for mention in ctx.message.mentions:
                if mention.id > ctx.author.id:
                    self.CUR.execute(f"Select PGN from Matches WHERE (User1ID={mention.id} AND User2ID={ctx.author.id}) AND GuildId={ctx.guid.id}")
                else:
                    self.CUR.execute(f"Select PGN from Matches WHERE (User1ID={ctx.author.id} OR User2ID={mention.id}) AND GuildId={ctx.guid.id}")

                try:
                    results = self.CUR.fetchall()
                    e = discord.Embed(title="Games")
                    for i in range(1,4):
                        FILE = open("board.png", "wb")
                        FILE.write(cairosvg.svg2png(chess.svg.board(board=chess.pgn.read_game(self.CUR[i][0]), size=500)))
                        self.prev = await ctx.send(file=discord.File("board.png"))
                        FILE.close()

                return

        return
    '''

    @commands.command(
        help="Requests a lichess link of a pgn of a previous game specified by the user, in order to use lichess' engine analysis",
        brief="analyzes a game",
        alias=["analysis"]
    )
    async def analyze(self, ctx, *args):

        if self.CUR is None:
            await ctx.send("Cannot fetch history right now, as the db is down")
            return

        num = 1 if len(args) == 0 else int(args[0])
        game = await find_game(ctx.author.id, ctx.message.mentions, num)

        if game[4] is None:
            if self.REQ_TIME is None or self.REQ_TIME-datetime.now() > timedelta(hours=1):
                self.REQ_TIME = None
                r = requests.post('https://lichess.org/api/import', data = {'pgn':game[3]})
                if r.status_code == 200:
                    txt = r.text.split(":\"")[2][0:-2]
                    await ctx.send(txt)
                    self.CUR.execute(f"update Matches SET link=\"{txt}\" WHERE MatchID={game[0]}")
                elif r.status_code == 400:
                    await ctx.send("Unable to fetch, currently rate limited")
                    self.REQ_TIME = datetime.now()
                else:
                    print("Error fetching link from server")
            else:
                await ctx.send("Unable to analize game, rate limit has been reached. You can get the pgn and upload yourself by calling pgn command and going to https://lichess.org/paste")
        else:
            await ctx.send(game[4])



    @commands.command(
        help="Returns the pgn of a specified game from the user's history",
        brief="gets pgn of a game",
        aliases=["PGN"]
    )
    async def pgn(self, ctx, *args):
        if self.CUR is None:
            ctx.send("Database is currently down.")
            return

        num = 1 if len(args) == 0 else int(args[0])
        game = find_game(ctx.author.id, ctx.message.mentions, num)
        if game == 0:
            ctx.send("Could not find game")
        else:
            e = discord.Embed(title="PGN")
            e.add_field(value=game[2], inline=False)
            ctx.send(embed=e)
        return

    #assumes db is up
    async def find_game(self, UserID, mentions, matchNum):
        if len(mentions) == 0:
            self.CUR.execute(f"Select * from Matches WHERE User1ID={UserID} OR User2ID={UserID} ORDER BY date")
        else:
            if mentions[0].id == 385618051548184593: #this is the id of the bot
                self.CUR.execute(f"Select PGN from Matches WHERE User1ID=0 AND User2ID={UserID} ORDER BY date")
            else:
                if UserID < mentions[0].id:
                    self.CUR.execute(f"Select PGN from Matches WHERE User1ID={UserID} AND User2ID={mentions[0].id} ORDER BY date")
                else:
                    self.CUR.execute(f"Select PGN from Matches WHERE User1ID={mentions[0].id} AND User2ID={UserID} ORDER BY date")
        try:
            games = self.CUR.fetchall()
            game = self.CUR[matchNum-1]
            return game
        except:
            return 0

def setup(bot):
    bot.add_cog(chess_cog(bot))

