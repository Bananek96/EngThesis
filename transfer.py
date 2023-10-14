from collections import OrderedDict

from utility.printable import Printable


class Transfer(Printable):
    """A transfer which can be added to a block in the blockchain.

    Attributes:
        :sender: The sender of the files.
        :recipient: The recipient of the files.
        :signature: The signature of the transfer.
        :file: The transfer file.
    """

    def __init__(self, sender, recipient, signature, file):
        self.sender = sender
        self.recipient = recipient
        self.file = file
        self.signature = signature

    def to_ordered_dict(self):
        """Converts this transfer into a (hashable) OrderedDict."""
        return OrderedDict([('sender', self.sender),
                            ('recipient', self.recipient),
                            ('file', self.file)])
