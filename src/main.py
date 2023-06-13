from typing import *
import hashlib
import json
import time
from textwrap import dedent
from uuid import uuid4
from flask import Flask, jsonify, request
from urllib.parse import urlparse
import requests

class Blockchain(object):
	def __init__(self):
		self.current_transactions = []
		self.chain = []
		self.nodes = set()

		self.new_block(proof=100, previous_hash=1)

	def new_block(self, proof: int, previous_hash: Optional[int] = None) -> dict:
		"""
		Create a new block in the chain
		:param proof: <int> The proof given by the Proof of Work algorithm
		:param previous_hash: (Optional) <str> Hash of the previous block
		:return: <dict> The new block
		"""
		block = {
			'index': len(self.chain) + 1,
			'timestamp': time.time(),
			'transactions': self.current_transactions,
			'proof': proof,
			'previous_hash': previous_hash or self.hash(self.chain[-1])
		}

		self.current_transactions = []
		self.chain.append(block)

		return block

	def new_transaction(self, sender: str, recipient: str, amount: float) -> int:
		"""
		Creates a new transaction to the next mined block
		:param sender: <str> Sender address
		:param recipient: <str> Recipient address
		:param amount: <float> Amount
		:return: <int> The index of the block that holds this transaction data
		"""
		self.current_transactions.append({
			'sender': sender,
			'recipient': recipient,
			'amount': amount
		})

		return self.last_block['index'] + 1

	@property
	def last_block(self): return self.chain[-1]

	@staticmethod
	def hash(block: dict) -> str:
		"""
		Creates a SHA-256 hash of the given block
		:param block: <dict> The block
		:return: <str>
		"""
		block_string = json.dumps(block, sort_keys=True).encode()
		return hashlib.sha256(block_string)

	def proof_of_work(self, last_proof: int) -> int:
		"""
		Proof of Work algorithm - simple
		- Using P new proof and P' previous proof, find a number P such that hash(PP') contains
		4 leading zeroes
		:param last_proof: <int>
		:return: <int>
		"""
		proof = 0
		while not self.valid_proof(last_proof, proof):
			proof += 1

		return proof

	@staticmethod
	def valid_proof(last_proof: int, proof: int) -> bool:
		"""
		Validates the proof - checks if there is 4 leading zeroes
		:param last_proof: <int> Previous proof
		:param proof: <int> Current proof
		:return: <bool> True if correct, False otherwise
		"""
		guess = f'{last_proof}{proof}'.encode()
		guess_hash = hashlib.sha256(guess).hexdigest()
		return guess_hash[:4] == '0000'

	def register_node(self, address: str) -> None:
		"""
		Registers a new node to the set of nodes
		:param address: <str> Address of the node
		:return: None
		"""
		parsed_url = urlparse(address)
		self.nodes.add(parsed_url.netloc)

		return

	def valid_chain(self, chain: list) -> bool:
		"""
		Determines if the given chain is valid
		:param chain: <list> A blockchain
		:return: <bool> True if valid, False otherwise
		"""
		last_block = chain[0]
		current_index = 1

		while current_index < len(chain):
			block = chain[current_index]
			if block['previous_hash'] != self.hash(last_block):
				return False

			if not self.valid_proof(last_block['proof'], block['proof']):
				return False

			last_block = block
			current_index += 1

		return True

	def resolve_conflicts(self) -> bool:
		"""
		Consensus algorithm that resolves conflicts by replacing the current chain
		with the longest one in the network
		:return: <bool> True if successful, False otherwise
		"""
		neighbors = self.nodes
		new_chain = None
		max_length = len(self.chain)

		for node in neighbors:
			response = requests.get(f'http://{node}/chain')

			if response.status_code == 200:
				length = response.json()['length']
				chain = response.json()['chain']

				if length > max_length and self.valid_chain(chain):
					max_length = length
					new_chain = chain

		if new_chain:
			self.chain = new_chain
			return True 

		return False

app = Flask(__name__)
node_identifier = str(uuid4()).replace('-', '')
blockchain = Blockchain()

@app.route('/min', method=['GET'])
def mine():
	last_block = block_chain.last_block
	last_proof = last_block['proof']
	proof = blockchain.proof_of_work(last_proof)

	blockchain.new_transaction(
		sender='0', recipient=node_identifier, amount=1
	)

	previous_hash = blockchain.hash(last_block)
	block = blockchain.new_block(proof, previous_hast)

	response = {
		'message': 'New block forged',
		'index': block['index'],
		'transactions': block['transactions'],
		'proof': block['proof'],
		'previous_hash': block['previous_hash']
	}

	return jsonify(response), 200

@app.route('/transactions/new', methods=['POST'])
def new_transaction():
	values = request.get_json()

	required = ('sender', 'recipient', 'amount')
	if not all(_ in values for _ in required):
		return 'Missing', 400

	index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])
	response = {'message': f'Transaction will be added to block #{index}'}

	return jsonify(response), 201

@app.route('/chain', methods=['GET'])
def full_chain():
	response = {
		'chain': blockchain.chain,
		'length': len(blockchain.chain)
	}
	return jsonify(response), 200

@app.route('/nodes/register', methods=['POST'])
def register_nodes():
	values = request.get_json()

	nodes = values.get('nodes')
	if nodes is None:
		return 'Error: Supply a valid list of nodes', 400

	for node in nodes:
		blockchain.register_node(node)

	response = {
		'message': 'New nodes registered',
		'total_nodes': list(blockchain.nodes)
	}

	return jsonify(response), 201

@app.route('/nodes/resolve', methods=['GET'])
def consensus():
	replaced = blockchain.resolve_conflicts()

	if replaced:
		response = {
			'message': 'Chain replaced',
			'new_chain': blockchain.chain
		}
	else:
		response = {
			'message': 'Current chain is authoritative',
			'chain': blockchain.chain
		}

	return jsonify(response), 200


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000)

