import argparse
import asyncio
import logging
import struct
from typing import Dict, Optional

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived, HandshakeCompleted
from aioquic.quic.logger import QuicFileLogger
from aioquic.tls import SessionTicket


class BTServerProtocol(QuicConnectionProtocol):
    receiving_file = False
    buffer = bytearray()
    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, StreamDataReceived):
            # parse query
            if event.data == \
            b"\023BitTorrent protocol\000\000\000\000\000\000\000\000\326\237\221\346\262\256LT$h\321\a:q\324\352\023\207\232\17700112233445566778899":
                print('handshake attempt')
                data = b"\023BitTorrent protocol\000\000\000\000\000\020\000\004\326\237\221\346\262\256LT$h\321\a:q\324\352\023\207\232\177-RN0.0.0-Z\365\302\317H\210\025\304\242\372\177"
                self._quic.send_stream_data(event.stream_id, data, end_stream=True)
            elif event.data[:4] == b'file':
                self.buffer.clear()
                self.receiving_file = True
                print('received file:')
                self.buffer.extend(event.data[4:])
            elif self.receiving_file == True:
                self.buffer.extend(event.data)
                if event.end_stream:
                    self.receiving_file = False
                    print(self.buffer.decode())
                    data = struct.pack("!I", len(self.buffer))
                    self._quic.send_stream_data(event.stream_id, data, end_stream=True)
            else:
                data = b'hello'
                self._quic.send_stream_data(event.stream_id, data, end_stream=False)


            # send answer


class SessionTicketStore:
    """
    Simple in-memory store for session tickets.
    """

    def __init__(self) -> None:
        self.tickets: Dict[bytes, SessionTicket] = {}

    def add(self, ticket: SessionTicket) -> None:
        self.tickets[ticket.ticket] = ticket

    def pop(self, label: bytes) -> Optional[SessionTicket]:
        return self.tickets.pop(label, None)


async def main(
    host: str,
    port: int,
    configuration: QuicConfiguration,
    session_ticket_store: SessionTicketStore,
) -> None:
    await serve(
        host,
        port,
        configuration=configuration,
        create_protocol=BTServerProtocol,
        session_ticket_fetcher=session_ticket_store.pop,
        session_ticket_handler=session_ticket_store.add,
    )
    await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QUIC Peer server")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    configuration = QuicConfiguration(
        is_client=False,
        # max_stream_data=100000
    )

    # configuration.load_cert_chain(args.certificate, args.private_key)
    configuration.load_cert_chain('ssl_cert.pem', 'ssl_key.pem')
    # configuration.verify_mode = 0

    try:
        asyncio.run(
            main(
                host='localhost',
                port=9999,
                configuration=configuration,
                session_ticket_store=SessionTicketStore(),
            )
        )
    except KeyboardInterrupt:
        pass
