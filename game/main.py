#import pygbag.aio as asyncio
import pygame
import numpy as np
import asyncio
import sys
import os
import logging

from human import HumanCardPlayer

# Set logging level to suppress warnings
logging.getLogger().setLevel(logging.ERROR)
# Just disables the warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# This import is only to help PyInstaller when generating the executables
import tensorflow as tf

from pathlib import Path

from table import Table
from drawing_func import redraw_bidding, redraw_playing, redraw_score
from player import Player
from buttons import Button
from card import Card

import conf
from nn.models import Models
from sample import Sample
from bidding import bidding
import deck52
from claim import Claimer
from objects import CardResp

from bots import BotBid, CardPlayer, BotLead

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

lobby_btn = Button(120, 60, (7, 32, 110), "Leave", 30, 900)
skip_btn = Button(120, 60, (7, 32, 110), "Skip", 30, 820)
table = Table(1)
table.set_player(0,"You")
table.set_player(1,"BEN")
table.set_player(2,"BEN")
table.set_player(3,"BEN")
user = Player("You")
user.position = 0
buttons = [lobby_btn, skip_btn]

configfile = "ben.conf"

verbose = False
ns = -1
ew = -1

async def get_user_input():
    waiting = True
    resp = None
    while waiting: 
        # If we are declarer or it is dummys turn wait for user input
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONUP:
                if lobby_btn.on_button():
                    pygame.quit()
                    sys.exit()
                if skip_btn.on_button():
                    return "Skip"
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
                                        resp = CardResp(card.get_ben_value(), [], [])
                                        table.board.make_move(card.symbol)
                                        redraw_playing(screen, font, font2, buttons, table, table.board, user)
                                        waiting = False
                                else:
                                    resp = CardResp(card.get_ben_value(), [], [])
                                    table.board.make_move(card.symbol)
                                    redraw_playing(screen, font, font2, buttons, table, table.board, user)
                                    waiting = False

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
                                            resp = CardResp(card.get_ben_value(), [], [])
                                            table.board.make_move(card.symbol)
                                            redraw_playing(screen, font, font2, buttons, table, table.board, user)
                                            waiting = False
                                    else:
                                        resp = CardResp(card.get_ben_value(), [], [])
                                        table.board.make_move(card.symbol)
                                        redraw_playing(screen, font, font2, buttons, table, table.board, user)
                                        waiting = False
        await asyncio.sleep(0)
    return resp
    

async def play(models, sampler, board, opening_lead52):
    # BEN is using 0,1,2,3 for positions so player is South and no 2
    # But pygame is having 0 as south, so North is No 2 (When checking turn)
    contract = bidding.get_contract(board.auction)
    
    level = int(contract[0])
    strain_i = bidding.get_strain_i(contract)
    decl_i = bidding.get_decl_i(contract)
    is_decl_vuln = board.vulnerable[decl_i]

    lefty_hand = board.hands[(decl_i + 1) % 4]
    dummy_hand = board.hands[(decl_i + 2) % 4]
    righty_hand = board.hands[(decl_i + 3) % 4]
    decl_hand = board.hands[decl_i]
    card_players = [
        CardPlayer(models.player_models,0,lefty_hand, dummy_hand,table.board.winning_bid,is_decl_vuln,verbose),
        CardPlayer(models.player_models,1,dummy_hand, decl_hand,table.board.winning_bid,is_decl_vuln,verbose),
        CardPlayer(models.player_models,2,righty_hand, dummy_hand,table.board.winning_bid,is_decl_vuln,verbose),
        CardPlayer(models.player_models,3,decl_hand, dummy_hand,table.board.winning_bid,is_decl_vuln,verbose)
    ]

    # check if user is playing and is declarer
    if decl_i == 2:
        card_players[1] = HumanCardPlayer(models.player_models,1,dummy_hand, decl_hand,table.board.winning_bid,is_decl_vuln)
        card_players[3] = HumanCardPlayer(models.player_models,3,decl_hand, dummy_hand,table.board.winning_bid,is_decl_vuln)
    #if decl_i == 0:
        # Let the bot play it out
    if decl_i == 3:
        card_players[2] = HumanCardPlayer(models.player_models,2,righty_hand, dummy_hand,table.board.winning_bid,is_decl_vuln)
    if decl_i == 1:
        card_players[0] = HumanCardPlayer(models.player_models,0,lefty_hand, dummy_hand,table.board.winning_bid,is_decl_vuln)


    claimer = Claimer(verbose)

    player_cards_played = [[] for _ in range(4)]
    shown_out_suits = [set() for _ in range(4)]

    leader_i = 0

    tricks = []
    tricks52 = []
    trick_won_by = []

    opening_lead = deck52.card52to32(opening_lead52)

    current_trick = [opening_lead]
    current_trick52 = [opening_lead52]

    card_players[0].hand52[opening_lead52] -= 1

    for trick_i in range(12):
        if trick_i != 0:
            if verbose:
                print("trick {}".format(trick_i+1))
            await asyncio.sleep(1)


        for player_i in map(lambda x: x % 4, range(leader_i, leader_i + 4)):
            if verbose:
                print('player {}'.format(player_i))
            
            if trick_i == 0 and player_i == 0:
                if verbose:
                    print('skipping opening lead for ',player_i)
                for i, card_player in enumerate(card_players):
                    card_player.set_card_played(trick_i=trick_i, leader_i=leader_i, i=0, card=opening_lead)
                continue

            if trick_i > 0 and len(current_trick) == 0 and player_i in (1, 3):
                claimer.claim(
                    strain_i=strain_i,
                    player_i=player_i,
                    hands52=[card_player.hand52 for card_player in card_players],
                    n_samples=20
                )

            rollout_states = None
            #print(player_i)
            if isinstance(card_players[player_i], CardPlayer):
                rollout_states = sampler.init_rollout_states(trick_i, player_i, card_players, player_cards_played, shown_out_suits, current_trick, board.auction, card_players[player_i].hand.reshape((-1, 32)), [board.vulnerable[0], board.vulnerable[1]], models, ns, ew)
                card_resp = card_players[player_i].play_card(trick_i, leader_i, current_trick52, rollout_states)  
                #print(card_resp.card)         
                card52 = deck52.encode_card(card_resp.card.symbol())
                table.board.make_move(card_resp.card.symbol().replace("A","14").replace("K","13").replace("Q","12").replace("J","11").replace("T","10"))
                redraw_playing(screen, font, font2, buttons, table, table.board, user)
                await asyncio.sleep(0)

            else:
                card_resp = await get_user_input()
                if (card_resp == "Skip"): return "Skip"
                card52 = deck52.encode_card(card_resp.card.replace("14","A").replace("13","K").replace("12","Q").replace("11","J").replace("10","T"))

            card = deck52.card52to32(card52)

            for card_player in card_players:
                card_player.set_card_played(trick_i=trick_i, leader_i=leader_i, i=player_i, card=card)

            current_trick.append(card)

            current_trick52.append(card52)

            card_players[player_i].set_own_card_played52(card52)
            if player_i == 1:
                for i in [0, 2, 3]:
                    card_players[i].set_public_card_played52(card52)
            if player_i == 3:
                card_players[1].set_public_card_played52(card52)

            # update shown out state
            if card // 8 != current_trick[0] // 8:  # card is different suit than lead card
                shown_out_suits[player_i].add(current_trick[0] // 8)

        # sanity checks after trick completed
        assert len(current_trick) == 4

        for i, card_player in enumerate(card_players):
            assert np.min(card_player.hand52) == 0
            assert np.min(card_player.public52) == 0
            assert np.sum(card_player.hand52) == 13 - trick_i - 1
            assert np.sum(card_player.public52) == 13 - trick_i - 1

        tricks.append(current_trick)
        tricks52.append(current_trick52)

        # initializing for the next trick
        # initialize hands
        for i, card in enumerate(current_trick):
            card_players[(leader_i + i) % 4].x_play[:, trick_i + 1, 0:32] = card_players[(leader_i + i) % 4].x_play[:, trick_i, 0:32]
            card_players[(leader_i + i) % 4].x_play[:, trick_i + 1, 0 + card] -= 1

        # initialize public hands
        for i in (0, 2, 3):
            card_players[i].x_play[:, trick_i + 1, 32:64] = card_players[1].x_play[:, trick_i + 1, 0:32]
        card_players[1].x_play[:, trick_i + 1, 32:64] = card_players[3].x_play[:, trick_i + 1, 0:32]

        for card_player in card_players:
            # initialize last trick
            for i, card in enumerate(current_trick):
                card_player.x_play[:, trick_i + 1, 64 + i * 32 + card] = 1
                
            # initialize last trick leader
            card_player.x_play[:, trick_i + 1, 288 + leader_i] = 1

            # initialize level
            card_player.x_play[:, trick_i + 1, 292] = level

            # initialize strain
            card_player.x_play[:, trick_i + 1, 293 + strain_i] = 1

        # sanity checks for next trick
        for i, card_player in enumerate(card_players):
            assert np.min(card_player.x_play[:, trick_i + 1, 0:32]) == 0
            assert np.min(card_player.x_play[:, trick_i + 1, 32:64]) == 0
            assert np.sum(card_player.x_play[:, trick_i + 1, 0:32], axis=1) == 13 - trick_i - 1
            assert np.sum(card_player.x_play[:, trick_i + 1, 32:64], axis=1) == 13 - trick_i - 1

        trick_winner = (leader_i + deck52.get_trick_winner_i(current_trick52, (strain_i - 1) % 5)) % 4
        trick_won_by.append(trick_winner)

        if trick_winner % 2 == 0:
            card_players[0].n_tricks_taken += 1
            card_players[2].n_tricks_taken += 1
        else:
            card_players[1].n_tricks_taken += 1
            card_players[3].n_tricks_taken += 1

        # update cards shown
        for i, card in enumerate(current_trick):
            player_cards_played[(leader_i + i) % 4].append(card)
        
        leader_i = trick_winner
        current_trick = []
        current_trick52 = []
        # Check for buttons
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONUP:
                if lobby_btn.on_button():
                    pygame.quit()
                    sys.exit()
                if skip_btn.on_button():
                    return "Skip"
        await asyncio.sleep(0)

    # play last trick
    print("trick 13")
    for player_i in map(lambda x: x % 4, range(leader_i, leader_i + 4)):
        
        if not isinstance(card_players[player_i], CardPlayer):
            card_resp = await get_user_input()
            if (card_resp == "Skip"): return "Skip"
            card52 = deck52.encode_card(card_resp.card.replace("14","A").replace("13","K").replace("12","Q").replace("11","J").replace("10","T"))
        else:
            card52 = np.nonzero(card_players[player_i].hand52)[0][0]
            last_card = deck52.decode_card(card52)
            table.board.make_move(last_card.replace("A","14").replace("K","13").replace("Q","12").replace("J","11").replace("T","10"))
            redraw_playing(screen, font, font2, buttons, table, table.board, user)
            await asyncio.sleep(0)

        card =deck52.card52to32(card52)

        current_trick.append(card)
        current_trick52.append(card52)

    tricks.append(current_trick)
    tricks52.append(current_trick52)

    trick_winner = (leader_i + deck52.get_trick_winner_i(current_trick52, (strain_i - 1) % 5)) % 4
    trick_won_by.append(trick_winner)

async def main():

    configuration = conf.load(configfile)

    models = Models.from_conf(configuration, ".")

    board_no = 0
    level = 0.1
    sampler = Sample.from_conf(configuration, verbose)
    # Main game loop
    running = True
    while running:
        await asyncio.sleep(0)
        board_no += 1
        print("Playing: ", board_no)
        table.next_board(board_no)
        skip = await bid_board(models, sampler, level)
        if skip == "Skip": continue
        # The board is passed out, dealing next board
        if not table.board.declarer:
            redraw_score(screen, font, font2, buttons, table, table.board, user)
        else:
            card_resp = await opening_lead(models, sampler)
            if (card_resp == "Skip"): continue
            print("Opening lead: ",card_resp.card)
            skip = await play(models, sampler, table.board, deck52.encode_card(card_resp.card))
            if skip == "Skip": continue
        # Board is done, displaying score and dealing next board
        if table.board.score:
            pygame.time.delay(500)
            redraw_score(screen, font, font2, buttons, table, table.board, user)
            pygame.time.delay(4000)

        pygame.display.update()
        await asyncio.sleep(0)

async def opening_lead(models, sampler):
    if table.board.turn == 0:
        lead_hand = table.board.south
    elif table.board.turn == 1:
        lead_hand = table.board.west
    elif table.board.turn == 2:
        lead_hand = table.board.north
    else:
        lead_hand = table.board.east
            # We are on lead
    if table.board.turn != 0:
        bot_lead = BotLead([table.board.vulnerable[0], table.board.vulnerable[1]],lead_hand,models,ns,ew,models.lead_threshold,sampler,verbose)
        card_resp = bot_lead.find_opening_lead(table.board.auction)
        table.board.make_move(card_resp.card.symbol().replace("A","14").replace("K","13").replace("Q","12").replace("J","11").replace("T","10"))
        redraw_playing(screen, font, font2, buttons, table, table.board, user)
        await asyncio.sleep(0)
    else:
        card_resp = await get_user_input()

        if (card_resp == "Skip"): return "Skip"


    return card_resp

async def bid_board(models, sampler, level):
    bidding = True
    west = BotBid([table.board.vulnerable[0], table.board.vulnerable[1]],table.board.west,models,ns, ew, level, sampler, verbose)
    north = BotBid([table.board.vulnerable[0], table.board.vulnerable[1]],table.board.north,models,ns, ew, level, sampler, verbose)
    east = BotBid([table.board.vulnerable[0], table.board.vulnerable[1]],table.board.east,models,ns, ew, level, sampler, verbose)
    redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)
    await asyncio.sleep(0)
    while bidding:
        if table.board.turn == 1:
            bid_resp = west.bid(table.board.auction)
        if table.board.turn == 2:
            bid_resp = north.bid(table.board.auction)
        if table.board.turn == 3:
            bid_resp = east.bid(table.board.auction)
        if table.board.turn != user.position:
            table.board.make_bid(table.board.turn,bid_resp.bid)
            redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONUP:
                if lobby_btn.on_button():
                    pygame.quit()
                    sys.exit()
                if skip_btn.on_button():
                    return "Skip"

                    # Iterating over levels and their denominations
                for bid, bid_suits in table.board.available_bids.items():
                        # Clicking on the level bid
                    if bid.click():
                        for b in table.board.available_bids.keys():
                            b.active = False
                        bid.active = True
                        redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)
                        # Clicking on the denomination, if the level bid has been chosen
                    if bid.active:
                        for bid_suit in bid_suits:
                            if bid_suit.click():
                                clicked_bid = bid.bid + bid_suit.bid
                                table.board.make_bid(table.board.turn,clicked_bid)
                                redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)
                                        # Clicking on fold or double/redouble bids
                for special_bid in table.board.special_bids:
                    if special_bid.click():
                        table.board.make_bid(table.board.turn,special_bid.bid)
                        redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)

        bidding = not table.board.end_bidding()
        await asyncio.sleep(0)
    # Bidding ended, so redraw
    print(table.board.available_bids)
    print(table.board.special_bids)
    redraw_bidding(screen, font, buttons, table, table.board, user, table.board.available_bids, table.board.special_bids)

    print("Contract: ",table.board.winning_bid)


# Quit Pygame
# pygame.quit()
# sys.exit()

asyncio.run(main())
