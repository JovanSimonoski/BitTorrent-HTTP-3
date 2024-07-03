import argparse
import asyncio
import logging
import pickle
import ssl
import struct
from typing import Optional, cast

from aioquic.asyncio.client import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, StreamDataReceived
from aioquic.quic.logger import QuicFileLogger

logger = logging.getLogger("client")


class BTClientProtocol(QuicConnectionProtocol):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ack_waiter: Optional[asyncio.Future] = None

    async def query(self) -> None:
        data = b"Hello!"
        data = struct.pack("!H", len(data)) + data + b"<BYE>"

        # send query and wait for answer
        stream_id = self._quic.get_next_available_stream_id()
        self._quic.send_stream_data(stream_id, data, end_stream=True)
        waiter = self._loop.create_future()
        self._ack_waiter = waiter
        self.transmit()

        return await asyncio.shield(waiter)

    def quic_event_received(self, event: QuicEvent) -> None:
        if self._ack_waiter is not None:
            if isinstance(event, StreamDataReceived):
                # parse answer
                # length = struct.unpack("!H", bytes(event.data[:2]))[0]
                answer = event.data
                print('server said:', answer)

                # return answer
                waiter = self._ack_waiter
                self._ack_waiter = None
                waiter.set_result(answer)


async def main(
    configuration: QuicConfiguration,
    host: str,
    port: int,
) -> None:
    logger.debug(f"Connecting to {host}:{port}")
    async with connect(
        host,
        port,
        configuration=configuration,
        # session_ticket_handler=save_session_ticket,
        create_protocol=BTClientProtocol,
    ) as client:
        client = cast(BTClientProtocol, client)
        answer = await client.query()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QUIC peer client")
    parser.add_argument(
        "--ca-certs", type=str, default="pycacert.pem", help="load CA certificates from the specified file"
    )
    parser.add_argument(
        "-l",
        "--secrets-log",
        type=str,
        help="log secrets to a file, for use with Wireshark",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

    args = parser.parse_args()

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    configuration = QuicConfiguration(is_client=True, )
    configuration.load_verify_locations("pycacert.pem")
    # configuration.verify_mode = ssl.CERT_NONE
    if args.secrets_log:
        configuration.secrets_log_file = open(args.secrets_log, "a")

    asyncio.run(
        main(
            configuration=configuration,
            host='localhost',
            port=9999,
        )
    )
