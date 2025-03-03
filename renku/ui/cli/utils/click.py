# Copyright Swiss Data Science Center (SDSC). A partnership between
# École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Click utilities."""

from typing import TYPE_CHECKING, List

import click

if TYPE_CHECKING:
    from renku.core.dataset.providers.models import ProviderParameter


def shell_complete_datasets(ctx, param, incomplete) -> List[str]:
    """Shell completion for dataset names."""
    from renku.command.dataset import search_datasets_command

    try:
        result = search_datasets_command().build().execute(name=incomplete)
    except Exception:
        return []
    else:
        return result.output


def shell_complete_workflows(ctx, param, incomplete) -> List[str]:
    """Shell completion for plan names."""
    from renku.command.workflow import search_workflows_command

    try:
        result = search_workflows_command().build().execute(name=incomplete)
    except Exception:
        return []
    else:
        return [n for n in result.output if n.startswith(incomplete)]


def shell_complete_sessions(ctx, param, incomplete) -> List[str]:
    """Shell completion for session names."""
    from renku.command.session import search_sessions_command

    try:
        result = search_sessions_command().build().execute(name=incomplete)
    except Exception:
        return []
    else:
        return result.output


def shell_complete_session_providers(ctx, param, incomplete) -> List[str]:
    """Shell completion for session providers names."""
    from renku.command.session import search_session_providers_command

    try:
        result = search_session_providers_command().build().execute(name=incomplete)
    except Exception:
        return []
    else:
        return result.output


class CaseInsensitiveChoice(click.Choice):
    """Case-insensitive click choice.

    Based on https://github.com/pallets/click/issues/569.
    """

    def convert(self, value, param, ctx):
        """Convert value to its choice value."""
        if value is None:
            return None
        return super().convert(value.lower(), param, ctx)


class MutuallyExclusiveOption(click.Option):
    """Custom option class to allow specifying mutually exclusive options in click commands."""

    def __init__(self, *args, **kwargs):
        mutually_exclusive = sorted(kwargs.pop("mutually_exclusive", []))
        self.mutually_exclusive = set()
        self.mutually_exclusive_names = []

        for mutex in mutually_exclusive:
            if isinstance(mutex, tuple):
                self.mutually_exclusive.add(mutex[0])
                self.mutually_exclusive_names.append(mutex[1])
            else:
                self.mutually_exclusive.add(mutex)
                self.mutually_exclusive_names.append(mutex)

        _help = kwargs.get("help", "")
        if self.mutually_exclusive:
            ex_str = ", ".join(self.mutually_exclusive_names)
            kwargs["help"] = f"{_help} NOTE: This argument is mutually exclusive with arguments: [{ex_str}]."
        super().__init__(*args, **kwargs)

    def handle_parse_result(self, ctx, opts, args):
        """Handles the parse result for the option."""
        if self.mutually_exclusive.intersection(opts) and self.name in opts:
            raise click.UsageError(
                "Illegal usage: `{}` is mutually exclusive with "
                "arguments `{}`.".format(self.name, ", ".join(sorted(self.mutually_exclusive_names)))
            )

        return super().handle_parse_result(ctx, opts, args)


def create_options(providers, parameter_function: str):
    """Create options for a group of providers."""

    def wrapper(f):
        from click_option_group import optgroup

        for i, provider in enumerate(sorted(providers, reverse=True, key=lambda p: p.name.lower())):
            parameters: List["ProviderParameter"] = getattr(provider, parameter_function)()
            for j, param in enumerate(parameters):
                param_help = f"\b\n{param.help}\n " if j == 0 else param.help  # NOTE: add newline after a group

                args = (
                    [f"-{a}" if len(a) == 1 else f"--{a}" for a in param.flags if a] + [param.name.replace("-", "_")]
                    if param.flags
                    else [f"--{param.name}"]
                )

                f = optgroup.option(
                    *args,
                    type=param.type,
                    help=param_help,
                    is_flag=param.is_flag,
                    default=param.default,
                    multiple=param.multiple,
                    metavar=param.metavar,
                )(f)

            name = f"{provider.name} configuration"
            if i == len(providers) - 1:
                name = "\n  " + name  # NOTE: add newline before first group

            f = optgroup.group(name=name)(f)

        return f

    return wrapper
