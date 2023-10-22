import json
import numpy as np
import bots
import deck52

from binary import *
from bidding.binary import parse_hand_f
from bidding.bidding import can_double, can_redouble
from objects import Card, CardResp, BidResp

class HumanCardPlayer:

    def __init__(self, player_models, player_i, hand, public_hand, contract, is_decl_vuln):
        self.player_models = player_models
        self.model = player_models[player_i]
        self.player_i = player_i
        self.hand_str = bots.hand_as_string(hand)
        self.public_hand_str = bots.hand_as_string(public_hand)
        self.hand = parse_hand_f(32)(self.hand_str).reshape(32)
        self.hand52 = parse_hand_f(52)(self.hand_str).reshape(52)
        self.public52 = parse_hand_f(52)(self.public_hand_str).reshape(52)
        self.n_tricks_taken = 0
        self.contract = contract
        self.is_decl_vuln = is_decl_vuln
        self.level = int(contract[0])
        self.strain_i = bidding.get_strain_i(contract)
        self.init_x_play(parse_hand_f(32)(self.public_hand_str), self.level, self.strain_i)
    
    def init_x_play(self, public_hand, level, strain_i):
        self.level = level
        self.strain_i = strain_i

        self.x_play = np.zeros((1, 13, 298))
        BinaryInput(self.x_play[:,0,:]).set_player_hand(self.hand)
        BinaryInput(self.x_play[:,0,:]).set_public_hand(public_hand)
        self.x_play[:,0,292] = level
        self.x_play[:,0,293+strain_i] = 1

    def set_card_played(self, trick_i, leader_i, i, card):
        played_to_the_trick_already = (i - leader_i) % 4 > (self.player_i - leader_i) % 4

        if played_to_the_trick_already:
            return

        if self.player_i == i:
            return

        # update the public hand when the public hand played
        if self.player_i in (0, 2, 3) and i == 1 or self.player_i == 1 and i == 3:
            self.x_play[:, trick_i, 32 + card] -= 1

        # update the current trick
        offset = (self.player_i - i) % 4   # 1 = rho, 2 = partner, 3 = lho
        self.x_play[:, trick_i, 192 + (3 - offset) * 32 + card] = 1

    def set_own_card_played52(self, card52):
        self.hand52[card52] -= 1

    def set_public_card_played52(self, card52):
        self.public52[card52] -= 1

    async def get_card_input(self):
        card = input('your play: ').strip().upper()
        return deck52.encode_card(card)


