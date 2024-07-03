import json
import sys
import hashlib
from app import networking
from app import torrent_info
from app import bencode_utils


def main():
    command = sys.argv[1]

    if command == "decode":
        bencoded_value = sys.argv[2].encode()

        def bytes_to_str(data):
            if isinstance(data, bytes):
                return data.decode()

            raise TypeError(f"Type not serializable: {type(data)}")

        print(json.dumps(bencode_utils.decode_bencode(bencoded_value), default=bytes_to_str))
    elif command == "info":
        filename = sys.argv[2].encode()
        torrentfile_data = bencode_utils.decode_torrentfile(filename)
        print("Tracker URL:", torrentfile_data[b"announce"].decode())
        print("Length:", torrentfile_data[b"info"][b"length"])
        info_hash = hashlib.sha1(bencode_utils.bencode(torrentfile_data[b"info"])).hexdigest()
        print("Info Hash:", info_hash)
        print("Piece Length:", torrentfile_data[b"info"][b"piece length"])
        pieces = torrentfile_data[b"info"][b"pieces"]
        pieces_hashes = torrent_info.piece_hashes(pieces)
        print("Piece Hashes:")
        for p in pieces_hashes:
            print(p.hex())
    elif command == "peers":
        filename = sys.argv[2].encode()
        torrentfile_data = bencode_utils.decode_torrentfile(filename)
        peers = networking.get_list_of_peers(torrentfile_data)
        for peer in peers:
            print(peer)
    elif command == "handshake":
        filename = sys.argv[2]
        peer = sys.argv[3]
        torrentfile_data = bencode_utils.decode_torrentfile(filename)
        s, receive_message = networking.perform_handshake(torrentfile_data, peer)
        print("Peer ID:", receive_message)
    elif command == "download_piece":
        output_file = sys.argv[3]
        torrent_file = sys.argv[4]
        piece_number = sys.argv[5]

        networking.download_piece(output_file, torrent_file, piece_number)
        print(f"Piece {piece_number} downloaded to {output_file}.")
    elif command == "download":
        output_file = sys.argv[3]
        torrent_file = sys.argv[4]
        networking.download(output_file, torrent_file)
        print(f"Downloaded {torrent_file} to {output_file}.")
    else:
        raise NotImplementedError(f"Unknown command {command}")


if __name__ == "__main__":
    main()
