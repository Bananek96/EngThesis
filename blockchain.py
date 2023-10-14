from functools import reduce

import json
import requests

# Import two functions from our hash_util.py file. Omit the ".py" in the import
from utility.hash_util import hash_block
from utility.verification import Verification
from block import Block
from transfer import Transfer
from wallet import Wallet

# The reward we give to miners (for creating a new block)
MINING_REWARD = 10

print(__name__)


class Blockchain:
    """The Blockchain class manages the chain of blocks as well as open
    transfers and the node on which it's running.

    Attributes:
        :chain: The list of blocks
        :open_transfers (private): The list of open transfers
        :hosting_node: The connected node (which runs the blockchain).
    """

    def __init__(self, public_key, node_id):
        """The constructor of the Blockchain class."""
        # Our starting block for the blockchain
        genesis_block = Block(0, '', [], 100, 0)
        # Initializing our (empty) blockchain list
        self.chain = [genesis_block]
        # Unhandled transfers
        self.__open_transfers = []
        self.public_key = public_key
        self.__peer_nodes = set()
        self.node_id = node_id
        self.resolve_conflicts = False
        self.load_data()

    # This turns the chain attribute into a property with a getter (the method
    # below) and a setter (@chain.setter)
    @property
    def chain(self):
        return self.__chain[:]

    # The setter for the chain property
    @chain.setter
    def chain(self, val):
        self.__chain = val

    def get_open_transfers(self):
        """Returns a copy of the open transfers list."""
        return self.__open_transfers[:]

    def load_data(self):
        """Initialize blockchain + open transfers data from a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='r') as f:
                # file_content = pickle.loads(f.read())
                file_content = f.readlines()
                # blockchain = file_content['chain']
                # open_transfers = file_content['ot']
                blockchain = json.loads(file_content[0][:-1])
                # We need to convert  the loaded data because transfers
                # should use OrderedDict
                updated_blockchain = []
                for block in blockchain:
                    converted_tx = [Transfer(
                        tx['sender'],
                        tx['recipient'],
                        tx['signature'],
                        tx['file']) for tx in block['transfers']]
                    updated_block = Block(
                        block['index'],
                        block['previous_hash'],
                        converted_tx,
                        block['proof'],
                        block['timestamp'])
                    updated_blockchain.append(updated_block)
                self.chain = updated_blockchain
                open_transfers = json.loads(file_content[1][:-1])
                # We need to convert  the loaded data because transfers
                # should use OrderedDict
                updated_transfers = []
                for tx in open_transfers:
                    updated_transfer = Transfer(
                        tx['sender'],
                        tx['recipient'],
                        tx['signature'],
                        tx['file'])
                    updated_transfers.append(updated_transfer)
                self.__open_transfers = updated_transfers
                peer_nodes = json.loads(file_content[2])
                self.__peer_nodes = set(peer_nodes)
        except (IOError, IndexError):
            pass
        finally:
            print('Cleanup!')

    def save_data(self):
        """Save blockchain + open transfers snapshot to a file."""
        try:
            with open('blockchain-{}.txt'.format(self.node_id), mode='w') as f:
                saveable_chain = [
                    block.__dict__ for block in
                    [
                        Block(block_el.index,
                              block_el.previous_hash,
                              [tx.__dict__ for tx in block_el.transfers],
                              block_el.proof,
                              block_el.timestamp) for block_el in self.__chain
                    ]
                ]
                f.write(json.dumps(saveable_chain))
                f.write('\n')
                saveable_tx = [tx.__dict__ for tx in self.__open_transfers]
                f.write(json.dumps(saveable_tx))
                f.write('\n')
                f.write(json.dumps(list(self.__peer_nodes)))
                # save_data = {
                #     'chain': blockchain,
                #     'ot': open_transfers
                # }
                # f.write(pickle.dumps(save_data))
        except IOError:
            print('Saving failed!')

    def proof_of_work(self):
        """Generate a proof of work for the open transfers, the hash of the
        previous block and a random number (which is guessed until it fits)."""
        last_block = self.__chain[-1]
        last_hash = hash_block(last_block)
        proof = 0
        # Try different PoW numbers and return the first valid one
        while not Verification.valid_proof(
            self.__open_transfers,
            last_hash, proof
        ):
            proof += 1
        return proof

    def get_balance(self, sender=None):
        """Calculate and return the balance for a participant.
        """
        if sender is None:
            if self.public_key is None:
                return None
            participant = self.public_key
        else:
            participant = sender
        # Fetch a list of all sent file files for the given person (empty
        # lists are returned if the person was NOT the sender)
        # This fetches sent files of transfers that were already included
        # in blocks of the blockchain
        tx_sender = [[tx.file for tx in block.transfers
                      if tx.sender == participant] for block in self.__chain]
        # Fetch a list of all sent file files for the given person (empty
        # lists are returned if the person was NOT the sender)
        # This fetches sent files of open transfers (to avoid double
        # spending)
        open_tx_sender = [
            tx.file for tx in self.__open_transfers
            if tx.sender == participant
        ]
        tx_sender.append(open_tx_sender)
        print(tx_sender)
        file_sent = reduce(lambda tx_sum, tx_amt: tx_sum + sum(tx_amt) if len(tx_amt) > 0 else tx_sum + 0, tx_sender, 0)
        # This fetches received file files of transfers that were already
        # included in blocks of the blockchain
        # We ignore open transfers here because you shouldn't be able to
        # spend files before the transfer was confirmed + included in a
        # block
        tx_recipient = [
            [
                tx.file for tx in block.transfers
                if tx.recipient == participant
            ] for block in self.__chain
        ]
        file_received = reduce(
            lambda tx_sum, tx_amt: tx_sum + sum(tx_amt)
            if len(tx_amt) > 0 else tx_sum + 0,
            tx_recipient,
            0
        )
        # Return the total balance
        return file_received - file_sent

    def get_last_blockchain_value(self):
        """ Returns the last value of the current blockchain. """
        if len(self.__chain) < 1:
            return None
        return self.__chain[-1]

    # This function accepts two arguments.
    # One required one (transfer_file) and one optional one
    # (last_transfer)
    # The optional one is optional because it has a default value => [1]

    def add_transfer(self, recipient, sender, signature, file=1.0, is_receiving=False):
        """ Append a new value as well as the last blockchain value to the blockchain.

        Arguments:
            :sender: The sender of the files.
            :recipient: The recipient of the files.
            :file: The file sent with the transfer
            (default = 1.0)
        """
        # transfer = {
        #     'sender': sender,
        #     'recipient': recipient,
        #     'file': file
        # }
        # if self.public_key == None:
        #     return False
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

    def mine_block(self):
        """Create a new block and add open transfers to it."""
        # Fetch the currently last block of the blockchain
        if self.public_key is None:
            return None
        last_block = self.__chain[-1]
        # Hash the last block (=> to be able to compare it to the stored hash
        # value)
        hashed_block = hash_block(last_block)
        proof = self.proof_of_work()
        # Miners should be rewarded, so let's create a reward transfer
        # reward_transfer = {
        #     'sender': 'MINING',
        #     'recipient': owner,
        #     'file': MINING_REWARD
        # }
        reward_transfer = Transfer(
            'MINING', self.public_key, '', MINING_REWARD)
        # Copy transfer instead of manipulating the original
        # open_transfers list
        # This ensures that if for some reason the mining should fail,
        # we don't have the reward transfer stored in the open transfers
        copied_transfers = self.__open_transfers[:]
        for tx in copied_transfers:
            if not Wallet.verify_transfer(tx):
                return None
        copied_transfers.append(reward_transfer)
        block = Block(len(self.__chain), hashed_block,
                      copied_transfers, proof)
        self.__chain.append(block)
        self.__open_transfers = []
        self.save_data()
        for node in self.__peer_nodes:
            url = 'http://{}/broadcast-block'.format(node)
            converted_block = block.__dict__.copy()
            converted_block['transfers'] = [
                tx.__dict__ for tx in converted_block['transfers']]
            try:
                response = requests.post(url, json={'block': converted_block})
                if response.status_code == 400 or response.status_code == 500:
                    print('Block declined, needs resolving')
                if response.status_code == 409:
                    self.resolve_conflicts = True
            except requests.exceptions.ConnectionError:
                continue
        return block

    def add_block(self, block):
        """Add a block which was received via broadcasting to the lockchain."""
        # Create a list of transfer objects
        transfers = [Transfer(
            tx['sender'],
            tx['recipient'],
            tx['signature'],
            tx['file']) for tx in block['transfers']]
        # Validate the proof of work of the block and store the result (True
        # or False) in a variable
        proof_is_valid = Verification.valid_proof(
            transfers[:-1], block['previous_hash'], block['proof'])
        # Check if previous_hash stored in the block is equal to the local
        # blockchain's last block's hash and store the result in a block
        hashes_match = hash_block(self.chain[-1]) == block['previous_hash']
        if not proof_is_valid or not hashes_match:
            return False
        # Create a Block object
        converted_block = Block(
            block['index'],
            block['previous_hash'],
            transfers,
            block['proof'],
            block['timestamp'])
        self.__chain.append(converted_block)
        stored_transfers = self.__open_transfers[:]
        # Check which open transfers were included in the received block
        # and remove them
        # This could be improved by giving each transfer an ID that would
        # uniquely identify it
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

    def resolve(self):
        """Checks all peer nodes' blockchains and replaces the local one with
        longer valid ones."""
        # Initialize the winner chain with the local chain
        winner_chain = self.chain
        replace = False
        for node in self.__peer_nodes:
            url = 'http://{}/chain'.format(node)
            try:
                # Send a request and store the response
                response = requests.get(url)
                # Retrieve the JSON data as a dictionary
                node_chain = response.json()
                # Convert the dictionary list to a list of block AND
                # transfer objects
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
                # Store the received chain as the current winner chain if it's
                # longer AND valid
                if (node_chain_length > local_chain_length and
                        Verification.verify_chain(node_chain)):
                    winner_chain = node_chain
                    replace = True
            except requests.exceptions.ConnectionError:
                continue
        self.resolve_conflicts = False
        # Replace the local chain with the winner chain
        self.chain = winner_chain
        if replace:
            self.__open_transfers = []
        self.save_data()
        return replace

    def add_peer_node(self, node):
        """Adds a new node to the peer node set.

        Arguments:
            :node: The node URL which should be added.
        """
        self.__peer_nodes.add(node)
        self.save_data()

    def remove_peer_node(self, node):
        """Removes a node from the peer node set.

        Arguments:
            :node: The node URL which should be removed.
        """
        self.__peer_nodes.discard(node)
        self.save_data()

    def get_peer_nodes(self):
        """Return a list of all connected peer nodes."""
        return list(self.__peer_nodes)
