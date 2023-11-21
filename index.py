from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS

from users import User
from blockchain import Blockchain

import base64

app = Flask(__name__)
CORS(app)


@app.route('/', methods=['GET'])
def index():
    return send_from_directory('templates', 'index.html')


@app.route('/pl', methods=['GET'])
def index_pl():
    return send_from_directory('templates', 'index_pl.html')


@app.route('/network', methods=['GET'])
def get_network_ui():
    return render_template('network.html')


@app.route('/network-pl', methods=['GET'])
def get_network_ui_pl():
    return render_template('network_pl.html')


@app.route('/user', methods=['POST'])
def create_keys():
    if user.create_keys():
        global blockchain
        blockchain = Blockchain(user.public_key, port)
        response = {
            'public_key': user.public_key,
            'private_key': user.private_key,
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Saving the keys failed.'
        }
        return jsonify(response), 500


@app.route('/user', methods=['GET'])
def load_keys():
    if user.load_keys_from_database():
        global blockchain
        blockchain = Blockchain(user.public_key, port)
        response = {
            'public_key': user.public_key,
            'private_key': user.private_key,
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Loading the keys failed.'
        }
        return jsonify(response), 500


@app.route('/broadcast-transfer', methods=['POST'])
def broadcast_transfer():
    values = request.get_json()
    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    required = ['sender', 'recipient', 'file', 'signature']
    if not all(key in values for key in required):
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400
    success = blockchain.add_transfer(
        values['recipient'],
        values['sender'],
        values['file_name'],
        values['file'],
        values['signature'],
        is_receiving=True)
    if success:
        response = {
            'message': 'Successfully added transfer.',
            'transfer': {
                'sender': values['sender'],
                'recipient': values['recipient'],
                'file': values['file'],
                'signature': values['signature']
            }
        }
        return jsonify(response), 201
    else:
        response = {
            'message': 'Creating a transfer failed.'
        }
        return jsonify(response), 500


@app.route('/broadcast-block', methods=['POST'])
def broadcast_block():
    values = request.get_json()
    if not values:
        response = {'message': 'No data found.'}
        return jsonify(response), 400
    if 'block' not in values:
        response = {'message': 'Some data is missing.'}
        return jsonify(response), 400
    block = values['block']
    if block['index'] == blockchain.chain[-1].index + 1:
        if blockchain.add_block(block):
            response = {'message': 'Block added'}
            return jsonify(response), 201
        else:
            response = {'message': 'Block seems invalid.'}
            return jsonify(response), 409
    elif block['index'] > blockchain.chain[-1].index:
        response = {
            'message': 'Blockchain seems to differ from local blockchain.'}
        blockchain.resolve_conflicts = True
        return jsonify(response), 200
    else:
        response = {
            'message': 'Blockchain seems to be shorter, block not added'}
        return jsonify(response), 409


@app.route('/transfer', methods=['POST'])
def add_transfer():
    if user.public_key is None:
        response = {
            'message': 'No user set up.'
        }
        return jsonify(response), 400
    recipient = request.form.get("recipient")
    uploaded_file = request.files["file"]

    if recipient and uploaded_file:
        file_name = uploaded_file.filename
        binary_data = uploaded_file.read()
        base64_data = base64.b64encode(binary_data).decode('utf-8')
        signature = user.sign_transfer(user.public_key, recipient, base64_data)

        success = blockchain.add_transfer(
            recipient, user.public_key, file_name, base64_data, signature)
        if success:
            response = {
                'message': 'Successfully added transfer.',
                'transfer': {
                    'sender': user.public_key,
                    'recipient': recipient,
                    'file_name': file_name,
                    'file': base64_data,
                    'signature': signature
                },
            }
            return jsonify(response), 201
        else:
            response = {
                'message': 'Creating a transfer failed.'
            }
            return jsonify(response), 500


@app.route('/mine', methods=['POST'])
def mine():
    file = request.files['file']

    if file:
        binary_data = file.read()
        base64_data = base64.b64encode(binary_data).decode('utf-8')
        block = blockchain.mine_block(base64_data)
        if block is not None:
            dict_block = block.__dict__.copy()
            dict_block['transfers'] = [
                tx.__dict__ for tx in dict_block['transfers']]
            for tx in dict_block['transfers']:
                tx['file_name'] = file.filename
            response = {
                'message': 'Block added successfully.',
                'block': {
                    'index': dict_block['index'],
                    'previous_hash': dict_block['previous_hash'],
                    'transfers': dict_block['transfers'],
                    'proof': dict_block['proof'],
                    'timestamp': dict_block['timestamp'],
                },
            }
            return jsonify(response), 201
        else:
            response = {
                'message': 'Adding a block failed.',
                'user_set_up': user.public_key is not None
            }
            return jsonify(response), 500
    else:
        response = {'message': 'No file uploaded.'}
        return jsonify(response), 400


@app.route('/resolve-conflicts', methods=['POST'])
def resolve_conflicts():
    replaced = blockchain.resolve()
    if replaced:
        response = {'message': 'Chain was replaced!'}
    else:
        response = {'message': 'Local chain kept!'}
    return jsonify(response), 200


@app.route('/transfers', methods=['GET'])
def get_open_transfer():
    transfers = blockchain.get_open_transfers()
    dict_transfers = [tx.__dict__ for tx in transfers]
    return jsonify(dict_transfers), 200


@app.route('/chain', methods=['GET'])
def get_chain():
    chain_snapshot = blockchain.chain
    dict_chain = [block.__dict__.copy() for block in chain_snapshot]
    for dict_block in dict_chain:
        dict_block['transfers'] = [
            tx.__dict__ for tx in dict_block['transfers']]
    return jsonify(dict_chain), 200


@app.route('/node', methods=['POST'])
def add_node():
    values = request.get_json()
    if not values:
        response = {
            'message': 'No data attached.'
        }
        return jsonify(response), 400
    if 'node' not in values:
        response = {
            'message': 'No node data found.'
        }
        return jsonify(response), 400
    node = values['node']
    blockchain.add_peer_node(node)
    response = {
        'message': 'Node added successfully.',
        'all_nodes': blockchain.get_peer_nodes()
    }
    return jsonify(response), 201


@app.route('/node/<node_url>', methods=['DELETE'])
def remove_node(node_url):
    if node_url == '' or node_url is None:
        response = {
            'message': 'No node found.'
        }
        return jsonify(response), 400
    blockchain.remove_peer_node(node_url)
    response = {
        'message': 'Node removed',
        'all_nodes': blockchain.get_peer_nodes()
    }
    return jsonify(response), 200


@app.route('/nodes', methods=['GET'])
def get_nodes():
    nodes = blockchain.get_peer_nodes()
    response = {
        'all_nodes': nodes
    }
    return jsonify(response), 200


if __name__ == '__main__':
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('-p', '--port', type=int, default=5000)
    args = parser.parse_args()
    port = args.port
    user = User(port)
    blockchain = Blockchain(user.public_key, port)
    app.run(host='0.0.0.0', port=port)
