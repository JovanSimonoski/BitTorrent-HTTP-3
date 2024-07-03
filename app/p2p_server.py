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
    def quic_event_received(self, event: QuicEvent):
        if isinstance(event, StreamDataReceived):
            # parse query
            length = struct.unpack("!H", bytes(event.data[:2]))[0]
            print('client said:', event.data[2 : 2 + length])
            print('message length:', length)
            print('full message:', event.data)
            # query = DNSRecord.parse(event.data[2 : 2 + length])

            # perform lookup and serialize answer
            # data = query.send(args.resolver, 53)
            data = b'Hello from server!'

            # send answer
            self._quic.send_stream_data(event.stream_id, data, end_stream=True)


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
    retry: bool,
) -> None:
    await serve(
        host,
        port,
        configuration=configuration,
        create_protocol=BTServerProtocol,
        session_ticket_fetcher=session_ticket_store.pop,
        session_ticket_handler=session_ticket_store.add,
        retry=retry,
    )
    await asyncio.Future()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DNS over QUIC server")
    parser.add_argument(
        "--host",
        type=str,
        default="::",
        help="listen on the specified address (defaults to ::)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9999,
        help="listen on the specified port (defaults to 853)",
    )
    parser.add_argument(
        "-k",
        "--private-key",
        default="ssl_key.pem",
        type=str,
        help="load the TLS private key from the specified file",
    )
    parser.add_argument(
        "-c",
        "--certificate",
        default="ssl_cert.pem",
        type=str,
        # required=True,
        help="load the TLS certificate from the specified file",
    )
    parser.add_argument(
        "--retry",
        action="store_true",
        help="send a retry for new connections",
    )
    parser.add_argument(
        "-q",
        "--quic-log",
        type=str,
        help="log QUIC events to QLOG files in the specified directory",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    # create QUIC logger
    if args.quic_log:
        quic_logger = QuicFileLogger(args.quic_log)
    else:
        quic_logger = None

    configuration = QuicConfiguration(
        is_client=False,
        quic_logger=quic_logger,
        verify_mode=0,
    )

    configuration.load_cert_chain(args.certificate, args.private_key)
    # configuration.verify_mode = 0

    try:
        asyncio.run(
            main(
                host=args.host,
                port=args.port,
                configuration=configuration,
                session_ticket_store=SessionTicketStore(),
                retry=args.retry,
            )
        )
    except KeyboardInterrupt:
        pass
