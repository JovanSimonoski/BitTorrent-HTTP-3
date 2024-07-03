import os
import socket
import hashlib
import struct
import requests
from app import bencode_utils
from app import torrent_info
from typing import Optional, cast
import asyncio

from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived

configuration = QuicConfiguration(is_client=True, )
configuration.load_verify_locations("pycacert.pem")
configuration.secrets_log_file = open('secrets', 'w')

class BTClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ack_waiter: Optional[asyncio.Future[bytes]] = None

    async def do_handshake(self, handshake_msg: bytes) -> None:
        # send query and wait for answer
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, handshake_msg, end_stream=True)
        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()

        return await asyncio.shield(waiter)

    def quic_event_received(self, event: QuicEvent) -> None:
        if self._ack_waiter is not None:
            if isinstance(event, StreamDataReceived):
                # parse answer
                answer = event.data
                print('server said:', answer)

                # return answer
                waiter = self._ack_waiter
                self._ack_waiter = None
                waiter.set_result(answer)

response = requests.get("http://127.0.0.1:8080/announce")
response_data = bencode_utils.decode_bencode_torrent(response.content)
decoded = bencode_utils.decode_bencode(response_data)
peers = decoded["peers"]
peers = bencode_utils.decode_bencode(peers)
peers_received = []
for peer in peers:
    peers_received.append(bencode_utils.decode_bencode(peer))
print(peers_received)


def get_list_of_peers(torrentfile_data):
    tracker_url = torrentfile_data[b"announce"].decode()
    torrent_info_hash = hashlib.sha1(
        bencode_utils.bencode(torrentfile_data[b"info"])).digest()
    torrent_length = torrentfile_data[b"info"][b"length"]
    peer_id = '00112233445566778899'
    port = '6881'
    uploaded = 0
    downloaded = 0
    left = torrent_length
    compact = 1
    data = {
        "info_hash": torrent_info_hash,
        "peer_id": peer_id,
        "port": port,
        "uploaded": uploaded,
        "downloaded": downloaded,
        "left": left,
        "compact": compact
    }
    response = requests.get("127.0.0.1:8080/announce", params=data)
    response_data = bencode_utils.decode_bencode_torrent(response.content)
    peers = response_data[b"peers"]
    peers_list = []
    for i in range(0, len(peers), 6):
        peer = peers[i: i + 6]
        ip_address = f"{peer[0]}.{peer[1]}.{peer[2]}.{peer[3]}"
        port = int.from_bytes(peer[4:], byteorder="big", signed=False)
        peers_list.append(f"{ip_address}:{port}")
    return peers_list


def perform_handshake(torrentfile_data, peer):
    peers = get_list_of_peers(torrentfile_data)
    wanted_peer = peers[0]
    for p in peers:
        if peer == p:
            wanted_peer = p
    tmp = wanted_peer.find(':')
    peer_ip = wanted_peer[:tmp]
    peer_port = int(wanted_peer[tmp + 1:])
    length_of_protocol_string = struct.pack("!B", 19)
    protocol_string = b"BitTorrent protocol"
    # reserver_bytes = b"\x00\x00\x00\x00\x00\x00\x00\x00"
    reserver_bytes = b"\x00" * 8

    torrent_info_hash = hashlib.sha1(
        bencode_utils.bencode(torrentfile_data[b"info"])).digest()
    peer_id = b"00112233445566778899"

    handshake_msg = length_of_protocol_string + protocol_string + \
        reserver_bytes + torrent_info_hash + peer_id

    async def handshake(conf: QuicConfiguration, host: str, port: int) -> None:
        print(f'initiating handshake with {host}:{port}')
        async with connect(host, port, configuration=conf, create_protocol=BTClientProtocol) as client:
            client = cast(BTClientProtocol, client)
            return await client.do_handshake(handshake_msg), client


    rcvd_msg, client = asyncio.run(handshake(
        configuration,
        'localhost', 9999))
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((peer_ip, peer_port))
    s.send(handshake_msg)
    received_msg = s.recv(68)
    # print(received_msg, rcvd_msg)
    # return s, received_msg[48:68].hex()
    return s, rcvd_msg[48:68].hex()


def receive_message(s):
    length = s.recv(4)
    while not length or not int.from_bytes(length, 'big'):
        length = s.recv(4)
    message = s.recv(int.from_bytes(length, 'big'))
    while len(message) < int.from_bytes(length, 'big'):
        message += s.recv(int.from_bytes(length, 'big') - len(message))
    return length + message


def request_block(s, piece_number, block_number, data_length):
    requested_piece_number = int(piece_number)
    begin = block_number * 2 ** 14
    payload = (struct.pack(">I", requested_piece_number) +
               struct.pack(">I", begin) + struct.pack(">I", data_length))

    message = int('6').to_bytes(1, 'big') + payload
    length_prefix = len(message).to_bytes(4, byteorder="big")
    message = length_prefix + message

    s.send(message)

    requested_piece_msg = receive_message(s)

    while requested_piece_msg[4] != 7:
        requested_piece_msg = receive_message(s)

    block = requested_piece_msg[13:]
    return block


def download_piece(output_file, file_name, piece_number):
    torrentfile_data = bencode_utils.decode_torrentfile(file_name)
    peers = get_list_of_peers(torrentfile_data)
    peer = peers[1]

    s, received_message = perform_handshake(torrentfile_data, peer)

    bitfield = receive_message(s)

    interested_id = int('2').to_bytes(1, 'big')
    interested_msg = interested_id + b""
    interested_msg_length_prefix = len(interested_msg).to_bytes(4, 'big')
    interested = interested_msg_length_prefix + interested_msg
    s.send(interested)

    unchoke = receive_message(s)
    while unchoke[4] != 1:
        unchoke = receive_message(s)

    torrent_data_length = int(torrentfile_data[b"info"][b"length"])
    torrent_piece_length = int(torrentfile_data[b"info"][b"piece length"])
    last_piece_length = (torrent_data_length % torrent_piece_length)

    pieces_number = len(torrent_info.piece_hashes(
        torrentfile_data[b"info"][b"pieces"]))
    if int(piece_number) + 1 == pieces_number and last_piece_length > 0:
        total_length = last_piece_length
    else:
        total_length = torrentfile_data[b"info"][b"piece length"]

    block_size = 16 * 1024

    full_blocks_number = total_length // block_size
    final_block_length = total_length % block_size

    piece = b""
    sha1hash = hashlib.sha1()

    num_blocks = full_blocks_number + \
        1 if final_block_length > 0 else full_blocks_number

    for i in range(num_blocks):
        current_block_size = final_block_length if i == full_blocks_number and final_block_length > 0 else block_size
        block = request_block(s, piece_number, i, current_block_size)
        piece += block
        sha1hash.update(block)

    expected_hash = torrent_info.piece_hashes(
        torrentfile_data[b"info"][b"pieces"])[int(piece_number)]
    calculated_hash = sha1hash.digest()
    if expected_hash != calculated_hash:
        raise ValueError("Calculated hash does not match expected hash")

    with open(output_file, "wb") as f:
        f.write(piece)

    s.close()

    return piece_number, output_file


def download(output_file, torrent_file):
    torrentfile_data = bencode_utils.decode_torrentfile(torrent_file)
    number_of_pieces = len(torrent_info.piece_hashes(
        torrentfile_data[b"info"][b"pieces"]))

    tmp_files = []

    for i in range(number_of_pieces):
        piece_number, output_file_tmp = download_piece(
            "/tmp/tmp-file-piece-" + str(i), torrent_file, i)
        tmp_files.append(output_file_tmp)
    with open(output_file, "ab") as f:
        for tmp_file in tmp_files:
            with open(tmp_file, "rb") as f_tmp:
                f.write(f_tmp.read())
            os.remove(tmp_file)
