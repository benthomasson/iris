
# A finite state machine that listens for the spoken command "computer".
# When it hears computer it will change state to "computer" and then
# list for further commmands.

from . import llm
from . import voice


class StateMachine(object):

    def __init__(self, states, initial_state, context, on_display=None):
        self.states = states
        self.state = initial_state
        self.state.enter()
        self.context = context
        self.on_display = on_display

    def transition(self, text):
        new_state = self.state.transition(text, context=self.context)
        if new_state is not None:
            print("Transitioning to state: " + new_state.name)
            self.state.exit(text)
            self.state = new_state
            self.state.enter(text)

    def run(self, text):
        self.transition(text)


class State(object):

    def __init__(self, name, states):
        self.name = name
        self.states = states

    def init(self, transitions):
        self.transitions = transitions

    def enter(self, text=None):
        print("Entering state", self.name)

    def exit(self, text=None):
        print("Exiting state", self.name)

    def transition(self, text, context):
        if text in self.transitions:
            return self.transitions[text]
        else:
            return None


class InitialState(State):

    def __init__(self, states):
        super().__init__("initial", states)

    def init(self):
        super().init({"computer": self.states["computer"],
                      "shutdown": self.states["shutdown"],
                      "shut down": self.states["shutdown"],
                      "goodbye": self.states["shutdown"],
                      "good night computer": self.states["shutdown"],
                      "good night": self.states["shutdown"],
                      "hello computer": self.states["computer"],
                      "good morning computer": self.states["computer"],
                      })


class ComputerState(State):

    def __init__(self, states):
        super().__init__("computer", states)

    def init(self):
        super().init({"exit": self.states["initial"],
                      "shutdown": self.states["shutdown"],
                      "goodbye": self.states["shutdown"],
                      "good bye": self.states["shutdown"],
                      "good night computer": self.states["shutdown"],
                      "good night": self.states["shutdown"],
                      "shut down": self.states["shutdown"]})

    def transition(self, text, context):
        next_state = super().transition(text, context)
        if next_state is None:
            print("Computer heard:", text)
            prompt = text
            if context.get('prompt'):
                prompt = context['prompt'] + " " + text
            response = llm.generate_response(prompt)
            if context.get('on_display'):
                context['on_display'](text, response)
            voice.say(response)
        return next_state

    def enter(self, text=None):
        super().enter()
        prompt = text or "hello computer"
        response = llm.generate_response(prompt)
        voice.say(response)


class ShutdownState(State):

    def __init__(self, states):
        super().__init__("shutdown", states)

    def init(self):
        super().init({"computer": self.states["computer"],
                      "shutdown": self.states["shutdown"],
                      "shut down": self.states["shutdown"],
                      "good night computer": self.states["shutdown"],
                      "goodbye": self.states["shutdown"],
                      "hello computer": self.states["computer"],
                      "good morning computer": self.states["computer"],
                      })

    def enter(self, text=None):
        super().enter()
        prompt = text if text and text not in ("shut down", "shutdown") else "goodbye"
        response = llm.generate_response(prompt)
        voice.say(response)
        raise SystemExit


class ComputerFSM(StateMachine):

    def __init__(self, context, on_display=None):
        context['on_display'] = on_display
        self.states = {}
        self.states.update({"shutdown": ShutdownState(self.states)})
        self.states.update({"computer": ComputerState(self.states)})
        self.states.update({"initial": InitialState(self.states)})
        super().__init__(self.states, self.states["initial"], context, on_display)
        for state in self.states.values():
            state.init()
        response = llm.init_conversation()
        if on_display:
            on_display("", response)
        voice.say(response)

    def run(self, text):
        print("Input:", text)
        super().run(text)
