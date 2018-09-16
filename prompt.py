#!/usr/bin/python3 -OO
"""
Provides left and right hand prompts for zshell.

Additionally a top line filling whole length of the terminal can be drawn. The output of this
command is expected to be piped to `source /dev/stdin`.
"""
from os import getenv, environ
from argparse import ArgumentParser
from enum import Enum, unique
from subprocess import run, PIPE, CalledProcessError, DEVNULL, TimeoutExpired
from datetime import datetime
from re import search, MULTILINE
from typing import Tuple, Union
from shlex import quote
from getpass import getuser

__author__ = "gilbus"
__license__ = "MIT"

HOME = getenv("HOME", f"/home/{getuser()}")
LAST_EXIT_CODE = int(getenv("LAST_EXIT_CODE", 0))
LAST_CMD = getenv("LAST_CMD", "")
try:
    PWD = getenv("PWD", "Unknown")
except FileNotFoundError:
    # happens if PWD points to a nonexistens directory
    PWD = "!!REMOVED!!"

NO_COLOR = False

OUTPUT = """\
function topline(){{
    echo '{topline}'
}};
topline;
export PROMPT='{prompt}';
export RPROMPT='{rprompt}'
export LAST_CMD=""
"""

RULE_CHAR = "~"

GIT_REGULAR_BRANCH_REGEX = r"\* (?P<branch>.*)"
GIT_COMMIT_OR_TAG_REGEX = r"\* \(HEAD detached at (?P<name>.*)\)"

GIT_CMD_TIMEOUT = 2


@unique
class Colors(Enum):
    default = 0
    red = 1
    green = 2
    yellow = 3
    blue = 4
    purple = 5
    teal = 6
    special1 = 16
    special2 = 17
    special3 = 18
    special4 = 19
    gray = 21

    def colorize(self, s: str, zero_width=True) -> str:
        if NO_COLOR:
            return s
        if zero_width:
            # makes sure that the shell does consider the ansi-color characters
            # as part of the prompt which would mess up the alignment
            return rf"%{{\e[38;5;{self.value}m%}}{s}%{{\e[0;m%}}"

        else:
            return rf"\e[38;5;{self.value}m{s}\e[0;m"


class PromptPart:
    def __init__(self) -> None:
        self.content = ""
        self.color = Colors.default
        self.zero_width = True

    def __str__(self) -> str:
        if not self.color.value:
            return self.content

        return self.color.colorize(self.content, zero_width=self.zero_width)

    def __len__(self) -> int:
        return len(self.content)

    @classmethod
    def empty(cls) -> "PromptPart":
        return cls()


class PromptPartContainer:
    def __init__(self, *parts: PromptPart, separator: str = RULE_CHAR) -> None:
        self.separator = separator
        self.parts = list(parts)

    def add(self, part: PromptPart) -> None:
        self.parts.append(part)

    def __len__(self) -> int:
        return sum(len(part) for part in self.parts)

    def __str__(self) -> str:
        return self.separator.join(str(part) for part in self.parts if part.content)

    def uncolorized_str(self) -> str:
        return self.separator.join(part.content for part in self.parts if part.content)


class LastCommandFragment(PromptPart):
    def __init__(self, color=Colors.green, format_str: str = "['{}']") -> None:
        super().__init__()
        self.color = color
        self.content = (
            format_str.format(quote(LAST_CMD).replace("\\", "\\\\\\\\"))
            if LAST_CMD
            else ""
        )

    def __len__(sekf) -> int:
        # +2 necessary to account for the enclosing square brackets
        return (len(LAST_CMD) + 2) if LAST_CMD else 0


class PWDFragment(PromptPart):
    def __init__(
        self, color=Colors.default, max_len: int = 60, format_str: str = "({})"
    ) -> None:
        """
        Displays the current working directory with a configurable length
        :param color: In which color the fragment should be presented
        :param max_len: Max len of the path to show, shortened on the left end if necessary
        :param format_str: Format string to use, must contain a single unnamed pair of curly braces
        """
        super().__init__()
        self.path = self._get_shortened_pwd(max_len=max_len)
        self.color = color
        self.content = format_str.format(self.path)

    @staticmethod
    def _get_shortened_pwd(max_len) -> str:
        pwd = PWD
        pwd = pwd.replace(HOME, "~")

        if len(pwd) > max_len:
            return "..." + pwd[-(max_len - 3) :]

        return pwd


class GitInfoFragment(PromptPart):
    mod_indicator_re = {
        "added": r"^\s?A  .*$",
        "modified": r"^\s?M .*$",
        "deleted": r"^\s?D .*$",
        "unknown": r"^[?]{2} .*$",
    }

    def __init__(
        self,
        format_str="[{head}{modifier}]",
        color=Colors.blue,
        indicators={"added": "+", "modified": "!", "deleted": "-", "unknown": "?"},
    ) -> None:
        super().__init__()
        try:
            mod_symbols = "".join(
                sorted(indicators[mod] for mod in self._git_mod_info())
            )

            if not mod_symbols:
                mod_str = ""
            else:
                mod_str = f"|{mod_symbols}|"

            format_dict = {"head": self.branch_info(), "modifier": mod_str}
        except CalledProcessError:
            pass
        except TimeoutExpired:
            pass
        else:
            self.content = format_str.format(**format_dict)
            self.color = color

    def branch_info(self) -> str:
        return self._head_info()

    def _git_mod_info(self) -> Tuple[str, ...]:
        status_str = run(
            ["git", "status", "-s", "--porcelain=v1"],
            universal_newlines=True,
            stdout=PIPE,
            stderr=DEVNULL,
            check=True,
            timeout=GIT_CMD_TIMEOUT,
        ).stdout

        return tuple(
            mod
            for mod, re in GitInfoFragment.mod_indicator_re.items()
            if search(re, status_str, MULTILINE)
        )

    def _head_info(self) -> str:
        git_info_str = run(
            ["git", "branch"],
            universal_newlines=True,
            stdout=PIPE,
            check=True,
            stderr=DEVNULL,
            timeout=GIT_CMD_TIMEOUT,
        ).stdout
        commit_or_tag_match = search(GIT_COMMIT_OR_TAG_REGEX, git_info_str)

        if commit_or_tag_match:
            head_name = commit_or_tag_match.group("name")

            return (
                f"{'(T)' if GitInfoFragment.is_tag(head_name) else '(D)'} {head_name}"
            )

        branch_name_match = search(GIT_REGULAR_BRANCH_REGEX, git_info_str)

        if branch_name_match:
            return f"(B) {branch_name_match.group('branch')}"

        return "(B) master"

    @staticmethod
    def is_tag(tag_str: str) -> bool:
        return (
            tag_str
            in run(
                ["git", "tag"],
                universal_newlines=True,
                stdout=PIPE,
                check=True,
                timeout=GIT_CMD_TIMEOUT,
            ).stdout
        )


class VirtualEnvFragment(PromptPart):
    def __init__(self, color=Colors.default, format_str: str = "({})") -> None:
        """
        Fragment which shows the currently activated Python virtual environment.
        :param color: Color to show the fragment with
        :param format_str: Format str to fill
        """
        super().__init__()
        try:
            self.content = format_str.format(environ["VIRTUAL_ENV"].split("/")[-1])
        except KeyError:
            return

        self.color = color


class CondaEnvFragment(PromptPart):
    def __init__(self, color=Colors.default, format_str: str = "({})") -> None:
        """
        Fragment which shows the currently activated Python virtual environment.
        :param color: Color to show the fragment with
        :param format_str: Format str to fill
        """
        super().__init__()
        try:
            self.content = format_str.format(
                environ["CONDA_DEFAULT_ENV"].split("/")[-1]
            )
        except KeyError:
            return

        self.color = color


class TimeFragment(PromptPart):
    def __init__(self, color=Colors.default, format_str: str = "[%H:%M:%S]") -> None:
        """
        Returns a fragment whose content has been filled by strftime of `datetime.now()`.
        :param color: Color to show the fragment with
        :param format_str: Format str passed to strftime
        """
        super().__init__()
        self.content = datetime.now().strftime(format_str)
        self.color = color


class ColoredTextFragment(PromptPart):
    def __init__(self, _str: str, color=Colors.default) -> None:
        """
        Simply returns the text colored.
        :param prompt_str: String to colorize
        :param color: Color to use
        """
        super().__init__()
        self.color = color
        self.content = _str


class ReturnStatusFragment(PromptPart):
    def __init__(
        self, return_status: int, color=Colors.default, format_str="{} ⏎"
    ) -> None:
        super().__init__()
        self.color = color

        if return_status:
            self.content = format_str.format(return_status)


def embed_in_horizontal_rule(
    left_container: PromptPartContainer = PromptPartContainer(),
    center_container: PromptPartContainer = PromptPartContainer(),
    right_container: PromptPartContainer = PromptPartContainer(),
    rule_char=RULE_CHAR,
) -> str:
    for container in (left_container, center_container, right_container):
        # disable zero width printing since it is not necessary inside the top line
        for part in container.parts:
            part.zero_width = False
    # idea: include date and time inside of rule
    terminal_width = int(
        run(["tput", "cols"], stdout=PIPE, universal_newlines=True).stdout.strip()
    )
    center_str = "{0:{fill}^{cols}}".format(
        center_container.uncolorized_str(),
        fill=rule_char,
        cols=terminal_width - len(left_container) - len(right_container),
    )
    # necessary since the ansi-color codes would also be considered for the centering
    # in the cmd above, shortening the rule
    center_str = center_str.replace(
        center_container.uncolorized_str(), str(center_container)
    )

    return f"{left_container}{center_str}{right_container}"


def main() -> None:
    left_container = PromptPartContainer(
        GitInfoFragment(), LastCommandFragment(), separator=""
    )
    center_container = PromptPartContainer(PWDFragment(color=Colors.teal))
    right_container = PromptPartContainer(TimeFragment(color=Colors.gray))
    prompt_str = " ".join(
        str(fragment)
        for fragment in (
            VirtualEnvFragment(Colors.teal),
            CondaEnvFragment(Colors.green),
            ColoredTextFragment("➤ ", Colors.red),
        )
        if fragment
    )
    prompt_dir = {
        "topline": embed_in_horizontal_rule(
            left_container=left_container,
            center_container=center_container,
            right_container=right_container,
        ),
        "prompt": prompt_str,
        "rprompt": ReturnStatusFragment(LAST_EXIT_CODE, Colors.red),
    }
    print(OUTPUT.format(**prompt_dir))


if __name__ == "__main__":
    main()
