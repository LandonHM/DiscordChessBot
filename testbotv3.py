#i added this line
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

#@commands.guild_only() - useful maybe

#global variables
FILE = None
REQUEST_TIME = None
CUR = None
CONN = None
TRANSPORT = None
ENG = None
challenges = []
ongoingGames = []

load_dotenv()

#if arg log is sent when running, then output should be put into a log file
if len(sys.argv) >= 2 and sys.argv[1] == "log":
    sys.stdout = sys.stderr = open('logfile.log', 'a')

#connect to the database
try:
    CONN = mariadb.connect(user=os.getenv("DB_USER"),password=os.getenv("DB_PASS"),host=os.getenv("DB_IP"),port=int(os.getenv("DB_PORT")),database=os.getenv("DB_DB"))
    if CONN.autocommit is False:
        CONN.autocommit = True
    CUR = CONN.cursor()
except mariadb.Error as e:
    print("Cannot connecto the the database")


#called when a command is being processed, fetches the custom command for the server
async def _determine_prefix(bot,msg):
    #print("det pref called")
    user_id = bot.user.id
    base = [f'<@!{user_id}>',f'<@{user_id}>']
    if msg.guild is None:
        base.append('')
        return base
    elif CUR is None:
        base.append('|')
        return base
    else:
        CUR.execute(f'select Command from GuildCommand where GuildID={msg.guild.id}')
        prefix = CUR.fetchone()
        if prefix is None:
            base.append('|')
            return base
        else:
            base.append(prefix[0])
            return base


#used for bot init
help = commands.DefaultHelpCommand(no_category='Commands')
desc = "Bot that lets users play chess against each other."
client = commands.Bot(command_prefix=_determine_prefix, description=desc, help_command=help)


#Start of bot functions

@client.event
async def on_ready():
    global ENG, TRANSPORT
    print(f'Logged in as {client.user}!')
    TRANSPORT, ENG = await chess.engine.popen_uci("/usr/games/stockfish")
    await client.change_presence(activity = discord.Game("Chess"))


@client.event
async def on_guild_join(guild):
    print("joined new guild",guild,guild.id)
    return


@client.command(
    help="Used to challenge another user in a standard chess game",
    brief="Used to start a game of chess.",
    aliases=['c']
)
async def challenge(ctx, *args):
    print("challenge read from", ctx.author)

    if len(args) == 0:
        return


    if not ctx.message.mention_everyone:
        if ctx.bot.user in ctx.message.mentions:
            #check if game already in channel
            for g in ongoingGames:
                if g.channel == ctx.channel:
                    return
            ongoingGames.append(ChessGame(ctx.author, 0, ctx.channel, args[-1]))
            await ongoingGames[-1].start_game()
        else:
            now = datetime.now()
            challenges.append((ctx.message.mentions, ctx.author, ctx.channel, now, args[-1]))


@client.command(
    help="Accepts a challenge from another user",
    brief="Accepts a pending challenge",
    usage="@user will accept a challenge from that user, or no @ will accept the most recent user",
    aliases=['a']
)
async def accept(ctx, *args):

    print("accept read from", ctx.author)
    now = datetime.now() #used to clear out old challenges

    for idx in range(len(challenges)):
        challenge = challenges[idx]

        if (challenge[3]-now) > timedelta(minutes=15):
            print("challenge timed out")
            challenges.pop(idk)
            continue

        #first see if the challenge is the same channel as the accept
        if challenge[2] == ctx.channel:

            #if there is a game already in the channel, do not start another
            for game in ongoingGames:
                if game.channel == ctx.channel:
                    return

            #see if the accepter is one of the people challenged
            for mention in challenge[0]:
                if mention.id == ctx.author.id:
                    #see if accepter @'d someone, if not just accept first challenge
                    if(len(ctx.message.mentions)) == 0:
                        print("game start between ", ctx.author, challenge[1], "in channel", ctx.channel)
                        ongoingGames.append(ChessGame(challenge[1], ctx.author, ctx.channel, challenge[4]))
                        await ongoingGames[-1].start_game()
                        challenges.pop(idx)
                        return
                    else:
                        #find the challenger who the accepter @'d
                        for mention2 in ctx.message.mentions:
                            if mention2.id == challenge[1]:
                                print("@ game start between ", ctx.author, challenge[1], "in channel", ctx.channel)
                                ongoingGames.append(ChessGame(challenge[1], ctx.author, ctx.channel, challenge[4]))
                                await ongoingGames[-1].start_game()
                                challenges.pop(idx)
                                return


@client.command(
    help="Plays the move sent by the user in the form of Standard Algebraic Notation",
    brief="Plays a move",
    aliases=['p']
)
async def play(ctx, *args):
    fin = None
    idx = 0
    for idx in range(len(ongoingGames)):
        if ongoingGames[idx].channel == ctx.channel:
            fin = await ongoingGames[idx].play_move(args[0], ctx.author.id, ctx.message)

    #if fin has data then the game ended
    if fin is not None:
        await end_game(ongoingGames[idx],fin)
        ongoingGames.pop(idx)


@client.command(
    help="If both players offer draw then game is ended on a draw, to recind a draw, use the command a second time",
    brief="Offers/Accept/Recinds draw",
    aliases=["d"]
)
async def draw(ctx, *args):
    fin = None
    idx = 0
    for idx in range(len(ongoingGames)):
        if ongoingGames[idx].channel == ctx.channel:
            fin = await ongoingGames[idx].play_move("draw", ctx.author.id, ctx.message)

    if fin is not None:
        await end_game(ongoingGames[idx],fin,ctx.guild,ctx.channel)
        ongoingGames.pop(idx)

async def end_game(cur_game, fin, guild, channel):
    if fin[1]:
        await cur_game.channel.send("Game was tied")
    elif fin[0]:
        await cur_game.channel.send("White Victory")
    else:
        await cur_game.channel.send("Black Victory")

    #if db is up, save to db
    if CUR is not None:
        #if player is 0, then played against the bot
        if cur_game.playerWhite == 0:
            t = (0,cur_game.playerBlack.id,str(cur_game.pgn),fin[0],fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
        elif cur_game.playerBlack == 0:
            t = (0,cur_game.playerWhite.id,str(cur_game.pgn),(1^fin[0]),fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
        elif cur_game.playerWhite.id > cur_game.playerBlack.id:
            t = (cur_game.playerBlack.id,cur_game.playerWhite.id,str(cur_game.pgn),(1^fin[0]),fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
        else:
            t = (cur_game.playerWhite.id,cur_game.playerBlack.id,str(cur_game.pgn),fin[0],fin[1],datetime.now().strftime("%Y-%m-%d %H:%M:%S"),channel,guild)
        CUR.execute("insert into Matches(User1ID,User2ID,PGN,win,tie,date,GuildID,ChannelID) values(%d,%d,%s,%d,%d,%s,%d,%d)", t)
    else:
        await cur_game.channel.send("The database is down, so this game will not be remebered")


@client.command(
    help="Changes the prefix used to use the bot's commands",
    brief="Changes the bot's prefix",
    usage="prefix (char) - where char is the prefix you would like the bot to recognize"
)
async def prefix(ctx, pref = None):
    if CUR is None:
        await ctx.channel.send("Database is currently down, the command character is not able to be updated.")
    else:
        if pref is None or not ctx.author.guild_permissions.manage_guild:
            return
        try:
            CUR.execute(f"INSERT INTO GuildCommand(GuildID,Command) VALUES({ctx.guild.id},\'{pref[0]}\') ON DUPLICATE KEY UPDATE Command=\'{pref[0]}\'")
            await ctx.channel.send(f"Prefix updated to {pref[0]}")
        except mariadb.Error as e:
            print("prefix update error")
            #if e.
            #CUR.execute("insert into GuildCommand(GuildID,Command) values(%d,%s)", (ctx.guild.id,pref[0]))


@client.command(
    help="Displays the previous matches played by the caller",
    brief="Returns last few matches of the caller",
    aliases=["h"]
)
async def history(ctx, *args):
    if CUR is None:
        await ctx.send("Cannot fetch history right now, as the db is down")
    else:
        if ctx.message.mentions is None:
            CUR.execute(f"Select PGN from Matches WHERE (User1ID={ctx.author.id} OR User2ID={ctx.author.id}) AND GuildId={ctx.guid.id}")
            num = min(3 if len(args) == 0 else (int(args[0])),len(CUR))
            for i in range(num-1):
                FILE = open("board.png", "wb")
                FILE.write(cairosvg.svg2png(chess.svg.board(board=chess.pgn.read_game(CUR[i][0]), size=500)))
                self.prev = await ctx.send(file=discord.File("board.png"))
                FILE.close()

        else: #complete
            for men in ctx.message.mentions:
                if men.id > ctx.author.id:
                    CUR.execute(f"Select PGN from Matches WHERE (User1ID={ctx.author.id} OR User2ID={ctx.author.id}) AND GuildId={ctx.guid.id}")
                return

    return


@client.command(
    help="Requests a lichess link of a pgn of a previous game specified by the user, in order to use lichess' engine analysis",
    brief="analyzes a game"
)
async def analyze(ctx, *args):
    global REQUEST_TIME
    num = 0 if len(args) == 0 else int(args[0])
    if CUR is None:
        await ctx.send("Cannot fetch history right now, as the db is down")
    else:
        CUR.execute(f"Select PGN,link,MatchID from Matches WHERE User1ID={ctx.author.id} OR User2ID={ctx.author.id} ORDER BY date")
        try:
            req = CUR.fetchmany(num)
            req = req[num-1]
        except:
            await ctx.send(f"Cannot find a game number {num}")
            return
            #also check if link is alread yehrer and update in dv

        if req[1] is None:
            if REQUEST_TIME is None or REQUEST_TIME-datetime.now() > timedelta(hours=1):
                REQUEST_TIME = None
                r = requests.post('https://lichess.org/api/import', data = {'pgn':req[0]})
                if r.status_code == 200:
                    txt = r.text.split(":\"")[2][0:-2]
                    await ctx.send(txt)
                    CUR.execute(f"update Matches SET link=\"{txt}\" WHERE MatchID={req[2]}")
                elif r.status_code == 400:
                    await ctx.send("Unable to fetch, currently rate limited")
                    REQUEST_TIME = datetime.now()
                else:
                    print("Some request error")
            else:
                await ctx.send("Unable to analize game, rate limit has been reached. You can get the pgn and upload yourself by calling pgn and going to https://lichess.org/paste")
        else:
            await ctx.send(req[1])

    return


@client.command(
    help="Changes the user's settings when the board is output",
    brief="Changes the user's settings",
    aliases=["s","Settings"]
)
async def settings(ctx, *args):
    num = 0 if len(args) == 0 else int(args[0])
    if CUR is None:
        await ctx.send("Cannot change settings right now, as the db is down")
    else:
        return
        """
        try:

            if len(args) == 0:
                return

            for arg in args:
                update_str = ""
                arg = arg.split("=")
                if arg[0] == "checks":
                    update_str.append(f"checks={arg[1]}")
                elif arg[0] == "coords":
                    update_str.append(f"coords={arg[1]}")
                elif arg[0] == "lastmove"
                    update_str.append(f"lastmove={arg[1]}")
            CUR.execute(f"update UserSettings SET Command=\"{args[0][0]}\" WHERE GuildID={ctx.guild.id}")
        except mariadb.Error as e:
            CUR.execute("insert into UserSettings(UserID,Coord,Checks,lastmove) values(%d,%s)", (ctx.user.id,))

        await ctx.channel.send("Prefix updated to {}".format(args[0][0]))
        """


@client.command(
    help="Returns the pgn of a specified game from the user's history",
    brief="gets pgn of a game",
    aliases=["PGN"]
)
async def pgn(ctx, *args):
    num = 0 if len(args) == 0 else int(args[0])
    if CUR is None:
        await ctx.send("Cannot fetch history right now, as the db is down")
    else:
        CUR.execute(f"Select PGN from Matches WHERE User1ID={ctx.author.id} OR User2ID={ctx.author.id} ORDER BY date")
        try:
            req = CUR.fetchmany()
            req = req[num-1]
        except:
            await ctx.send(f"Cannot find a game number {num}")
            return
        await ctx.send(req[0])

    return



class ChessGame:

    #Contructor
    def __init__(self, pC, pA, chan, w):
        if w == "black":
            self.playerWhite = pA
            self.playerBlack = pC
        else:
            self.playerWhite = pC
            self.playerBlack = pA

        self.channel = chan
        self.white = w
        self.board = chess.Board()
        self.attempts = []
        self.prevErr = None
        self.prevErr2 = None
        self.prev = None
        self.prev2 = None
        self.svg = None
        self.pgn = None
        self.turnMsg = None
        self.turnMsg2 = None
        self.draw_offer = False
        self.draw_offer_side = None #white = true, black = false
        self.pWhiteSettings = None
        self.pBlackSettings = None

        if CUR is not None:
            if self.playerWhite != 0:
                CUR.execute(f"SELECT Coord,Checks,lastmove from UserSettings WHERE UserID={self.playerWhite.id}")
                self.pWhiteSettings = CUR.fetchone()
            elif self.playerBlack != 0:
                CUR.execute(f"SELECT Coord,Checks,lastmove from UserSettings WHERE UserID={self.playerBlack.id}")
                self.pBlackSettings = CUR.fetchone()


    #Sends the initial board state to the channel the game was started in
    async def start_game(self):
        #check whose turn it is then fetch their settings but for now.
        FILE = open("board.png", "wb")
        FILE.write(cairosvg.svg2png(chess.svg.board(board=self.board, size=500)))
        self.turnMsg = await self.channel.send(f"<@!{self.playerWhite.id}> to move")
        self.prev = await self.channel.send(file=discord.File("board.png"))
        FILE.close()


    #Parses the input, plays the board on the internal board, then creates and sends the board image
    async def play_move(self, stri, id, msg):
        try:
            if (self.board.turn == chess.WHITE and self.playerWhite.id == id) or (self.board.turn == chess.BLACK and self.playerBlack.id  == id):
                #push the move onto the board
                #print(stri)
                stri_l = stri.lower()
                if stri_l == "castle":
                    self.board.push_san("O-O")
                elif stri_l == "castlelong":
                    self.board.push_san("O-O-O")
                elif stri_l == "draw":
                    return
                    '''if self.board.can_claim_draw() and ((self.board.turn == chess.WHITE and self.playerWhite.id == id)  or (self.board.turn == chess.BLACK and self.playerBlack.id == id)):
                        self.board.

                    if self.draw_offer:
                        if (self.draw_offer_side and self.playerBlack.id == id) or (not self.draw_offer_side and self.playerWhite.id == id):
                            #handle draw
                    else:
                        if self.draw_offer_side is None:
                            if self.playerWhite.id == id:
                                self.
                                self.channel.send(f"Draw has been offered from <@!{self.playerWhite.id}>")
                            else:
                                self.channel.send(f"Draw has been offered from <@!{self.playerBlack.id}>")'''

                    #process a draw
                else:
                    self.board.push_san(stri)

                #if here move got played correctly
                #so, delete the error message and all attempts
                if self.prevErr is not None:
                    await clear_errors()


                #am able to control the time the control difficulty now that it is awaited
                if self.playerWhite == 0 or self.playerBlack == 0:
                    mv = await ENG.play(self.board, chess.engine.Limit(time=0.5))
                    self.board.push(mv.move)


                if self.board.turn == chess.WHITE:
                    self.turnMsg2 = await self.channel.send(f"<@!{self.playerWhite.id}> to move")
                    if self.pWhiteSettings is None:
                        self.svg = chess.svg.board(board=self.board, lastmove=self.board.peek(), check=self.board.checkers(), size=500)
                    else:
                        #settings are in order of coord,checks,lastmove
                        self.svg = chess.svg.board(board=self.board, size=500)
                        self.svg.coordinates = self.pWhiteSettings[0]
                        if self.pWhiteSettings[1]:
                            self.svg.check = self.board.checkers()
                        if self.pWhiteSettings[2]:
                            self.svg.lastmove = self.board.peek()

                else:
                    self.turnMsg2 = await self.channel.send(f"<@!{self.playerBlack.id}> to move")
                    if self.pBlackSettings is None:
                        self.svg = chess.svg.board(board=self.board, orientation=chess.BLACK, lastmove=self.board.peek(),check=self.board.checkers() ,size=500)
                    else:
                        #settings are in order of coord,checks,lastmove
                        self.svg = chess.svg.board(board=self.board, size=500)
                        self.svg.coordinates = self.pBlackSettings[0]
                        if self.pBlackSettings[1]:
                            self.svg.check = self.board.checkers()
                        if self.pBlackSettings[2]:
                            self.svg.lastmove = self.board.peek()

                FILE = open("board.png","wb")
                FILE.write(cairosvg.svg2png(self.svg))
                self.prev2 = await self.channel.send(file=discord.File("board.png"))
                FILE.close()

                if self.prev is not None:
                    await self.prev.delete()
                await msg.delete()
                self.prev = self.prev2

                if self.turnMsg is not None:
                    await self.turnMsg.delete()
                self.turnMsg = self.turnMsg2


                if self.board.is_game_over():
                    return await end_game()
                else:
                    return None
            else:
                return None
        except ValueError:
            #move was invalid
            self.prevErr2 = await self.channel.send("Invalid Move")
            if self.prevErr is not None:
                await self.prevErr.delete()
                self.prevErr = None
            self.prevErr = self.prevErr2
            self.prevErr2 = None
            self.attempts.append(msg)
            return None


    async def clear_errors():
        await self.prevErr.delete()
        self.prevErr = None
        for m in range(len(self.attempts)):
            await self.attempts[m].delete()
        self.attempts = []

    async def end_game():
        await self.channel.send("Game is over")
        self.pgn = chess.pgn.Game.from_board(self.board)
        self.pgn.headers.__delitem__("Event")
        self.pgn.headers.__delitem__("Site")
        self.pgn.headers.__delitem__("Round")
        self.pgn.headers.__setitem__("Date",datetime.now().strftime("%Y.%m.%d"))
        self.pgn.headers.__setitem__("White","Scuffed Stockfish" if self.playerWhite == 0 else self.playerWhite.name)
        self.pgn.headers.__setitem__("Black","Scuffed Stockfish" if self.playerBlack == 0 else self.playerBlack.name)


        if self.board.result() == "1/2-1/2":
            return (0,1)
        if self.board.result() == "1-0":
            return (1,0)
        else:
            return (0,0)


#Run
client.run(os.getenv("DISCORD_TOKEN"))
