import socket
import struct


def create_piece_message(piece_number, begin, block):
    message_id = 7
    payload = struct.pack(">I", piece_number) + struct.pack(">I", begin) + block
    length_prefix = struct.pack(">I", len(payload) + 1)
    return length_prefix + message_id.to_bytes(1, 'big') + payload


def handle_client_connection(client_socket, torrent_data):
    try:
        while True:
            length_prefix = client_socket.recv(4)
            if not length_prefix:
                break

            message_length = int.from_bytes(length_prefix, 'big')
            message = client_socket.recv(message_length)
            while len(message) < message_length:
                message += client_socket.recv(message_length - len(message))

            message_id = message[0]

            if message_id == 2:  # Interested message
                unchoke_message = struct.pack(">Ib", 1, 1)
                client_socket.send(unchoke_message)
            elif message_id == 6:  # Request message
                piece_index = struct.unpack(">I", message[1:5])[0]
                begin = struct.unpack(">I", message[5:9])[0]
                length = struct.unpack(">I", message[9:13])[0]

                piece_data = get_piece_data(torrent_data, piece_index, begin, length)
                piece_message = create_piece_message(piece_index, begin, piece_data)
                client_socket.send(piece_message)
            else:
                print(f"Received unknown message ID: {message_id}")
    finally:
        client_socket.close()


def get_piece_data(torrent_data, piece_index, begin, length):
    piece_length = torrent_data['piece_length']
    piece_offset = piece_index * piece_length + begin
    return torrent_data['file_data'][piece_offset:piece_offset + length]


def load_torrent_data(file_path):
    file_data = b"A" * 1024 * 1024  # 1 MB of dummy data for testing
    piece_length = 16 * 1024  # 16 KB pieces
    torrent_data = {
        'piece_length': piece_length,
        'file_data': file_data
    }
    return torrent_data


def main():
    server_address = ('localhost', 6881)
    torrent_data = load_torrent_data('dummy.torrent')

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind(server_address)
        server_socket.listen()

        print(f"Server listening on {server_address}")

        while True:
            client_socket, client_address = server_socket.accept()
            print(f"Accepted connection from {client_address}")
            handle_client_connection(client_socket, torrent_data)


if __name__ == "__main__":
    main()
