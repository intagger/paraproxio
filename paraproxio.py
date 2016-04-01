#!/usr/bin/python

import asyncio
import sys
import time

import aiohttp
import aiohttp.hdrs
import aiohttp.server
from aiohttp.protocol import RawRequestMessage
from aiohttp.streams import EmptyStreamReader

DEFAULT_CHUNK_SIZE = 16 * 1024


class HttpRequestHandler(aiohttp.server.ServerHttpProtocol):
    async def handle_request(self, message: RawRequestMessage, payload):
        self.log_message('%s %s' % (message.method, message.path))

        path = message.path
        method = message.method
        data = payload if not isinstance(payload, EmptyStreamReader) else None

        try:
            with aiohttp.ClientSession(headers=message.headers) as session:
                async with session.request(method, path, data=data) as host_resp:  # type: aiohttp.ClientResponse
                    client_res = aiohttp.Response(
                        self.writer, host_resp.status, http_version=message.version)

                    # Process host response headers.
                    for name, value in host_resp.headers.items():
                        if name == 'CONTENT-ENCODING':
                            continue
                        client_res.add_header(name, value)

                    client_res.headers['CONNECTION'] = 'keep-alive'
                    client_res.send_headers()

                    while True:
                        chunk = await host_resp.content.read(DEFAULT_CHUNK_SIZE)
                        if not chunk:
                            break
                        client_res.write(chunk)
                        # await client_res.write_eof()
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError):
            self.log_message("Connection error.")
            pass

    def log_message(self, mformat, *args):
        """Log an arbitrary message.

        This is used by all other logging functions.  Override
        it if you have specific logging wishes.

        The first argument, FORMAT, is a format string for the
        message to be logged.  If the format string contains
        any % escapes requiring parameters, they should be
        specified as subsequent arguments (it's just like
        printf!).

        The client ip and current date/time are prefixed to
        every message.

        """
        sys.stderr.write("%s - - [%s] %s\n" %
                         (self.get_client_address(),
                          self.get_log_date_time_string(),
                          mformat % args))

    def get_client_address(self):
        address, port = self.transport.get_extra_info('peername')
        return '%s:%s' % (address, port)

    def get_log_date_time_string(self):
        """Return the current time formatted for logging."""
        now = time.time()
        year, month, day, hh, mm, ss, x, y, z = time.localtime(now)
        s = "%02d/%3s/%04d %02d:%02d:%02d" % (
            day, self.monthname[month], year, hh, mm, ss)
        return s

    weekdayname = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

    monthname = [None,
                 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    f = loop.create_server(
        lambda: HttpRequestHandler(debug=True, keep_alive=75),
        '127.0.0.1', '8880')
    srv = loop.run_until_complete(f)
    print('serving on', srv.sockets[0].getsockname())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass