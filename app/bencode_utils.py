import bencodepy

bc = bencodepy.Bencode(encoding="utf-8")
bc_torrent = bencodepy.Bencode()


def decode_bencode(bencoded_value):
    return bc.decode(bencoded_value)


def decode_bencode_torrent(bencoded_value):
    return bc_torrent.decode(bencoded_value)


def decode_torrentfile(filename):
    with open(filename, "rb") as f:
        bencoded_content = f.read()
        decoded_value = decode_bencode_torrent(bencoded_content)
        return decoded_value


def bencode(value):
    if isinstance(value, str):
        length = len(value)
        return (str(length) + ":" + value).encode()
    elif isinstance(value, int):
        return ("i" + str(value) + "e").encode()
    elif isinstance(value, list):
        result = b"l"
        for i in value:
            result += bencode(i)
        return result + b"e"
    elif isinstance(value, dict):
        result = b"d"
        for k in value:
            result += bencode(k) + bencode(value[k])
        return result + b"e"
    elif isinstance(value, bytes):
        length = len(value)
        return str(length).encode() + b":" + value
    else:
        raise TypeError("Value type is not supported for bencoding")
