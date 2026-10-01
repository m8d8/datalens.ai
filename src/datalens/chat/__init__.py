"""
Chat with a finished run: ``datalens serve <run_dir>`` (report + chat panel on
localhost) and ``datalens ask "<question>" <run_dir>`` (one-shot, scriptable).

Answers come from the run's findings plus read-only SQL over a PII-masked
sample of the data; every query is shown to the user.
"""

from datalens.chat.engine import ChatSession, answer_to_markdown
from datalens.chat.workspace import RunWorkspace

__all__ = ["ChatSession", "RunWorkspace", "answer_to_markdown"]
