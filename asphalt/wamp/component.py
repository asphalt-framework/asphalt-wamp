import logging
from asyncio import get_event_loop
from typing import Any, Dict

import txaio
from asphalt.core import Component, Context, merge_config, context_teardown
from async_generator import yield_
from typeguard import check_argument_types

from asphalt.wamp.client import WAMPClient

__all__ = ('WAMPComponent',)

logger = logging.getLogger(__name__)


class WAMPComponent(Component):
    """Creates one or more :class:`~asphalt.wamp.client.WAMPClient` resources."""

    def __init__(self, clients: Dict[str, Dict[str, Any]] = None, **default_client_args):
        """
        If the ``clients`` argument is omitted or empty, a default client with the context
        attribute ``wamp`` will be created.

        If ``clients`` is defined, any keyword arguments to the component become default options
        for the clients.

        If you wish to change the context attribute of a WAMP client, use the ``context_attr``
        argument.

        :param clients: a dictionary of resource name ⭢ :class:`.WAMPClient` constructor arguments
        :param default_client_args: :class:`.WAMPClient` base options for all clients or arguments
            for the default client if ``clients`` is not specified

        """
        assert check_argument_types()
        if not clients:
            default_client_args.setdefault('context_attr', 'wamp')
            clients = {'default': default_client_args}

        self.clients = []
        for resource_name, config in clients.items():
            config = merge_config(default_client_args, config)
            context_attr = config.pop('context_attr', resource_name)
            client = WAMPClient(**config)
            self.clients.append((resource_name, context_attr, client))

    @context_teardown
    async def start(self, ctx: Context):
        # Autobahn uses txaio to bridge the API gap between asyncio and Twisted so we need to set
        # it up for asyncio here
        txaio.use_asyncio()
        txaio.config.loop = get_event_loop()

        for resource_name, context_attr, client in self.clients:
            await client.start(ctx)
            ctx.add_resource(client, resource_name, context_attr)
            logger.info('Configured WAMP client (%s / ctx.%s; host=%s; port=%d; realm=%s)',
                        resource_name, context_attr, client.host, client.port, client.realm)

        await yield_()

        for resource_name, context_attr, client in self.clients:
            await client.close()
            logger.info('Shut down WAMP client (%s)', resource_name)
