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

class ChessGame:
    #Contructor
    def __init__(self, pC, pA, chan, side):
        if side == "black":
            self.playerWhite = pA
            self.playerBlack = pC
        else:
            self.playerWhite = pC
            self.playerBlack = pA

        if self.playerWhite == 0 or self.playerBlack == 0:
            self.bot = True
        else:
            self.bot = False

        #channel in which game is occuring
        self.channel = chan
        #chess board object in which the game is being played
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


    #Sends the initial board state to the channel the game was started in
    async def start_game(self):
        FILE = open("board.png", "wb")
        FILE.write(cairosvg.svg2png(chess.svg.board(board=self.board, size=500)))
        self.turnMsg = await self.channel.send(f"<@!{self.playerWhite.id}> to move")
        self.prev = await self.channel.send(file=discord.File("board.png"))
        FILE.close()


    #Parses the input, plays the board on the internal board, then creates and sends the board image
    async def play_move(self, stri, id, msg, engine):
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
                elif stri_l == "ff" or stri_l == "forfeit" or stri_l == "resign":
                    return

                else:
                    self.board.push_san(stri)

                #if here move got played correctly
                #so, delete the error message and all attempts
                if self.prevErr is not None:
                    await self.clear_errors()

                #if the bot is playing request a move from the engine
                if self.bot:
                    mv = await engine.play(self.board, chess.engine.Limit(time=0.5))
                    self.board.push(mv.move)


                if self.board.turn == chess.WHITE:
                    self.turnMsg2 = await self.channel.send(f"<@!{self.playerWhite.id}> to move")
                    self.svg = chess.svg.board(board=self.board, lastmove=self.board.peek(), size=500)
                else:
                    self.turnMsg2 = await self.channel.send(f"<@!{self.playerBlack.id}> to move")
                    self.svg = chess.svg.board(board=self.board, orientation=chess.BLACK, lastmove=self.board.peek(),size=500)

                #create the board image and send it in the channel
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
                    return await self.end_game()
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


    async def clear_errors(self):
        await self.prevErr.delete()
        self.prevErr = None
        for m in range(len(self.attempts)):
            await self.attempts[m].delete()
        self.attempts = []

    async def end_game(self):
        await self.channel.send("Game is over")
        self.pgn = chess.pgn.Game.from_board(self.board)
        self.pgn.headers.__delitem__("Event")
        self.pgn.headers.__delitem__("Site")
        self.pgn.headers.__delitem__("Round")
        self.pgn.headers.__setitem__("Date",datetime.now().strftime("%Y.%m.%d"))
        self.pgn.headers.__setitem__("White","Stockfish" if self.playerWhite == 0 else self.playerWhite.name)
        self.pgn.headers.__setitem__("Black","Stockfish" if self.playerBlack == 0 else self.playerBlack.name)


        if self.board.result() == "1/2-1/2":
            return (0,1)
        if self.board.result() == "1-0":
            return (1,0)
        else:
            return (0,0)
