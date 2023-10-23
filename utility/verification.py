"""Provides verification helper methods."""

from utility.hash_util import hash_string_256, hash_block
from users import User


class Verification:
    @staticmethod
    def valid_proof(transfers, last_hash, proof):
        guess = (str([tx.to_ordered_dict() for tx in transfers]) + str(last_hash) + str(proof)).encode()
        guess_hash = hash_string_256(guess)
        return guess_hash[0:2] == '00'

    @classmethod
    def verify_chain(cls, blockchain):
        for (index, block) in enumerate(blockchain):
            if index == 0:
                continue
            if block.previous_hash != hash_block(blockchain[index - 1]):
                return False
            if not cls.valid_proof(block.transfers[:-1], block.previous_hash, block.proof):
                print('Proof of work is invalid')
                return False
        return True

    @staticmethod
    def verify_transfer(transfer, get_balance, check_funds=True):
        if check_funds:
            sender_balance = get_balance(transfer.sender)
            return sender_balance >= transfer.file and User.verify_transfer(transfer)
        else:
            return User.verify_transfer(transfer)

    @classmethod
    def verify_transfers(cls, open_transfers, get_balance):
        return all([cls.verify_transfer(tx, get_balance, False) for tx in open_transfers])
