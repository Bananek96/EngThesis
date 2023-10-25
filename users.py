from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
import Crypto.Random
import binascii
import sqlite3


class User:
    def __init__(self, node_id):
        self.private_key = None
        self.public_key = None
        self.node_id = node_id

    def create_keys(self):
        private_key, public_key = self.generate_keys()
        self.private_key = private_key
        self.public_key = public_key

        if self.save_keys_to_database():
            return False
        return True

    def save_keys_to_database(self):
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                node_id TEXT PRIMARY KEY,
                public_key TEXT,
                private_key TEXT
            )
        ''')

        # Check if the node_id already exists in the database
        res = cursor.execute('SELECT node_id FROM users WHERE node_id = ?', (self.node_id,))
        row = res.fetchone()

        if row is None:
            cursor.execute('''
                INSERT INTO users (node_id, public_key, private_key)
                VALUES (?, ?, ?)
            ''', (self.node_id, self.public_key, self.private_key))

        conn.commit()
        conn.close()

    def load_keys_from_database(self):
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        cursor.execute('SELECT public_key, private_key FROM users WHERE node_id = ?', (self.node_id,))
        row = cursor.fetchone()

        conditional = False
        if row:
            self.public_key = row[0]
            self.private_key = row[1]
            conditional = True

        conn.close()
        return conditional

    @staticmethod
    def generate_keys():
        private_key = RSA.generate(1024, Crypto.Random.new().read)
        public_key = private_key.publickey()
        return (
            binascii
            .hexlify(private_key.exportKey(format='DER'))
            .decode('ascii'),
            binascii
            .hexlify(public_key.exportKey(format='DER'))
            .decode('ascii')
        )

    def sign_transfer(self, sender, recipient, file):
        private_key = RSA.importKey(binascii.unhexlify(self.private_key))
        h = SHA256.new((str(sender) + str(recipient) +
                        str(file)).encode('utf8'))
        signature = PKCS1_v1_5.new(private_key).sign(h)
        return binascii.hexlify(signature).decode('ascii')

    @staticmethod
    def verify_transfer(transfer):
        public_key = RSA.importKey(binascii.unhexlify(transfer.sender))
        verifier = PKCS1_v1_5.new(public_key)
        h = SHA256.new((str(transfer.sender) + str(transfer.recipient) +
                        str(transfer.file)).encode('utf8'))
        return verifier.verify(h, binascii.unhexlify(transfer.signature))
