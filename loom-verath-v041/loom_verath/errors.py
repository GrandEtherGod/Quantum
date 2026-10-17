class LoomVerathError(Exception):
    """Base runtime error."""


class InvariantViolation(LoomVerathError):
    """A system invariant would be violated."""


class ConcurrentWrite(LoomVerathError):
    """A compare-and-swap state write used a stale version."""


class CapabilityDenied(LoomVerathError):
    """A capability is missing, expired, revoked, or out of scope."""


class ReplayUnavailable(LoomVerathError):
    """Required replay material is unavailable or was deleted."""


class CodePetError(LoomVerathError):
    """A CodePet workspace contract was violated."""


class ProposalStateError(CodePetError):
    """A proposal transition was attempted from an invalid state."""


class WorkspaceBoundaryError(CodePetError):
    """A path or operation escaped the authorized workspace boundary."""


class StaleProposalError(CodePetError):
    """Workspace content changed after a proposal was prepared or approved."""
