from asyncio import coroutine, get_event_loop
from typing import Any, Dict, Union
from ssl import SSLContext
import logging

from asphalt.core.component import Component
from asphalt.core.context import Context
from asphalt.core.util import resolve_reference
from asphalt.serialization.api import Serializer
import txaio

from .router import WAMPRouter
from .client import WAMPClient

logger = logging.getLogger(__name__)


class WAMPComponent(Component):
    """
    Provides one or more WAMP clients.

    Publishes one or more :class:`~asphalt.wamp.client.WAMPClient` objects as resources and
    context variables.

    By default, a WAMP client that connects to the ``default`` realm is created with the context
    attribute ``wamp``.

    :param clients: a dictionary of resource name -> :meth:`create_client` keyword arguments
    :param default_client_args: :meth:`create_client` arguments for the default client
    """

    def __init__(self, clients: Dict[str, Dict[str, Any]]=None, **default_client_args):
        if clients and default_client_args:
            raise ValueError('specify either a "clients" dictionary or the default client\'s '
                             'options directly, but not both')

        if not clients:
            default_client_args.setdefault('context_attr', 'wamp')
            default_client_args.setdefault('url', 'ws://127.0.0.1/')
            clients = {'default': default_client_args}

        self.clients = []
        for resource_name, client_config in clients.items():
            client_config.setdefault('realm', resource_name)
            client_config.setdefault('context_attr', resource_name)
            self.clients.append((resource_name,) + self.create_client(**client_config))

    @staticmethod
    def create_client(url: str, context_attr: str=None, realm: str=None,
                      ssl_context: Union[SSLContext, str]=None,
                      serializer: Union[Serializer, str]=None,
                      router: Union[WAMPRouter, str]=None, debug_wamp: bool=False,
                      debug_app: bool=False, debug_client_factory: bool=False):
        """
        Configure a WAMP client with the given parameters.

        :param context_attr: context attribute of the WAMP client (defaults to the resource name
            if not specified)
        :param realm: the WAMP realm to join the application session to (defaults to the resource
            name if not specified)
        :param url: the Websocket URL to connect to
        :param ssl_context: an SSL context or the name of an :class:`ssl.SSLContext` resource
        :param serializer: a serializer instance or the name of a
            :class:`asphalt.serialization.api.Serializer` resource
        :param router: a WAMP router instance or a string reference to one
        :param debug_client_factory: ``True`` to enable debugging of the client socket factory
        :param debug_wamp: ``True`` to enable WAMP protocol debugging

        """
        router = resolve_reference(router)
        return (context_attr, realm, url, ssl_context, router, serializer, debug_app,
                debug_client_factory, debug_wamp)

    @coroutine
    def start(self, ctx: Context):
        # Autobahn uses txaio to bridge the API gap between asyncio and Twisted so we need to set
        # it up for asyncio here
        txaio.use_asyncio()
        txaio.config.loop = get_event_loop()

        for (resource_name, context_attr, realm, url, ssl_context, router, serializer, debug_app,
             debug_wamp, debug_factory) in self.clients:
            if isinstance(serializer, str):
                serializer = yield from ctx.request_resource(Serializer, serializer)
            if isinstance(ssl_context, str):
                ssl_context = yield from ctx.request_resource(SSLContext, ssl_context)

            client = WAMPClient(ctx, realm, url, ssl_context, router, serializer, debug_app,
                                debug_factory, debug_wamp)
            yield from ctx.publish_resource(client, resource_name, context_attr)
            logger.info('Configured WAMP client (%s / ctx.%s; realm=%s; url=%s)', resource_name,
                        context_attr, realm, url)
