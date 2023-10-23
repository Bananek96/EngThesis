from functools import reduce

import json
import requests
import sqlite3

from utility.hash_util import hash_block
from utility.verification import Verification
from block import Block
from transfer import Transfer
from users import User


class Blockchain:
    def __init__(self, public_key, node_id):
        genesis_block = Block(0, '', [], 100, 0)
        self.chain = [genesis_block]
        self.__open_transfers = []
        self.public_key = public_key
        self.__peer_nodes = set()
        self.node_id = node_id
        self.resolve_conflicts = False

        self.conn = sqlite3.connect('blockchain-{}.db'.format(self.node_id))
        self.cursor = self.conn.cursor()

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS blockchain (
                block_id INTEGER PRIMARY KEY,
                block_data TEXT
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS open_transfers (
                transfer_id INTEGER PRIMARY KEY,
                sender TEXT,
                recipient TEXT,
                filename TEXT,
                file BLOB,
                signature TEXT
            )
        ''')

        self.conn.commit()
        self.load_data()

    @property
    def chain(self):
        return self.__chain[:]

    @chain.setter
    def chain(self, val):
        self.__chain = val

    def get_open_transfers(self):
        return self.__open_transfers[:]

    def get_last_blockchain_value(self):
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]

    def get_balance(self, sender=None):
        if sender is None:
            if self.public_key is None:
                return None
            participant = self.public_key
        else:
            participant = sender

        tx_sender = [[tx.file for tx in block.transfers if tx.sender == participant] for block in self.__chain]

        open_tx_sender = [tx.file for tx in self.__open_transfers if tx.sender == participant]
        tx_sender.append(open_tx_sender)

        count_files_sent = sum(len(tx_amt) for tx_amt in tx_sender)

        tx_recipient = [[tx.file for tx in block.transfers if tx.recipient == participant] for block in self.__chain]

        count_files_received = sum(len(tx_amt) for tx_amt in tx_recipient)

        return count_files_received + count_files_sent

    def mine_block(self, file):
        if self.public_key is None:
            return None
        last_block = self.__chain[-1]

        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()
        reward_transfer = Transfer('SYSTEM', self.public_key, '', file)

        copied_transfers = self.__open_transfers[:]
        for tx in copied_transfers:
            if not User.verify_transfer(tx):
                return None
        copied_transfers.append(reward_transfer)

        block = Block(
            len(self.__chain),
            hashed_block,
            copied_transfers,
            proof
        )

        self.__chain.append(block)
        self.__open_transfers = []
        self.save_data()

        for node in self.__peer_nodes:
            url = f'http://{node}/broadcast-block'
            converted_block = block.__dict__.copy()
            converted_block['transfers'] = [tx.__dict__ for tx in converted_block['transfers']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or 500:
                    print('Block declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return block

    def add_transfer(self, recipient, sender, file, signature, is_receiving=False):
        transfer = Transfer(sender, recipient, signature, file)
        if Verification.verify_transfer(transfer, self.get_balance):
            self.__open_transfers.append(transfer)
            self.save_data()
            if not is_receiving:
                for node in self.__peer_nodes:
                    url = 'http://{}/broadcast-transfer'.format(node)
                    try:
                        response = requests.post(url,
                                                 json={
                                                     'sender': sender,
                                                     'recipient': recipient,
                                                     'file': file,
                                                     'signature': signature
                                                 })
                        if (response.status_code == 400 or
                                response.status_code == 500):
                            print('transfer declined, needs resolving')
                            return False
                    except requests.exceptions.ConnectionError:
                        continue
            return True
        return False

    def add_block(self, block):
        transfers = [Transfer(
            tx['sender'],
            tx['recipient'],
            tx['signature'],
            tx['file']) for tx in block['transfers']]

        proof_is_valid = Verification.valid_proof(
            transfers[:-1], block['previous_hash'], block['proof'])

        hashes_match = hash_block(self.chain[-1]) == block['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        converted_block = Block(
            block['index'],
            block['previous_hash'],
            transfers,
            block['proof'],
            block['timestamp'])
        self.__chain.append(converted_block)
        stored_transfers = self.__open_transfers[:]

        for itx in block['transfers']:
            for opentx in stored_transfers:
                if (opentx.sender == itx['sender'] and
                        opentx.recipient == itx['recipient'] and
                        opentx.file == itx['file'] and
                        opentx.signature == itx['signature']):
                    try:
                        self.__open_transfers.remove(opentx)
                    except ValueError:
                        print('Item was already removed')
        self.save_data()
        return True

    def proof_of_work(self):
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        proof = 0

        while not Verification.valid_proof(
            self.__open_transfers,
            last_hash, proof
        ):
            proof += 1
        return proof

    def save_data(self):
        saveable_chain = json.dumps([block.__dict__ for block in self.__chain])
        saveable_open_transfers = json.dumps(
            [tx.__dict__ for tx in self.__open_transfers])

        self.cursor.execute('DELETE FROM blockchain')
        self.cursor.execute('DELETE FROM open_transfers')
        self.cursor.execute('INSERT INTO blockchain (block_data) VALUES (?)', (saveable_chain,))
        self.cursor.execute('INSERT INTO open_transactions (sender, recipient, file, signature) VALUES (?, ?, ?, ?)', (sender, recipient, file, signature))

        self.conn.commit()

    def load_data(self):
        self.chain = []
        self.__open_transfers = []

        self.cursor.execute('SELECT block_data FROM blockchain')
        data = self.cursor.fetchone()
        if data:
            blockchain_data = json.loads(data[0])
            self.chain = [Block(**block) for block in blockchain_data]

        self.cursor.execute('SELECT * FROM open_transfers')
        data = self.cursor.fetchall()
        if data:
            self.__open_transfers = [Transfer(sender=row[1], recipient=row[2], file=row[3], signature=row[4]) for row in data]

    def resolve(self):
        winner_chain = self.chain
        replace = False
        for node in self.__peer_nodes:
            url = 'http://{}/chain'.format(node)
            try:
                response = requests.get(url)
                node_chain = response.json()
                node_chain = [
                    Block(block['index'],
                          block['previous_hash'],
                          [
                              Transfer(
                                  tx['sender'],
                                  tx['recipient'],
                                  tx['signature'],
                                  tx['file']) for tx in block['transfers']
                          ],
                          block['proof'],
                          block['timestamp']) for block in node_chain
                ]
                node_chain_length = len(node_chain)
                local_chain_length = len(winner_chain)

                if (node_chain_length > local_chain_length and
                        Verification.verify_chain(node_chain)):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        self.chain = winner_chain
        if replace:
            self.__open_transfers = []
        self.save_data()
        return replace

    def add_peer_node(self, node):
        self.__peer_nodes.add(node)
        self.save_data()

    def remove_peer_node(self, node):
        self.__peer_nodes.discard(node)
        self.save_data()

    def get_peer_nodes(self):
        return list(self.__peer_nodes)
