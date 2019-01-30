"""
An alternative, more direct implementation of event handling using cffi
calls to SDL functions.  The current code is incomplete, but can be
extended easily by following the official SDL documentation.

This module be run directly like any other event get example, but is meant
to be copied into your code base.  Then you can use the tcod.event.get and
tcod.event.wait functions in your code.

Printing any event will tell you its attributes in a human readable format.
An events type attr is just the classes name with all letters upper-case.

Like in tdl, events use a type attribute to tell events apart.  Unlike tdl
and tcod the names and values used are directly derived from SDL.

As a general guideline for turn-based rouge-likes, you should use
KeyDown.sym for commands, and TextInput.text for name entry fields.

.. versionadded:: 8.4
"""
from typing import Any, Dict, NamedTuple, Optional, Iterator, Tuple

import tcod
import tcod.event_constants
from tcod.event_constants import *  # noqa: F4


def _describe_bitmask(
    bits: int, table: Dict[Any, str], default: Any = "0"
) -> str:
    """Returns a bitmask in human readable form.

    This is a private function, used internally.

    Args:
        bits (int): The bitmask to be represented.
        table (Dict[Any,str]): A reverse lookup table.
        default (Any): A default return value when bits is 0.

    Returns: str: A printable version of the bits variable.
    """
    result = []
    for bit, name in table.items():
        if bit & bits:
            result.append(name)
    if not result:
        return default
    return "|".join(result)


def _pixel_to_tile(x: float, y: float) -> Tuple[float, float]:
    """Convert pixel coordinates to tile coordinates."""
    xy = tcod.ffi.new("double[2]", (x, y))
    tcod.lib.TCOD_sys_pixel_to_tile(xy, xy + 1)
    return xy[0], xy[1]


Point = NamedTuple("Point", [("x", float), ("y", float)])

# manually define names for SDL macros
BUTTON_LEFT = 1
BUTTON_MIDDLE = 2
BUTTON_RIGHT = 3
BUTTON_X1 = 4
BUTTON_X2 = 5
BUTTON_LMASK = 0x01
BUTTON_MMASK = 0x02
BUTTON_RMASK = 0x04
BUTTON_X1MASK = 0x08
BUTTON_X2MASK = 0x10

# reverse tables are used to get the tcod.event name from the value.
_REVERSE_BUTTON_TABLE = {
    BUTTON_LEFT: "tcod.event.BUTTON_LEFT",
    BUTTON_MIDDLE: "tcod.event.BUTTON_MIDDLE",
    BUTTON_RIGHT: "tcod.event.BUTTON_RIGHT",
    BUTTON_X1: "tcod.event.BUTTON_X1",
    BUTTON_X2: "tcod.event.BUTTON_X2",
}

_REVERSE_BUTTON_MASK_TABLE = {
    BUTTON_LMASK: "tcod.event.BUTTON_LMASK",
    BUTTON_MMASK: "tcod.event.BUTTON_MMASK",
    BUTTON_RMASK: "tcod.event.BUTTON_RMASK",
    BUTTON_X1MASK: "tcod.event.BUTTON_X1MASK",
    BUTTON_X2MASK: "tcod.event.BUTTON_X2MASK",
}


class Event:
    """The base event class."""

    def __init__(self, type: Optional[str] = None):
        if type is None:
            type = self.__class__.__name__.upper()
        self.type = type
        self.sdl_event = None

    @classmethod
    def from_sdl_event(cls, sdl_event):
        """Return a class instance from a cffi SDL_Event pointer."""
        raise NotImplementedError()


class Quit(Event):
    """An application quit request event.

    For more info on when this event is triggered see:
    https://wiki.libsdl.org/SDL_EventType#SDL_QUIT
    """

    @classmethod
    def from_sdl_event(cls, sdl_event):
        self = cls()
        self.sdl_event = sdl_event
        return self

    def __repr__(self):
        return "tcod.event.%s()" % self.__class__.__name__


class KeyboardEvent(Event):
    def __init__(
        self, scancode: int, sym: int, mod: int, repeat: bool = False
    ):
        super().__init__()
        self.scancode = scancode
        self.sym = sym
        self.mod = mod
        self.repeat = repeat

    @classmethod
    def from_sdl_event(cls, sdl_event):
        keysym = sdl_event.key.keysym
        self = cls(
            keysym.scancode, keysym.sym, keysym.mod, bool(sdl_event.key.repeat)
        )
        self.sdl_event = sdl_event
        return self

    def __repr__(self):
        return "tcod.event.%s(scancode=%s, sym=%s, mod=%s%s)" % (
            self.__class__.__name__,
            tcod.event_constants._REVERSE_SCANCODE_TABLE[self.scancode],
            tcod.event_constants._REVERSE_SYM_TABLE[self.sym],
            _describe_bitmask(
                self.mod, tcod.event_constants._REVERSE_MOD_TABLE
            ),
            ", repeat=True" if self.repeat else "",
        )


class KeyDown(KeyboardEvent):
    pass


class KeyUp(KeyboardEvent):
    pass


class MouseMotion(Event):
    def __init__(
        self,
        pixel: Tuple[int, int] = (0, 0),
        pixel_motion: Tuple[int, int] = (0, 0),
        tile: Tuple[int, int] = (0, 0),
        tile_motion: Tuple[int, int] = (0, 0),
        state: int = 0,
    ):
        super().__init__()
        self.pixel = Point(*pixel)
        self.pixel_motion = Point(*pixel_motion)
        self.tile = Point(*tile)
        self.tile_motion = Point(*tile_motion)
        self.state = state

    @classmethod
    def from_sdl_event(cls, sdl_event):
        motion = sdl_event.motion

        pixel = motion.x, motion.y
        pixel_motion = motion.xrel, motion.yrel
        subtile = _pixel_to_tile(*pixel)
        tile = int(subtile[0]), int(subtile[1])
        prev_pixel = pixel[0] - pixel_motion[0], pixel[1] - pixel_motion[1]
        prev_subtile = _pixel_to_tile(*prev_pixel)
        prev_tile = int(prev_subtile[0]), int(prev_subtile[1])
        tile_motion = tile[0] - prev_tile[0], tile[1] - prev_tile[1]
        self = cls(pixel, pixel_motion, tile, tile_motion, motion.state)
        self.sdl_event = sdl_event
        return self

    def __repr__(self):
        return (
            "tcod.event.%s(pixel=%r, pixel_motion=%r, "
            "tile=%r, tile_motion=%r, state=%s)"
        ) % (
            self.__class__.__name__,
            self.pixel,
            self.pixel_motion,
            self.tile,
            self.tile_motion,
            _describe_bitmask(self.state, _REVERSE_BUTTON_MASK_TABLE),
        )


class MouseButtonEvent(Event):
    def __init__(
        self,
        pixel: Tuple[int, int] = (0, 0),
        tile: Tuple[int, int] = (0, 0),
        button: int = 0,
    ):
        super().__init__()
        self.pixel = Point(*pixel)
        self.tile = Point(*tile)
        self.button = button

    @classmethod
    def from_sdl_event(cls, sdl_event):
        button = sdl_event.button
        pixel = button.x, button.y
        subtile = _pixel_to_tile(*pixel)
        tile = int(subtile[0]), int(subtile[1])
        self = cls(pixel, tile, button.button)
        self.sdl_event = sdl_event
        return self

    def __repr__(self):
        return "tcod.event.%s(pixel=%r, tile=%r, button=%s)" % (
            self.__class__.__name__,
            self.pixel,
            self.tile,
            _REVERSE_BUTTON_TABLE[self.button],
        )


class MouseButtonDown(MouseButtonEvent):
    pass


class MouseButtonUp(MouseButtonEvent):
    pass


class MouseWheel(Event):
    def __init__(self, x: int, y: int, flipped: bool = False):
        super().__init__()
        self.x = x
        self.y = y
        self.flipped = flipped

    @classmethod
    def from_sdl_event(cls, sdl_event):
        wheel = sdl_event.wheel
        self = cls(wheel.x, wheel.y, bool(wheel.direction))
        self.sdl_event = sdl_event
        return self

    def __repr__(self):
        return "tcod.event.%s(x=%i, y=%i%s)" % (
            self.__class__.__name__,
            self.x,
            self.y,
            ", flipped=True" if self.flipped else "",
        )


class TextInput(Event):
    def __init__(self, text: str):
        super().__init__()
        self.text = text

    @classmethod
    def from_sdl_event(cls, sdl_event):
        self = cls(tcod.ffi.string(sdl_event.text.text, 32).decode("utf8"))
        self.sdl_event = sdl_event
        return self

    def __repr__(self) -> str:
        return "tcod.event.%s(text=%r)" % (self.__class__.__name__, self.text)


class WindowEvent(Event):
    def __init__(self, type: str, x: Optional[int] = 0, y: Optional[int] = 0):
        super().__init__(type)
        self.x = x
        self.y = y

    @classmethod
    def from_sdl_event(cls, sdl_event: Any):
        if sdl_event.window.event not in cls.__WINDOW_TYPES:
            return Undefined.from_sdl_event(sdl_event)
        self = cls(
            cls.__WINDOW_TYPES[sdl_event.window.event],
            sdl_event.window.data1,
            sdl_event.window.data2,
        )
        self.sdl_event = sdl_event
        return self

    def __repr__(self) -> str:
        params = ""
        if self.x or self.y:
            params = ", x=%r, y=%r" % (self.x, self.y)
        return "tcod.event.%s(type=%r%s)" % (
            self.__class__.__name__,
            self.type,
            params,
        )

    __WINDOW_TYPES = {
        tcod.lib.SDL_WINDOWEVENT_SHOWN: "WindowShown",
        tcod.lib.SDL_WINDOWEVENT_HIDDEN: "WindowHidden",
        tcod.lib.SDL_WINDOWEVENT_EXPOSED: "WindowExposed",
        tcod.lib.SDL_WINDOWEVENT_MOVED: "WindowMoved",
        tcod.lib.SDL_WINDOWEVENT_RESIZED: "WindowResized",
        tcod.lib.SDL_WINDOWEVENT_SIZE_CHANGED: "WindowSizeChanged",
        tcod.lib.SDL_WINDOWEVENT_MINIMIZED: "WindowMinimized",
        tcod.lib.SDL_WINDOWEVENT_MAXIMIZED: "WindowMaximized",
        tcod.lib.SDL_WINDOWEVENT_RESTORED: "WindowRestored",
        tcod.lib.SDL_WINDOWEVENT_ENTER: "WindowEnter",
        tcod.lib.SDL_WINDOWEVENT_LEAVE: "WindowLeave",
        tcod.lib.SDL_WINDOWEVENT_FOCUS_GAINED: "WindowFocusGained",
        tcod.lib.SDL_WINDOWEVENT_FOCUS_LOST: "WindowFocusLost",
        tcod.lib.SDL_WINDOWEVENT_CLOSE: "WindowClose",
        tcod.lib.SDL_WINDOWEVENT_TAKE_FOCUS: "WindowTakeFocus",
        tcod.lib.SDL_WINDOWEVENT_HIT_TEST: "WindowHitTest",
    }


class Undefined(Event):
    """This class is a place holder for SDL events without a Python class."""

    def __init__(self) -> None:
        super().__init__("")

    @classmethod
    def from_sdl_event(cls, sdl_event: Any) -> "Undefined":
        self = cls()
        self.sdl_event = sdl_event
        return self

    def __str__(self) -> str:
        if self.sdl_event:
            return "<Undefined sdl_event.type=%i>" % self.sdl_event.type
        return "<Undefined>"


_SDL_TO_CLASS_TABLE = {
    tcod.lib.SDL_QUIT: Quit,
    tcod.lib.SDL_KEYDOWN: KeyDown,
    tcod.lib.SDL_KEYUP: KeyUp,
    tcod.lib.SDL_MOUSEMOTION: MouseMotion,
    tcod.lib.SDL_MOUSEBUTTONDOWN: MouseButtonDown,
    tcod.lib.SDL_MOUSEBUTTONUP: MouseButtonUp,
    tcod.lib.SDL_MOUSEWHEEL: MouseWheel,
    tcod.lib.SDL_TEXTINPUT: TextInput,
    tcod.lib.SDL_WINDOWEVENT: WindowEvent,
}  # type: Dict[int, Any]


def get() -> Iterator[Any]:
    """Iterate over all pending events.

    Returns:
        Iterator[tcod.event.Event]:
            An iterator of Event subclasses.
    """
    sdl_event = tcod.ffi.new("SDL_Event*")
    while tcod.lib.SDL_PollEvent(sdl_event):
        if sdl_event.type in _SDL_TO_CLASS_TABLE:
            yield _SDL_TO_CLASS_TABLE[sdl_event.type].from_sdl_event(sdl_event)
        else:
            yield Undefined.from_sdl_event(sdl_event)


def wait(timeout: Optional[float] = None) -> Iterator[Any]:
    """Block until events exist, then iterate over all events.

    Keep in mind that this function will wake even for events not handled by
    this module.

    Args:
        timeout (Optional[float]):
            Maximum number of seconds to wait, or None to wait forever.
            Has millisecond percision.

    Returns:
        Iterator[tcod.event.Event]: Same iterator as a call to tcod.event.get
    """
    if timeout is not None:
        tcod.lib.SDL_WaitEventTimeout(tcod.ffi.NULL, int(timeout * 1000))
    else:
        tcod.lib.SDL_WaitEvent(tcod.ffi.NULL)
    return get()


class EventDispatch:
    def dispatch(self, event: Any) -> None:
        if event.type:
            getattr(self, "ev_%s" % (event.type.lower(),))(event)

    def event_get(self) -> None:
        for event in get():
            self.dispatch(event)

    def event_wait(self, timeout: Optional[float]) -> None:
        wait(timeout)
        self.event_get()

    def ev_quit(self, event: Quit) -> None:
        pass

    def ev_keydown(self, event: KeyDown) -> None:
        pass

    def ev_keyup(self, event: KeyUp) -> None:
        pass

    def ev_mousemotion(self, event: MouseMotion) -> None:
        pass

    def ev_mousebuttondown(self, event: MouseButtonDown) -> None:
        pass

    def ev_mousebuttonup(self, event: MouseButtonUp) -> None:
        pass

    def ev_mousewheel(self, event: MouseWheel) -> None:
        pass

    def ev_textinput(self, event: TextInput) -> None:
        pass

    def ev_windowshown(self, event: WindowEvent) -> None:
        pass

    def ev_windowhidden(self, event: WindowEvent) -> None:
        pass

    def ev_windowexposed(self, event: WindowEvent) -> None:
        pass

    def ev_windowmoved(self, event: WindowEvent) -> None:
        pass

    def ev_windowresized(self, event: WindowEvent) -> None:
        pass

    def ev_windowsizechanged(self, event: WindowEvent) -> None:
        pass

    def ev_windowminimized(self, event: WindowEvent) -> None:
        pass

    def ev_windowmaximized(self, event: WindowEvent) -> None:
        pass

    def ev_windowrestored(self, event: WindowEvent) -> None:
        pass

    def ev_windowenter(self, event: WindowEvent) -> None:
        pass

    def ev_windowleave(self, event: WindowEvent) -> None:
        pass

    def ev_windowfocusgained(self, event: WindowEvent) -> None:
        pass

    def ev_windowfocuslost(self, event: WindowEvent) -> None:
        pass

    def ev_windowclose(self, event: WindowEvent) -> None:
        pass

    def ev_windowtakefocus(self, event: WindowEvent) -> None:
        pass

    def ev_windowhittest(self, event: WindowEvent) -> None:
        pass


__all__ = [
    "Point",
    "BUTTON_LEFT",
    "BUTTON_MIDDLE",
    "BUTTON_RIGHT",
    "BUTTON_X1",
    "BUTTON_X2",
    "BUTTON_LMASK",
    "BUTTON_MMASK",
    "BUTTON_RMASK",
    "BUTTON_X1MASK",
    "BUTTON_X2MASK",
    "Event",
    "Quit",
    "KeyboardEvent",
    "KeyDown",
    "KeyUp",
    "MouseMotion",
    "MouseButtonEvent",
    "MouseButtonDown",
    "MouseButtonUp",
    "MouseWheel",
    "TextInput",
    "WindowEvent",
    "Undefined",
    "get",
    "wait",
    "EventDispatch",
] + tcod.event_constants.__all__
