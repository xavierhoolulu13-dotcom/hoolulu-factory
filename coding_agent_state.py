"""
coding_agent_state — State machine for the CodingAgent.
Follows the factory's state_machine.py pattern.

States:
  idle → planning → executing → testing → completed
                                    ↓
                                 failed → retrying → planning
                          ↓
                       frozen (terminal — agent snapshot saved)
"""

from datetime import datetime


class CodingAgentState:
    """Manages the state transitions for a coding agent."""

    STATES = ["idle", "planning", "executing", "testing", "completed", "failed", "retrying", "frozen"]
    TRANSITIONS = {
        "idle":      ["planning"],
        "planning":  ["executing", "failed"],
        "executing": ["testing", "failed"],
        "testing":   ["completed", "failed"],
        "completed": ["idle", "frozen"],
        "failed":    ["retrying", "idle"],
        "retrying":  ["planning", "failed"],
        "frozen":    [],  # terminal
    }

    def __init__(self, initial="idle"):
        self.current = initial
        self.history = [{"state": initial, "timestamp": datetime.now().isoformat()}]
        self._callbacks = {}

    def transition(self, new_state):
        """Transition to a new state if allowed."""
        allowed = self.TRANSITIONS.get(self.current, [])
        if new_state not in allowed:
            raise ValueError(f"Invalid transition: {self.current} → {new_state}. Allowed: {allowed}")

        old = self.current
        self.current = new_state
        entry = {"state": new_state, "from": old, "timestamp": datetime.now().isoformat()}
        self.history.append(entry)

        # Fire callback if registered
        if new_state in self._callbacks:
            for cb in self._callbacks[new_state]:
                cb(old, new_state)

        print(f"[state] {old} → {new_state}")
        return True

    def on(self, state, callback):
        """Register a callback for a state transition."""
        self._callbacks.setdefault(state, []).append(callback)

    def can_transition(self, new_state):
        """Check if a transition is allowed."""
        return new_state in self.TRANSITIONS.get(self.current, [])

    def is_terminal(self):
        """Check if the current state is terminal."""
        return self.current == "frozen"

    def reset(self):
        """Reset to idle."""
        self.current = "idle"
        self.history.append({"state": "idle", "reset": True, "timestamp": datetime.now().isoformat()})

    def freeze(self):
        """Transition to frozen (terminal) state."""
        if self.current == "completed":
            return self.transition("frozen")
        elif self.current == "idle":
            self.transition("completed")
            return self.transition("frozen")
        else:
            raise ValueError(f"Cannot freeze from state: {self.current}. Complete the task first.")

    def get_history(self):
        """Return the state transition history."""
        return self.history

    def status(self):
        """Return current state info."""
        return {
            "current": self.current,
            "is_terminal": self.is_terminal(),
            "transitions": len(self.history),
            "allowed_next": self.TRANSITIONS.get(self.current, []),
        }


if __name__ == "__main__":
    sm = CodingAgentState()
    sm.transition("planning")
    sm.transition("executing")
    sm.transition("testing")
    sm.transition("completed")
    sm.freeze()
    print(f"Final state: {sm.current} (terminal: {sm.is_terminal()})")
