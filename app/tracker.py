from app import bencode_utils
from flask import Flask, request, jsonify, Response
import hashlib

peer1 = "192.168.100.1:6061"
peer1 = bencode_utils.bencode(peer1)
peer2 = "192.168.100.2:6062"
peer2 = bencode_utils.bencode(peer2)
peers = [peer1, peer2]
peers = bencode_utils.bencode(peers)
print(peers)
response = {
    "peers": peers
}

response = bencode_utils.bencode(response)
print(response)

app = Flask(__name__)


@app.route('/announce', methods=['GET'])
def announce():
    response_data = bencode_utils.bencode(response)
    return Response(response_data, content_type='text/plain')


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080)
