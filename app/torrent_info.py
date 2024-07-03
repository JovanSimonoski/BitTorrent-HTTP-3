from app import bencode_utils


def piece_hashes(pieces):
    n = 20
    result = []
    for i in range(0, len(pieces), n):
        chunk = pieces[i:i + n]
        result.append(chunk)
    return result


def get_tracker_url(torrent_file):
    torrentfile_data = bencode_utils.decode_torrentfile(torrent_file)
    return torrentfile_data[b"announce"].decode()
