class NLKEError(Exception):
    """Base error for a declared pipeline contract failure."""


class ConfigError(NLKEError):
    """Configuration does not meet the declared schema."""


class ProviderError(NLKEError):
    """A selected provider rejected or failed a request."""


class IdentityError(NLKEError):
    """An installed component or vector does not match its declared identity."""


class ContextOverflow(NLKEError):
    """A complete formatted model input would exceed its declared limit."""
