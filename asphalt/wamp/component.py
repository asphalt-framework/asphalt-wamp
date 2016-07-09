import logging
from asyncio import get_event_loop
from typing import Any, Dict

import txaio
from typeguard import check_argument_types

from asphalt.core import Component, Context
from asphalt.core.util import merge_config
from asphalt.wamp.client import WAMPClient

logger = logging.getLogger(__name__)


class WAMPComponent(Component):
    """
    Publishes one or more :class:`~asphalt.wamp.client.WAMPClient` objects as resources and
    context variables.
    """

    def __init__(self, clients: Dict[str, Dict[str, Any]]=None, **default_client_args):
        """
        If the ``clients`` argument is omitted or empty, a default client with the context
        attribute ``wamp`` will be created that connects to the realm named ``default``.

        If ``clients`` is defined, any keyword arguments to the component become default options
        for the clients.

        If you wish to change the context attribute of a WAMP client, use the ``context_attr``
        argument.

        :param clients: a dictionary of resource name -> :class:`.WAMPClient` constructor arguments
        :param default_client_args: :class:`.WAMPClient` base options for all clients or arguments
            for the default client if ``clients`` is not specified

        """
        check_argument_types()
        if not clients:
            default_client_args.setdefault('context_attr', 'wamp')
            default_client_args.setdefault('url', 'ws://127.0.0.1/')
            clients = {'default': default_client_args}

        self.clients = []
        for resource_name, config in clients.items():
            config = merge_config(default_client_args, config)
            config.setdefault('realm', resource_name)
            context_attr = config.pop('context_attr', resource_name)
            client = WAMPClient(**config)
            self.clients.append((resource_name, context_attr, client))

    async def start(self, ctx: Context):
        # Autobahn uses txaio to bridge the API gap between asyncio and Twisted so we need to set
        # it up for asyncio here
        txaio.use_asyncio()
        txaio.config.loop = get_event_loop()

        for resource_name, context_attr, client in self.clients:
            await client.start(ctx)
            ctx.publish_resource(client, resource_name, context_attr)
            logger.info('Configured WAMP client (%s / ctx.%s; realm=%s; url=%s)', resource_name,
                        context_attr, client.realm, client.url)
