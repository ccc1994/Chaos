import json
from typing import Any, Callable, Dict, Optional, Union

from opentelemetry import trace
from opentelemetry.trace import Link, SpanContext, Status, StatusCode
from autogen import ConversableAgent
from openinference.instrumentation.autogen import AutogenInstrumentor

# Use the SpanAttributes defined in the package if possible
try:
    from openinference.instrumentation.autogen import SpanAttributes
except ImportError:
    class SpanAttributes:
        OPENINFERENCE_SPAN_KIND: str = "openinference.span.kind"
        INPUT_VALUE: str = "input.value"
        INPUT_MIME_TYPE: str = "input.mime_type"
        OUTPUT_VALUE: str = "output.value"
        OUTPUT_MIME_TYPE: str = "output.mime_type"
        TOOL_NAME: str = "tool.name"
        TOOL_ARGS: str = "tool.args"
        TOOL_KWARGS: str = "tool.kwargs"
        TOOL_PARAMETERS: str = "tool.parameters"
        TOOL_CALL_FUNCTION_ARGUMENTS: str = "tool_call.function.arguments"
        TOOL_CALL_FUNCTION_NAME: str = "tool_call.function.name"

def patch_autogen_instrumentation():
    """
    Patches AutogenInstrumentor to use agent.name instead of class name for span names.
    This fixes the issue where Phoenix displays 'AssistantAgent' instead of the agent name (e.g., 'Coder').
    """
    
    # Save original methods if not already saved
    if not hasattr(AutogenInstrumentor, "_original_generate"):
        # We'll use a dummy instance to keep track of original methods globally if needed, 
        # or just use the one provided by the library.
        pass

    def wrapped_generate(
        instrumentor: AutogenInstrumentor,
        agent_self: ConversableAgent,
        messages: Optional[Any] = None,
        sender: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        try:
            current_span = trace.get_current_span()
            current_context: SpanContext = current_span.get_span_context()

            # FIX: Use agent_self.name if available
            span_name = getattr(agent_self, "name", agent_self.__class__.__name__)

            with instrumentor.tracer.start_as_current_span(
                span_name,
                context=trace.set_span_in_context(current_span),
                links=[Link(current_context)],
            ) as span:
                span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "AGENT")
                span.set_attribute(
                    SpanAttributes.INPUT_VALUE,
                    instrumentor._safe_json_dumps(messages),
                )
                span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")
                span.set_attribute("agent.type", agent_self.__class__.__name__)
                span.set_attribute("agent.name", span_name)

                if instrumentor._original_generate is not None:
                    response = instrumentor._original_generate(
                        agent_self, messages=messages, sender=sender, **kwargs
                    )
                else:
                    response = None

                span.set_attribute(
                    SpanAttributes.OUTPUT_VALUE,
                    instrumentor._safe_json_dumps(response),
                )
                span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")

                return response
        except Exception as e:
            # Note: span might be undefined if start_as_current_span fails, 
            # but in this structured with-block it should be fine.
            raise

    # Override the instrument method of AutogenInstrumentor
    original_instrument = AutogenInstrumentor.instrument

    def patched_instrument(self: AutogenInstrumentor) -> AutogenInstrumentor:
        # 1. First, call the original instrument to set up tracers and save original methods
        original_instrument(self)
        
        # 2. Now, override the wrapper that was just installed on ConversableAgent
        instrumentor = self
        
        # We need to re-wrap because wrapped_generate in the original is a local function (closure)
        # and we can't easily modify it.
        
        def new_wrapped_generate(
            agent_self: ConversableAgent,
            messages: Optional[Any] = None,
            sender: Optional[str] = None,
            **kwargs: Any,
        ) -> Any:
            return wrapped_generate(instrumentor, agent_self, messages, sender, **kwargs)

        ConversableAgent.generate_reply = new_wrapped_generate
        return self

    AutogenInstrumentor.instrument = patched_instrument
    print("Autogen instrumentation patched successfully to show agent names.")
