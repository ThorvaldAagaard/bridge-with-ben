#import pygbag.aio as asyncio
import pygame
import asyncio
import sys
import os
from pathlib import Path

from table import Table
from drawing_func import redraw_bidding, redraw_playing, redraw_score
from player import Player
from buttons import Button

# Initialize Pygame
pygame.init()
try:
    base_directory = Path(__file__).parent
except:
    base_directory = os.getcwd()

# Images
icon = pygame.image.load(os.path.join(base_directory, "images/icon.png"))

# Constants
WIDTH, HEIGHT = 1200, 1000
WHITE = (255, 255, 255)

font = pygame.font.SysFont("Arial", 32)
font2 = pygame.font.SysFont("Arial", 64)

# Create the Pygame window
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Bridge with BEN")
pygame.display.set_icon(icon)

lobby_btn = Button(200, 80, (7, 32, 110), "Leave", 30, 900)
table = Table(1)
table.set_player(0,"You")
table.set_player(1,"BEN")
table.set_player(2,"BEN")
table.set_player(3,"BEN")
user = Player("You")
user.position = 0
buttons = [lobby_btn]

async def main():

    board_no = 0
    running = True
    # Main game loop
    while running:
        await asyncio.sleep(0)
        board_no += 1
        table.next_board(board_no)
        bidding = True
        while bidding:
            #print(table.board.turn, bidding)
            if table.board.turn != user.position:
                table.board.make_bid(table.board.turn,"pas")
                redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.MOUSEBUTTONUP:
                    if lobby_btn.on_button():
                        pygame.quit()
                        sys.exit()

                    # Iterating over levels and their denominations
                    for bid, bidSuits in table.board.available_bids.items():
                        # Clicking on the level bid
                        if bid.click():
                            for b in table.board.available_bids.keys():
                                b.active = False
                            bid.active = True
                            redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)
                        # Clicking on the denomination, if the level bid has been chosen
                        if bid.active:
                            for bidSuit in bidSuits:
                                if bidSuit.click():
                                    clicked_bid = bid.bid + bidSuit.bid
                                    table.board.make_bid(table.board.turn,clicked_bid)
                                    redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)
            bidding = not table.board.end_bidding()
            await asyncio.sleep(0)

        # The board is passed out, dealing next board
        if not table.board.declarer:
            redraw_score(screen, font, font2, buttons, table, table.board, user)
        else:
            playing = True

            while playing:
                if table.board.turn == 1:
                    print(table.board.west[0].symbol)
                    table.board.make_move(table.board.west[0].symbol)
                    redraw_playing(screen, font, font2, buttons, table, table.board, user)
                if table.board.turn == 3:
                    print(table.board.east[0].symbol)
                    table.board.make_move(table.board.east[0].symbol)
                    redraw_playing(screen, font, font2, buttons, table, table.board, user)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    if event.type == pygame.MOUSEBUTTONUP:
                        if lobby_btn.on_button():
                            pygame.quit()
                            sys.exit()

                        # Dummy can't do any move
                        if user.position != table.board.dummy:
                            # Player's turn
                            if user.position == table.board.turn:
                                # We are always South
                                hand = table.board.south
                                for card in hand:
                                    # Play specific card (if able to do so)
                                    if card.click():
                                        if table.board.color_lead and any(c.symbol[0] == table.board.color_lead for c in hand):
                                            if card.symbol[0] == table.board.color_lead:
                                                table.board.make_move(card.symbol)
                                                redraw_playing(screen, font, font2, buttons, table, table.board, user)
                                        else:
                                            table.board.make_move(card.symbol)
                                            redraw_playing(screen, font, font2, buttons, table, table.board, user)

                            # Declarer plays dummy hand too
                            elif user.position in table.board.declarer[1]:
                                if table.board.dummy == table.board.turn:
                                    if table.board.dummy == 0:
                                        dummy_hand = table.board.south
                                    elif table.board.dummy == 1:
                                        dummy_hand = table.board.west
                                    elif table.board.dummy == 2:
                                        dummy_hand = table.board.north
                                    else:
                                        dummy_hand = table.board.east

                                    for card in dummy_hand:
                                        # Play specific card (if able to do so)
                                        if card.click():
                                            if table.board.color_lead and any(c.symbol[0] == table.board.color_lead for c in dummy_hand):
                                                if card.symbol[0] == table.board.color_lead:
                                                    table.board.make_move(card.symbol)
                                                    redraw_playing(screen, font, font2, buttons, table, table.board, user)
                                            else:
                                                table.board.make_move(card.symbol)
                                                redraw_playing(screen, font, font2, buttons, table, table.board, user)
                playing = table.board.score == 0
                await asyncio.sleep(0)

        # Board is done, displaying score and dealing next board
        if table.board.score:
            pygame.time.delay(500)
            redraw_score(screen, font, font2, buttons, table, table.board, user)
            pygame.time.delay(4000)

        pygame.display.update()
        await asyncio.sleep(0)


# Quit Pygame
# pygame.quit()
# sys.exit()

asyncio.run(main())
