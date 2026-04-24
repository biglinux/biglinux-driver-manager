"""Minimal GTK/Adwaita fakes for headless UI coverage tests."""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace


class EnumProxy:
    """Return symbolic values for enum attributes."""

    def __getattr__(self, name: str):
        return name


class FakeAdjustment:
    def __init__(self) -> None:
        self.value = 0
        self.upper = 100
        self.page_size = 10

    def set_value(self, value) -> None:
        self.value = value

    def get_upper(self):
        return self.upper

    def get_page_size(self):
        return self.page_size


class FakeTagTable:
    def __init__(self, tags: dict[str, object]) -> None:
        self._tags = tags

    def lookup(self, name: str):
        return self._tags.get(name)


class FakeTextBuffer:
    def __init__(self) -> None:
        self.text = ""
        self._tags: dict[str, object] = {}

    def create_tag(self, name: str, **_kwargs):
        tag = SimpleNamespace(name=name)
        self._tags[name] = tag
        return tag

    def set_text(self, text: str, *_args) -> None:
        self.text = text

    def get_line_count(self) -> int:
        if not self.text:
            return 0
        return self.text.count("\n") + (0 if self.text.endswith("\n") else 1)

    def get_start_iter(self):
        return 0

    def get_iter_at_line(self, line_number: int):
        return line_number

    def delete(self, start, end) -> None:
        if start != 0:
            return
        lines = self.text.splitlines(keepends=True)
        self.text = "".join(lines[int(end) :])

    def get_end_iter(self):
        return len(self.text)

    def get_tag_table(self):
        return FakeTagTable(self._tags)

    def insert(self, _end_iter, text: str) -> None:
        self.text += text

    def insert_with_tags(self, _end_iter, text: str, *_tags) -> None:
        self.text += text


class FakeWidget:
    """Flexible fake widget that stores state and children."""

    def __init__(self, *args, **kwargs) -> None:
        self._args = args
        self._kwargs = kwargs
        self._children: list[object] = []
        self._controllers: list[object] = []
        self._signals: dict[str, list[tuple[object, tuple]]] = {}
        self._visible = True
        self._active = False
        self._expanded = False
        self._revealed = False
        self._fraction = 0.0
        self._name = kwargs.get("name", "")
        self._label = kwargs.get("label", "")
        self._text = kwargs.get("label", "")
        self._title = kwargs.get("title", "")
        self._subtitle = ""
        self._tooltip_text = ""
        self._parent = None
        self._root = None
        self._child = None
        self._selected_row = None
        self._visible_child_name = ""
        self._width = 0
        self._height = 0
        self._maximized = False
        self._application = kwargs.get("application")
        self._menu_entries: list[tuple] = []
        self._actions: list[object] = []
        self._accessible = []

    @classmethod
    def new(cls, *args, **kwargs):
        return cls(*args, **kwargs)

    @classmethod
    def new_from_icon_name(cls, icon_name: str):
        return cls(icon_name=icon_name)

    @classmethod
    def new_from_file(cls, filename: str):
        return cls(filename=filename)

    def _attach_child(self, child) -> None:
        if hasattr(child, "_parent"):
            child._parent = self
        self._children.append(child)

    def append(self, *items) -> None:
        if len(items) == 1:
            self._attach_child(items[0])
            return
        self._children.append(tuple(items))

    def prepend(self, child) -> None:
        if hasattr(child, "_parent"):
            child._parent = self
        self._children.insert(0, child)

    def set_child(self, child) -> None:
        self._children = []
        self._child = child
        if child is not None:
            self._attach_child(child)

    def set_content(self, child) -> None:
        self.set_child(child)

    def set_sidebar(self, child) -> None:
        self._sidebar = child

    def set_show_content(self, value) -> None:
        self._show_content = value

    def add_named(self, child, name: str) -> None:
        child._stack_name = name
        self._attach_child(child)

    def add_prefix(self, child) -> None:
        self._attach_child(child)

    def add_suffix(self, child) -> None:
        self._attach_child(child)

    def add_top_bar(self, child) -> None:
        self._attach_child(child)

    def pack_end(self, child) -> None:
        self._attach_child(child)

    def add_breakpoint(self, bp) -> None:
        self._attach_child(bp)

    def add_controller(self, controller) -> None:
        self._controllers.append(controller)

    def remove(self, child) -> None:
        if child in self._children:
            self._children.remove(child)
        if hasattr(child, "_parent"):
            child._parent = None
        if self._child is child:
            self._child = None

    def unparent(self) -> None:
        if self._parent is not None:
            self._parent.remove(self)

    def get_first_child(self):
        return self._children[0] if self._children else None

    def get_last_child(self):
        return self._children[-1] if self._children else None

    def get_next_sibling(self):
        if self._parent is None:
            return None
        siblings = [child for child in self._parent._children if hasattr(child, "_parent")]
        try:
            idx = siblings.index(self)
        except ValueError:
            return None
        return siblings[idx + 1] if idx + 1 < len(siblings) else None

    def get_parent(self):
        return self._parent

    def get_root(self):
        widget = self
        while getattr(widget, "_parent", None) is not None:
            widget = widget._parent
        return widget

    def connect(self, signal_name: str, callback, *extra) -> None:
        self._signals.setdefault(signal_name, []).append((callback, extra))

    def _emit(self, signal_name: str, *args) -> None:
        for callback, extra in self._signals.get(signal_name, []):
            callback(self, *args, *extra)

    def set_visible(self, value: bool) -> None:
        self._visible = value

    def get_visible(self):
        return self._visible

    def set_name(self, name: str) -> None:
        self._name = name

    def get_name(self):
        return self._name

    def set_label(self, label: str) -> None:
        self._label = label

    def get_label(self):
        return self._label

    def set_text(self, text: str) -> None:
        self._text = text

    def get_text(self):
        return self._text

    def set_markup(self, text: str) -> None:
        self._text = text

    def set_title(self, title: str) -> None:
        self._title = title

    def get_title(self):
        return self._title

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle = subtitle

    def get_subtitle(self):
        return self._subtitle

    def set_tooltip_text(self, text: str) -> None:
        self._tooltip_text = text

    def get_tooltip_text(self):
        return self._tooltip_text

    def update_property(self, keys, values) -> None:
        self._accessible = list(zip(keys, values))

    def set_active(self, value: bool) -> None:
        self._active = value
        self._emit("notify::active", None)

    def get_active(self):
        return self._active

    def set_expanded(self, value: bool) -> None:
        self._expanded = value

    def get_expanded(self):
        return self._expanded

    def set_revealed(self, value: bool) -> None:
        self._revealed = value

    def set_reveal_child(self, value: bool) -> None:
        self._revealed = value

    def get_reveal_child(self):
        return self._revealed

    def set_fraction(self, value: float) -> None:
        self._fraction = value

    def get_fraction(self):
        return self._fraction

    def set_visible_child_name(self, name: str) -> None:
        self._visible_child_name = name

    def get_visible_child_name(self):
        return self._visible_child_name

    def set_default_size(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def set_size_request(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def get_width(self):
        return self._width

    def get_height(self):
        return self._height

    def maximize(self) -> None:
        self._maximized = True

    def is_maximized(self):
        return self._maximized

    def get_application(self):
        return self._application

    def add_action(self, action) -> None:
        self._actions.append(action)

    def set_accels_for_action(self, action: str, accels) -> None:
        self._accels = getattr(self, "_accels", {})
        self._accels[action] = list(accels)

    def get_active_window(self):
        return getattr(self, "_active_window", None)

    def present(self, parent=None) -> None:
        self._visible = True
        self._presented_with = parent

    def close(self) -> None:
        self._visible = False

    def popup(self) -> None:
        self._visible = True

    def popdown(self) -> None:
        self._visible = False

    def start(self) -> None:
        self._started = True

    def stop(self) -> None:
        self._started = False

    def get_row_at_index(self, index: int):
        try:
            return self._children[index]
        except IndexError:
            return None

    def select_row(self, row) -> None:
        self._selected_row = row
        self._emit("row-selected", row)

    def run(self, argv) -> int:
        self._ran_with = list(argv)
        return 0

    def quit(self) -> None:
        self._quit_called = True

    def __getattr__(self, name: str):
        if name.startswith("set_"):
            key = "_" + name[4:]

            def setter(*args, **_kwargs):
                if len(args) == 1:
                    setattr(self, key, args[0])
                else:
                    setattr(self, key, args)

            return setter

        if name.startswith("get_"):
            key = "_" + name[4:]
            return lambda *args, **_kwargs: getattr(self, key, None)

        if name.startswith("add_") or name in {
            "remove_css_class",
            "set_can_focus",
            "set_can_target",
        }:
            return lambda *args, **_kwargs: None

        raise AttributeError(name)


class FakeWindow(FakeWidget):
    pass


class FakeDialog(FakeWindow):
    pass


class FakeApplication(FakeWidget):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._actions = []


class FakeAction(FakeWidget):
    def __init__(self, name: str = "", parameter_type=None) -> None:
        super().__init__(name=name)
        self.name = name
        self.parameter_type = parameter_type

    @classmethod
    def new(cls, name: str, parameter_type=None):
        return cls(name, parameter_type)


class FakeMenu(FakeWidget):
    def append(self, *items) -> None:
        self._menu_entries.append(tuple(items))


class FakeCssProvider(FakeWidget):
    def load_from_path(self, path: str) -> None:
        self._loaded_path = path


class FakeIconTheme(FakeWidget):
    @classmethod
    def get_for_display(cls, _display):
        return cls()

    def add_search_path(self, path: str) -> None:
        self._search_path = path


class FakeStyleContext(FakeWidget):
    @staticmethod
    def add_provider_for_display(_display, _provider, _priority) -> None:
        return None

    @staticmethod
    def remove_provider_for_display(_display, _provider) -> None:
        return None


class FakeRGBA(FakeWidget):
    def parse(self, _text: str) -> bool:
        return False


class FakeDisplay(FakeWidget):
    @classmethod
    def get_default(cls):
        return cls()


class FakeTextView(FakeWidget):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._buffer = FakeTextBuffer()
        self._vadjustment = FakeAdjustment()

    def get_buffer(self):
        return self._buffer

    def get_vadjustment(self):
        return self._vadjustment


class FakeModule(types.ModuleType):
    """Dynamic module that lazily exposes widget classes and enums."""

    def __init__(self, name: str, custom: dict[str, object] | None = None):
        super().__init__(name)
        self._custom = custom or {}

    def __getattr__(self, name: str):
        if name in self._custom:
            return self._custom[name]
        enum_like = {
            "Orientation",
            "Align",
            "PolicyType",
            "AccessibleProperty",
            "AccessibleRole",
            "SelectionMode",
            "Justification",
            "StackTransitionType",
            "RevealerTransitionType",
            "PositionType",
            "EllipsizeMode",
            "ToolbarStyle",
            "ResponseAppearance",
            "ColorScheme",
            "ApplicationFlags",
            "License",
        }
        if name in enum_like:
            value = EnumProxy()
            setattr(self, name, value)
            return value
        base = FakeWindow if name in {"Window"} else FakeWidget
        value = type(name, (base,), {})
        setattr(self, name, value)
        return value


def install_fake_gi() -> None:
    """Install fake gi.repository modules into sys.modules."""
    if getattr(install_fake_gi, "_installed", False):
        return

    gi_module = types.ModuleType("gi")
    gi_module.require_version = lambda *_args, **_kwargs: None

    repository = types.ModuleType("gi.repository")

    gtk = FakeModule(
        "Gtk",
        {
            "Widget": FakeWidget,
            "Window": FakeWindow,
            "Box": type("Box", (FakeWidget,), {}),
            "Spinner": type("Spinner", (FakeWidget,), {}),
            "Label": type("Label", (FakeWidget,), {"new": classmethod(lambda cls, text: cls(label=text))}),
            "Button": type("Button", (FakeWidget,), {}),
            "Image": type("Image", (FakeWidget,), {"set_from_icon_name": lambda self, name: setattr(self, "_icon_name", name)}),
            "Revealer": type("Revealer", (FakeWidget,), {}),
            "SearchEntry": type("SearchEntry", (FakeWidget,), {}),
            "Switch": type("Switch", (FakeWidget,), {}),
            "Expander": type("Expander", (FakeWidget,), {}),
            "Popover": type("Popover", (FakeWidget,), {}),
            "EventControllerMotion": type("EventControllerMotion", (FakeWidget,), {}),
            "EventControllerKey": type("EventControllerKey", (FakeWidget,), {}),
            "ScrolledWindow": type("ScrolledWindow", (FakeWidget,), {}),
            "ListBox": type("ListBox", (FakeWidget,), {}),
            "ListBoxRow": type("ListBoxRow", (FakeWidget,), {}),
            "Separator": type("Separator", (FakeWidget,), {}),
            "MenuButton": type("MenuButton", (FakeWidget,), {}),
            "Stack": type("Stack", (FakeWidget,), {}),
            "ProgressBar": type("ProgressBar", (FakeWidget,), {}),
            "TextView": FakeTextView,
            "CssProvider": FakeCssProvider,
            "StyleContext": FakeStyleContext,
            "IconTheme": FakeIconTheme,
            "STYLE_PROVIDER_PRIORITY_APPLICATION": 600,
        },
    )
    adw = FakeModule(
        "Adw",
        {
            "Application": type("Application", (FakeApplication,), {}),
            "ApplicationWindow": type("ApplicationWindow", (FakeWindow,), {}),
            "Dialog": type("Dialog", (FakeDialog,), {}),
            "NavigationSplitView": type("NavigationSplitView", (FakeWidget,), {}),
            "NavigationPage": type("NavigationPage", (FakeWidget,), {"new": classmethod(lambda cls, child, title: cls(child=child, title=title))}),
            "ToolbarView": type("ToolbarView", (FakeWidget,), {}),
            "HeaderBar": type("HeaderBar", (FakeWidget,), {}),
            "Banner": type("Banner", (FakeWidget,), {}),
            "StatusPage": type("StatusPage", (FakeWidget,), {}),
            "AlertDialog": type("AlertDialog", (FakeDialog,), {}),
            "Breakpoint": type("Breakpoint", (FakeWidget,), {"new": classmethod(lambda cls, condition: cls(condition=condition))}),
            "BreakpointCondition": type("BreakpointCondition", (FakeWidget,), {"parse": classmethod(lambda cls, text: cls(text=text))}),
            "Clamp": type("Clamp", (FakeWidget,), {}),
            "ActionRow": type(
                "ActionRow",
                (FakeWidget,),
                {"add_prefix": FakeWidget._attach_child, "add_suffix": FakeWidget._attach_child},
            ),
            "PreferencesGroup": type(
                "PreferencesGroup",
                (FakeWidget,),
                {"add": FakeWidget._attach_child},
            ),
            "AboutDialog": type("AboutDialog", (FakeDialog,), {}),
            "WindowTitle": type("WindowTitle", (FakeWidget,), {"new": classmethod(lambda cls, title, subtitle: cls(title=title, subtitle=subtitle))}),
        },
    )
    gio = FakeModule(
        "Gio",
        {
            "SimpleAction": FakeAction,
            "Menu": FakeMenu,
        },
    )
    gdk = FakeModule(
        "Gdk",
        {
            "Display": FakeDisplay,
            "RGBA": FakeRGBA,
            "KEY_Escape": "Escape",
        },
    )
    glib = FakeModule(
        "GLib",
        {
            "timeout_add": lambda _ms, func, *args: func(*args),
            "idle_add": lambda func, *args: func(*args),
            "source_remove": lambda *_args: None,
            "markup_escape_text": lambda text: text,
        },
    )
    pango = FakeModule("Pango")

    repository.Gtk = gtk
    repository.Adw = adw
    repository.Gio = gio
    repository.Gdk = gdk
    repository.GLib = glib
    repository.Pango = pango

    gi_module.repository = repository

    sys.modules["gi"] = gi_module
    sys.modules["gi.repository"] = repository
    sys.modules["gi.repository.Gtk"] = gtk
    sys.modules["gi.repository.Adw"] = adw
    sys.modules["gi.repository.Gio"] = gio
    sys.modules["gi.repository.Gdk"] = gdk
    sys.modules["gi.repository.GLib"] = glib
    sys.modules["gi.repository.Pango"] = pango
    install_fake_gi._installed = True


def reload_ui_modules() -> None:
    """Drop already-loaded UI/style modules so imports use the fake GI."""
    for name in list(sys.modules):
        if (
            name == "ui"
            or name.startswith("ui.")
            or name == "utils.style_manager"
        ):
            sys.modules.pop(name, None)
