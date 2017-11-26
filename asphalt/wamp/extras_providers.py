from typing import Optional, Dict, Any

from asphalt.core import qualified_name, Context
from asphalt.exceptions.api import ExceptionReporter, ExtrasProvider

SENTRY_CLASS_NAME = 'asphalt.exceptions.reporters.sentry.SentryExceptionReporter'


class WAMPExtrasProvider(ExtrasProvider):
    def get_extras(self, ctx: Context, reporter: ExceptionReporter) -> Optional[Dict[str, Any]]:
        from asphalt.wamp import CallContext, EventContext

        extra = None
        if qualified_name(reporter) == SENTRY_CLASS_NAME:
            if isinstance(ctx, CallContext):
                extra = {'extra': {'procedure': ctx.procedure}}
                if ctx.caller_auth_id:
                    extra['user_context'] = {
                        'id': ctx.caller_auth_id,
                        'auth_role': ctx.caller_auth_role,
                        'session_id': ctx.caller_session_id
                    }
            elif isinstance(ctx, EventContext):
                extra = {'extra': {'topic': ctx.topic}}
                if ctx.publisher_auth_id:
                    extra['user_context'] = {
                        'id': ctx.publisher_auth_id,
                        'auth_role': ctx.publisher_auth_role,
                        'session_id': ctx.publisher_session_id
                    }

        return extra
